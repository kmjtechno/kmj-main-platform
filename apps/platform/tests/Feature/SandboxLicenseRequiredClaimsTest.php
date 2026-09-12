<?php

namespace Tests\Feature;

use App\Services\Licensing\LicenseValidator;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class SandboxLicenseRequiredClaimsTest extends TestCase
{
    use RefreshDatabase;

    public function test_signed_license_without_tenant_identity_claims_is_rejected(): void
    {
        $secret = str_repeat('k', 32);
        $validator = new LicenseValidator($secret);
        $now = time();

        $license = $this->sign([
            'environment' => 'sandbox',
            'jti' => 'claim-contract-test',
            'product_id' => 'product-1',
            'entitlement_id' => 'entitlement-1',
            'issued_at' => $now,
            'expires_at' => $now + 3600,
        ], $secret);

        $result = $validator->validate($license);

        self::assertFalse($result['valid']);
        self::assertSame('missing_claims', $result['reason']);
    }

    public function test_signed_license_with_invalid_time_order_is_rejected(): void
    {
        $secret = str_repeat('k', 32);
        $validator = new LicenseValidator($secret);
        $now = time();

        $license = $this->sign([
            'environment' => 'sandbox',
            'jti' => 'claim-time-order-test',
            'organization_id' => 'organization-1',
            'product_id' => 'product-1',
            'entitlement_id' => 'entitlement-1',
            'issued_at' => $now + 3600,
            'expires_at' => $now + 1800,
        ], $secret);

        $result = $validator->validate($license);

        self::assertFalse($result['valid']);
        self::assertSame('missing_claims', $result['reason']);
    }

    /** @param array<string, mixed> $claims */
    private function sign(array $claims, string $secret): string
    {
        $payload = rtrim(strtr(base64_encode(json_encode($claims, JSON_THROW_ON_ERROR)), '+/', '-_'), '=');
        $signature = hash_hmac('sha256', $payload, $secret, true);
        $encodedSignature = rtrim(strtr(base64_encode($signature), '+/', '-_'), '=');

        return $payload.'.'.$encodedSignature;
    }
}
