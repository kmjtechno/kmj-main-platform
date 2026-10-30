<?php

declare(strict_types=1);

namespace App\Services\Licensing;

use DomainException;

/**
 * Verifies KMJ-OMNIDESK-RENEW-v1 device proof-of-possession.
 *
 * This checks only the caller's signature over an exact renewal request.
 * It does not authenticate a customer, fetch a trusted device key, validate a
 * server-issued challenge, consume a nonce, enforce monotonic sequence or
 * issue a signed lease. All of those are mandatory server-side API gates.
 */
final class OmniDeskDeviceRenewalProof
{
    private const DOMAIN = 'KMJ-OMNIDESK-RENEW-v1';

    private const STRING_FIELDS = [
        'activation_id',
        'current_jti',
        'server_challenge',
        'client_nonce',
        'client_version',
    ];

    /**
     * Canonical binary bytes matching the OmniDesk Rust renewal-proof module.
     * The unsigned PHP integer is encoded as a decimal UTF-8 field.
     *
     * @param  array<string, mixed>  $request
     */
    public function canonicalMessage(array $request): string
    {
        $this->validateShape($request);

        $message = self::DOMAIN;
        foreach ([
            $request['activation_id'],
            $request['current_jti'],
            (string) $request['current_sequence'],
            $request['server_challenge'],
            $request['client_nonce'],
            $request['client_version'],
        ] as $value) {
            $message .= pack('N', strlen($value)).$value;
        }

        return $message;
    }

    /**
     * $trustedDevicePublicKey must come from an independently authenticated
     * and tenant-checked activation binding, never the caller's request.
     *
     * @param  array<string, mixed>  $request
     */
    public function verify(array $request, string $trustedDevicePublicKey): void
    {
        if (strlen($trustedDevicePublicKey) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES) {
            throw new DomainException('INVALID_REQUEST');
        }

        $message = $this->canonicalMessage($request);
        $signature = $this->decodeSignature($request['device_signature']);

        if (! sodium_crypto_sign_verify_detached($signature, $message, $trustedDevicePublicKey)) {
            throw new DomainException('FORBIDDEN');
        }
    }

    /**
     * @param  array<string, mixed>  $request
     */
    private function validateShape(array $request): void
    {
        $expected = [...self::STRING_FIELDS, 'current_sequence', 'proof_scheme', 'device_signature'];
        $actual = array_keys($request);
        sort($expected);
        sort($actual);
        if ($actual !== $expected
            || $request['proof_scheme'] !== self::DOMAIN
            || ! is_int($request['current_sequence'])
            || $request['current_sequence'] < 1
            || ! is_string($request['device_signature'])
        ) {
            throw new DomainException('INVALID_REQUEST');
        }

        $total = 0;
        foreach (self::STRING_FIELDS as $field) {
            $value = $request[$field];
            if (! is_string($value)
                || $value === ''
                || strlen($value) > 512
                || preg_match('//u', $value) !== 1
                || str_contains($value, "\0")
            ) {
                throw new DomainException('INVALID_REQUEST');
            }
            $total += strlen($value);
        }

        if ($total > 2048
            || strlen($request['activation_id']) < 8
            || strlen($request['current_jti']) < 8
            || strlen($request['server_challenge']) < 16
            || strlen($request['client_nonce']) < 16
        ) {
            throw new DomainException('INVALID_REQUEST');
        }
    }

    /** @return non-empty-string */
    private function decodeSignature(string $encoded): string
    {
        if (strlen($encoded) !== 86 || preg_match('/\A[A-Za-z0-9_-]+\z/D', $encoded) !== 1) {
            throw new DomainException('INVALID_REQUEST');
        }

        $raw = base64_decode(strtr($encoded, '-_', '+/').'==', true);
        if ($raw === false
            || $raw === ''
            || strlen($raw) !== SODIUM_CRYPTO_SIGN_BYTES
            || rtrim(strtr(base64_encode($raw), '+/', '-_'), '=') !== $encoded
        ) {
            throw new DomainException('INVALID_REQUEST');
        }

        return $raw;
    }
}
