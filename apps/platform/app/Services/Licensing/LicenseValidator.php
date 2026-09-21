<?php

namespace App\Services\Licensing;

use App\Models\LicenseRevocation;
use InvalidArgumentException;
use JsonException;

final class LicenseValidator
{
    public function __construct(
        private readonly string $secret,
    ) {
        if (trim($this->secret) === '') {
            throw new InvalidArgumentException('Sandbox validation secret must be non-blank.');
        }

        if (strlen($this->secret) < 32) {
            throw new InvalidArgumentException('Sandbox validation secret must be at least 32 bytes.');
        }
    }

    /**
     * @return array{valid: bool, reason: string|null, claims: array<string, mixed>|null}
     */
    public function validate(string $license): array
    {
        $parts = explode('.', $license);

        if (count($parts) !== 2) {
            return $this->invalid('malformed');
        }

        [$encodedPayload, $encodedSignature] = $parts;
        $signature = $this->base64UrlDecode($encodedSignature);

        if ($signature === null) {
            return $this->invalid('malformed_signature');
        }

        $expected = hash_hmac('sha256', $encodedPayload, $this->secret, true);

        if (hash_equals($expected, $signature) === false) {
            return $this->invalid('invalid_signature');
        }

        $payloadJson = $this->base64UrlDecode($encodedPayload);

        if ($payloadJson === null) {
            return $this->invalid('malformed_payload');
        }

        try {
            $claims = json_decode($payloadJson, true, flags: JSON_THROW_ON_ERROR);
        } catch (JsonException) {
            return $this->invalid('invalid_payload');
        }

        if (! is_array($claims) || array_is_list($claims)) {
            return $this->invalid('invalid_payload');
        }

        if (($claims['environment'] ?? null) !== 'sandbox') {
            return $this->invalid('wrong_environment');
        }

        if (! SandboxLicenseContract::supports($claims['contract_version'] ?? null)) {
            return $this->invalid('unsupported_contract_version');
        }

        $jti = $claims['jti'] ?? null;
        $organizationId = $claims['organization_id'] ?? null;
        $productId = $claims['product_id'] ?? null;
        $entitlementId = $claims['entitlement_id'] ?? null;
        $issuedAt = $claims['issued_at'] ?? null;
        $expiresAt = $claims['expires_at'] ?? null;

        if (
            is_string($jti) === false || trim($jti) === ''
            || is_string($organizationId) === false || trim($organizationId) === ''
            || is_string($productId) === false || trim($productId) === ''
            || is_string($entitlementId) === false || trim($entitlementId) === ''
            || is_int($issuedAt) === false
            || is_int($expiresAt) === false
            || $issuedAt >= $expiresAt
        ) {
            return $this->invalid('missing_claims');
        }

        if (
            trim($jti) !== $jti
            || trim($organizationId) !== $organizationId
            || trim($productId) !== $productId
            || trim($entitlementId) !== $entitlementId
        ) {
            return $this->invalid('non_canonical_identity');
        }

        $now = time();

        if ($issuedAt > $now + SandboxLicensePolicy::MAX_FUTURE_ISSUED_AT_SKEW_SECONDS) {
            return $this->invalid('issued_in_future', $claims);
        }

        if ($expiresAt - $issuedAt > SandboxLicensePolicy::MAX_LIFETIME_SECONDS) {
            return $this->invalid('lifetime_exceeded', $claims);
        }

        if ($expiresAt <= $now) {
            return $this->invalid('expired', $claims);
        }

        if (LicenseRevocation::query()->where('jti', $jti)->exists()) {
            return $this->invalid('revoked', $claims);
        }

        return [
            'valid' => true,
            'reason' => null,
            'claims' => $claims,
        ];
    }

    /**
     * @param  array<string, mixed>|null  $claims
     * @return array{valid: false, reason: string, claims: array<string, mixed>|null}
     */
    private function invalid(string $reason, ?array $claims = null): array
    {
        return [
            'valid' => false,
            'reason' => $reason,
            'claims' => $claims,
        ];
    }

    private function base64UrlDecode(string $value): ?string
    {
        $padding = strlen($value) % 4;
        if ($padding !== 0) {
            $value .= str_repeat('=', 4 - $padding);
        }

        $decoded = base64_decode(strtr($value, '-_', '+/'), true);

        return $decoded === false ? null : $decoded;
    }
}
