#!/usr/bin/env bash
# Isolated, free KSLP PR verification. Never alters the original checkout, DB or DNS.
set -Eeuo pipefail
umask 077

usage() {
  echo "Usage: $0 <exact-40-character-commit-sha>" >&2
  echo "Run inside an authorized kmj-main-platform Git checkout with installed test dependencies." >&2
  exit 2
}
[[ ${1:-} =~ ^[a-f0-9]{40}$ ]] || usage
expected_sha="$1"
repo="$(git rev-parse --show-toplevel)"
cd "$repo"
[[ "$(basename "$repo")" == "kmj-main-platform" ]] || {
  echo "BLOCKED: not the KMJ Main Platform repository" >&2
  exit 2
}
git cat-file -e "${expected_sha}^{commit}" || {
  echo "BLOCKED: expected commit is not present locally; fetch the exact PR head first" >&2
  exit 2
}
tmp="$(mktemp -d "${TMPDIR:-/tmp}/kmj-kslp-verify.XXXXXXXX")"
cleanup() {
  git -C "$repo" worktree remove --force "$tmp/tree" >/dev/null 2>&1 || true
  rm -rf -- "$tmp"
}
trap cleanup EXIT HUP INT TERM
git -C "$repo" worktree add --detach "$tmp/tree" "$expected_sha" >/dev/null
actual_sha="$(git -C "$tmp/tree" rev-parse HEAD)"
[[ "$actual_sha" == "$expected_sha" ]] || {
  echo "BLOCKED: exact SHA mismatch" >&2
  exit 2
}
echo "KMJ KSLP isolated verification SHA=$actual_sha"
cd "$tmp/tree/apps/platform"

for file in \
  app/Services/Licensing/Kslp/KslpCodec.php \
  app/Services/Licensing/Kslp/KslpVerifier.php \
  app/Services/Licensing/Kslp/KslpLicenseControlPlane.php \
  app/Services/Licensing/Kslp/KslpActivationProof.php \
  app/Services/Licensing/Kslp/KslpActivationReplayGuard.php \
  app/Services/Licensing/Kslp/KslpOfflineLeaseGuard.php \
  tests/Feature/KslpLifecycleTest.php \
  tests/Unit/Kslp/KslpActivationReplayGuardTest.php \
  tests/Unit/Kslp/KslpOfflineLeaseGuardTest.php; do
  php -l "$file" >/dev/null
done
echo "PASS: 9 PHP files syntax"

# Copy existing local *development* dependencies only, rather than silently
# running a paid service, pulling unknown code or using production credentials.
src="$repo/apps/platform"
if [[ ! -f "$src/vendor/autoload.php" || ! -x "$src/vendor/bin/phpunit" ]]; then
  echo "BLOCKED: this checkout lacks installed Composer test dependencies" >&2
  exit 3
fi
cp -a "$src/vendor" ./vendor
[[ -f vendor/autoload.php && -x vendor/bin/phpunit ]] || exit 3
if ! php -r 'exit(extension_loaded("sodium") && extension_loaded("pdo_sqlite") ? 0 : 1);'; then
  echo "BLOCKED: PHP sodium and pdo_sqlite extensions required for isolated tests" >&2
  exit 3
fi
if ! [[ -f "$src/.env.testing" ]]; then
  echo "INFO: no .env.testing copied; using ephemeral APP_KEY and SQLite in memory"
fi
export APP_ENV=testing
export DB_CONNECTION=sqlite
export DB_DATABASE=:memory:
export QUEUE_CONNECTION=sync
export CACHE_STORE=array
export SESSION_DRIVER=array
export APP_KEY="base64:$(php -r 'echo base64_encode(random_bytes(32));')"

# No migration against production and no credential import.
php artisan test --filter=Kslp --no-ansi
./vendor/bin/pint --test \
  app/Services/Licensing/Kslp/KslpActivationReplayGuard.php \
  app/Services/Licensing/Kslp/KslpOfflineLeaseGuard.php \
  app/Services/Licensing/Kslp/KslpLicenseControlPlane.php \
  tests/Feature/KslpLifecycleTest.php \
  tests/Unit/Kslp/KslpOfflineLeaseGuardTest.php \
  tests/Unit/Kslp/KslpActivationReplayGuardTest.php
./vendor/bin/phpstan analyse --no-progress
echo "PASS: KSLP PHPUnit, Pint and PHPStan on SHA $actual_sha (isolated worktree)"
