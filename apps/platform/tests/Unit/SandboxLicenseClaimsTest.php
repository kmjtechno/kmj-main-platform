<?php

namespace Tests\Unit;

use App\Services\Licensing\SandboxLicenseClaims;
use PHPUnit\Framework\TestCase;

final class SandboxLicenseClaimsTest extends TestCase
{
    public function test_claims_value_object_is_explicit_and_read_only(): void
    {
        $claims = new SandboxLicenseClaims('jti', 'kmj.sandbox.v1', 'org', 'product', 'entitlement', 1, 2);

        self::assertSame('jti', $claims->jti);
        self::assertSame('kmj.sandbox.v1', $claims->contractVersion);
        self::assertSame('org', $claims->organizationId);
        self::assertSame('product', $claims->productId);
        self::assertSame('entitlement', $claims->entitlementId);
        self::assertSame(1, $claims->issuedAt);
        self::assertSame(2, $claims->expiresAt);
    }
}
