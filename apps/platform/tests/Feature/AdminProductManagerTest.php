<?php

namespace Tests\Feature;

use App\Services\Commerce\AdminProductManager;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use KMJ\MainPlatform\Catalog\Models\Product;
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

    public function test_reorder_is_deterministic_and_rejects_unknown_products(): void
    {
        $manager = app(AdminProductManager::class);
        $a = $manager->create(['slug'=>'a-product','name'=>'A Product','status'=>'sandbox','lifecycle'=>'research']);
        $b = $manager->create(['slug'=>'b-product','name'=>'B Product','status'=>'sandbox','lifecycle'=>'research']);
        $manager->reorder([(string) $b->getKey(), (string) $a->getKey()]);
        self::assertSame(10, $b->refresh()->sort_order);
        self::assertSame(20, $a->refresh()->sort_order);
        $this->expectException(DomainException::class);
        $manager->reorder([(string) $a->getKey(), '00000000-0000-0000-0000-000000000000']);
    }
}
