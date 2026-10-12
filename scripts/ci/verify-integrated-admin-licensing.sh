#!/usr/bin/env bash
# Free, exact-SHA development verification for the combined KMJ release.
# It only invokes pre-existing isolated-worktree verification scripts.
set -Eeuo pipefail

if [[ ! ${1:-} =~ ^[a-f0-9]{40}$ ]]; then
    echo "Usage: bash scripts/ci/verify-integrated-admin-licensing.sh <exact-40-char-SHA>" >&2
    exit 2
fi

sha="$1"
root="$(git rev-parse --show-toplevel)"
cd "$root"
[[ "$(basename "$root")" == "kmj-main-platform" ]] || {
    echo "BLOCKED: incorrect repository" >&2
    exit 2
}
git cat-file -e "${sha}^{commit}" || {
    echo "BLOCKED: exact PR head unavailable. Fetch the reviewed commit before running." >&2
    exit 3
}

echo "KMJ INTEGRATION_VERIFICATION_SHA=$sha"

# First execute zero-install tests on the exact commit in a disposable
# worktree. This gives actionable evidence even when vendor/node_modules
# are not preinstalled on the approved development machine.
tmp_preflight="$(mktemp -d "${TMPDIR:-/tmp}/kmj-release-preflight.XXXXXXXX")"
preflight_cleanup() {
    git -C "$root" worktree remove --force "$tmp_preflight/tree" >/dev/null 2>&1 || true
    rm -rf -- "$tmp_preflight"
}
trap preflight_cleanup EXIT HUP INT TERM
git -C "$root" worktree add --detach "$tmp_preflight/tree" "$sha" >/dev/null
[[ "$(git -C "$tmp_preflight/tree" rev-parse HEAD)" == "$sha" ]] || exit 3
cd "$tmp_preflight/tree/apps/platform"
if ! command -v php >/dev/null; then
    echo "BLOCKED: PHP CLI missing" >&2
    exit 3
fi
echo "== Preflight: PHP syntax =="
for path in \
    routes/web.php routes/developer-licenses.php routes/developer-activation-api.php \
    routes/operator-directory.php routes/payments-console.php \
    app/Services/Licensing/Kslp/KslpDeveloperKeys.php \
    app/Services/Licensing/Kslp/KslpLicenseControlPlane.php \
    app/Services/Licensing/Kslp/KslpOfflineLeaseGuard.php \
    app/Services/Payments/OwnerPaymentGatewaySettings.php \
    database/migrations/2026_10_12_120000_create_kslp_license_keys_table.php \
    database/migrations/2026_10_12_010000_create_payment_gateway_settings_table.php \
    tests/Feature/KslpLifecycleTest.php \
    tests/Feature/KslpDeveloperAppsTest.php \
    tests/Feature/KslpDeveloperActivationApiTest.php \
    tests/Feature/PlatformOwnerConsoleTest.php; do
    php -l "$path" >/dev/null
done
echo "PASS: 15 PHP files syntax"

if ! command -v node >/dev/null; then
    echo "BLOCKED: Node.js CLI missing for built-in integration tests" >&2
    exit 3
fi
echo "== Preflight: built-in Node integration contracts =="
node --test scripts/check-licensing-integration.test.mjs
echo "PASS: zero-install exact-SHA preflight"
cd "$root"
preflight_cleanup
trap - EXIT HUP INT TERM

# The current checkout can remain on main: the review scripts are extracted
# from the exact candidate commit, not from whichever branch is checked out.
tmp="$(mktemp -d "${TMPDIR:-/tmp}/kmj-release-driver.XXXXXXXX")"
trap 'rm -rf -- "$tmp"' EXIT HUP INT TERM
for path in \
    scripts/ci/verify-super-admin-pr.sh \
    scripts/ci/verify-kslp-pr.sh; do
    name="$(basename "$path")"
    git show "$sha:$path" > "$tmp/$name" || {
        echo "BLOCKED: verifier missing from pinned release commit: $path" >&2
        exit 3
    }
done

failures=0
echo "== Admin routes/UI/permissions =="
if bash "$tmp/verify-super-admin-pr.sh" "$sha"; then
    echo "PASS: Admin integration suite"
else
    echo "FAIL: Admin integration suite"
    failures=$((failures + 1))
fi

echo "== KSLP security, developer activation and SDK setup UI =="
if bash "$tmp/verify-kslp-pr.sh" "$sha"; then
    echo "PASS: KSLP integration suite"
else
    echo "FAIL: KSLP integration suite"
    failures=$((failures + 1))
fi

echo "INTEGRATION_SUITE_FAILURES=$failures SHA=$sha"
if (( failures != 0 )); then
    exit 1
fi
echo "PASS: exact-SHA isolated code suites for $sha"
echo "NOT VERIFIED: protected GitHub Actions, disposable PostgreSQL migration/rollback,"
echo "production signed KSLP SDKs, settlement/reconciliation, canary or production deployment"
