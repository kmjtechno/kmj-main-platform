<?php

namespace Tests\Feature;

use App\Services\Commerce\KmjProductCatalog;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Catalog\Models\Product;
use Tests\TestCase;

final class PublicProductHubTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
        app(KmjProductCatalog::class)->syncAll();
    }

    public function test_homepage_exposes_the_complete_canonical_public_portfolio(): void
    {
        $this->get('/')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('welcome')
                ->where('portfolioCount', 15)
                ->has('products', 15)
                ->where('products', function ($products): bool {
                    $bySlug = collect($products)->keyBy('slug');

                    return $bySlug->has('kmj-cloudos')
                        && $bySlug->has('kmj-calibration-pro')
                        && $bySlug->has('kmj-cinema-platform')
                        && $bySlug->has('kmj-360-dome')
                        && $bySlug->has('kmj-omnidesk')
                        && $bySlug->has('kmj-codebridge')
                        && $bySlug->has('kmj-desktop-commander')
                        && $bySlug['kmj-cloudos']['lifecycle'] === 'available'
                        && $bySlug['kmj-codebridge']['lifecycle'] === 'research'
                        && $bySlug['kmj-desktop-commander']['lifecycle'] === 'public-beta';
                }));
    }

    public function test_admin_product_order_drives_the_locked_landing_order(): void
    {
        $cloudOS = Product::query()->where('slug', 'kmj-cloudos')->firstOrFail();
        $calibration = Product::query()->where('slug', 'kmj-calibration-pro')->firstOrFail();

        app(\App\Services\Commerce\AdminProductManager::class)->reorder([
            (string) $calibration->getKey(),
            (string) $cloudOS->getKey(),
            ...Product::query()
                ->whereNotIn('id', [$cloudOS->getKey(), $calibration->getKey()])
                ->orderBy('sort_order')
                ->orderBy('name')
                ->pluck('id')
                ->map(fn ($id): string => (string) $id)
                ->all(),
        ]);

        $this->get('/')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('welcome')
                ->where('products.0.slug', 'kmj-calibration-pro')
                ->where('products.1.slug', 'kmj-cloudos'));
    }

    public function test_products_hub_uses_only_canonical_public_lifecycle_vocabulary(): void
    {
        $this->get('/products')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/index')
                ->has('products', 15)
                ->where('products', function ($products): bool {
                    $allowed = ['available', 'preview', 'research', 'planned', 'public-beta'];

                    foreach ($products as $product) {
                        if (! in_array($product['lifecycle'], $allowed, true)) {
                            return false;
                        }
                    }

                    return true;
                }));
    }

    public function test_cloudos_detail_exposes_simulation_and_commercial_cta_state(): void
    {
        $this->get('/products/kmj-cloudos')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/show')
                ->where('product.slug', 'kmj-cloudos')
                ->where('product.lifecycle', 'available')
                ->where('product.purchase_enabled', true)
                ->where('product.demo.kind', 'cloudos')
                ->where('product.demo.simulation', true));
    }

    public function test_calibration_detail_is_truthful_and_demo_first(): void
    {
        $this->get('/products/kmj-calibration-pro')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/show')
                ->where('product.slug', 'kmj-calibration-pro')
                ->where('product.lifecycle', 'preview')
                ->where('product.purchase_enabled', false)
                ->where('product.demo.kind', 'calibration')
                ->where('product.demo.simulation', true)
                ->where('product.truth.physical_capability_certified', false));
    }

    public function test_non_available_products_remain_non_commercial(): void
    {
        foreach ([
            'kmj-calibration-pro' => 'preview',
            'kmj-cinema-platform' => 'research',
            'kmj-360-dome' => 'research',
            'kmj-immersive-cinema-suite' => 'planned',
            'kmj-cinema-player' => 'research',
            'kmj-licensing-hub' => 'research',
            'kmj-forge' => 'research',
            'kmj-omnidesk' => 'research',
            'kmj-codebridge' => 'research',
            'kmj-desktop-commander' => 'public-beta',
            'kmj-connect' => 'planned',
            'kmj-cloud-nexus' => 'research',
            'kmj-agent' => 'research',
            'kmj-creative-studio' => 'planned',
        ] as $slug => $lifecycle) {
            $this->get('/products/'.$slug)
                ->assertOk()
                ->assertInertia(fn (Assert $page) => $page
                    ->component('products/show')
                    ->where('product.slug', $slug)
                    ->where('product.lifecycle', $lifecycle)
                    ->where('product.purchase_enabled', false));
        }
    }

    public function test_legacy_cinema_variant_urls_redirect_to_the_master_platform(): void
    {
        foreach (KmjProductCatalog::LEGACY_CINEMA_VARIANT_SLUGS as $slug) {
            $this->get('/products/'.$slug)
                ->assertRedirect('/products/'.KmjProductCatalog::CINEMA_PLATFORM_SLUG)
                ->assertStatus(301);
        }
    }

    public function test_unknown_product_is_not_found(): void
    {
        $this->get('/products/not-a-kmj-product')->assertNotFound();
    }
}
