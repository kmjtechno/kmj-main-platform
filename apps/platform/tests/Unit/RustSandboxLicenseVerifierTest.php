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
}
