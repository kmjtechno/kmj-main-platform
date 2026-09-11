<?php

namespace App\Services\Licensing;

use DateTimeImmutable;
use Illuminate\Support\Str;
use InvalidArgumentException;

final class SandboxLicenseIssuer
{
    public function __construct(private readonly string $secret)
    {
        if (strlen($this->secret) < 32) {
            throw new InvalidArgumentException('Sandbox signing secret must be at least 32 bytes.');
        }
    }

    public function issue(
        int|string $organizationId,
        int|string $productId,
        int|string $entitlementId,
        DateTimeImmutable $expiresAt,
    ): string {
        $now = new DateTimeImmutable('now');

        if ($expiresAt <= $now) {
            throw new InvalidArgumentException('License expiry must be in the future.');
        }

        $payload = [
            'environment' => 'sandbox',
            'jti' => (string) Str::uuid(),
            'organization_id' => (string) $organizationId,
            'product_id' => (string) $productId,
            'entitlement_id' => (string) $entitlementId,
            'issued_at' => $now->getTimestamp(),
            'expires_at' => $expiresAt->getTimestamp(),
        ];

        $encodedPayload = $this->base64UrlEncode(json_encode($payload, JSON_THROW_ON_ERROR));
        $signature = hash_hmac('sha256', $encodedPayload, $this->secret, true);

        return $encodedPayload.'.'.$this->base64UrlEncode($signature);
    }

    private function base64UrlEncode(string $value): string
    {
        return rtrim(strtr(base64_encode($value), '+/', '-_'), '=');
    }
}
