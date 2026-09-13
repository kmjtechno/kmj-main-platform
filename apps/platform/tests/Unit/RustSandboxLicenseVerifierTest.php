<?php

namespace Tests\Unit;

use App\Services\Licensing\RustSandboxLicenseVerifier;
use Tests\TestCase;

final class RustSandboxLicenseVerifierTest extends TestCase
{
    public function test_unconfigured_verifier_fails_closed(): void
    {
        $verifier = new RustSandboxLicenseVerifier('', 'secret');

        self::assertSame([
            'valid' => false,
            'reason' => 'verifier_unconfigured',
            'claims' => null,
        ], $verifier->validate('license'));
    }

    public function test_successful_verifier_response_is_mapped(): void
    {
        $verifier = new RustSandboxLicenseVerifier(
            '/configured/verifier',
            'secret',
            runner: static fn (string $license, string $secret, float $timeout): array => [
                'exit_code' => 0,
                'output' => json_encode([
                    'valid' => true,
                    'reason' => null,
                    'claims' => ['environment' => 'sandbox', 'jti' => 'test-jti'],
                ], JSON_THROW_ON_ERROR),
            ],
        );

        $result = $verifier->validate('license');

        self::assertTrue($result['valid']);
        self::assertNull($result['reason']);
        self::assertSame('sandbox', $result['claims']['environment']);
        self::assertSame('test-jti', $result['claims']['jti']);
    }

    public function test_process_failure_fails_closed(): void
    {
        $verifier = new RustSandboxLicenseVerifier(
            '/configured/verifier',
            'secret',
            runner: static fn (string $license, string $secret, float $timeout): array => [
                'exit_code' => 1,
                'output' => '',
            ],
        );

        $result = $verifier->validate('license');

        self::assertFalse($result['valid']);
        self::assertSame('verifier_failed', $result['reason']);
        self::assertNull($result['claims']);
    }

    public function test_invalid_json_fails_closed(): void
    {
        $verifier = new RustSandboxLicenseVerifier(
            '/configured/verifier',
            'secret',
            runner: static fn (string $license, string $secret, float $timeout): array => [
                'exit_code' => 0,
                'output' => 'not-json',
            ],
        );

        $result = $verifier->validate('license');

        self::assertFalse($result['valid']);
        self::assertSame('verifier_invalid_response', $result['reason']);
        self::assertNull($result['claims']);
    }

    public function test_valid_response_without_claims_fails_closed(): void
    {
        $verifier = $this->verifierReturning([
            'valid' => true,
            'reason' => null,
            'claims' => null,
        ]);

        self::assertSame([
            'valid' => false,
            'reason' => 'verifier_invalid_response',
            'claims' => null,
        ], $verifier->validate('license'));
    }

    public function test_valid_response_with_failure_reason_fails_closed(): void
    {
        $verifier = $this->verifierReturning([
            'valid' => true,
            'reason' => 'expired',
            'claims' => ['environment' => 'sandbox'],
        ]);

        self::assertSame('verifier_invalid_response', $verifier->validate('license')['reason']);
    }

    public function test_invalid_response_without_reason_fails_closed(): void
    {
        $verifier = $this->verifierReturning([
            'valid' => false,
            'reason' => null,
            'claims' => null,
        ]);

        self::assertSame('verifier_invalid_response', $verifier->validate('license')['reason']);
    }

    public function test_invalid_response_with_claims_fails_closed(): void
    {
        $verifier = $this->verifierReturning([
            'valid' => false,
            'reason' => 'expired',
            'claims' => ['environment' => 'sandbox', 'jti' => 'should-not-leak'],
        ]);

        self::assertSame([
            'valid' => false,
            'reason' => 'verifier_invalid_response',
            'claims' => null,
        ], $verifier->validate('license'));
    }

    /**
     * @param  array<string, mixed>  $response
     */
    private function verifierReturning(array $response): RustSandboxLicenseVerifier
    {
        return new RustSandboxLicenseVerifier(
            '/configured/verifier',
            'secret',
            runner: static fn (string $license, string $secret, float $timeout): array => [
                'exit_code' => 0,
                'output' => json_encode($response, JSON_THROW_ON_ERROR),
            ],
        );
    }
}
