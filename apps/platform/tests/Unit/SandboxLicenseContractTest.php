<?php

namespace Tests\Unit;

use App\Services\Licensing\LicenseValidator;
use App\Services\Licensing\SandboxLicenseContract;
use Carbon\CarbonImmutable;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class SandboxLicenseContractTest extends TestCase
{
    use RefreshDatabase;

    public function test_current_contract_version_is_explicit(): void
    {
        self::assertSame('kmj.sandbox.v1', SandboxLicenseContract::CURRENT_VERSION);
    }

    public function test_php_validator_accepts_shared_v1_golden_vector(): void
    {
        $vector = json_decode(
            file_get_contents(base_path('../../services/license-core/vectors/sandbox-v1.json')),
            true,
            flags: JSON_THROW_ON_ERROR,
        );

        self::assertIsArray($vector);
        $this->travelTo(CarbonImmutable::createFromTimestamp($vector['claims']['issued_at'] + 1));
        $result = (new LicenseValidator($vector['secret']))->validate($vector['license']);

        self::assertTrue($result['valid']);
        self::assertSame(SandboxLicenseContract::CURRENT_VERSION, $result['claims']['contract_version']);
        self::assertSame($vector['claims']['jti'], $result['claims']['jti']);
    }

    public function test_php_validator_rejects_missing_contract_version(): void
    {
        $secret = str_repeat('k', 32);
        $claims = $this->claims();
        unset($claims['contract_version']);

        $result = (new LicenseValidator($secret))->validate($this->sign($claims, $secret));

        self::assertFalse($result['valid']);
        self::assertSame('unsupported_contract_version', $result['reason']);
        self::assertNull($result['claims']);
    }

    public function test_php_validator_rejects_unsupported_contract_version(): void
    {
        $secret = str_repeat('k', 32);
        $claims = $this->claims();
        $claims['contract_version'] = 'kmj.sandbox.v999';

        $result = (new LicenseValidator($secret))->validate($this->sign($claims, $secret));

        self::assertFalse($result['valid']);
        self::assertSame('unsupported_contract_version', $result['reason']);
        self::assertNull($result['claims']);
    }

    /** @return array<string, mixed> */
    private function claims(): array
    {
        $now = time();

        return [
            'environment' => 'sandbox',
            'contract_version' => SandboxLicenseContract::CURRENT_VERSION,
            'jti' => 'contract-test-jti',
            'organization_id' => 'org-1',
            'product_id' => 'product-1',
            'entitlement_id' => 'entitlement-1',
            'issued_at' => $now,
            'expires_at' => $now + 300,
        ];
    }

    /** @param array<string, mixed> $claims */
    private function sign(array $claims, string $secret): string
    {
        $payload = rtrim(strtr(base64_encode(json_encode($claims, JSON_THROW_ON_ERROR)), '+/', '-_'), '=');
        $signature = hash_hmac('sha256', $payload, $secret, true);

        return $payload.'.'.rtrim(strtr(base64_encode($signature), '+/', '-_'), '=');
    }
}
