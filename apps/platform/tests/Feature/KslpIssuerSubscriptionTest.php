<?php

namespace Tests\Feature;

use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
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
}
