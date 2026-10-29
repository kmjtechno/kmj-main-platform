import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const operator = readFileSync('resources/js/pages/operator.tsx', 'utf8');
const dashboard = readFileSync('resources/js/pages/dashboard.tsx', 'utf8');
const modules = readFileSync(
    'resources/js/components/operator-control-overview.tsx',
    'utf8',
);
const ownerRules = readFileSync('routes/web.php', 'utf8');

void test('owner command center uses separated, real admin module routes', () => {
    assert.ok(operator.includes('<OperatorControlOverview'));
    for (const target of [
        '/operator/products',
        '/operator/directory',
        '/operator/kslp',
        '/operator/payments',
        '/operator/codebridge/owner-plan',
        '/operator/ops',
    ]) {
        assert.ok(modules.includes(`href: '${target}'`), target);
    }
    assert.ok(!operator.includes('visibleProducts.map('));
    assert.ok(!operator.includes('Product & licensing matrix'));
});

void test('operator and super-admin route views remain distinct', () => {
    assert.match(
        ownerRules,
        /'ownerView' => \$request->routeIs\('super-admin\.index'\) \? 'dashboard' : 'command-center'/,
    );
    assert.match(
        ownerRules,
        /Route::get\('operator', \$ownerCommandDashboard\)/,
    );
    assert.match(
        ownerRules,
        /Route::get\('super-admin', \$ownerCommandDashboard\)/,
    );
    assert.match(operator, /ownerView: 'dashboard' \| 'command-center'/);
    assert.match(operator, /ownerView === 'dashboard' \? \(/);
    assert.match(operator, /aria-label="Owner task-first Command Center"/);
    assert.match(operator, /Back to Enterprise Dashboard/);
    assert.match(operator, /<OperatorCommandOs/);
    assert.match(operator, /<OperatorControlOverview/);
    assert.match(operator, /id="commercial-orders"/);
});

void test('catalog readiness is informative, never a payment or license grant', () => {
    assert.ok(modules.includes('product.active_policy_count === 0'));
    assert.ok(modules.includes('product.is_public'));
    assert.ok(modules.includes('product.licensing_enabled'));
    assert.ok(modules.includes('Visibility does not imply a sale or license'));
    assert.ok(modules.includes('Customer entitlements are granted separately'));
    assert.ok(modules.includes('orders.filter('));
    assert.ok(modules.includes("order.status === 'requested'"));
    assert.ok(modules.includes("order.fulfillment_state === 'ready'"));
    assert.ok(!modules.includes('router.post('));
});

void test('owner-only entry is above customer services, never public listing', () => {
    const panel = dashboard.indexOf('<OwnerProductsPanel');
    const services = dashboard.indexOf('Your authorized services');
    assert.ok(panel > 0 && services > panel);
    assert.ok(dashboard.includes('{ownerProducts !== null && ('));
    assert.ok(dashboard.includes('href="/operator"'));
    assert.ok(dashboard.includes('{ownerProducts === null && ('));
    const dashboardRoute = ownerRules.indexOf("Route::get('dashboard', function (");
    const ownerGuard = ownerRules.indexOf(
        'if (app(PlatformOwnerAccess::class)->allows($user)) {',
        dashboardRoute,
    );
    const redirected = ownerRules.indexOf(
        "return redirect()->route('super-admin.index');",
        ownerGuard,
    );
    const customerOnly = ownerRules.indexOf(
        '$ownerProducts = null;',
        redirected,
    );
    const exposed = ownerRules.indexOf(
        "'ownerProducts' => $ownerProducts",
        customerOnly,
    );
    assert.ok(
        dashboardRoute > 0 &&
            ownerGuard > dashboardRoute &&
            redirected > ownerGuard &&
            customerOnly > redirected &&
            exposed > customerOnly,
    );
});

void test('overview retains governed order confirmation and explicit fulfillment', () => {
    assert.ok(operator.includes('ManualPaymentConfirmation'));
    assert.ok(operator.includes('order.fulfillment_state ==='));
    assert.ok(operator.includes('href="/operator/products"'));
    assert.ok(operator.includes('id="commercial-orders"'));
    assert.ok(modules.includes('Requires owner review'));
});
