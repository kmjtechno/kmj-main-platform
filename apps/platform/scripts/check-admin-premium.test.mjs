import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const root = new URL('../', import.meta.url);
const read = (path) => readFileSync(new URL(path, root), 'utf8');

const nav = read('resources/js/components/operator-module-navigation.tsx');
const overview = read('resources/js/components/operator-control-overview.tsx');
const dashboard = read('resources/js/pages/dashboard.tsx');
const sidebar = read('resources/js/components/app-sidebar.tsx');
const operator = read('resources/js/pages/operator.tsx');
const payments = read('resources/js/pages/operator-payments.tsx');
const license = read('resources/js/pages/operator-kslp.tsx');
const ops = read('resources/js/pages/operator-ops.tsx');
const codebridge = read('resources/js/pages/operator-codebridge-owner.tsx');
const styles = read('resources/css/admin-premium.css');
const baseStyles = read('resources/css/app.css');
const routes = read('routes/web.php');

void test('admin visuals remain scoped to authenticated owner workspace', () => {
    assert.match(baseStyles, /admin-premium\.css/);
    assert.match(styles, /\.dark \.kmj-admin-shell/);
    assert.match(styles, /\.kmj-premium-dashboard/);
    assert.match(operator, /kmj-admin-shell/);
    assert.match(payments, /kmj-admin-shell/);
    assert.match(license, /kmj-admin-shell/);
    assert.match(ops, /kmj-admin-shell/);
    assert.match(codebridge, /kmj-admin-shell/);
    assert.match(dashboard, /kmj-premium-dashboard/);
    assert.match(sidebar, /kmj-premium-sidebar/);
});

void test('every admin section is a real owner route, not an inert card', () => {
    for (const url of [
        '/operator', '/operator/products', '/operator#commercial-orders',
        '/operator/directory', '/operator/payments', '/operator/kslp',
        '/operator/codebridge/owner-plan', '/operator/ops', '/settings/security',
    ]) {
        assert.ok(nav.includes(`href: '${url}'`), `Missing real navigation: ${url}`);
    }
    assert.match(nav, /aria-label="Super Admin modules"/);
    assert.match(nav, /aria-current=/);
    assert.match(nav, /aria-label="Find an admin module"/);
    assert.match(nav, /No matching module/);
    assert.match(nav, /overflow-x-auto/);
});

void test('design accents have semantic variety and reduced-motion accessibility', () => {
    for (const token of ['text-violet-', 'text-sky-', 'text-amber-', 'text-emerald-', 'text-rose-', 'text-cyan-']) {
        assert.ok(overview.includes(token), `Missing semantic accent: ${token}`);
    }
    assert.match(styles, /prefers-reduced-motion/);
    assert.match(styles, /focus-visible/);
    assert.match(styles, /kmj-admin-module-card/);
});

void test('owner dashboard entry remains authority-gated and leaves customer services separate', () => {
    assert.match(dashboard, /\{ownerProducts !== null && \(/);
    assert.match(dashboard, /\{ownerProducts === null && \(/);
    assert.match(dashboard, /Super Admin Control Center/);
    assert.match(dashboard, /href="\/operator"/);
    assert.match(dashboard, /href="\/operator\/kslp"/);
    assert.ok(dashboard.indexOf('<OwnerProductsPanel') < dashboard.indexOf('Your authorized services'));
    assert.match(routes, /\$isPlatformOwner = app\(PlatformOwnerAccess::class\)->allows\(\$user\)/);
});

void test('payment and license security flows survive the visual redesign', () => {
    assert.match(operator, /ManualPaymentConfirmation/);
    assert.match(operator, /id="commercial-orders"/);
    assert.match(operator, /order\.fulfillment_state ===/);
    assert.match(payments, /live_charging_enabled/);
    assert.match(license, /Confirm/);
    assert.match(codebridge, /UPGRADE_CODEBRIDGE_OWNER/);
    assert.doesNotMatch(styles, /display:\s*none\s*!important/);
});
