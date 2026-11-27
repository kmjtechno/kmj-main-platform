import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
    featureLabel,
    isUsableLicenseState,
    licenseStateLabel,
    planLabel,
    productLabel,
} from '../resources/js/lib/customer-labels.ts';

const read = (path) =>
    readFileSync(new URL('../' + path, import.meta.url), 'utf8');

void test('stored codes are shown in plain words', () => {
    assert.equal(productLabel('KMJ_CLOUDOS'), 'KMJ CloudOS');
    assert.equal(productLabel('KMJ_NEW_PRODUCT'), 'KMJ New Product');
    assert.equal(planLabel('custom_oem'), 'Custom / OEM');
    assert.equal(planLabel('professional'), 'Professional');
    assert.equal(licenseStateLabel('GRACE'), 'Expired · grace period');
    assert.equal(licenseStateLabel('ANYTHING'), 'Unknown');
    assert.equal(
        featureLabel('codebridge.remote_access'),
        'CodeBridge Remote Access',
    );
    assert.equal(isUsableLicenseState('REVOKED'), false);
    assert.equal(isUsableLicenseState('NOT_STARTED'), false);
});

void test('customer pages avoid internal jargon in visible copy', () => {
    for (const path of [
        'resources/js/pages/licensing-hub.tsx',
        'resources/js/pages/purchase.tsx',
        'resources/js/components/customer/record-explainer.tsx',
    ]) {
        const source = read(path);
        // JSX text only: identifiers such as product_entitlements stay.
        const visible = source.match(/>[^<>{}]+</g)?.join(' ') ?? '';
        assert.doesNotMatch(visible, /KSLP|entitlement|device binding/i, path);
    }
});

void test('dashboard shows license records beside product access', () => {
    const dashboard = read('resources/js/pages/dashboard.tsx');
    assert.match(dashboard, /Your licenses/);
    assert.match(dashboard, /license-without-access/);
    assert.match(dashboard, /<RecordExplainer \/>/);
    assert.match(dashboard, /auto-fit,minmax/);
    assert.match(
        read('routes/web.php'),
        /\$licensing->licensesForUser\(\$user\)/,
    );
});
