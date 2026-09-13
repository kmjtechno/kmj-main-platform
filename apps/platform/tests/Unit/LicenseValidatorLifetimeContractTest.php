<?php

namespace Tests\Unit;

use App\Services\Licensing\LicenseValidator;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class LicenseValidatorLifetimeContractTest extends TestCase
{
    use RefreshDatabase;

    public function test_php_validator_rejects_zero_length_license_lifetime(): void
    {
        $secret = str_repeat('k', 32);
        $validator = new LicenseValidator($secret);
        $issuedAt = time() + 5;
        $claims = [
            'environment' => 'sandbox',
            'jti' => 'license-zero-lifetime',
            'organization_id' => 'org-1',
            'product_id' => 'product-1',
            'entitlement_id' => 'entitlement-1',
            'issued_at' => $issuedAt,
            'expires_at' => $issuedAt,
        ];

        $validation = $validator->validate($this->sign($claims, $secret));

        self::assertFalse($validation['valid']);
        self::assertSame('missing_claims', $validation['reason']);
        self::assertNull($validation['claims']);
    }

    /** @param array<string, mixed> $claims */
    private function sign(array $claims, string $secret): string
    {
        $payload = rtrim(strtr(base64_encode(json_encode($claims, JSON_THROW_ON_ERROR)), '+/', '-_'), '=');
        $signature = hash_hmac('sha256', $payload, $secret, true);

        return $payload.'.'.rtrim(strtr(base64_encode($signature), '+/', '-_'), '=');
    }
}
