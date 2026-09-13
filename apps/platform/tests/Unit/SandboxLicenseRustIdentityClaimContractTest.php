<?php

namespace Tests\Unit;

use App\Services\Licensing\LicenseValidator;
use App\Services\Licensing\RustSandboxLicenseVerifier;
use App\Services\Licensing\SandboxLicenseIssuer;
use App\Services\Licensing\SandboxLicenseValidationEngine;
use DateTimeImmutable;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class SandboxLicenseRustIdentityClaimContractTest extends TestCase
{
    use RefreshDatabase;

    public function test_rust_mode_rejects_whitespace_only_identity_claims(): void
    {
        $secret = str_repeat('k', 32);
        $phpValidator = new LicenseValidator($secret);
        $license = (new SandboxLicenseIssuer($secret))->issue(
            'org-1',
            'product-1',
            'entitlement-1',
            new DateTimeImmutable('+30 minutes'),
        );
        $validResult = $phpValidator->validate($license);
        self::assertIsArray($validResult['claims']);

        foreach (['jti', 'organization_id', 'product_id', 'entitlement_id'] as $claim) {
            $claims = $validResult['claims'];
            $claims[$claim] = " \t\n ";

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

            self::assertFalse($validation['valid'], "{$claim} must not accept whitespace-only identity.");
            self::assertSame('missing_claims', $validation['reason']);
            self::assertNull($validation['claims']);
        }
    }
}
