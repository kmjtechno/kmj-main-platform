#!/usr/bin/env bash
# Isolated AuthSP licensing formatter. Never deploys; never force-pushes.
set -Eeuo pipefail
BRANCH="feat/authsp-license-device-center-20261016"
PUSH=0
if [[ "${1:-}" == "--push" && $# -eq 1 ]]; then
  PUSH=1
elif [[ -n "${1:-}" ]]; then
  echo "USAGE: bash scripts/ci/authsp-fix-isolated.sh [--push]" >&2
  exit 2
fi
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
test -d apps/platform || { echo WRONG_REPO >&2; exit 2; }
test -z "$(git diff --name-only --diff-filter=U)" || { echo SOURCE_CONFLICT >&2; exit 2; }
git fetch --no-tags origin "refs/heads/$BRANCH"
PIN="$(git rev-parse FETCH_HEAD)"
test "$PIN" = "$(git ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')" || {
  echo REMOTE_HEAD_RACE >&2; exit 3;
}
OUT="$(mktemp -d "${TMPDIR:-/tmp}/kmj-kslp-report.XXXXXX")"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/kmj-kslp-worktree.XXXXXX")"
ATTACHED=0
cleanup() {
  status=$?
  if [[ "$ATTACHED" == 1 ]]; then
    if [[ ! -s "$OUT/fix.patch" ]]; then
      git -C "$WORK" diff --binary > "$OUT/fix.patch" 2>/dev/null || true
    fi
    git worktree remove --force "$WORK" >/dev/null 2>&1 || true
  fi
  printf 'SOURCE_SHA=%s\nREPORT_DIR=%s\nEXIT=%s\n' "$PIN" "$OUT" "$status"
}
trap cleanup EXIT
git worktree add --detach "$WORK" "$PIN"
ATTACHED=1
cd "$WORK"
test "$(git rev-parse HEAD)" = "$PIN" || { echo HEAD_MISMATCH; exit 3; }
test -z "$(git status --porcelain --untracked-files=normal)" || {
  echo WORKTREE_NOT_CLEAN; exit 3;
}
test ! -f apps/platform/.env || { echo SECRET_ENV_PRESENT; exit 3; }
export APP_ENV=testing DB_CONNECTION=sqlite DB_DATABASE=:memory:
export CACHE_STORE=array SESSION_DRIVER=array QUEUE_CONNECTION=sync MAIL_MAILER=array
export KMJ_DEVELOPER_LICENSING_ENABLED=false
export APP_KEY="base64:$(php -r 'echo base64_encode(random_bytes(32));')"
PHP_FILES=(
 routes/developer-licenses.php
 app/Services/Licensing/Kslp/KslpDeveloperKeys.php
 app/Services/Licensing/Kslp/KslpLicenseControlPlane.php
 app/Services/Licensing/Kslp/KslpActivationProof.php
 app/Services/Licensing/Kslp/KslpIssuerSubscriptionAuthority.php
 tests/Feature/KslpDeveloperAppsTest.php
 tests/Feature/KslpLifecycleTest.php
 tests/Feature/KslpActivationProofTest.php
 tests/Feature/KslpDelegatedIssueTest.php
 tests/Feature/KslpIssuerSubscriptionTest.php
)
ALLOWED=(
 apps/platform/routes/developer-licenses.php
 apps/platform/app/Services/Licensing/Kslp/KslpDeveloperKeys.php
 apps/platform/app/Services/Licensing/Kslp/KslpLicenseControlPlane.php
 apps/platform/app/Services/Licensing/Kslp/KslpActivationProof.php
 apps/platform/app/Services/Licensing/Kslp/KslpIssuerSubscriptionAuthority.php
 apps/platform/tests/Feature/KslpDeveloperAppsTest.php
 apps/platform/tests/Feature/KslpLifecycleTest.php
 apps/platform/tests/Feature/KslpActivationProofTest.php
 apps/platform/tests/Feature/KslpDelegatedIssueTest.php
 apps/platform/tests/Feature/KslpIssuerSubscriptionTest.php
 apps/platform/resources/js/pages/developer-apps.tsx
 apps/platform/resources/js/pages/operator-kslp.tsx
 apps/platform/public/sdk/javascript/kmj_kslp_first_use.d.mts
 apps/platform/public/sdk/javascript/kmj_kslp_first_use.mjs
)
cd apps/platform
composer install --no-interaction --prefer-dist --no-progress
npm ci --ignore-scripts --no-audit --no-fund
vendor/bin/pint "${PHP_FILES[@]}"
if ! npm run check:fix; then
  echo FRONTEND_AUTOFIX_INCOMPLETE >&2
  exit 20
fi
cd "$WORK"
mapfile -t CHANGED < <(git diff --name-only)
printf '%s\n' "${CHANGED[@]}" > "$OUT/formatter-changed-paths.txt"
UNEXPECTED=0
for path in "${CHANGED[@]}"; do
  ok=0
  for allowed in "${ALLOWED[@]}"; do
    if [[ "$path" == "$allowed" ]]; then ok=1; break; fi
  done
  if [[ "$ok" != 1 ]]; then
    printf 'UNRELATED_FORMAT_CHANGE=%s\n' "$path" >&2
    UNEXPECTED=1
  fi
done
if [[ "$UNEXPECTED" -ne 0 ]]; then
  echo "FORMATTER_CHANGED_PATHS=$OUT/formatter-changed-paths.txt" >&2
  exit 21
fi
test -z "$(git ls-files --others --exclude-standard)" || {
  echo UNTRACKED_OUTPUT_DENIED >&2; exit 21;
}
git diff --check
cd apps/platform
vendor/bin/pint --test "${PHP_FILES[@]}"
npm run check
php artisan test --filter='KslpDeveloperAppsTest|KslpLifecycleTest|KslpDeveloperActivationApiTest|KslpDelegatedIssueTest|KslpIssuerSubscriptionTest|KslpActivationProofTest' --no-ansi
php artisan wayfinder:generate --with-form --no-ansi
npm run types:check
npm run build
test -s public/build/manifest.json
cd "$WORK"
printf 'VERIFIED_SHA=%s\nISOLATED_QA=PASS\nPRODUCTION_DEPLOYMENT=NO\n' "$PIN" > "$OUT/result.txt"
printf '%s\n' "${CHANGED[@]}" > "$OUT/changed.txt"
git diff --binary > "$OUT/fix.patch"
if [[ "${#CHANGED[@]}" -eq 0 ]]; then
  echo NO_FORMAT_DIFF
  exit 0
fi
if [[ "$PUSH" == 1 ]]; then
  test "$PIN" = "$(git ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')" || {
    echo REMOTE_BRANCH_ADVANCED_NO_PUSH >&2; exit 22;
  }
  git add -- "${CHANGED[@]}"
  git -c user.name="KMJ TECHNO QA" -c user.email="kmjtechnonet@gmail.com" \
    commit -m "style(licensing): exact-head Pint and Vite Plus autofix"
  git push origin "HEAD:refs/heads/$BRANCH"
  printf 'PUSHED_SHA=%s\n' "$(git rev-parse HEAD)" | tee -a "$OUT/result.txt"
else
  echo VERIFIED_PATCH_ONLY_RERUN_WITH_PUSH | tee -a "$OUT/result.txt"
fi
echo "ISOLATED_FORMATTING_QA_PASS; full release requires separate signing/payment/staging gates"
