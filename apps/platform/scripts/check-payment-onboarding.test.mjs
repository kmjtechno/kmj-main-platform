import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');

test('both payment providers have explicit, opt-in dashboard onboarding', () => {
    const guide = read('../resources/js/components/payment-gateway-onboarding.tsx');
    assert.match(guide, /https:\/\/dashboard\.razorpay\.com\/app\/account-settings/);
    assert.match(guide, /https:\/\/merchant\.cashfree\.com\/merchant\/pg#api-key/);
    assert.match(guide, /selected\?\.storage_ready/);
    assert.match(guide, /gateway-settings-\$\{provider\}/);
    assert.match(guide, /target="_blank"/);
    assert.match(guide, /rel="noopener noreferrer"/);
});

test('gateway setup is explicitly sandbox-only and does not publish an invented webhook', () => {
    const guide = read('../resources/js/components/payment-gateway-onboarding.tsx');
    const server = read('../app/Services/Payments/PaymentGatewayReadiness.php');
    const routes = read('../routes/payments-console.php');
    assert.match(guide, /live checkout locked/i);
    assert.match(guide, /does NOT mean a webhook endpoint/i);
    assert.match(guide, /Do not configure a public webhook URL/i);
    assert.match(server, /'live_charging_enabled' => false/);
    assert.match(routes, /'environment' => \['required', 'in:sandbox'\]/);
    assert.doesNotMatch(routes, /Route::post\('payments\/webhooks\//);
});

test('keys remain encrypted and owner access and validation stay mandatory', () => {
    const view = read('../resources/js/components/operator-payment-settings.tsx');
    const routes = read('../routes/payments-console.php');
    const vault = read('../app/Services/Payments/OwnerPaymentGatewaySettings.php');
    assert.match(view, /useForm\(/);
    assert.match(view, /type=\{/);
    assert.match(routes, /PlatformOwnerAccess/);
    assert.match(routes, /'password.confirm'/);
    assert.match(routes, /in:sandbox/);
    assert.match(vault, /Crypt::encryptString/);
    assert.match(vault, /Razorpay test keys only/);
});

test('owner sandbox connection is explicit, rate limited and never charges money', () => {
    const probe = read('../app/Services/Payments/PaymentGatewaySandboxProbe.php');
    const page = read('../resources/js/components/payment-gateway-onboarding.tsx');
    const routes = read('../routes/payments-console.php');
    assert.match(routes, /test-connection/);
    assert.match(routes, /middleware\('throttle:3,10'\)/);
    assert.match(routes, /PlatformOwnerAccess/);
    assert.match(page, /Test Connection/);
    assert.match(page, /!keysSaved/);
    assert.match(page, /test_phone/);
    assert.match(probe, /sandboxCredentials\(/);
    assert.match(probe, /RazorpaySandboxOrderClient/);
    assert.match(probe, /CashfreeSandboxOrderClient/);
    assert.match(probe, /'INR'/);
    assert.match(probe, /'charged' => false/);
    assert.match(probe, /'entitlement_issued' => false/);
    assert.doesNotMatch(probe, /rzp_live_/);
});

test('one active merchant drives both guided steps and encrypted credential entry', () => {
    const page = read('../resources/js/pages/operator-payments.tsx');
    const wizard = read('../resources/js/components/payment-gateway-onboarding.tsx');
    const vault = read('../resources/js/components/operator-payment-settings.tsx');
    assert.match(page, /onProviderChange=\{setSelectedProvider\}/);
    assert.match(page, /selectedProvider=\{selectedProvider\}/);
    assert.match(wizard, /onProviderChange\(id\)/);
    assert.match(vault, /gatewaySettings\.find\(/);
    assert.doesNotMatch(vault, /gatewaySettings\.map\(/);
    assert.match(page, /Other payment options \(planned, not integrated\)/);
    assert.match(page, /gateway\.id === 'razorpay' \|\| gateway\.id === 'cashfree'/);
    assert.match(page, /gateway\.id !== 'razorpay' && gateway\.id !== 'cashfree'/);
});
