import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const routes = readFileSync('routes/web.php', 'utf8');
const dashboard = readFileSync('resources/js/pages/dashboard.tsx', 'utf8');
const access = readFileSync('app/Services/PlatformOwnerAccess.php', 'utf8');

void test('server derives owner controls from the verified role guard', () => {
    assert.ok(
        routes.includes(
            "'canManageCodeBridgeOwnerPlan' => app(PlatformOwnerAccess::class)->allows($user)",
        ),
    );
    assert.ok(access.includes("getAttribute('is_platform_owner')"));
    assert.ok(access.includes('hasVerifiedEmail()'));
    assert.ok(access.includes('passkeys()->exists()'));
});

void test('owner controls are conditional and point to the guarded route', () => {
    assert.match(
        dashboard,
        /canManageOwnerPlan=\{\s*canManageCodeBridgeOwnerPlan\s*\}/,
    );
    assert.ok(dashboard.includes('{canManageOwnerPlan && ('));
    assert.ok(dashboard.includes('href="/operator/codebridge/owner-plan"'));
    assert.ok(dashboard.includes('Owner plan controls'));
});

void test('plan display remains bound to the actual license value', () => {
    assert.ok(dashboard.includes('detail?.plan'));
    assert.ok(dashboard.includes('titleCase(detail.plan)'));
    assert.ok(!dashboard.includes("plan: 'owner'"));
});

void test('verified owner product authority is exposed only through the compact admin entry', () => {
    // The catalog is only queried inside the owner guard and is null for everyone else.
    const start = routes.indexOf('$ownerProducts = null;');
    const guard = routes.indexOf('if ($isPlatformOwner) {', start);
    const query = routes.indexOf('Product::query()', guard);
    const render = routes.indexOf("'ownerProducts' => $ownerProducts", query);
    assert.ok(start > 0 && guard > start && query > guard && render > query);
    assert.ok(
        routes.includes(
            '$isPlatformOwner = app(PlatformOwnerAccess::class)->allows($user);',
        ),
    );
    assert.ok(dashboard.includes('{ownerProducts !== null && ('));
    assert.ok(dashboard.includes('Super Admin Control Center'));
    assert.ok(dashboard.includes('href="/operator"'));
    assert.ok(dashboard.includes('href="/operator/kslp"'));
    assert.ok(dashboard.includes('{ownerProducts === null && ('));
    assert.ok(!dashboard.includes('href="/operator#product-manager"'));
});
