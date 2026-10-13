#!/usr/bin/env bash
# Safe exact-head CodeBridge dashboard QA. Runs in a disposable worktree.
set -Eeuo pipefail
umask 077

[[ ${1:-} =~ ^[a-f0-9]{40}$ ]] || { echo 'Usage: verify-codebridge-dashboard-pr.sh <exact-commit-SHA>' >&2; exit 2; }
sha="$1"
[[ "$(id -u)" != 0 ]] || { echo 'BLOCKED: use the unprivileged checkout owner' >&2; exit 2; }
repo="$(git rev-parse --show-toplevel)"
[[ "$(basename "$repo")" == 'kmj-main-platform' ]] || { echo 'BLOCKED: incorrect repo' >&2; exit 2; }
git cat-file -e "${sha}^{commit}" || { echo 'BLOCKED: fetch candidate SHA first' >&2; exit 3; }

src="$repo/apps/platform"
[[ -d "$src/node_modules" && -x "$src/node_modules/.bin/vp" ]] || {
  echo 'BLOCKED: preinstalled Node development dependencies unavailable' >&2
  exit 3
}
[[ -f "$src/vendor/autoload.php" ]] || {
  echo 'BLOCKED: preinstalled Laravel Composer dependencies unavailable' >&2
  exit 3
}
tmp="$(mktemp -d "${TMPDIR:-/tmp}/kmj-codebridge-ui.XXXXXXXX")"
cleanup() {
  git -C "$repo" worktree remove --force "$tmp/tree" >/dev/null 2>&1 || true
  rm -rf -- "$tmp"
}
trap cleanup EXIT HUP INT TERM
git -C "$repo" worktree add --detach "$tmp/tree" "$sha" >/dev/null
[[ "$(git -C "$tmp/tree" rev-parse HEAD)" == "$sha" ]] || exit 3
cp -a "$src/vendor" "$tmp/tree/apps/platform/vendor"
cp -a "$src/node_modules" "$tmp/tree/apps/platform/node_modules"
cd "$tmp/tree/apps/platform"
printf '# temporary CodeBridge dashboard QA; no live secrets\n' > .env
chmod 600 .env
export APP_ENV=testing APP_KEY="base64:$(php -r 'echo base64_encode(random_bytes(32));')"
export DB_CONNECTION=sqlite DB_DATABASE=':memory:' CACHE_STORE=array SESSION_DRIVER=array QUEUE_CONNECTION=sync
failures=0
echo "CODEBRIDGE_DASHBOARD_SHA=$sha"
echo '== Vite / Wayfinder build =='
if npm run build && test -s public/build/manifest.json; then echo 'PASS: frontend build'
else echo 'FAIL: frontend build'; failures=$((failures+1)); fi
echo '== TypeScript =='
if npm run types:check; then echo 'PASS: TypeScript'
else echo 'FAIL: TypeScript'; failures=$((failures+1)); fi
echo '== Formatter, lint, onboarding contracts and new dashboard contracts =='
if npm run check; then echo 'PASS: full frontend check'
else echo 'FAIL: frontend check'; failures=$((failures+1)); fi
echo "CODEBRIDGE_DASHBOARD_FAILURES=$failures SHA=$sha"
if (( failures )); then exit 1; fi
echo "PASS: isolated CodeBridge dashboard frontend gates at exact $sha"
echo 'NOT VERIFIED: production deploy, live gateway heartbeat status and device recovery'
