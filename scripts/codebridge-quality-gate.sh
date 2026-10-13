#!/usr/bin/env bash
# Fixed quality gates for KMJ CodeBridge. No arbitrary command passthrough.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-}"
PLATFORM="$ROOT/apps/platform"

fail() {
  printf 'CodeBridge gate error: %s\n' "$*" >&2
  exit 2
}

require_file() {
  [[ -f "$1" ]] || fail "missing required file: $1"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

run_fast() {
  require_cmd git
  require_cmd python3
  git -C "$ROOT" diff --check
  python3 -B "$ROOT/scripts/verify_architecture.py"
  python3 -B "$ROOT/scripts/verify_runtime.py"
  python3 -B "$ROOT/scripts/verify_contracts.py"
  python3 -B "$ROOT/scripts/verify_public_surface.py"
  python3 -B "$ROOT/scripts/verify_cloudos_main_platform_contract.py"
}

run_platform() {
  require_file "$PLATFORM/artisan"
  require_file "$PLATFORM/composer.json"
  require_file "$PLATFORM/package.json"
  require_cmd php
  require_cmd npm

  cd "$PLATFORM"

  [[ -d node_modules ]] || fail "apps/platform/node_modules is missing; dependency installation is an explicit setup action, not a quality gate"
  [[ -d vendor ]] || fail "apps/platform/vendor is missing; dependency installation is an explicit setup action, not a quality gate"

  npm run check
  npm run types:check

  if [[ -x vendor/bin/pint ]]; then
    vendor/bin/pint --parallel --test
  else
    fail "vendor/bin/pint is missing"
  fi

  if [[ -x vendor/bin/phpstan ]]; then
    vendor/bin/phpstan analyse
  else
    fail "vendor/bin/phpstan is missing"
  fi

  php artisan test
}

run_full() {
  run_fast
  run_platform
  cd "$PLATFORM"
  npm run build
}

case "$MODE" in
  fast)
    run_fast
    ;;
  platform)
    run_platform
    ;;
  full)
    run_full
    ;;
  *)
    fail "allowed modes: fast | platform | full"
    ;;
esac

printf 'KMJ Main Platform CodeBridge gate PASS: %s\n' "$MODE"
