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
}
