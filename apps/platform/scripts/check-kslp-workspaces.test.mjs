import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');

void test('owner Licensing Hub presents separate tasks and payment setup', () => {
    const hub = read('../resources/js/pages/operator-kslp.tsx');
    assert.match(
        hub,
        /type HubWorkspace = 'overview' \| 'licenses' \| 'developers' \| 'security'/,
    );
    const workspaceLabels = [
        'Customers & licenses',
        'Developer apps & keys',
        'Security & audit',
        'Payment gateway setup',
    ];
    for (const label of workspaceLabels) {
        assert.ok(hub.includes(label), `Missing workspace: ${label}`);
    }
    assert.match(hub, /workspaceForHash\(window\.location\.hash\)/);
    assert.match(hub, /window\.addEventListener\('hashchange', syncWorkspace\)/);
    assert.match(hub, /aria-current=\{/);
});

void test('owner and developer flows keep distinct permission boundaries', () => {
    const hub = read('../resources/js/pages/operator-kslp.tsx');
    const ownerRoutes = read('../routes/kslp-admin.php');
    const sectionWorkspaces = [
        ['issuer-workspaces', 'developers'],
        ['developer-workspace', 'developers'],
        ['unverified-accounts', 'security'],
        ['license-issue', 'licenses'],
        ['license-search', 'licenses'],
        ['license-register', 'licenses'],
        ['license-entitlements', 'licenses'],
        ['license-audit', 'security'],
    ];
    for (const [section, workspace] of sectionWorkspaces) {
        const expected = `id="${section}"`;
        const visibility = `hidden={activeWorkspace !== '${workspace}'}`;
        assert.ok(hub.includes(expected), `Missing section: ${section}`);
        assert.ok(
            hub.includes(`${expected}\n                    ${visibility}`),
            `Incorrect workspace for: ${section}`,
        );
    }
    assert.match(hub, /DeveloperAppsWorkspace/);
    assert.match(ownerRoutes, /PlatformOwnerAccess/);
    assert.match(ownerRoutes, /'password\.confirm'/);
    assert.match(hub, /CloudOS license lifecycle/);
    assert.match(hub, /Live checkout, settlement and automatic/);
    assert.doesNotMatch(hub, /rzp_live_|cashfree.*client_secret/i);
});
