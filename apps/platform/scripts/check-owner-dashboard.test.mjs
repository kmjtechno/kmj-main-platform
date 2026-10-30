import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const routes = readFileSync('routes/web.php', 'utf8');
const dashboard = readFileSync('resources/js/pages/dashboard.tsx', 'utf8');
const access = readFileSync('app/Services/PlatformOwnerAccess.php', 'utf8');

void test('server derives owner controls from the verified role guard', () => {
    // Owners are redirected to the guarded Super Admin route; the customer
    // dashboard never grants owner-plan controls.
    assert.ok(
        routes.includes(
            'if (app(PlatformOwnerAccess::class)->allows($user)) {',
        ),
    );
    assert.ok(
        routes.includes("return redirect()->route('super-admin.index');"),
    );
    assert.ok(routes.includes("'canManageCodeBridgeOwnerPlan' => false,"));
    assert.ok(
        readFileSync('routes/codebridge-admin.php', 'utf8').includes(
            "Route::get('owner-plan', function (Request $request, PlatformOwnerAccess $access",
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
    // The customer dashboard never queries the catalog for owners: they are
    // redirected first and ownerProducts is always null on this response.
    const redirect = routes.indexOf(
        "return redirect()->route('super-admin.index');",
    );
    const nulled = routes.indexOf('$ownerProducts = null;', redirect);
    const render = routes.indexOf("'ownerProducts' => $ownerProducts", nulled);
    assert.ok(redirect > 0 && nulled > redirect && render > nulled);
    assert.ok(
        routes.includes(
            'if (app(PlatformOwnerAccess::class)->allows($user)) {',
        ),
    );
    assert.ok(dashboard.includes('{ownerProducts !== null && ('));
    assert.ok(dashboard.includes('Super Admin Control Center'));
    assert.ok(dashboard.includes('href="/operator"'));
    assert.ok(dashboard.includes('href="/operator/kslp"'));
    assert.ok(dashboard.includes('{ownerProducts === null && ('));
    assert.ok(!dashboard.includes('href="/operator#product-manager"'));
});
