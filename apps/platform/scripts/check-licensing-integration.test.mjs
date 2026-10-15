import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(path, 'utf8');
const web = read('routes/web.php');
const bootstrap = read('bootstrap/app.php');
const dashboard = read('resources/js/pages/dashboard.tsx');
const sidebar = read('resources/js/components/app-sidebar.tsx');
const sandbox = read('resources/js/pages/sandbox-licenses.tsx');
const admin = read('resources/js/pages/operator.tsx');
const adminOverview = read(
    'resources/js/components/operator-control-overview.tsx',
);
const config = read('config/services.php');
const keys = read('app/Services/Licensing/Kslp/KslpDeveloperKeys.php');
const activation = read('routes/developer-activation-api.php');
const developerRoutes = read('routes/developer-licenses.php');
const developerApps = read('resources/js/pages/developer-apps.tsx');
const ownerLicensing = read('resources/js/pages/operator-kslp.tsx');
const firstUseSdk = read('public/sdk/python/kmj_kslp_first_use.py');
const localVerifier = read('../../scripts/ci/verify-authsp-licensing-local.sh');

void test('Admin and developer routes both stay registered', () => {
    assert.ok(web.includes("require __DIR__.'/developer-licenses.php'"));
    assert.ok(web.includes("require __DIR__.'/payments-console.php'"));
    assert.ok(bootstrap.includes('routes/operator-directory.php'));
});

void test('Customer entitlements and public catalog stay separate', () => {
    assert.ok(web.includes("'discoverableProducts' => $discoverableProducts"));
    assert.ok(dashboard.includes('organizations.flatMap'));
    assert.ok(dashboard.includes('Explore KMJ products'));
});

void test('Admin inventory reports missing registrations, not fake entitlements', () => {
    assert.ok(
        web.includes("'missingCanonicalSlugs' => $missingCanonicalSlugs"),
    );
    assert.ok(admin.includes('<OperatorControlOverview'));
    assert.ok(adminOverview.includes('missingCanonicalSlugs.map'));
    assert.ok(adminOverview.includes('Entries missing from the database'));
    assert.ok(adminOverview.includes('do not grant'));
    assert.ok(adminOverview.includes('customer access'));
});

void test('Owner, developer and sandbox navigation all remain visible', () => {
    for (const path of [
        '/operator/kslp',
        '/operator/payments',
        '/developer/apps',
    ]) {
        assert.ok(sidebar.includes(path));
    }
    assert.ok(sandbox.includes('Sandbox Token Lab'));
    assert.ok(sandbox.includes('href="/developer/apps"'));
    assert.ok(sandbox.includes('href="/operator/kslp"'));
});

void test('Developer activation stays feature-flagged off by default', () => {
    assert.ok(config.includes("KMJ_DEVELOPER_LICENSING_ENABLED', false"));
    assert.ok(
        activation.includes(
            "config('services.kmj_developer_licensing.enabled', false)",
        ),
    );
});

void test('Self-service can never mint an unverified paid license', () => {
    assert.ok(keys.includes("if ($plan !== 'trial')"));
    assert.ok(keys.includes('KSLP_PAID_ENTITLEMENT_REQUIRED'));
});

void test('Random bootstrap keys are stored as digests only', () => {
    assert.ok(keys.includes('random_bytes(32)'));
    assert.ok(keys.includes("hash('sha256', $plain)"));
});

void test('Device registration does not pretend to issue a signed license', () => {
    assert.ok(activation.includes("'signed_lease_issued' => false"));
});

void test('Consent withdrawal clears optional first-login telemetry', () => {
    assert.ok(
        activation.includes("'client_platform' => $data['metadata_consent'] ?"),
    );
    assert.ok(
        activation.includes(
            "'metadata_consented_at' => $data['metadata_consent'] ?",
        ),
    );
});

void test('Global PHP route imports cannot produce DomainException Wayfinder warnings', () => {
    for (const source of [activation, developerRoutes]) {
        assert.doesNotMatch(source, /^use DomainException;$/m);
        assert.ok(source.includes('catch (DomainException'));
    }
});

void test('Guided AuthSP-style onboarding retains governed server issuance', () => {
    assert.ok(developerApps.includes('Four-step licensing setup'));
    assert.ok(developerApps.includes('suggestProductCode(name)'));
    assert.ok(developerApps.includes('customProductCode'));
    assert.ok(developerApps.includes('readyToIssue'));
    assert.ok(developerApps.includes('Use this app'));
    assert.ok(developerApps.includes('Continue to integration starter'));
    assert.ok(developerApps.includes('disabled={!displayedApp}'));
    assert.ok(developerApps.includes('starter only, not a signed SDK'));
    assert.ok(developerRoutes.includes("'plan' => ['required', 'in:trial']"));
    assert.ok(developerRoutes.includes("'password.confirm'"));
    assert.ok(developerRoutes.includes("'throttle:10,1'"));
});

void test('AuthSP-inspired licensing directory contains no raw device identifiers', () => {
    assert.ok(developerRoutes.includes("'activeDevices' => $activeDevices"));
    assert.ok(developerRoutes.includes("'activeSeatCounts' => $activeSeatCounts"));
    assert.ok(developerRoutes.includes("'recentEvents' => $recentEvents"));
    assert.ok(developerRoutes.includes("->whereIn('license_id', $licenseIds)"));
    assert.ok(developerRoutes.includes("->whereNull('deactivated_at')"));
    assert.ok(developerRoutes.includes("->get(['id', 'license_id', 'activated_at'])"));
    assert.ok(developerRoutes.includes("->get(['license_id', 'action', 'created_at'])"));
    assert.ok(developerApps.includes('Search issued licenses'));
    assert.ok(developerApps.includes('Release device seat'));
    assert.ok(developerApps.includes('Confirm seat release'));
    assert.ok(ownerLicensing.includes('Licensing quick start'));
    assert.ok(ownerLicensing.includes('/developer/apps'));
});

void test('Developer product ID fits the actual commercial license schema', () => {
    const keysService = read('app/Services/Licensing/Kslp/KslpDeveloperKeys.php');
    assert.ok(developerRoutes.includes("'max:64'"));
    assert.ok(developerApps.includes('maxLength={64}'));
    assert.ok(developerApps.includes('.slice(0, 60)'));
    assert.ok(keysService.includes('KSLP_PRODUCT_CODE_TOO_LONG'));
});

void test('Device seat release stays authenticated, governed and idempotent', () => {
    assert.ok(developerRoutes.includes("keys/{key}/devices/{activation}/release"));
    assert.ok(developerRoutes.includes("'license.manage'"));
    assert.ok(developerRoutes.includes("'password.confirm', 'throttle:5,1'"));
    assert.ok(developerRoutes.includes("->lockForUpdate()"));
    assert.ok(developerRoutes.includes("where('license_id', $record->license_id)"));
    assert.ok(developerRoutes.includes("if ($device->deactivated_at !== null)"));
    assert.ok(developerRoutes.includes("'developer_device_released'"));
    assert.ok(developerRoutes.includes("'sequence' => DB::raw('sequence + 1')"));
    assert.ok(developerRoutes.includes("config('services.kmj_developer_licensing.enabled', false)"));
});

void test('Python first use proves device ownership without issuing a commercial lease', () => {
    assert.ok(firstUseSdk.includes('KSLP-ACTIVATE-v1|'));
    assert.ok(firstUseSdk.includes('parts.hostname.lower() != "kmjtechno.com"'));
    assert.ok(firstUseSdk.includes('signed_lease_issued'));
    assert.ok(firstUseSdk.includes('return False'));
    assert.ok(firstUseSdk.includes('license_key'));
    assert.ok(!firstUseSdk.includes('open("private_key"'));
    assert.ok(developerRoutes.includes("'plan' => ['required', 'in:trial']"));
});

void test('Local licensing verifier cannot run from production or satisfy hosted CI', () => {
    assert.ok(localVerifier.includes('ISOLATED_WORKTREE_REQUIRED'));
    assert.ok(localVerifier.includes('HEAD_MISMATCH'));
    assert.ok(localVerifier.includes('DIRTY_TRACKED_CHECKOUT'));
    assert.ok(localVerifier.includes('PRODUCTION_ENV_DENIED'));
    assert.ok(localVerifier.includes('ENV_SECRET_FILE_PRESENT'));
    assert.ok(localVerifier.includes('LOCAL_ISOLATED_NOT_GITHUB_HOSTED'));
    assert.ok(localVerifier.includes('HOSTED_BRANCH_PROTECTION=UNCHANGED'));
    assert.ok(!localVerifier.includes('git push'));
    assert.ok(!localVerifier.includes('artisan migrate'));
});
