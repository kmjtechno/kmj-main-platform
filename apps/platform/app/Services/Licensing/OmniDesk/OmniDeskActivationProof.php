<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use DomainException;

/**
 * Verifies possession of the Ed25519 device key before an OmniDesk activation
 * can bind a commercial entitlement to that device.
 *
 * This service performs no entitlement mutation and holds no private signing
 * material. It verifies only the client/device proof defined by
 * KMJ-OMNIDESK-ACTIVATE-v1.
 */
final class OmniDeskActivationProof
{
    private const DOMAIN = 'KMJ-OMNIDESK-ACTIVATE-v1';

    /**
     * @param array{
     *   license_or_entitlement_reference:string,
     *   device_public_key:string,
     *   device_public_key_fingerprint:string,
     *   installation_id:string,
     *   client_version:string,
     *   protocol_version:string,
     *   platform:string,
     *   architecture:string,
     *   client_nonce:string,
     *   proof_scheme:string,
     *   device_signature:string
     * } $request
     */
    public function verify(array $request, string $idempotencyKey): void
    {
        if ($request['proof_scheme'] !== self::DOMAIN) {
            throw new DomainException('OMNIDESK_ACTIVATION_PROOF_INVALID');
        }

        $publicKey = $this->decodeBase64Url($request['device_public_key']);
        $signature = $this->decodeBase64Url($request['device_signature']);
        if (strlen($publicKey) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES
            || strlen($signature) !== SODIUM_CRYPTO_SIGN_BYTES) {
            throw new DomainException('OMNIDESK_ACTIVATION_PROOF_INVALID');
        }

        $fingerprint = 'sha256:'.hash('sha256', $publicKey);
        if (! hash_equals($fingerprint, $request['device_public_key_fingerprint'])) {
            throw new DomainException('OMNIDESK_ACTIVATION_PROOF_INVALID');
        }

        $message = $this->canonicalMessage($request, $idempotencyKey);
        if (! sodium_crypto_sign_verify_detached($signature, $message, $publicKey)) {
            throw new DomainException('OMNIDESK_ACTIVATION_PROOF_INVALID');
        }
    }

    /**
     * @param array{
     *   license_or_entitlement_reference:string,
     *   device_public_key:string,
     *   device_public_key_fingerprint:string,
     *   installation_id:string,
     *   client_version:string,
     *   protocol_version:string,
     *   platform:string,
     *   architecture:string,
     *   client_nonce:string
     * } $request
     */
    public function canonicalMessage(array $request, string $idempotencyKey): string
    {
        $output = self::DOMAIN;
        foreach ([
            $idempotencyKey,
            $request['license_or_entitlement_reference'],
            $request['device_public_key'],
            $request['device_public_key_fingerprint'],
            $request['installation_id'],
            $request['client_version'],
            $request['protocol_version'],
            $request['platform'],
            $request['architecture'],
            $request['client_nonce'],
        ] as $value) {
            if ($value === '' || strlen($value) > 4096) {
                throw new DomainException('OMNIDESK_ACTIVATION_PROOF_INVALID');
            }
            $output .= pack('N', strlen($value)).$value;
        }

        return $output;
    }

    private function decodeBase64Url(string $value): string
    {
        if ($value === '' || preg_match('/\A[A-Za-z0-9_-]+\z/', $value) !== 1) {
            throw new DomainException('OMNIDESK_ACTIVATION_PROOF_INVALID');
        }

        $padding = (4 - strlen($value) % 4) % 4;
        $decoded = base64_decode(strtr($value, '-_', '+/').str_repeat('=', $padding), true);
        if ($decoded === false) {
            throw new DomainException('OMNIDESK_ACTIVATION_PROOF_INVALID');
        }

        return $decoded;
    }
}
