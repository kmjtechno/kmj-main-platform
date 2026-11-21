<?php

namespace App\Services\Licensing\Kslp;

use DomainException;

/**
 * Strict KSLP-v1 verifier for the CloudOS signing audience.
 *
 * This is a compatibility hardening of the existing Ed25519 envelope, NOT a
 * replacement protocol, an issuer, or an offline revocation service.
 * Replay/clock checkpoint policy is enforced by KslpOfflineLeaseGuard.
 */
final class KslpVerifier
{
    private const MAX_TOKEN_BYTES = 16384;

    private const MAX_KID_BYTES = 128;

    /** @var list<string> */
    private const V1_CLAIMS = [
        'protocol_version', 'license_id', 'customer_id', 'product', 'plan',
        'server_identity', 'activation_id', 'features', 'limits',
        'iat', 'nbf', 'exp', 'sequence', 'nonce', 'kid', 'jti', 'aud',
        'grace_until',
    ];

    /**
     * @param  callable(string): (?string)  $publicKeyForKid Trusted signing-purpose key lookup.
     * @return array<array-key, mixed>
     */
    public function verify(string $token, callable $publicKeyForKid, string $serverIdentity, int $now, string $expectedProduct = 'KMJ_CLOUDOS'): array
    {
        if ($token === '' || strlen($token) > self::MAX_TOKEN_BYTES) {
            throw new DomainException('KSLP_MALFORMED');
        }

        [$header, $claims, $signature, $signed] = KslpCodec::decode($token);

        if (array_diff(array_keys($header), ['alg', 'kid', 'typ']) !== []
            || ! is_string($header['kid'] ?? null)
            || $header['kid'] === ''
            || strlen($header['kid']) > self::MAX_KID_BYTES
            || strlen($signature) !== SODIUM_CRYPTO_SIGN_BYTES) {
            throw new DomainException('KSLP_MALFORMED');
        }

        // Look up ONLY a preconfigured license-purpose public key; the JWT
        // payload is not allowed to supply or select an arbitrary public key.
        $publicKey = $publicKeyForKid($header['kid']);
        if (! is_string($publicKey) || strlen($publicKey) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES) {
            throw new DomainException('KSLP_UNKNOWN_KID');
        }
        if (! sodium_crypto_sign_verify_detached($signature, $signed, $publicKey)) {
            throw new DomainException('KSLP_INVALID_SIGNATURE');
        }
        if (! KslpCodec::isCanonicalSignedPayload($signed, $header, $claims)) {
            throw new DomainException('KSLP_MALFORMED');
        }

        // Interpret NO untrusted entitlement claims until signature verifies.
        foreach (self::V1_CLAIMS as $field) {
            if ($field !== 'grace_until' && ! array_key_exists($field, $claims)) {
                throw new DomainException('KSLP_MALFORMED');
            }
        }
        if (array_diff(array_keys($claims), self::V1_CLAIMS) !== []) {
            throw new DomainException('KSLP_MALFORMED');
        }

        foreach (['license_id', 'customer_id', 'product', 'plan', 'server_identity', 'activation_id', 'nonce', 'kid', 'jti', 'aud'] as $field) {
            if (! is_string($claims[$field] ?? null) || $claims[$field] === '') {
                throw new DomainException('KSLP_MALFORMED');
            }
        }
        foreach (['iat', 'nbf', 'exp', 'sequence'] as $field) {
            if (! is_int($claims[$field] ?? null)) {
                throw new DomainException('KSLP_MALFORMED');
            }
        }
        if (! is_array($claims['features'] ?? null)
            || ! is_array($claims['limits'] ?? null)
            || (array_key_exists('grace_until', $claims)
                && $claims['grace_until'] !== null
                && ! is_int($claims['grace_until']))) {
            throw new DomainException('KSLP_MALFORMED');
        }

        if ($claims['protocol_version'] !== 'KSLP-v1') {
            throw new DomainException('KSLP_UNSUPPORTED_VERSION');
        }
        if (! hash_equals($header['kid'], $claims['kid'])) {
            throw new DomainException('KSLP_MALFORMED');
        }
        if ($claims['iat'] <= 0
            || $claims['nbf'] > $claims['iat']
            || $claims['sequence'] < 1) {
            throw new DomainException('KSLP_MALFORMED');
        }
        if ($claims['product'] !== $expectedProduct) {
            throw new DomainException('KSLP_WRONG_PRODUCT');
        }
        if ($claims['aud'] !== 'kmj-cloudos') {
            throw new DomainException('KSLP_WRONG_AUDIENCE');
        }
        if (! hash_equals($serverIdentity, $claims['server_identity'])) {
            throw new DomainException('KSLP_SERVER_MISMATCH');
        }
        if ($now < $claims['nbf']) {
            throw new DomainException('KSLP_NOT_YET_VALID');
        }
        if ($claims['exp'] <= $claims['iat'] || $now > $claims['exp']) {
            throw new DomainException('KSLP_EXPIRED');
        }

        return $claims;
    }
}
