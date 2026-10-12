<?php

namespace Tests\Feature;

use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Organizations\Models\Organization;
use Tests\TestCase;

final class KslpIssuerSubscriptionTest extends TestCase
{
    use RefreshDatabase;

    public function test_own_product_requires_active_issuer_subscription(): void
    {
        $organization = Organization::query()->create(['name' => 'Vendor', 'slug' => 'vendor']);
        $authority = app(KslpIssuerSubscriptionAuthority::class);

        try {
            $authority->registerProduct((string) $organization->id, 'VENDOR.APP', 'Vendor App');
            self::fail('Registration without a subscription must fail closed.');
        } catch (DomainException $exception) {
            self::assertSame('KSLP_ISSUER_SUBSCRIPTION_REQUIRED', $exception->getMessage());
        }

        $authority->subscribe((string) $organization->id, 'professional', 5, 1000);
        $product = $authority->registerProduct(
            (string) $organization->id,
            'VENDOR.APP',
            'Vendor App',
            ['pro' => true],
            ['seats' => 10],
        );

        self::assertSame('VENDOR.APP', $product['product_code']);
        self::assertSame(
            'VENDOR.APP',
            $authority->authorizeIssue((string) $organization->id, 'VENDOR.APP')['product_code'],
        );
    }

    public function test_subscription_update_preserves_identity_and_updates_policy(): void
    {
        $organization = Organization::query()->create(['name' => 'Vendor', 'slug' => 'vendor-update']);
        $authority = app(KslpIssuerSubscriptionAuthority::class);

        $first = $authority->subscribe((string) $organization->id, 'professional', 1, 10);
        $second = $authority->subscribe((string) $organization->id, 'business', 3, 100);

        self::assertSame($first['id'], $second['id']);
        self::assertSame('business', $second['tier']);
        self::assertSame(3, (int) $second['product_limit']);
        self::assertSame(100, (int) $second['monthly_issue_limit']);
        $this->assertDatabaseCount('kslp_issuer_subscriptions', 1);
    }

    public function test_product_limit_fails_closed_without_over_issuing(): void
    {
        $organization = Organization::query()->create(['name' => 'Vendor', 'slug' => 'vendor-limit']);
        $authority = app(KslpIssuerSubscriptionAuthority::class);
        $authority->subscribe((string) $organization->id, 'professional', 1, 100);
        $authority->registerProduct((string) $organization->id, 'VENDOR.ONE', 'Vendor One');

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('KSLP_ISSUER_PRODUCT_LIMIT');

        $authority->registerProduct((string) $organization->id, 'VENDOR.TWO', 'Vendor Two');
    }

    public function test_suspended_issuer_cannot_mint_delegated_trial_license(): void
    {
        $org = Organization::query()->create(['name' => 'Suspended Vendor', 'slug' => 'suspended-vendor']);
        $id = (string) $org->id;
        $issuer = app(KslpIssuerSubscriptionAuthority::class);
        $issuer->subscribe($id, 'professional', 2, 10);
        $issuer->registerProduct($id, 'VENDOR.SUSPENDED', 'Suspended App');
        DB::table('kslp_issuer_subscriptions')->where('organization_id', $id)
            ->update(['status' => 'suspended']);

        try {
            app(KslpLicenseControlPlane::class)->issueDelegated(
                $id, 'customer-one', 'VENDOR.SUSPENDED', 'trial', 'owner',
            );
            self::fail('A suspended issuer must not issue trial or paid licenses.');
        } catch (DomainException $exception) {
            self::assertSame('KSLP_ISSUER_SUBSCRIPTION_REQUIRED', $exception->getMessage());
        }
        $this->assertDatabaseCount('kslp_licenses', 0);
    }

    public function test_revoked_product_cannot_issue_delegated_license(): void
    {
        $org = Organization::query()->create(['name' => 'Revoked Vendor', 'slug' => 'revoked-vendor']);
        $id = (string) $org->id;
        $issuer = app(KslpIssuerSubscriptionAuthority::class);
        $issuer->subscribe($id, 'professional', 2, 10);
        $issuer->registerProduct($id, 'VENDOR.REVOKED', 'Revoked App');
        DB::table('kslp_licensed_products')->where('product_code', 'VENDOR.REVOKED')
            ->update(['status' => 'revoked']);

        try {
            app(KslpLicenseControlPlane::class)->issueDelegated(
                $id, 'customer-two', 'VENDOR.REVOKED', 'trial', 'owner',
            );
            self::fail('Revoked product cannot issue any delegated license.');
        } catch (DomainException $exception) {
            self::assertSame('KSLP_ISSUER_PRODUCT_NOT_AUTHORIZED', $exception->getMessage());
        }
        $this->assertDatabaseCount('kslp_licenses', 0);
    }
}
