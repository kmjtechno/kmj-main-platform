#!/usr/bin/env bash
# Local-first no-network CodeBridge device-control verification.
# Requires Node/Composer dependencies already installed in a disposable checkout.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

if [[ ! -f artisan || ! -f package.json ]] || ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "BLOCKED: run from a Git source checkout of apps/platform" >&2
  exit 2
fi
# Protect production and user environments. Run only against a clean,
# disposable checkout with no local deployment secrets.
if [[ -e .env || -e .env.production || -e bootstrap/cache/config.php ]]; then
  echo "BLOCKED: existing environment or cached production config; use a disposable checkout" >&2
  exit 3
fi
if ! command -v php >/dev/null || ! command -v node >/dev/null || ! command -v npm >/dev/null; then
  echo "BLOCKED: PHP, Node and npm must be installed" >&2
  exit 4
fi
if [[ ! -f vendor/autoload.php || ! -x node_modules/.bin/tsc ]]; then
  echo "BLOCKED: restore dependencies once from trusted lockfiles. This verification never downloads dependencies." >&2
  exit 5
fi

export APP_ENV=testing
export APP_DEBUG=false
export DB_CONNECTION=sqlite
export DB_DATABASE=':memory:'
export QUEUE_CONNECTION=sync
export MAIL_MAILER=array
export SESSION_DRIVER=array
export CACHE_STORE=array
export APP_KEY
APP_KEY="$(php -r 'echo "base64:".base64_encode(random_bytes(32));')"
echo "VERIFY_MODE=LOCAL_OFFLINE_NO_NETWORK"
echo "VERIFY_SCOPE=CODEBRIDGE_DEVICE_CONTROL"
php -l routes/codebridge-device-control.php
php -l routes/web.php
php -l tests/Feature/CodeBridgeAdminHttpTest.php
php -l app/Services/Licensing/CodeBridge/CodeBridgeDeviceEnrollmentService.php
php artisan route:clear
php artisan wayfinder:generate --with-form
test -f resources/js/routes/index.ts
test -d resources/js/actions
test -d resources/js/wayfinder
npm run types:check
node --test scripts/check-codebridge-safe-onboarding.test.mjs scripts/check-codebridge-dashboard-truth.test.mjs
php artisan test --filter=CodeBridgeAdminHttpTest
php artisan test --filter=CodeBridgeDeviceEnrollmentTest
echo "PASS: local device-control contracts and isolated tenant-safe tests"
