<?php

namespace Tests\Unit;

use App\Services\Licensing\SandboxLicenseIssuer;
use InvalidArgumentException;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

final class SandboxLicenseIssuerSecretContractTest extends TestCase
{
    #[DataProvider('blankSecretProvider')]
    public function test_issuer_rejects_blank_signing_secrets(string $secret): void
    {
        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('Sandbox signing secret must be non-blank.');

        new SandboxLicenseIssuer($secret);
    }

    /**
     * @return array<string, array{string}>
     */
    public static function blankSecretProvider(): array
    {
        return [
            'spaces' => [str_repeat(' ', 32)],
            'tabs' => [str_repeat("\t", 32)],
            'mixed whitespace' => [str_repeat(" \t\n", 11)],
        ];
    }
}
