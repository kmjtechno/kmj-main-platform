<?php

namespace Tests\Unit;

use App\Services\Licensing\LicenseRevoker;
use App\Services\Licensing\LicenseValidator;
use App\Services\Licensing\RustSandboxLicenseVerifier;
use App\Services\Licensing\SandboxLicenseIssuer;
use App\Services\Licensing\SandboxLicenseValidationEngine;
use DateTimeImmutable;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class SandboxLicenseValidationEngineTest extends TestCase
{
    use RefreshDatabase;

    public function test_php_mode_remains_authoritative_without_rust_configuration(): void
    {
        [$license, $phpValidator] = $this->licenseFixture();
        $engine = new SandboxLicenseValidationEngine(
            $phpValidator,
            new RustSandboxLicenseVerifier('', 'unused'),
            'php',
        );

        self::assertTrue($engine->validate($license)['valid']);
    }

    public function test_cross_check_accepts_matching_rust_claims(): void
    {
        [$license, $phpValidator] = $this->licenseFixture();
        $rustVerifier = new RustSandboxLicenseVerifier(
            '/configured/verifier',
            'unused',
            runner: static function (string $license, string $secret, float $timeout) use ($phpValidator): array {
                return [
                    'exit_code' => 0,
                    'output' => json_encode($phpValidator->validate($license), JSON_THROW_ON_ERROR),
                ];
            },
        );
        $engine = new SandboxLicenseValidationEngine($phpValidator, $rustVerifier, 'cross_check');

        self::assertTrue($engine->validate($license)['valid']);
    }

    public function test_cross_check_fails_closed_on_claim_disagreement(): void
    {
        [$license, $phpValidator] = $this->licenseFixture();
        $rustVerifier = new RustSandboxLicenseVerifier(
            '/configured/verifier',
            'unused',
            runner: static function (string $license, string $secret, float $timeout) use ($phpValidator): array {
                $result = $phpValidator->validate($license);
                $result['claims']['product_id'] = 'different-product';

                return [
                    'exit_code' => 0,
                    'output' => json_encode($result, JSON_THROW_ON_ERROR),
                ];
            },
        );
        $engine = new SandboxLicenseValidationEngine($phpValidator, $rustVerifier, 'cross_check');

        self::assertSame('verifier_disagreement', $engine->validate($license)['reason']);
    }

    public function test_cross_check_preserves_php_revocation_before_rust(): void
    {
        [$license, $phpValidator] = $this->licenseFixture();
        $claims = $phpValidator->validate($license)['claims'];
        self::assertIsArray($claims);
        (new LicenseRevoker)->revoke((string) $claims['jti'], 'test');

        $rustVerifier = new RustSandboxLicenseVerifier(
            '/configured/verifier',
            'unused',
            runner: static fn (string $license, string $secret, float $timeout): never => throw new \RuntimeException('Rust should not run for PHP-invalid licenses.'),
        );
        $engine = new SandboxLicenseValidationEngine($phpValidator, $rustVerifier, 'cross_check');
        $result = $engine->validate($license);

        self::assertFalse($result['valid']);
        self::assertSame('revoked', $result['reason']);
    }

    public function test_rust_mode_accepts_rust_verified_license(): void
    {
        [$license, $phpValidator] = $this->licenseFixture();
        $claims = $phpValidator->validate($license);
        $rustVerifier = new RustSandboxLicenseVerifier(
            '/configured/verifier',
            'unused',
            runner: static fn (string $license, string $secret, float $timeout): array => [
                'exit_code' => 0,
                'output' => json_encode($claims, JSON_THROW_ON_ERROR),
            ],
        );
        $engine = new SandboxLicenseValidationEngine($phpValidator, $rustVerifier, 'rust');

        self::assertTrue($engine->validate($license)['valid']);
    }

    public function test_rust_mode_fails_closed_when_valid_response_omits_tenant_claims(): void
    {
        [$license, $phpValidator] = $this->licenseFixture();
        $validResult = $phpValidator->validate($license);
        self::assertIsArray($validResult['claims']);
        $claims = $validResult['claims'];
        unset($claims['organization_id']);

        $rustVerifier = new RustSandboxLicenseVerifier(
            '/configured/verifier',
            'unused',
            runner: static fn (string $license, string $secret, float $timeout): array => [
                'exit_code' => 0,
                'output' => json_encode([
                    'valid' => true,
                    'reason' => null,
                    'claims' => $claims,
                ], JSON_THROW_ON_ERROR),
            ],
        );
        $engine = new SandboxLicenseValidationEngine($phpValidator, $rustVerifier, 'rust');
        $validation = $engine->validate($license);

        self::assertFalse($validation['valid']);
        self::assertSame('missing_claims', $validation['reason']);
    }

    public function test_rust_mode_preserves_database_revocation(): void
    {
        [$license, $phpValidator] = $this->licenseFixture();
        $result = $phpValidator->validate($license);
        self::assertIsArray($result['claims']);
        (new LicenseRevoker)->revoke((string) $result['claims']['jti'], 'test');

        $rustVerifier = new RustSandboxLicenseVerifier(
            '/configured/verifier',
            'unused',
            runner: static fn (string $license, string $secret, float $timeout): array => [
                'exit_code' => 0,
                'output' => json_encode($result, JSON_THROW_ON_ERROR),
            ],
        );
        $engine = new SandboxLicenseValidationEngine($phpValidator, $rustVerifier, 'rust');
        $validation = $engine->validate($license);

        self::assertFalse($validation['valid']);
        self::assertSame('revoked', $validation['reason']);
    }

    public function test_unknown_mode_fails_closed(): void
    {
        [$license, $phpValidator] = $this->licenseFixture();
        $engine = new SandboxLicenseValidationEngine(
            $phpValidator,
            new RustSandboxLicenseVerifier('', 'unused'),
            'unknown',
        );

        self::assertSame('validation_engine_unconfigured', $engine->validate($license)['reason']);
    }

    /** @return array{string, LicenseValidator} */
    private function licenseFixture(): array
    {
        $secret = str_repeat('k', 32);
        $issuer = new SandboxLicenseIssuer($secret);
        $validator = new LicenseValidator($secret);
        $license = $issuer->issue('org-1', 'product-1', 'entitlement-1', new DateTimeImmutable('+30 minutes'));

        return [$license, $validator];
    }
}
