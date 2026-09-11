<?php

namespace Tests\Feature;

use App\Services\Licensing\LicenseRevoker;
use App\Services\Licensing\LicenseValidator;
use App\Services\Licensing\SandboxLicenseIssuer;
use DateTimeImmutable;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class SandboxLicenseLifecycleSmokeTest extends TestCase
{
    use RefreshDatabase;

    public function test_license_lifecycle_smoke_path(): void
    {
        $secret = str_repeat('s', 32);
        $issuer = new SandboxLicenseIssuer($secret);
        $validator = new LicenseValidator($secret);
        $revoker = new LicenseRevoker();

        $license = $issuer->issue(1, 1, 1, new DateTimeImmutable('+5 minutes'));
        $validation = $validator->validate($license);

        self::assertTrue($validation['valid']);

        $revoker->revoke($validation['claims']['jti']);

        self::assertSame('revoked', $validator->validate($license)['reason']);
    }
}
