#!/usr/bin/env bash
# Isolated CI verification; never point this script at the live staging checkout.
set -euo pipefail

platform_dir="${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}/apps/platform"
test "${DB_CONNECTION:-}" = sqlite
test "${DB_DATABASE:-}" = "$platform_dir/database/database.sqlite"
cd "$platform_dir"
test -f composer.lock
test -f package.json

verify_dir="$(mktemp -d "${RUNNER_TEMP:?RUNNER_TEMP is required}/kmj-platform-verify.XXXXXX")"
declare -a task_pids=()
declare -a task_names=()
cleanup() {
  for pid in "${task_pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  rm -rf -- "$verify_dir"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

export TMPDIR="$verify_dir/tmp"
mkdir -p "$TMPDIR"
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=4096}"
started=$SECONDS

start_task() {
  local task="$1"
  shift
  ( "$@" ) >"$verify_dir/$task.log" 2>&1 &
  task_pids+=("$!")
  task_names+=("$task")
}
wait_tasks() {
  local failed=0
  for i in "${!task_pids[@]}"; do
    if wait "${task_pids[$i]}"; then
      echo "::group::${task_names[$i]} PASS"
    else
      echo "::group::${task_names[$i]} FAILED"
      failed=1
    fi
    cat "$verify_dir/${task_names[$i]}.log"
    echo '::endgroup::'
  done
  task_pids=()
  task_names=()
  test "$failed" -eq 0
}
install_frontend() {
  if [ -f package-lock.json ]; then
    npm ci --prefer-offline --no-audit --no-fund
  else
    npm install --prefer-offline --no-audit --no-fund
  fi
}
verify_php() {
  if composer test; then
    return 0
  fi
  # Show the concrete formatter diff on failure so repair does not need another CI cycle.
  if [ -f vendor/bin/pint ]; then
    php vendor/bin/pint --test -v || true
  fi
  return 1
}
verify_frontend() {
  ./node_modules/.bin/vp fmt --check
  ./node_modules/.bin/vp lint
  npm run types:check
}

touch database/database.sqlite
test -f .env || cp .env.example .env
start_task composer-install composer install --no-interaction --prefer-dist --no-progress
start_task npm-install install_frontend
wait_tasks
echo "Dependency installation elapsed: $((SECONDS - started)) seconds"

# The PDF-inspired release gate uses only the repository lockfiles and the
# official advisory services. No paid scanning service or application secrets.
# Production dependencies with known vulnerabilities block the candidate.
start_task composer-production-audit composer audit --locked --no-dev --no-interaction
start_task npm-production-audit npm audit --omit=dev --audit-level=high
wait_tasks

if [ -n "${KMJ_FORMAT_PATHS:-}" ]; then
  mapfile -t format_paths <<< "$KMJ_FORMAT_PATHS"
  ./node_modules/.bin/vp fmt "${format_paths[@]}"
fi

php artisan key:generate --force
php artisan migrate --force
npm run build

checks_started=$SECONDS
start_task php-quality-and-tests verify_php
start_task frontend-quality verify_frontend
wait_tasks
echo "Parallel quality checks elapsed: $((SECONDS - checks_started)) seconds"
echo "Platform verification PASS; total elapsed: $((SECONDS - started)) seconds"
