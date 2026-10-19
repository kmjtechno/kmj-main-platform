<?php

namespace Tests\Unit;

use App\Services\Licensing\SandboxLicenseIssuer;
use DateTimeImmutable;
use InvalidArgumentException;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

final class SandboxLicenseIssuerIdentityContractTest extends TestCase
{
    #[DataProvider('blankIdentityProvider')]
    public function test_issuer_rejects_blank_identity_values(
        string $organizationId,
        string $productId,
        string $entitlementId,
    ): void {
        $issuer = new SandboxLicenseIssuer(str_repeat('s', 32));

        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('Sandbox license identity values must be non-blank.');

        $issuer->issue(
            $organizationId,
            $productId,
            $entitlementId,
            new DateTimeImmutable('+5 minutes'),
        );
    }

    #[DataProvider('paddedIdentityProvider')]
    public function test_issuer_rejects_identity_values_with_surrounding_whitespace(
        string $organizationId,
        string $productId,
        string $entitlementId,
    ): void {
        $issuer = new SandboxLicenseIssuer(str_repeat('s', 32));

        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('Sandbox license identity values must not contain surrounding whitespace.');

        $issuer->issue(
            $organizationId,
            $productId,
            $entitlementId,
            new DateTimeImmutable('+5 minutes'),
        );
    }

    #[DataProvider('oversizedIdentityProvider')]
    public function test_issuer_rejects_identity_larger_than_validation_contract(
        string $organizationId,
        string $productId,
        string $entitlementId,
    ): void {
        $issuer = new SandboxLicenseIssuer(str_repeat('s', 32));

        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('Sandbox license identity values exceed maximum length.');

        $issuer->issue(
            $organizationId,
            $productId,
            $entitlementId,
            new DateTimeImmutable('+5 minutes'),
        );
    }

    /**
     * @return array<string, array{string, string, string}>
     */
    public static function oversizedIdentityProvider(): array
    {
        return [
            'long organization' => [str_repeat('a', 256), 'product', 'entitlement'],
            'long product' => ['organization', str_repeat('p', 256), 'entitlement'],
            'long entitlement' => ['organization', 'product', str_repeat('e', 256)],
        ];
    }

    /**
     * @return array<string, array{string, string, string}>
     */
    public static function blankIdentityProvider(): array
    {
        return [
            'blank organization' => ['   ', 'product', 'entitlement'],
            'blank product' => ['organization', "\t", 'entitlement'],
            'blank entitlement' => ['organization', 'product', "\n"],
        ];
    }

    /**
     * @return array<string, array{string, string, string}>
     */
    public static function paddedIdentityProvider(): array
    {
        return [
            'padded organization' => [' organization ', 'product', 'entitlement'],
            'padded product' => ['organization', "\tproduct", 'entitlement'],
            'padded entitlement' => ['organization', 'product', "entitlement\n"],
        ];
    }
}
