<?php

declare(strict_types=1);

namespace App\Services\CodeBridge;

use App\Services\Licensing\Kslp\KslpCodec;
use DomainException;
use Illuminate\Support\Str;
use JsonException;

/**
 * Source-only KSLP paid-seat proof contract. The expected assignment must come
 * from current authoritative commercial records, not from the token or client.
 * This verifier neither issues seats nor activates checkout or hosted metering.
 */
final class HostedSeatProofVerifier
{
    /**
     * @param  array{organization_id: string, membership_id: string, user_id: string, license_id: string, seat_id: string, assignment_revision: int}  $expected
     */
    public function verifyTrusted(string $token, array $expected, string $pinnedKid, string $pinnedPublicKeyBase64, int $now): bool
    {
        if (strlen($token) > 4096 || $now < 0 || preg_match('/\A[A-Za-z0-9_-]{1,128}\z/D', $pinnedKid) !== 1
            || strlen($pinnedPublicKeyBase64) !== 44) {
            return false;
        }
        $key = base64_decode($pinnedPublicKeyBase64, true);
        if (! is_string($key) || strlen($key) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES
            || base64_encode($key) !== $pinnedPublicKeyBase64) {
            return false;
        }

        try {
            [$header, $claims, $signature, $signed] = KslpCodec::decode($token);
            if (count($header) !== 3 || ($header['kid'] ?? null) !== $pinnedKid
                || strlen($signature) !== SODIUM_CRYPTO_SIGN_BYTES
                || ! sodium_crypto_sign_verify_detached($signature, $signed, $key)
                || ! KslpCodec::isCanonicalSignedPayload($signed, $header, $claims)) {
                return false;
            }

            if (count($claims) !== 13 || ($claims['protocol_version'] ?? null) !== 'KSLP-seat-v1'
                || ($claims['aud'] ?? null) !== 'kmj-codebridge-hosted-seat'
                || ($claims['product'] ?? null) !== 'KMJ_CODEBRIDGE'
                || ($claims['plan'] ?? null) !== 'team') {
                return false;
            }
            foreach (['organization_id', 'membership_id', 'license_id', 'seat_id'] as $field) {
                if (! is_string($claims[$field] ?? null) || ! Str::isUuid($claims[$field])
                    || $claims[$field] !== $expected[$field]) {
                    return false;
                }
            }
            if (! is_string($claims['user_id'] ?? null) || preg_match('/\A[1-9][0-9]{0,18}\z/D', $claims['user_id']) !== 1
                || $claims['user_id'] !== $expected['user_id']
                || ! is_int($claims['assignment_revision'] ?? null) || $claims['assignment_revision'] < 1
                || $claims['assignment_revision'] !== $expected['assignment_revision']) {
                return false;
            }

            $issued = $claims['iat'] ?? null;
            $notBefore = $claims['nbf'] ?? null;
            $expires = $claims['exp'] ?? null;

            return is_int($issued) && is_int($notBefore) && is_int($expires)
                && $issued >= 0 && $notBefore >= $issued && $notBefore <= $now
                && $issued <= $now && $expires > $now && $expires - $issued <= 300;
        } catch (DomainException|JsonException) {
            return false;
        }
    }
}
