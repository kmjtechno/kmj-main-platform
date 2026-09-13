<?php

namespace Tests\Unit;

use App\Services\Licensing\LicenseValidator;
use InvalidArgumentException;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

final class LicenseValidatorSecretContractTest extends TestCase
{
    #[DataProvider('blankSecretProvider')]
    public function test_validator_rejects_blank_signing_secrets(string $secret): void
    {
        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('Sandbox validation secret must be non-blank.');

        new LicenseValidator($secret);
    }

    public function test_validator_rejects_short_signing_secrets(): void
    {
        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('Sandbox validation secret must be at least 32 bytes.');

        new LicenseValidator(str_repeat('a', 31));
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
