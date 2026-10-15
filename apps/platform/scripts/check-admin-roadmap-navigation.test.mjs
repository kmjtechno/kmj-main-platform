import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const read = (path) =>
    readFileSync(new URL('../' + path, import.meta.url), 'utf8');
const map = read('resources/js/components/operator-workspace-map.tsx');
// Normalize source formatting only; every expected sentence still must exist.
const normalizedMap = map.replace(/\s+/g, ' ');
const overview = read('resources/js/components/operator-control-overview.tsx');
const sidebar = read('resources/js/components/app-sidebar.tsx');
const dashboard = read('resources/js/pages/dashboard.tsx');
const css = read('resources/css/admin-premium.css');
const routes = [
    read('routes/web.php'),
    read('routes/operator-directory.php'),
    read('routes/payments-console.php'),
    read('routes/operator-ops.php'),
    read('routes/codebridge-admin.php'),
    read('routes/kslp-admin.php'),
    read('routes/developer-licenses.php'),
].join('\n');

void test('task-first categories contain real, inspectable workspaces', () => {
    for (const title of [
        'People & access',
        'Products & lifecycle',
        'Revenue & entitlements',
        'Systems & developers',
    ]) {
        assert.ok(map.includes(title), 'Missing group: ' + title);
    }
    const links = [
        '/operator/directory',
        '/settings/security',
        '/operator/products',
        '/products',
        '/operator#commercial-orders',
        '/operator/payments',
        '/operator/kslp',
        '/operator/ops',
        '/operator/codebridge/owner-plan',
        '/developer/apps',
        '/sandbox-licenses',
    ];
    for (const href of links) {
        assert.ok(
            map.includes("href: '" + href + "'"),
            'Missing tested navigation: ' + href,
        );
    }
    assert.match(routes, /Route::get\('products'/);
    assert.match(routes, /Route::get\('directory'/);
    assert.match(routes, /Route::get\('payments'/);
    assert.match(routes, /Route::get\('ops'/);
    assert.match(routes, /Route::get\('operator\/kslp'/);
    assert.match(routes, /Route::get\('owner-plan'/);
    assert.match(routes, /Route::get\('apps'/);
    assert.match(routes, /Route::get\('sandbox-licenses'/);
});

void test('roadmap-only modules cannot look like operational services', () => {
    const planned = map.slice(
        map.indexOf('const roadmapQueue = ['),
        map.indexOf('export default function'),
    );
    for (const name of [
        'KMJ Mail administration',
        'Support & Trust cases',
        'Content & SEO studio',
        'Release registry',
        'Reporting & analytics',
    ]) {
        assert.ok(planned.includes(name), 'Missing planned module: ' + name);
    }
    assert.doesNotMatch(planned, /href:/);
    assert.match(
        normalizedMap,
        /Roadmap concepts, not live services or available controls/,
    );
    assert.match(map, /Planned/);
    assert.doesNotMatch(map, /99\.9%|fake|mockMetrics|activeLicenses:\s*\d+/);
});

void test('mobile owner search and roadmap disclosure are accessible', () => {
    assert.match(map, /aria-label="Search owner tasks and modules"/);
    assert.match(map, /type="search"/);
    assert.match(map, /onChange=\{\(event\) => setQuery/);
    assert.match(map, /value=\{query\}/);
    assert.match(map, /aria-expanded=\{showRoadmap\}/);
    assert.match(map, /aria-controls="kmj-roadmap-modules"/);
    assert.match(map, /hidden=\{!listRoadmap\}/);
    assert.match(map, /focus-visible:outline-2/);
    assert.match(css, /prefers-reduced-motion: reduce/);
    assert.match(css, /\.kmj-admin-workspace-map \[hidden\]/);
    assert.match(css, /kmj-admin-category/);
});

void test('owner-only sidebar separates personal workspace from governed areas', () => {
    assert.match(sidebar, /const ownerBusiness: NavItem\[\]/);
    assert.match(sidebar, /const ownerCommerce: NavItem\[\]/);
    assert.match(sidebar, /const ownerSystems: NavItem\[\]/);
    assert.match(sidebar, /\{operator\?\.enabled && \(/);
    assert.match(sidebar, /Business · Owner/);
    assert.match(sidebar, /Commerce & Access/);
    assert.match(sidebar, /Systems & Trust/);
    assert.match(
        sidebar,
        /<NavMain items=\{baseNavItems\} label="My workspace"/,
    );
    assert.match(overview, /<OperatorWorkspaceMap \/>/);
    assert.match(dashboard, /Open Command Center/);
    assert.match(dashboard, /href="\/operator"/);
    assert.match(dashboard, /ownerProducts !== null/);
    assert.match(overview, /<details className=/);
    assert.match(overview, /Advanced module index/);
});

void test('task-based navigation never issues a license or payment as a side effect', () => {
    assert.doesNotMatch(map, /router\.(post|put|delete)\(/);
    assert.doesNotMatch(map, /fetch\(/);
    assert.match(
        normalizedMap,
        /Commercial approval, license issuance and production publishing/,
    );
    assert.match(overview, /order\.fulfillment_state === 'ready'/);
    assert.match(overview, /product\.active_policy_count === 0/);
});
