#!/usr/bin/env bash
# Zero-extra-hosted-CI verifier. Does not replace GitHub required checks.
# Invoke only from a clean, non-production SHA-pinned Git worktree.
set -euo pipefail

die() { printf 'KMJ_LICENSING_VERIFY_BLOCKED=%s\n' "$1" >&2; exit 2; }
[ "$#" -eq 1 ] || die EXPECTED_HEAD_REQUIRED
expected="$1"
[[ "$expected" =~ ^[0-9a-f]{40}$ ]] || die EXPECTED_HEAD_INVALID

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$repo"
current="$(git rev-parse HEAD 2>/dev/null)" || die NOT_A_GIT_WORKTREE
[ "$current" = "$expected" ] || die HEAD_MISMATCH
git diff --quiet && git diff --cached --quiet || die DIRTY_TRACKED_CHECKOUT
[ -z "$(git ls-files --others --exclude-standard)" ] || die UNTRACKED_CHECKOUT

git_dir="$(git rev-parse --absolute-git-dir)"
common_dir="$(git rev-parse --path-format=absolute --git-common-dir)"
[ "$git_dir" != "$common_dir" ] || die ISOLATED_WORKTREE_REQUIRED
case "$repo" in
  /home/kmjprod/*|/srv/www/*|/var/www/*) die PRODUCTION_CHECKOUT_DENIED ;;
esac

# Never load or package production/local secrets through the frontend build.
[ "${APP_ENV:-testing}" != "production" ] || die PRODUCTION_ENV_DENIED
for envfile in \
  .env .env.local .env.production .env.production.local \
  apps/platform/.env apps/platform/.env.local \
  apps/platform/.env.production apps/platform/.env.production.local; do
  [ ! -f "$envfile" ] || die ENV_SECRET_FILE_PRESENT
done

command -v php >/dev/null || die PHP_REQUIRED
command -v python3 >/dev/null || die PYTHON_REQUIRED
command -v npm >/dev/null || die NPM_REQUIRED

printf 'KMJ_LOCAL_HEAD=%s\n' "$current"
printf 'KMJ_CI_EXECUTION=LOCAL_ISOLATED_NOT_GITHUB_HOSTED\n'

for file in \
  apps/platform/routes/developer-licenses.php \
  apps/platform/tests/Feature/KslpDeveloperAppsTest.php; do
  php -l "$file"
done
python3 -m unittest discover -s tests -p 'test_kslp_python_first_use.py'
node --test tests/kslp-javascript-first-use.test.mjs

# Install from the checked-in lockfile. Skip third-party lifecycle scripts,
# external audit services and any paid/production command.
npm --prefix apps/platform ci --ignore-scripts --no-audit --no-fund
npm --prefix apps/platform run check
npm --prefix apps/platform run types:check
npm --prefix apps/platform run build

# Worktree artifacts are local only. No hosted green or release authority.
printf 'KMJ_LOCAL_STATIC_CHECKS_PASS_HEAD=%s\n' "$current"
printf 'KMJ_HOSTED_BRANCH_PROTECTION=UNCHANGED\n'
