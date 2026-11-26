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
    // The sandbox order is never claimed done from the UI.
    assert.match(step, /id: 'sandbox-order'[\s\S]*?done: false/);
});

void test('guidance never offers to enable live charging or asks for secrets in chat', () => {
    assert.doesNotMatch(step, /live_charging_enabled\s*[:=]\s*true/);
    assert.match(step, /Nothing on this page can switch it on/);
    assert.match(step, /Never share keys in chat/);
    assert.match(step, /role="progressbar"/);
});
