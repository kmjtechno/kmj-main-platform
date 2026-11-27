import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) =>
    readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const step = read('resources/js/components/payment-next-step.tsx');
const page = read('resources/js/pages/operator-payments.tsx');

void test('payments page shows the guided next step and a webhook anchor', () => {
    assert.match(page, /<PaymentNextStep/);
    assert.match(page, /id="webhook-setup"/);
});

void test('guided progress only turns green from real stored or proven state', () => {
    assert.match(
        step,
        /setting\?\.merchant_status === 'owner_reports_approved'/,
    );
    assert.match(step, /setting\?\.webhook_secret_stored === true/);
    assert.match(step, /readiness\?\.webhook_verification_configured === true/);
    // The sandbox order turns green only from the server-recorded provider acceptance.
    assert.match(
        step,
        /id: 'sandbox-order'[\s\S]*?done: Boolean\(readiness\?\.sandbox_order_probe_at\)/,
    );
    assert.doesNotMatch(step, /id: 'sandbox-order'[\s\S]*?done: true/);
});

void test('guidance never offers to enable live charging or asks for secrets in chat', () => {
    assert.doesNotMatch(step, /live_charging_enabled\s*[:=]\s*true/);
    assert.match(step, /Nothing on this page can switch it on/);
    assert.match(step, /Never share keys in chat/);
    assert.match(step, /role="progressbar"/);
});

void test('recent webhook events are shown without implying settlement', () => {
    assert.match(step, /Recent webhook events/);
    assert.match(step, /Received \(not settled\)/);
    assert.match(step, /does not settle an\s+order or issue a license/);
});

void test('Cashfree step 3 follows the client secret, not a separate webhook secret', () => {
    assert.match(step, /provider === 'cashfree'\s*\?\s*keysSaved/);
    const guide = read(
        'resources/js/components/payment-gateway-onboarding.tsx',
    );
    assert.match(guide, /provider === 'cashfree'\s*\?\s*keysSaved/);
});
