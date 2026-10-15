/**
 * KMJ KSLP first-use registration for JavaScript / TypeScript.
 *
 * This is NOT a commercial license SDK or a lease verifier.
 * Pass a caller-managed, non-extractable Ed25519 signer. Never embed a
 * bootstrap license key or private device key in source or localStorage.
 * Device registration DOES NOT grant product entitlements.
 *
 * This module has no dependencies and does not persist client credentials.
 */
const ORIGIN = 'https://kmjtechno.com';
const MAX_BODY = 4096;
const PRODUCT = /^[A-Z0-9][A-Z0-9_.:-]{2,63}$/;
const BOOTSTRAP = /^KMJ1-[A-Za-z0-9_-]{43}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const BASE64URL = /^[A-Za-z0-9_-]{43}$/;
const PLATFORMS = new Set(['windows', 'linux', 'macos', 'android', 'ios', 'other']);

export class KslpFirstUseError extends Error {
    constructor(code) {
        super(code);
        this.name = 'KslpFirstUseError';
        this.code = code;
    }
}

function requireThat(condition, code) {
    if (!condition) throw new KslpFirstUseError(code);
}

function b64url(data) {
    requireThat(data instanceof Uint8Array, 'DEVICE_BYTES_REQUIRED');
    // Chunking avoids stack overflows for unexpectedly large data arrays.
    let binary = '';
    for (const byte of data) binary += String.fromCharCode(byte);
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function boundedResponse(response) {
    requireThat(response?.ok === true && response.status === 200, 'ACTIVATION_UNAVAILABLE_OR_DENIED');
    requireThat(response.headers?.get('content-type')?.toLowerCase().startsWith('application/json'), 'ACTIVATION_RESPONSE_INVALID');
    const reported = response.headers.get('content-length');
    if (reported !== null) {
        requireThat(/^\d+$/.test(reported) && Number(reported) <= MAX_BODY, 'ACTIVATION_RESPONSE_TOO_LARGE');
    }
    requireThat(response.body && typeof response.body.getReader === 'function', 'ACTIVATION_RESPONSE_INVALID');
    const reader = response.body.getReader();
    const chunks = [];
    let size = 0;
    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            requireThat(value instanceof Uint8Array, 'ACTIVATION_RESPONSE_INVALID');
            size += value.byteLength;
            requireThat(size <= MAX_BODY, 'ACTIVATION_RESPONSE_TOO_LARGE');
            chunks.push(value);
        }
    } finally {
        if (size > MAX_BODY) {
            try {
                await reader.cancel();
            } catch {
                // Keep the size-limit rejection as the public error.
            }
        }
        reader.releaseLock();
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
        bytes.set(chunk, offset);
        offset += chunk.byteLength;
    }
    let parsed;
    try {
        parsed = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
    } catch {
        throw new KslpFirstUseError('ACTIVATION_RESPONSE_INVALID');
    }
    requireThat(parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed), 'ACTIVATION_RESPONSE_INVALID');
    return parsed;
}

export async function postKslpFirstUse(url, payload) {
    const parsed = new URL(url);
    requireThat(parsed.origin === ORIGIN && /^\/api\/v1\/kslp\/developer\/activation\/(challenge|complete)$/.test(parsed.pathname) && parsed.search === '' && parsed.hash === '', 'KSLP_HTTPS_ORIGIN_REQUIRED');
    const raw = JSON.stringify(payload);
    requireThat(new TextEncoder().encode(raw).length <= MAX_BODY, 'REQUEST_TOO_LARGE');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
        const response = await fetch(parsed.toString(), {
            method: 'POST',
            headers: { 'content-type': 'application/json', accept: 'application/json' },
            body: raw,
            mode: 'cors',
            credentials: 'omit',
            cache: 'no-store',
            redirect: 'error',
            referrerPolicy: 'no-referrer',
            signal: controller.signal,
        });
        return await boundedResponse(response);
    } catch (error) {
        if (error instanceof KslpFirstUseError) throw error;
        throw new KslpFirstUseError('ACTIVATION_UNAVAILABLE_OR_DENIED');
    } finally {
        clearTimeout(timeout);
    }
}

/**
 * sign(message: Uint8Array): Promise<Uint8Array> | Uint8Array
 * Caller must own the matching stable Ed25519 private key in an OS keystore.
 * request is injectable only for deterministic offline tests.
 */
export async function registerKslpFirstUseDevice({
    licenseKey,
    productCode,
    devicePublicKey,
    machineHash,
    sign,
    metadataConsent = false,
    platform = null,
    appVersion = null,
    request = postKslpFirstUse,
}) {
    requireThat(typeof licenseKey === 'string' && BOOTSTRAP.test(licenseKey), 'LICENSE_KEY_FORMAT_INVALID');
    requireThat(typeof productCode === 'string' && PRODUCT.test(productCode), 'PRODUCT_INVALID');
    requireThat(devicePublicKey instanceof Uint8Array && devicePublicKey.length === 32, 'ED25519_PUBLIC_KEY_REQUIRED');
    requireThat(typeof machineHash === 'string' && SHA256.test(machineHash), 'MACHINE_HASH_INVALID');
    requireThat(typeof sign === 'function', 'ED25519_SIGNER_REQUIRED');
    requireThat(typeof metadataConsent === 'boolean', 'CONSENT_INVALID');
    requireThat(platform === null || PLATFORMS.has(platform), 'PLATFORM_INVALID');
    requireThat(appVersion === null || (typeof appVersion === 'string' && appVersion.length <= 64), 'APP_VERSION_INVALID');
    requireThat(typeof request === 'function', 'TRANSPORT_INVALID');

    const deviceIdentity = 'ed25519:' + b64url(devicePublicKey);
    const challenge = await request(ORIGIN + '/api/v1/kslp/developer/activation/challenge', {
        license_key: licenseKey,
        server_identity: deviceIdentity,
    });
    requireThat(challenge && UUID.test(challenge.license_id ?? '') && UUID.test(challenge.challenge_id ?? '')
        && typeof challenge.nonce === 'string' && BASE64URL.test(challenge.nonce)
        && challenge.product === productCode && challenge.expires_in === 300,
    'CHALLENGE_RESPONSE_INVALID');

    // Exact same signed string as KslpActivationProof::consume().
    const signedBytes = new TextEncoder().encode(
        'KSLP-ACTIVATE-v1|' + challenge.license_id + '|' + challenge.nonce,
    );
    const signature = await sign(signedBytes);
    requireThat(signature instanceof Uint8Array && signature.length === 64, 'ED25519_SIGNATURE_INVALID');
    const receipt = await request(ORIGIN + '/api/v1/kslp/developer/activation/complete', {
        license_key: licenseKey,
        server_identity: deviceIdentity,
        machine_hash: machineHash,
        request_id: crypto.randomUUID(),
        challenge_id: challenge.challenge_id,
        nonce: challenge.nonce,
        signature: b64url(signature),
        metadata_consent: metadataConsent,
        platform: metadataConsent ? platform : null,
        app_version: metadataConsent ? appVersion : null,
    });
    requireThat(receipt && receipt.product === productCode
        && UUID.test(receipt.activation_id ?? '')
        && receipt.device_registered === true
        && receipt.signed_lease_issued === false
        && receipt.status === 'activation_recorded_pending_signed_lease',
    'UNEXPECTED_ACTIVATION_STATE');

    return Object.freeze({
        activationId: receipt.activation_id,
        productCode,
        deviceRegistered: true,
        signedLeaseIssued: false,
        grantsEntitlement: false,
    });
}
