<?php

namespace App\Services\Licensing;

use DateTimeImmutable;
use Illuminate\Support\Str;
use InvalidArgumentException;

final class SandboxLicenseIssuer
{
    public function __construct(private readonly string $secret)
    {
        if (trim($this->secret) === '') {
            throw new InvalidArgumentException('Sandbox signing secret must be non-blank.');
        }

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
        $organizationId = (string) $organizationId;
        $productId = (string) $productId;
        $entitlementId = (string) $entitlementId;

        if (trim($organizationId) === '' || trim($productId) === '' || trim($entitlementId) === '') {
            throw new InvalidArgumentException('Sandbox license identity values must be non-blank.');
        }

        if (
            trim($organizationId) !== $organizationId
            || trim($productId) !== $productId
            || trim($entitlementId) !== $entitlementId
        ) {
            throw new InvalidArgumentException('Sandbox license identity values must not contain surrounding whitespace.');
        }

        $now = new DateTimeImmutable('now');

        if ($expiresAt <= $now) {
            throw new InvalidArgumentException('License expiry must be in the future.');
        }

        if ($expiresAt->getTimestamp() - $now->getTimestamp() > SandboxLicensePolicy::MAX_LIFETIME_SECONDS) {
            throw new InvalidArgumentException('Sandbox license lifetime cannot exceed 30 minutes.');
        }

        $payload = [
            'environment' => 'sandbox',
            'jti' => (string) Str::uuid(),
            'organization_id' => $organizationId,
            'product_id' => $productId,
            'entitlement_id' => $entitlementId,
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
