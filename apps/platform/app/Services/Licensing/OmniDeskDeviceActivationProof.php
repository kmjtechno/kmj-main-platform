<?php

declare(strict_types=1);

namespace App\Services\Licensing;

use DomainException;

/**
 * Verifies the exact device-owned Ed25519 proof from KMJ OmniDesk's
 * KMJ-OMNIDESK-ACTIVATE-v1 protocol.
 *
 * This is only a proof-of-possession precondition. It does NOT grant an
 * entitlement, consume an idempotency key, issue a lease, or sign a token.
 * Callers must independently authenticate the customer, bind the entitlement
 * and product, enforce replay/seat limits and use an approved production signer.
 */
final class OmniDeskDeviceActivationProof
{
    private const DOMAIN = 'KMJ-OMNIDESK-ACTIVATE-v1';

    private const FIELDS = [
        'idempotency_key',
        'license_or_entitlement_reference',
        'device_public_key',
        'device_public_key_fingerprint',
        'installation_id',
        'client_version',
        'protocol_version',
        'platform',
        'architecture',
        'client_nonce',
    ];

    /**
     * Canonical binary message: domain bytes followed by ten u32be
     * length-prefixed UTF-8 fields, exactly matching OmniDesk Rust.
     *
     * @param  array<string, mixed>  $request
     */
    public function canonicalMessage(array $request): string
    {
        $this->validateShape($request);

        $message = self::DOMAIN;
        foreach (self::FIELDS as $name) {
            $value = $request[$name];
            $message .= pack('N', strlen($value)).$value;
        }

        return $message;
    }

    /**
     * @param  array<string, mixed>  $request
     */
    public function verify(array $request): void
    {
        $message = $this->canonicalMessage($request);
        $publicKey = $this->decodeCanonicalBase64Url($request['device_public_key'], 32);
        $signature = $this->decodeCanonicalBase64Url($request['device_signature'], 64);

        if (! sodium_crypto_sign_verify_detached($signature, $message, $publicKey)) {
            throw new DomainException('FORBIDDEN');
        }
    }

    /**
     * @param  array<string, mixed>  $request
     */
    private function validateShape(array $request): void
    {
        $expected = [...self::FIELDS, 'proof_scheme', 'device_signature'];
        $actual = array_keys($request);
        sort($expected);
        sort($actual);

        if ($actual !== $expected) {
            throw new DomainException('INVALID_REQUEST');
        }

        $total = 0;
        foreach (self::FIELDS as $name) {
            $value = $request[$name];
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

        if ($total > 4096
            || strlen($request['idempotency_key']) < 8
            || strlen($request['client_nonce']) < 16
            || $request['protocol_version'] !== OmniDeskLicenseContract::PROTOCOL_VERSION
            || $request['proof_scheme'] !== self::DOMAIN
            || ! is_string($request['device_signature'])
        ) {
            throw new DomainException('INVALID_REQUEST');
        }

        $publicKey = $this->decodeCanonicalBase64Url($request['device_public_key'], 32);
        $expectedFingerprint = 'sha256:'.hash('sha256', $publicKey);
        if (! hash_equals($expectedFingerprint, $request['device_public_key_fingerprint'])) {
            throw new DomainException('FORBIDDEN');
        }
    }

    /** @return non-empty-string */
    private function decodeCanonicalBase64Url(string $encoded, int $expectedLength): string
    {
        $encodedLength = $expectedLength === 32 ? 43 : 86;
        if (strlen($encoded) !== $encodedLength
            || preg_match('/\A[A-Za-z0-9_-]+\z/D', $encoded) !== 1
        ) {
            throw new DomainException('INVALID_REQUEST');
        }

        $padding = str_repeat('=', (4 - strlen($encoded) % 4) % 4);
        $raw = base64_decode(strtr($encoded, '-_', '+/').$padding, true);
        if ($raw === false
            || $raw === ''
            || strlen($raw) !== $expectedLength
            || rtrim(strtr(base64_encode($raw), '+/', '-_'), '=') !== $encoded
        ) {
            throw new DomainException('INVALID_REQUEST');
        }

        return $raw;
    }
}
