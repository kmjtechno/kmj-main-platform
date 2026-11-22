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
    assert.ok(!sidebar.includes("href: '/sandbox-licenses'"));
    assert.ok(sidebar.includes("title: 'Licensing Hub'"));
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

void test('one KMJ Licensing Hub embeds developer workflow and retains owner authority', () => {
    const owner = read('resources/js/pages/operator-kslp.tsx');
    const developer = read('resources/js/pages/developer-apps.tsx');
    const ownerRoutes = read('routes/kslp-admin.php');
    const commands = read('resources/js/components/operator-command-os.tsx');
    const workspaces = read(
        'resources/js/components/operator-workspace-map.tsx',
    );

    assert.ok(
        owner.includes(
            '<DeveloperAppsWorkspace {...developerWorkspace} embedded />',
        ),
    );
    assert.ok(developer.includes('export function DeveloperAppsWorkspace'));
    assert.ok(
        developerRoutes.includes(
            "return redirect('/operator/kslp#developer-workspace')",
        ),
    );
    assert.ok(ownerRoutes.includes("'developerWorkspace' => ["));
    assert.ok(commands.includes("['KMJ Licensing Hub', '/operator/kslp'"));
    assert.ok(
        !commands.includes("['Developer Apps & Keys', '/developer/apps'"),
    );
    assert.ok(!workspaces.includes("href: '/developer/apps'"));
});

void test('account cleanup is an owner-only exact-snapshot action, disabled by default', () => {
    const ownerRoutes = read('routes/kslp-admin.php');
    const cleanup = read('app/Services/Licensing/UnverifiedAccountCleanup.php');
    const ownerUi = read('resources/js/pages/operator-kslp.tsx');
    const config = read('config/services.php');

    assert.match(config, /KMJ_UNVERIFIED_ACCOUNT_CLEANUP_ENABLED', false/);
    assert.match(ownerRoutes, /\$access->require\(\$actor\)/);
    assert.match(ownerRoutes, /REMOVE_UNVERIFIED_EMAIL_USERS/);
    assert.match(cleanup, /whereNull\('email_verified_at'\)/);
    assert.match(cleanup, /MIN_AGE_DAYS = 7/);
    assert.match(cleanup, /getForeignKeys\(\$table\)/);
    assert.match(cleanup, /UNVERIFIED_CLEANUP_STALE_PREVIEW/);
    assert.match(ownerUi, /unverifiedEmailCleanup\.enabled/);
    assert.doesNotMatch(cleanup, /whereNull\('email_verified_at'\)->delete\(/);
});

void test('owner Licensing Hub renders bounded searchable registers and accessible actions', () => {
    const owner = read('resources/js/pages/operator-kslp.tsx');

    // Large owner-only dataset remains available by paging; never silently omit records.
    assert.match(owner, /const LIST_PAGE_SIZE = 10/);
    assert.match(owner, /issuerWorkspaces\.filter/);
    assert.match(owner, /issuerRows\.map/);
    assert.match(owner, /entitlementRows\.map/);
    assert.match(owner, /auditRows\.map/);
    assert.match(owner, /label="Developer issuer organizations"/);
    assert.match(owner, /label="Product entitlements"/);
    assert.match(owner, /label="License lifecycle audit trail"/);
    assert.match(owner, /onPageChange=\{setIssuerPage\}/);
    assert.match(owner, /onPageChange=\{setEntitlementPage\}/);
    assert.match(owner, /onPageChange=\{setAuditPage\}/);
    assert.match(owner, /setIssuerPage\(0\)/);
    assert.match(owner, /disabled=\{page === 0\}/);
    assert.match(owner, /disabled=\{page >= pageCount - 1\}/);

    // The single integrated owner hub retains the real developer workspace and protected forms.
    assert.match(owner, /<details className=.*open=\{developerWorkspace\.newKey/);
    assert.match(owner, /<DeveloperAppsWorkspace \{\.\.\.developerWorkspace\} embedded \/>/);
    assert.match(owner, /aria-label="Customer or organization ID"/);
    assert.match(owner, /aria-label="License plan"/);
    assert.match(owner, /aria-label="Reason for license issuance"/);
    assert.match(owner, /unverifiedEmailCleanup\.enabled/);
    assert.match(owner, /\/operator\/kslp\/licenses/);
});
