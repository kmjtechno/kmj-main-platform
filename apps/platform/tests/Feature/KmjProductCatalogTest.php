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

    public function test_sync_all_creates_the_canonical_kmj_product_portfolio_idempotently(): void
    {
        $catalog = app(KmjProductCatalog::class);

        $first = $catalog->syncAll();
        $second = $catalog->syncAll();

        foreach ([
            KmjProductCatalog::CLOUDOS_SLUG,
            KmjProductCatalog::CALIBRATION_SLUG,
            KmjProductCatalog::CLOUD_NEXUS_SLUG,
            KmjProductCatalog::FORGE_SLUG,
            KmjProductCatalog::AGENT_SLUG,
            KmjProductCatalog::CONNECT_SLUG,
        ] as $slug) {
            self::assertSame(
                $first[$slug]->getKey(),
                $second[$slug]->getKey(),
            );
        }

        $this->assertDatabaseCount('products', 6);
        $this->assertDatabaseHas('products', [
            'slug' => CloudOSProductCatalog::SLUG,
            'name' => CloudOSProductCatalog::NAME,
            'status' => 'active',
        ]);

        foreach ([
            KmjProductCatalog::CALIBRATION_SLUG => KmjProductCatalog::CALIBRATION_NAME,
            KmjProductCatalog::CLOUD_NEXUS_SLUG => KmjProductCatalog::CLOUD_NEXUS_NAME,
            KmjProductCatalog::FORGE_SLUG => KmjProductCatalog::FORGE_NAME,
            KmjProductCatalog::AGENT_SLUG => KmjProductCatalog::AGENT_NAME,
            KmjProductCatalog::CONNECT_SLUG => KmjProductCatalog::CONNECT_NAME,
        ] as $slug => $name) {
            $this->assertDatabaseHas('products', [
                'slug' => $slug,
                'name' => $name,
                'status' => 'sandbox',
            ]);
        }
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