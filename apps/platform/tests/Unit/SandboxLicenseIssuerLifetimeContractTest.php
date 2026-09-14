<?php

namespace Tests\Unit;

use App\Services\Licensing\SandboxLicenseIssuer;
use DateTimeImmutable;
use InvalidArgumentException;
use Tests\TestCase;

final class SandboxLicenseIssuerLifetimeContractTest extends TestCase
{
    public function test_issuer_rejects_expiry_that_collapses_to_the_issuance_second(): void
    {
        $issuer = new SandboxLicenseIssuer(str_repeat('k', 32));
        $expiresAt = (new DateTimeImmutable)->setTimestamp(time());

        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('License expiry must be at least one second after issuance.');

        $issuer->issue('org-1', 'product-1', 'entitlement-1', $expiresAt);
    }
}
