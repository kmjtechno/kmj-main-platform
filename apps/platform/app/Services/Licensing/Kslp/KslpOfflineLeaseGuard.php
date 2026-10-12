<?php

declare(strict_types=1);

namespace App\Services\Licensing\Kslp;

use DomainException;

/**
 * Fail-closed checks for a cached KSLP-v1 CloudOS lease.
 *
 * The KSLP verifier remains responsible for Ed25519 signatures and wire
 * compatibility. This guard adds exact activation/license binding, capped
 * offline lifetime, revocation evidence and trusted-time rollback checks.
 *
 * Callers MUST preserve lastTrustedUnixTime and minimumSequence in an
 * OS-protected store and refresh them via authenticated online reconciliation.
 * This class never issues licenses, fetches keys, or persists state.
 */
final class KslpOfflineLeaseGuard
{
    public const MAX_OFFLINE_SECONDS = 86400;

    private const MAX_TOKEN_BYTES = 16384;

    private const CLOCK_SKEW_SECONDS = 5;

    /** @var list<string> */
    private const V1_CLAIMS = [
        'protocol_version',
        'license_id',
        'customer_id',
        'product',
        'plan',
        'server_identity',
        'activation_id',
        'features',
        'limits',
        'iat',
        'nbf',
        'exp',
        'sequence',
        'nonce',
        'kid',
        'jti',
        'aud',
        'grace_until',
    ];

    /**
     * @param  callable(string): (?string)  $publicKeyForKid  Trusted license-purpose key lookup, never a token-provided key.
     * @return array<array-key, mixed>
     */
    public function verify(
        string $token,
        callable $publicKeyForKid,
        string $serverIdentity,
        string $activationId,
        string $licenseId,
        int $now,
        int $lastTrustedUnixTime,
        int $minimumSequence,
        bool $knownRevoked = false,
    ): array {
        if ($knownRevoked) {
            throw new DomainException('KSLP_REVOKED');
        }
        if ($now <= 0 || $lastTrustedUnixTime <= 0 || $minimumSequence < 1) {
            throw new DomainException('KSLP_MALFORMED');
        }
        if ($now < $lastTrustedUnixTime - self::CLOCK_SKEW_SECONDS) {
            throw new DomainException('KSLP_CLOCK_ROLLBACK');
        }
        if ($token === '' || strlen($token) > self::MAX_TOKEN_BYTES) {
            throw new DomainException('KSLP_MALFORMED');
        }

        // Existing KSLP-v1 checks Ed25519, kid, audience, signature, product,
        // server identity and signed time range before claims are consumed.
        $claims = (new KslpVerifier)->verify(
            $token,
            $publicKeyForKid,
            $serverIdentity,
            $now,
            'KMJ_CLOUDOS',
        );

        // KSLP-v1 must not silently reinterpret extensions: future wire
        // claims require an explicitly versioned profile and interop vectors.
        if (array_diff(array_keys($claims), self::V1_CLAIMS) !== []) {
            throw new DomainException('KSLP_MALFORMED');
        }

        foreach (['iat', 'nbf', 'exp', 'sequence'] as $name) {
            if (! isset($claims[$name]) || ! is_int($claims[$name])) {
                throw new DomainException('KSLP_MALFORMED');
            }
        }
        foreach (['activation_id' => $activationId, 'license_id' => $licenseId] as $name => $expected) {
            if ($expected === '' || ! is_string($claims[$name] ?? null) || ! hash_equals($expected, $claims[$name])) {
                throw new DomainException('KSLP_ACTIVATION_CONFLICT');
            }
        }
        if (! is_string($claims['customer_id'] ?? null)
            || $claims['customer_id'] === ''
            || ! is_array($claims['features'] ?? null)
            || ! is_array($claims['limits'] ?? null)
            || ! is_string($claims['jti'] ?? null)
            || $claims['jti'] === ''
            || ! is_string($claims['nonce'] ?? null)
            || $claims['nonce'] === '') {
            throw new DomainException('KSLP_MALFORMED');
        }
        if ($claims['sequence'] < $minimumSequence) {
            throw new DomainException('KSLP_REPLAY');
        }
        if ($claims['iat'] > $now + self::CLOCK_SKEW_SECONDS
            || $claims['nbf'] > $claims['iat']
            || $claims['exp'] <= $claims['iat']
            || $claims['exp'] - $claims['iat'] > self::MAX_OFFLINE_SECONDS) {
            throw new DomainException('KSLP_EXPIRED');
        }
        // Current v1 leases include the commercial grace ceiling. Never
        // extend a valid signed lease beyond that ceiling if supplied.
        $graceUntil = $claims['grace_until'] ?? null;
        if ($graceUntil !== null && (! is_int($graceUntil) || $claims['exp'] > $graceUntil)) {
            throw new DomainException('KSLP_EXPIRED');
        }

        return $claims;
    }
}
