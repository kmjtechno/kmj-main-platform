<?php

namespace App\Services\Licensing;

use App\Models\LicenseRevocation;
use JsonException;

final class LicenseValidator
{
    public function __construct(private readonly string $secret) {}

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
            /** @var array<string, mixed> $claims */
            $claims = json_decode($payloadJson, true, flags: JSON_THROW_ON_ERROR);
        } catch (JsonException) {
            return $this->invalid('invalid_payload');
        }

        if (($claims['environment'] ?? null) !== 'sandbox') {
            return $this->invalid('wrong_environment');
        }

        $expiresAt = $claims['expires_at'] ?? null;
        $jti = $claims['jti'] ?? null;

        if (is_int($expiresAt) === false || is_string($jti) === false || $jti === '') {
            return $this->invalid('missing_claims');
        }

        if ($expiresAt <= time()) {
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
     *
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
