<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use DomainException;

/**
 * Verifies continued possession of the activation-bound Ed25519 device key
 * before Main Platform renews an OmniDesk lease.
 *
 * This class is mutation-free and stores no signing material. The server
 * challenge must be generated/consumed by the authenticated renewal adapter.
 */
final class OmniDeskRenewalProof
{
    private const DOMAIN = 'KMJ-OMNIDESK-RENEW-v1';

    /**
     * @param array{
     *   activation_id:string,
     *   current_jti:string,
     *   current_sequence:int,
     *   server_challenge:string,
     *   client_nonce:string,
     *   client_version:string,
     *   proof_scheme:string,
     *   device_signature:string
     * } $request
     */
    public function verify(array $request, string $devicePublicKey): void
    {
        if (($request['proof_scheme'] ?? null) !== self::DOMAIN
            || ($request['current_sequence'] ?? 0) < 1) {
            throw new DomainException('OMNIDESK_RENEWAL_PROOF_INVALID');
        }

        $publicKey = $this->decodeBase64Url($devicePublicKey);
        $signature = $this->decodeBase64Url($request['device_signature'] ?? '');

        if (strlen($publicKey) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES
            || strlen($signature) !== SODIUM_CRYPTO_SIGN_BYTES) {
            throw new DomainException('OMNIDESK_RENEWAL_PROOF_INVALID');
        }

        if (! sodium_crypto_sign_verify_detached(
            $signature,
            $this->canonicalMessage($request),
            $publicKey,
        )) {
            throw new DomainException('OMNIDESK_RENEWAL_PROOF_INVALID');
        }
    }

    /**
     * @param array{
     *   activation_id:string,
     *   current_jti:string,
     *   current_sequence:int,
     *   server_challenge:string,
     *   client_nonce:string,
     *   client_version:string
     * } $request
     */
    public function canonicalMessage(array $request): string
    {
        $sequence = (string) ($request['current_sequence'] ?? 0);
        $output = self::DOMAIN;

        foreach ([
            $request['activation_id'] ?? '',
            $request['current_jti'] ?? '',
            $sequence,
            $request['server_challenge'] ?? '',
            $request['client_nonce'] ?? '',
            $request['client_version'] ?? '',
        ] as $value) {
            if ($value === '' || strlen($value) > 4096) {
                throw new DomainException('OMNIDESK_RENEWAL_PROOF_INVALID');
            }

            $output .= pack('N', strlen($value)).$value;
        }

        return $output;
    }

    private function decodeBase64Url(string $value): string
    {
        if ($value === '' || preg_match('/\A[A-Za-z0-9_-]+\z/', $value) !== 1) {
            throw new DomainException('OMNIDESK_RENEWAL_PROOF_INVALID');
        }

        $padding = (4 - strlen($value) % 4) % 4;
        $decoded = base64_decode(strtr($value, '-_', '+/').str_repeat('=', $padding), true);
        if ($decoded === false) {
            throw new DomainException('OMNIDESK_RENEWAL_PROOF_INVALID');
        }

        return $decoded;
    }
}
