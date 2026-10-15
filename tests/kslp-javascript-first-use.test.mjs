import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
    KslpFirstUseError,
    postKslpFirstUse,
    registerKslpFirstUseDevice,
} from '../apps/platform/public/sdk/javascript/kmj_kslp_first_use.mjs';

const licenseKey = 'KMJ1-' + 'A'.repeat(43);
const productCode = 'KMJ.OMNIDESK';
const machineHash = 'a'.repeat(64);
const devicePublicKey = new Uint8Array(Array.from({ length: 32 }, (_, i) => i));
const license = '22222222-2222-4222-8222-222222222222';
const challengeId = '33333333-3333-4333-8333-333333333333';
const activationId = '44444444-4444-4444-8444-444444444444';
const nonce = 'A'.repeat(43);
const signed = new Uint8Array(64).fill(7);
const requestMock = (calls, overrides = {}) => async (url, body) => {
    calls.push({ url, body });
    if (url.endsWith('/challenge')) return {
        license_id: license, challenge_id: challengeId, nonce,
        expires_in: 300, product: overrides.product ?? productCode,
    };
    return {
        activation_id: activationId,
        product: overrides.product ?? productCode,
        device_registered: true,
        signed_lease_issued: overrides.signedLease ?? false,
        status: overrides.status ?? 'activation_recorded_pending_signed_lease',
    };
};

const options = (extra = {}) => ({
    licenseKey, productCode, machineHash, devicePublicKey,
    sign: async () => signed,
    ...extra,
});

test('exact challenge protocol, private key omitted and no entitlement granted', async () => {
    const calls = [];
    let signedMessage;
    const receipt = await registerKslpFirstUseDevice(options({
        request: requestMock(calls),
        sign: async (bytes) => {
            signedMessage = new TextDecoder().decode(bytes);
            return signed;
        },
    }));
    assert.equal(signedMessage, `KSLP-ACTIVATE-v1|${license}|${nonce}`);
    assert.equal(calls.length, 2);
    assert.equal(calls[0].url, 'https://kmjtechno.com/api/v1/kslp/developer/activation/challenge');
    assert.equal(calls[1].url, 'https://kmjtechno.com/api/v1/kslp/developer/activation/complete');
    assert.equal(calls[1].body.metadata_consent, false);
    assert.equal(calls[1].body.platform, null);
    assert.equal(calls[1].body.app_version, null);
    assert.match(calls[1].body.signature, /^[A-Za-z0-9_-]{86}$/);
    assert.match(calls[1].body.request_id, /^[0-9a-f-]{36}$/);
    assert.ok(!JSON.stringify(calls).includes('private_key'));
    assert.equal(receipt.activationId, activationId);
    assert.equal(receipt.deviceRegistered, true);
    assert.equal(receipt.signedLeaseIssued, false);
    assert.equal(receipt.grantsEntitlement, false);
    assert.equal(Object.isFrozen(receipt), true);
});

test('consent scopes optional metadata to explicit opt in', async () => {
    const calls = [];
    await registerKslpFirstUseDevice(options({
        metadataConsent: true, platform: 'windows', appVersion: '1.0',
        request: requestMock(calls),
    }));
    assert.equal(calls[1].body.platform, 'windows');
    assert.equal(calls[1].body.app_version, '1.0');
    assert.equal(calls[1].body.metadata_consent, true);
});

test('rejects substituted product, fake signed lease and suspicious receipt states', async () => {
    for (const [overrides, code] of [
        [{ product: 'ATTACKER.APP' }, 'CHALLENGE_RESPONSE_INVALID'],
        [{ signedLease: true }, 'UNEXPECTED_ACTIVATION_STATE'],
        [{ status: 'active' }, 'UNEXPECTED_ACTIVATION_STATE'],
    ]) {
        const calls = [];
        await assert.rejects(
            registerKslpFirstUseDevice(options({ request: requestMock(calls, overrides) })),
            (error) => error instanceof KslpFirstUseError && error.code === code,
        );
        if (code === 'CHALLENGE_RESPONSE_INVALID') assert.equal(calls.length, 1);
    }
});

test('reject invalid input before transport or signature work', async () => {
    const violations = [
        [{ licenseKey: 'bad' }, 'LICENSE_KEY_FORMAT_INVALID'],
        [{ productCode: 'UNAUTHORIZED APP' }, 'PRODUCT_INVALID'],
        [{ productCode: 'A'.repeat(65) }, 'PRODUCT_INVALID'],
        [{ devicePublicKey: new Uint8Array(31) }, 'ED25519_PUBLIC_KEY_REQUIRED'],
        [{ machineHash: 'not-a-hash' }, 'MACHINE_HASH_INVALID'],
        [{ metadataConsent: 'yes' }, 'CONSENT_INVALID'],
        [{ platform: 'unknown' }, 'PLATFORM_INVALID'],
        [{ appVersion: 'x'.repeat(65) }, 'APP_VERSION_INVALID'],
        [{ sign: null }, 'ED25519_SIGNER_REQUIRED'],
    ];
    for (const [modified, code] of violations) {
        let invoked = false;
        await assert.rejects(registerKslpFirstUseDevice(options({
            ...modified,
            request: async () => {
                invoked = true;
                throw Error('unexpected transport');
            },
        })), (error) => error.code === code);
        assert.equal(invoked, false);
    }
});

test('wrong signing length rejected without hitting completion endpoint', async () => {
    const calls = [];
    await assert.rejects(
        registerKslpFirstUseDevice(options({
            sign: () => new Uint8Array(63),
            request: requestMock(calls),
        })),
        (error) => error.code === 'ED25519_SIGNATURE_INVALID',
    );
    assert.equal(calls.length, 1);
});

test('transport refuses external origins, incorrect paths and cleartext', async () => {
    const wrong = [
        'http://kmjtechno.com/api/v1/kslp/developer/activation/challenge',
        'https://malicious.test/api/v1/kslp/developer/activation/challenge',
        'https://kmjtechno.com@malicious.test/api/v1/kslp/developer/activation/challenge',
        'https://kmjtechno.com/api/v1/kslp/developer/activation/challenge?key=leak',
        'https://kmjtechno.com/api/v1/kslp/developer/activation/anything',
    ];
    for (const url of wrong) {
        await assert.rejects(postKslpFirstUse(url, {}),
            (error) => error.code === 'KSLP_HTTPS_ORIGIN_REQUIRED');
    }
});

test('transport sends no cookies, no referrer, and forbids redirects', async (t) => {
    const original = globalThis.fetch;
    t.after(() => { globalThis.fetch = original; });
    let seen;
    globalThis.fetch = async (_url, init) => {
        seen = init;
        return new Response(JSON.stringify({ id: 'ok' }), {
            status: 200, headers: { 'content-type': 'application/json' },
        });
    };
    const value = await postKslpFirstUse(
        'https://kmjtechno.com/api/v1/kslp/developer/activation/challenge',
        { example: true },
    );
    assert.equal(value.id, 'ok');
    assert.equal(seen.credentials, 'omit');
    assert.equal(seen.cache, 'no-store');
    assert.equal(seen.redirect, 'error');
    assert.equal(seen.referrerPolicy, 'no-referrer');
    assert.equal(seen.method, 'POST');
});

test('oversized and non-JSON responses are rejected', async (t) => {
    const original = globalThis.fetch;
    t.after(() => { globalThis.fetch = original; });
    const url = 'https://kmjtechno.com/api/v1/kslp/developer/activation/challenge';
    globalThis.fetch = async () => new Response('x'.repeat(4100), {
        status: 200, headers: { 'content-type': 'application/json' },
    });
    await assert.rejects(postKslpFirstUse(url, {}),
        (error) => error.code === 'ACTIVATION_RESPONSE_TOO_LARGE');
    globalThis.fetch = async () => new Response('javascript', {
        status: 200, headers: { 'content-type': 'text/javascript' },
    });
    await assert.rejects(postKslpFirstUse(url, {}),
        (error) => error.code === 'ACTIVATION_RESPONSE_INVALID');
});
