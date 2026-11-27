import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) =>
    readFileSync(new URL('../' + path, import.meta.url), 'utf8');
const ownerRoutes = read('routes/kslp-admin.php');
const developerRoutes = read('routes/developer-licenses.php');
const developerWorkspace = read(
    'app/Services/Licensing/Kslp/KslpDeveloperWorkspaceQuery.php',
);
const ownerUi = read('resources/js/pages/operator-kslp.tsx');
const dashboard = read('resources/js/pages/dashboard.tsx');
const developerUi = read('resources/js/pages/developer-apps.tsx');
const sidebar = read('resources/js/components/app-sidebar.tsx');
const nav = read('resources/js/components/operator-module-navigation.tsx');
const profile = read(
    'app/Services/Licensing/ProductLicenseProfileRegistry.php',
);

void test('KMJ Licensing Hub owns consistent project identity without new authority', () => {
    assert.match(ownerUi, /KMJ Licensing Hub · Owner Authority/);
    assert.match(ownerUi, /KMJ Licensing Hub · Super Admin/);
    assert.match(dashboard, /KMJ Licensing Hub · Customer access/);
    assert.match(developerUi, /KMJ Licensing Hub · Developer Apps/);
    assert.match(sidebar, /KMJ Licensing Hub · Owner/);
    assert.match(nav, /label: 'Licensing Hub'/);
    assert.match(profile, /LICENSING_HUB_SLUG/);
});

void test('all owner licensing read/write endpoints require platform owner and recent password', () => {
    assert.equal(
        (ownerRoutes.match(/\$access->require\(\$user\);/g) || []).length,
        3,
    );
    assert.equal(
        (ownerRoutes.match(/middleware\('password\.confirm'\)/g) || []).length,
        3,
    );
    assert.match(ownerRoutes, /Route::get\('operator\/kslp'/);
    assert.match(ownerRoutes, /Route::post\('operator\/kslp\/licenses'/);
    assert.match(
        ownerRoutes,
        /Route::post\('operator\/kslp\/licenses\/\{license\}\/action'/,
    );
});

void test('customers see only actual organization entitlements, never catalog-inferred purchases', () => {
    assert.match(dashboard, /organizations\.flatMap/);
    assert.match(dashboard, /organization\.entitlements\.map/);
    assert.match(dashboard, /entitlement\.status === 'active'/);
    assert.match(dashboard, /does not give you access to it/);
    assert.match(dashboard, /service\.product_slug === 'kmj-codebridge'/);
    assert.match(dashboard, /detail\?\.plan/);
    assert.match(dashboard, /Switched on for your organization/);
    assert.match(dashboard, /The product may run its own checks/);
    assert.match(dashboard, /Not active: this gives no feature access/);
    assert.doesNotMatch(dashboard, /customers cannot change/);
});

void test('developer license management retains tenant and paid-license gates', () => {
    assert.match(developerRoutes, /'license\.manage'/);
    // Both owner and tenant views must share this exact restrictive KSLP
    // query; its move to a service must not remove the security assertion.
    assert.match(developerRoutes, /KslpDeveloperWorkspaceQuery/);
    assert.match(ownerRoutes, /KslpDeveloperWorkspaceQuery/);
    assert.match(
        developerWorkspace,
        /->whereIn\('k\.organization_id', \$tenantIds\)/,
    );
    assert.match(
        developerRoutes,
        /->middleware\(\['password\.confirm', 'throttle:/,
    );
    assert.match(developerUi, /global customer\/license policy remains/);
    assert.match(developerUi, /Super Admin-only/);
});

void test('customer navigation does not advertise owner licensing control', () => {
    const ownerStart = sidebar.indexOf('const ownerCommerce: NavItem[]');
    const ownerEnd = sidebar.indexOf('const ownerSystems: NavItem[]');
    assert.ok(ownerStart > 0 && ownerEnd > ownerStart);
    assert.match(sidebar.slice(ownerStart, ownerEnd), /operator\?\.enabled/);
    assert.match(
        sidebar.slice(ownerStart, ownerEnd),
        /KMJ Licensing Hub · Owner/,
    );
    assert.ok(
        !sidebar
            .slice(
                sidebar.indexOf('const baseNavItems:'),
                sidebar.indexOf('const footerNavItems:'),
            )
            .includes('/operator/kslp'),
    );
});
