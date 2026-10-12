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
const config = read('config/services.php');
const keys = read('app/Services/Licensing/Kslp/KslpDeveloperKeys.php');
const activation = read('routes/developer-activation-api.php');

test('Admin and developer routes both stay registered', () => {
    assert.ok(web.includes("require __DIR__.'/developer-licenses.php'"));
    assert.ok(web.includes("require __DIR__.'/payments-console.php'"));
    assert.ok(bootstrap.includes("routes/operator-directory.php"));
});

test('Customer entitlements and public catalog stay separate', () => {
    assert.ok(web.includes("'discoverableProducts' => $discoverableProducts"));
    assert.ok(dashboard.includes('organizations.flatMap'));
    assert.ok(dashboard.includes('Explore KMJ products'));
});

test('Admin inventory reports missing registrations, not fake entitlements', () => {
    assert.ok(web.includes("'missingCanonicalSlugs' => $missingCanonicalSlugs"));
    assert.ok(admin.includes('missingCanonicalSlugs.map'));
    assert.ok(admin.includes('Product & licensing matrix'));
});

test('Owner, developer and sandbox navigation all remain visible', () => {
    for (const path of ['/operator/kslp', '/operator/payments', '/developer/apps']) {
        assert.ok(sidebar.includes(path));
    }
    assert.ok(sandbox.includes('Sandbox Token Lab'));
    assert.ok(sandbox.includes('href="/developer/apps"'));
    assert.ok(sandbox.includes('href="/operator/kslp"'));
});

test('Developer activation stays feature-flagged off by default', () => {
    assert.ok(config.includes("KMJ_DEVELOPER_LICENSING_ENABLED', false"));
    assert.ok(activation.includes("config('services.kmj_developer_licensing.enabled', false)"));
});

test('Self-service can never mint an unverified paid license', () => {
    assert.ok(keys.includes("if ($plan !== 'trial')"));
    assert.ok(keys.includes('KSLP_PAID_ENTITLEMENT_REQUIRED'));
});

test('Random bootstrap keys are stored as digests only', () => {
    assert.ok(keys.includes('random_bytes(32)'));
    assert.ok(keys.includes("hash('sha256', $plain)"));
});

test('Device registration does not pretend to issue a signed license', () => {
    assert.ok(activation.includes("'signed_lease_issued' => false"));
});

test('Consent withdrawal clears optional first-login telemetry', () => {
    assert.ok(activation.includes("'client_platform' => $data['metadata_consent'] ?"));
    assert.ok(activation.includes("'metadata_consented_at' => $data['metadata_consent'] ?"));
});
