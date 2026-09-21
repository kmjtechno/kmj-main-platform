<?php

namespace Tests\Feature;

use App\Services\Commerce\CloudOSProductCatalog;
use App\Services\Commerce\KmjProductCatalog;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use KMJ\MainPlatform\Catalog\Models\Product;
use Tests\TestCase;

final class KmjProductCatalogTest extends TestCase
{
    use RefreshDatabase;

    public function test_sync_all_creates_canonical_cloudos_and_calibration_products_idempotently(): void
    {
        $catalog = app(KmjProductCatalog::class);

        $first = $catalog->syncAll();
        $second = $catalog->syncAll();

        self::assertSame(
            $first[KmjProductCatalog::CLOUDOS_SLUG]->getKey(),
            $second[KmjProductCatalog::CLOUDOS_SLUG]->getKey(),
        );
        self::assertSame(
            $first[KmjProductCatalog::CALIBRATION_SLUG]->getKey(),
            $second[KmjProductCatalog::CALIBRATION_SLUG]->getKey(),
        );

        $this->assertDatabaseCount('products', 2);
        $this->assertDatabaseHas('products', [
            'slug' => CloudOSProductCatalog::SLUG,
            'name' => CloudOSProductCatalog::NAME,
            'status' => 'active',
        ]);
        $this->assertDatabaseHas('products', [
            'slug' => KmjProductCatalog::CALIBRATION_SLUG,
            'name' => KmjProductCatalog::CALIBRATION_NAME,
            'status' => 'sandbox',
        ]);
    }

    public function test_calibration_preview_fails_closed_if_slug_is_bound_to_conflicting_facts(): void
    {
        Product::query()->create([
            'slug' => KmjProductCatalog::CALIBRATION_SLUG,
            'name' => 'Conflicting Calibration Product',
            'status' => 'active',
        ]);

        $this->expectException(DomainException::class);

        app(KmjProductCatalog::class)->syncAll();
    }
}
