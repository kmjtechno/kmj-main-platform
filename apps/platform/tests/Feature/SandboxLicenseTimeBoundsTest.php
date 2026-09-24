<?php

namespace Tests\Feature;

use App\Services\Licensing\LicenseValidator;
use App\Services\Licensing\SandboxLicenseContract;
use App\Services\Licensing\SandboxLicenseIssuer;
use DateTimeImmutable;
use InvalidArgumentException;
use Tests\TestCase;

final class SandboxLicenseTimeBoundsTest extends TestCase
{
    private const SECRET = 'kmj-sandbox-test-secret-32-bytes-minimum';

    public function test_issuer_rejects_sandbox_license_lifetime_over_thirty_minutes(): void
    {
        $issuer = new SandboxLicenseIssuer(self::SECRET);

        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('Sandbox license lifetime cannot exceed 30 minutes.');

        $issuer->issue('org-1', 'product-1', 'entitlement-1', new DateTimeImmutable('+31 minutes'));
    }

    public function test_validator_rejects_token_issued_too_far_in_future(): void
    {
        $now = time();
        $license = $this->signedLicense([
            'environment' => 'sandbox',
            'contract_version' => SandboxLicenseContract::CURRENT_VERSION,
            'jti' => 'future-jti',
            'organization_id' => 'org-1',
            'product_id' => 'product-1',
            'entitlement_id' => 'entitlement-1',
            'issued_at' => $now + 120,
            'expires_at' => $now + 600,
        ]);

        $result = (new LicenseValidator(self::SECRET))->validate($license);

        self::assertFalse($result['valid']);
        self::assertSame('issued_in_future', $result['reason']);
    }

    public function test_validator_rejects_token_with_lifetime_over_thirty_minutes(): void
    {
        $now = time();
        $license = $this->signedLicense([
            'environment' => 'sandbox',
            'contract_version' => SandboxLicenseContract::CURRENT_VERSION,
            'jti' => 'long-lived-jti',
            'organization_id' => 'org-1',
            'product_id' => 'product-1',
            'entitlement_id' => 'entitlement-1',
            'issued_at' => $now - 10,
            'expires_at' => $now + 1801,
        ]);

        $result = (new LicenseValidator(self::SECRET))->validate($license);

        self::assertFalse($result['valid']);
        self::assertSame('lifetime_exceeded', $result['reason']);
    }

    /** @param array<string, mixed> $claims */
    private function signedLicense(array $claims): string
    {
        $payload = $this->base64UrlEncode(json_encode($claims, JSON_THROW_ON_ERROR));
        $signature = hash_hmac('sha256', $payload, self::SECRET, true);

        return $payload.'.'.$this->base64UrlEncode($signature);
    }

    private function base64UrlEncode(string $value): string
    {
        return rtrim(strtr(base64_encode($value), '+/', '-_'), '=');
    }
}
