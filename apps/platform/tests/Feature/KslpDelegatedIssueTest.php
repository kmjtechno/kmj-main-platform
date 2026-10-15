<?php

namespace Tests\Feature;

use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use Illuminate\Foundation\Testing\RefreshDatabase;
use KMJ\MainPlatform\Organizations\Models\Organization;
use Tests\TestCase;

final class KslpDelegatedIssueTest extends TestCase
{
    use RefreshDatabase;

    public function test_issuer_cannot_register_or_issue_product_code_longer_than_license_schema(): void
    {
        $organization = Organization::query()->create([
            'name' => 'Product Contract Guard',
            'slug' => 'product-contract-guard',
        ]);
        $organizationId = (string) $organization->id;
        $authority = app(KslpIssuerSubscriptionAuthority::class);
        $authority->subscribe($organizationId, 'professional', 5, 1000);

        $overlong = str_repeat('A', 65);
        try {
            $authority->registerProduct($organizationId, $overlong, 'Oversized App');
            self::fail('Overlong product registration must fail before writing');
        } catch (\DomainException $exception) {
            self::assertSame('KSLP_INVALID_PRODUCT_CODE', $exception->getMessage());
        }

        try {
            app(KslpLicenseControlPlane::class)->issueDelegated(
                $organizationId,
                'customer-oversized',
                $overlong,
                'trial',
                'owner',
            );
            self::fail('Overlong direct delegated issuance must fail');
        } catch (\DomainException $exception) {
            self::assertSame('KSLP_PRODUCT_CODE_TOO_LONG', $exception->getMessage());
        }

        $this->assertDatabaseCount('kslp_licensed_products', 0);
        $this->assertDatabaseCount('kslp_licenses', 0);
    }

    public function test_subscribed_vendor_can_issue_server_bound_license_for_own_registered_product(): void
    {
        $o = Organization::query()->create(['name' => 'Vendor', 'slug' => 'vendor']);
        $a = app(KslpIssuerSubscriptionAuthority::class);
        $a->subscribe((string) $o->id, 'professional', 5, 1000);
        $a->registerProduct((string) $o->id, 'VENDOR.APP', 'Vendor App', ['pro' => true]);
        $l = app(KslpLicenseControlPlane::class)->issueDelegated((string) $o->id, 'customer-1', 'VENDOR.APP', 'professional', 'vendor-admin');
        self::assertSame('VENDOR.APP', $l['product']);
        self::assertSame((string) $o->id, $l['issuer_organization_id']);
        $this->assertDatabaseHas('kslp_license_events', ['license_id' => $l['id'], 'action' => 'delegated_issued']);
    }
}
