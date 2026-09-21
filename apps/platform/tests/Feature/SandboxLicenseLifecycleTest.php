<?php

namespace Tests\Feature;

use App\Models\LicenseRevocation;
use App\Services\Licensing\LicenseRevoker;
use App\Services\Licensing\LicenseValidator;
use App\Services\Licensing\SandboxLicenseContract;
use App\Services\Licensing\SandboxLicenseIssuer;
use DateTimeImmutable;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class SandboxLicenseLifecycleTest extends TestCase
{
    use RefreshDatabase;

    public function test_signed_sandbox_license_can_be_validated_and_revoked(): void
    {
        $secret = str_repeat('k', 32);
        $issuer = new SandboxLicenseIssuer($secret);
        $validator = new LicenseValidator($secret);
        $revoker = new LicenseRevoker;

        $license = $issuer->issue(
            organizationId: 10,
            productId: 20,
            entitlementId: 30,
            expiresAt: new DateTimeImmutable('+30 minutes'),
        );

        $valid = $validator->validate($license);

        self::assertTrue($valid['valid']);
        self::assertSame('sandbox', $valid['claims']['environment']);
        self::assertSame(SandboxLicenseContract::CURRENT_VERSION, $valid['claims']['contract_version']);
        self::assertSame('10', $valid['claims']['organization_id']);
        self::assertSame('20', $valid['claims']['product_id']);
        self::assertSame('30', $valid['claims']['entitlement_id']);

        $revoker->revoke($valid['claims']['jti'], 'test revocation');

        $revoked = $validator->validate($license);

        self::assertFalse($revoked['valid']);
        self::assertSame('revoked', $revoked['reason']);
    }

    public function test_revoking_the_same_license_is_idempotent(): void
    {
        $revoker = new LicenseRevoker;

        $first = $revoker->revoke('sandbox-idempotency-jti', 'initial reason');
        $second = $revoker->revoke('sandbox-idempotency-jti', 'duplicate retry');

        self::assertSame($first->getKey(), $second->getKey());
        self::assertSame(1, LicenseRevocation::query()->where('jti', 'sandbox-idempotency-jti')->count());
        self::assertSame('initial reason', $second->reason);
    }

    public function test_tampered_license_is_rejected(): void
    {
        $secret = str_repeat('k', 32);
        $issuer = new SandboxLicenseIssuer($secret);
        $validator = new LicenseValidator($secret);

        $license = $issuer->issue(1, 2, 3, new DateTimeImmutable('+30 minutes'));
        [$payload, $signature] = explode('.', $license);
        $tampered = substr($payload, 0, -1).($payload[-1] === 'A' ? 'B' : 'A').'.'.$signature;

        $result = $validator->validate($tampered);

        self::assertFalse($result['valid']);
        self::assertSame('invalid_signature', $result['reason']);
    }
}
