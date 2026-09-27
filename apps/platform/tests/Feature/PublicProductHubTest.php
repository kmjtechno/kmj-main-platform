<?php

namespace Tests\Feature;

use App\Services\Commerce\KmjProductCatalog;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Inertia\Testing\AssertableInertia as Assert;
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
                ->has('products', 12)
                ->where('products.0.slug', 'kmj-cloudos')
                ->where('products.0.lifecycle', 'available')
                ->where('products.0.purchase_enabled', true)
                ->where('products.1.slug', 'kmj-calibration-pro')
                ->where('products.1.lifecycle', 'preview')
                ->where('products.2.slug', 'kmj-cinema-platform')
                ->where('products.2.lifecycle', 'research')
                ->where('products.3.slug', 'kmj-360-dome')
                ->where('products.3.lifecycle', 'research')
                ->where('products.4.slug', 'kmj-immersive-cinema-suite')
                ->where('products.4.lifecycle', 'planned')
                ->where('products.5.slug', 'kmj-cinema-player')
                ->where('products.5.lifecycle', 'research')
                ->where('products.6.slug', 'kmj-licensing-hub')
                ->where('products.6.lifecycle', 'research')
                ->where('products.7.slug', 'kmj-forge')
                ->where('products.7.lifecycle', 'research')
                ->where('products.8.slug', 'kmj-connect')
                ->where('products.8.lifecycle', 'planned')
                ->where('products.9.slug', 'kmj-cloud-nexus')
                ->where('products.9.lifecycle', 'research')
                ->where('products.10.slug', 'kmj-agent')
                ->where('products.10.lifecycle', 'research')
                ->where('products.11.slug', 'kmj-creative-studio')
                ->where('products.11.lifecycle', 'planned'));
    }

    public function test_products_hub_uses_only_canonical_public_lifecycle_vocabulary(): void
    {
        $this->get('/products')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/index')
                ->has('products', 12)
                ->where('products', function (array $products): bool {
                    $allowed = ['available', 'preview', 'research', 'planned'];

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

    public function test_unknown_product_is_not_found(): void
    {
        $this->get('/products/not-a-kmj-product')->assertNotFound();
    }
}
