<?php

namespace Tests\Feature;

use App\Services\Commerce\AdminProductManager;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class AdminProductManagerTest extends TestCase
{
    use RefreshDatabase;

    public function test_owner_catalog_fields_are_created_and_updated_from_one_record(): void
    {
        $manager = app(AdminProductManager::class);
        $product = $manager->create([
            'slug' => 'kmj-test-product', 'name' => 'KMJ Test Product', 'status' => 'sandbox',
            'lifecycle' => 'planned', 'is_public' => true, 'image_path' => '/assets/products/test.webp',
            'summary' => 'Test summary', 'purchase_enabled' => false, 'licensing_enabled' => false,
        ]);
        self::assertTrue($product->is_public);
        self::assertSame('planned', $product->lifecycle);

        $updated = $manager->update($product, [
            'lifecycle' => 'available', 'is_public' => false,
            'purchase_enabled' => true, 'licensing_enabled' => true,
        ]);
        self::assertFalse($updated->is_public);
        self::assertSame('available', $updated->lifecycle);
        self::assertTrue($updated->purchase_enabled);
        self::assertTrue($updated->licensing_enabled);
    }

    public function test_public_beta_is_a_supported_governed_lifecycle(): void
    {
        $manager = app(AdminProductManager::class);
        $product = $manager->create([
            'slug' => 'kmj-beta-product',
            'name' => 'KMJ Beta Product',
            'status' => 'sandbox',
            'lifecycle' => 'public-beta',
            'is_public' => true,
            'purchase_enabled' => false,
            'licensing_enabled' => true,
        ]);

        self::assertSame('public-beta', $product->lifecycle);
        self::assertTrue($product->is_public);
        self::assertFalse($product->purchase_enabled);
        self::assertTrue($product->licensing_enabled);
    }

    public function test_purchase_cannot_be_enabled_before_product_is_available(): void
    {
        $manager = app(AdminProductManager::class);
        $product = $manager->create([
            'slug' => 'kmj-research-product',
            'name' => 'KMJ Research Product',
            'status' => 'sandbox',
            'lifecycle' => 'research',
            'purchase_enabled' => false,
        ]);

        $this->expectException(DomainException::class);
        $manager->update($product, ['purchase_enabled' => true]);
    }

    public function test_reorder_requires_the_complete_catalog(): void
    {
        $manager = app(AdminProductManager::class);
        $manager->create(['slug' => 'a-product', 'name' => 'A Product', 'status' => 'sandbox', 'lifecycle' => 'research']);
        $manager->create(['slug' => 'b-product', 'name' => 'B Product', 'status' => 'sandbox', 'lifecycle' => 'research']);
        $c = $manager->create(['slug' => 'c-product', 'name' => 'C Product', 'status' => 'sandbox', 'lifecycle' => 'research']);

        $this->expectException(DomainException::class);
        $manager->reorder([(string) $c->getKey()]);
    }

    public function test_reorder_is_deterministic_and_rejects_unknown_products(): void
    {
        $manager = app(AdminProductManager::class);
        $a = $manager->create(['slug' => 'a-product', 'name' => 'A Product', 'status' => 'sandbox', 'lifecycle' => 'research']);
        $b = $manager->create(['slug' => 'b-product', 'name' => 'B Product', 'status' => 'sandbox', 'lifecycle' => 'research']);
        $manager->reorder([(string) $b->getKey(), (string) $a->getKey()]);
        self::assertSame(10, $b->refresh()->sort_order);
        self::assertSame(20, $a->refresh()->sort_order);
        $this->expectException(DomainException::class);
        $manager->reorder([(string) $a->getKey(), '00000000-0000-0000-0000-000000000000']);
    }
}
