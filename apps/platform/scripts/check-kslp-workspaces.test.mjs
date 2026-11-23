import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');

void test('owner Licensing Hub presents four distinct task workspaces and payment setup', () => {
    const hub = read('../resources/js/pages/operator-kslp.tsx');
    assert.match(hub, /type HubWorkspace = 'overview' \| 'licenses' \| 'developers' \| 'security'/);
    for (const label of ['Customers & licenses', 'Developer apps & keys', 'Security & audit', 'Payment gateway setup']) {
        assert.ok(hub.includes(label), `Missing workspace: ${label}`);
    }
    assert.match(hub, /workspaceForHash\(window\.location\.hash\)/);
    assert.match(hub, /window\.addEventListener\('hashchange', syncWorkspace\)/);
    assert.match(hub, /aria-current=\{activeWorkspace === workspace\.id \? 'page' : undefined\}/);
});

void test('sensitive owner workflows stay isolated and no second licensing authority is introduced', () => {
    const hub = read('../resources/js/pages/operator-kslp.tsx');
    const ownerRoutes = read('../routes/kslp-admin.php');
    for (const [section, workspace] of [
        ['issuer-workspaces', 'developers'],
        ['developer-workspace', 'developers'],
        ['unverified-accounts', 'security'],
        ['license-issue', 'licenses'],
        ['license-search', 'licenses'],
        ['license-register', 'licenses'],
        ['license-entitlements', 'licenses'],
        ['license-audit', 'security'],
    ]) {
        const safeSection = section.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const pattern = new RegExp(`id="${safeSection}"\\s+hidden=\\{activeWorkspace !== '${workspace}'\\}`);
        assert.match(hub, pattern, `Wrong workspace for ${section}`);
    }
    assert.match(hub, /DeveloperAppsWorkspace/);
    assert.match(ownerRoutes, /PlatformOwnerAccess/);
    assert.match(ownerRoutes, /'password\.confirm'/);
    assert.match(hub, /CloudOS license lifecycle/);
    assert.match(hub, /Live checkout, settlement and automatic/);
    assert.doesNotMatch(hub, /rzp_live_|cashfree.*client_secret/i);
});
