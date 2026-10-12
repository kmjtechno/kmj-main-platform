#!/usr/bin/env bash
# KMJ exact-commit Super Admin verification; no live DB/DNS changes.
set -Eeuo pipefail
umask 077
if [[ ! ${1:-} =~ ^[a-f0-9]{40}$ ]]; then
    echo "Usage: bash scripts/ci/verify-super-admin-pr.sh <exact-40-char-SHA>" >&2
    exit 2
fi
sha="$1"
root="$(git rev-parse --show-toplevel)"
[[ "$(basename "$root")" == "kmj-main-platform" ]] || {
    echo "BLOCKED: run inside kmj-main-platform checkout" >&2
    exit 2
}
git -C "$root" cat-file -e "${sha}^{commit}" || {
    echo "BLOCKED: exact PR commit missing; fetch origin pull/368/head first" >&2
    exit 3
}
tmp="$(mktemp -d "${TMPDIR:-/tmp}/kmj-admin-pr.XXXXXXXX")"
cleanup() {
    git -C "$root" worktree remove --force "$tmp/worktree" >/dev/null 2>&1 || true
    rm -rf -- "$tmp"
}
trap cleanup EXIT HUP INT TERM
git -C "$root" worktree add --detach "$tmp/worktree" "$sha" >/dev/null
cd "$tmp/worktree"
[[ "$(git rev-parse HEAD)" == "$sha" ]] || exit 3
echo "VERIFICATION_SHA=$sha"

src="$root/apps/platform"
cd apps/platform
[[ -f "$src/vendor/autoload.php" && -x "$src/vendor/bin/phpunit" ]] || {
    echo "BLOCKED: development Composer dependencies unavailable" >&2
    exit 3
}
[[ -d "$src/node_modules" && -x "$src/node_modules/.bin/vp" ]] || {
    echo "BLOCKED: development npm dependencies unavailable" >&2
    exit 3
}
php -r 'exit(extension_loaded("sodium") && extension_loaded("pdo_sqlite") ? 0 : 1);' || {
    echo "BLOCKED: PHP sodium and pdo_sqlite required" >&2
    exit 3
}
cp -a "$src/vendor" ./vendor
cp -a "$src/node_modules" ./node_modules

export APP_ENV=testing DB_CONNECTION=sqlite DB_DATABASE=:memory:
export QUEUE_CONNECTION=sync CACHE_STORE=array SESSION_DRIVER=array
export APP_KEY="base64:$(php -r 'echo base64_encode(random_bytes(32));')"
export MAIL_MAILER=log

echo "== PHP syntax =="
for file in \
    routes/web.php routes/operator-directory.php routes/payments-console.php \
    app/Services/Payments/OwnerPaymentGatewaySettings.php \
    app/Services/Payments/PaymentGatewayReadiness.php \
    tests/Feature/PlatformOwnerConsoleTest.php \
    tests/Feature/OwnerDirectoryHttpTest.php \
    tests/Feature/OwnerPaymentGatewaySettingsTest.php \
    database/migrations/2026_10_12_010000_create_payment_gateway_settings_table.php
do
    php -l "$file" >/dev/null
done
echo "PASS: PHP syntax"

echo "== TypeScript, frontend checks and Vite build =="
npm run types:check
npm run check
npm run build
test -s public/build/manifest.json || {
    echo "FAIL: frontend build completed without a Vite manifest" >&2
    exit 1
}
echo "PASS: isolated frontend build and Vite manifest"

echo "== Laravel owner security tests =="
php artisan test --filter='PlatformOwnerConsoleTest|OwnerDirectoryHttpTest|OwnerPaymentGatewaySettingsTest' --no-ansi

echo "== PHP formatting and static analysis =="
./vendor/bin/pint --test
./vendor/bin/phpstan analyse --no-progress

echo "PASS: isolated Super Admin exact SHA $sha"
echo "NOT CHECKED: real PostgreSQL staging, paid gateway E2E, required GitHub Actions and release smoke"
