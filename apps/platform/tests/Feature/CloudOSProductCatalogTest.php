<?php

namespace Tests\Feature;

use App\Services\Commerce\CloudOSProductCatalog;
use App\Services\Commerce\KmjProductCatalog;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use Tests\TestCase;

final class CloudOSProductCatalogTest extends TestCase
{
    use RefreshDatabase;

    public function test_cloudos_product_sync_is_idempotent_and_canonical(): void
    {
        $catalog = app(CloudOSProductCatalog::class);

        $first = $catalog->sync();
        $second = $catalog->sync();

        self::assertSame($first->getKey(), $second->getKey());
        $this->assertDatabaseCount('products', 1);
        $this->assertDatabaseCount('entitlement_policies', 1);

        $this->assertDatabaseHas('products', [
            'id' => $first->getKey(),
            'slug' => CloudOSProductCatalog::SLUG,
            'name' => CloudOSProductCatalog::NAME,
            'status' => 'active',
        ]);
        $this->assertDatabaseHas('entitlement_policies', [
            'product_id' => $first->getKey(),
            'code' => CloudOSProductCatalog::POLICY_CODE,
            'capability' => CloudOSProductCatalog::CAPABILITY,
            'status' => 'active',
        ]);
    }

    public function test_sync_command_reuses_the_same_canonical_products(): void
    {
        $this->artisan('kmj:catalog:sync')->assertSuccessful();
        $this->artisan('kmj:catalog:sync')->assertSuccessful();

        $this->assertDatabaseCount('products', 11);
        $this->assertDatabaseCount('entitlement_policies', 1);
        $this->assertDatabaseHas('products', [
            'slug' => CloudOSProductCatalog::SLUG,
            'status' => 'active',
        ]);
        $this->assertDatabaseHas('products', [
            'slug' => KmjProductCatalog::CALIBRATION_SLUG,
            'status' => 'sandbox',
        ]);
    }

    public function test_conflicting_policy_facts_fail_closed(): void
    {
        $other = Product::query()->create([
            'slug' => 'other-product',
            'name' => 'Other Product',
            'status' => 'active',
        ]);

        EntitlementPolicy::query()->create([
            'product_id' => $other->getKey(),
            'code' => CloudOSProductCatalog::POLICY_CODE,
            'capability' => 'other.capability',
            'status' => 'active',
        ]);

        $this->expectException(DomainException::class);

        app(CloudOSProductCatalog::class)->sync();
    }
}
