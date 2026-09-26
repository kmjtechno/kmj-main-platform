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

    public function test_homepage_exposes_the_canonical_public_product_portfolio(): void
    {
        $this->get('/')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('welcome')
                ->where('portfolioCount', 11)
                ->has('products', 4)
                ->where('products.0.slug', 'kmj-cloudos')
                ->where('products.0.purchase_enabled', true)
                ->where('products.1.slug', 'kmj-calibration-pro')
                ->where('products.1.purchase_enabled', false)
                ->where('products.2.slug', 'kmj-cinema-platform')
                ->where('products.2.lifecycle', 'development')
                ->where('products.2.variants.0', '5D')
                ->where('products.2.variants.6', '5DX')
                ->where('products.3.slug', 'kmj-licensing-hub')
                ->where('products.3.lifecycle', 'roadmap')
                ->where('products.3.purchase_enabled', false));
    }

    public function test_products_hub_exposes_truthful_lifecycle_for_all_roadmap_products(): void
    {
        $this->get('/products')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/index')
                ->has('products', 11)
                ->where('products.0.slug', 'kmj-cloudos')
                ->where('products.0.lifecycle', 'active')
                ->where('products.0.demo.kind', 'cloudos')
                ->where('products.0.demo.simulation', true)
                ->where('products.1.slug', 'kmj-calibration-pro')
                ->where('products.1.lifecycle', 'development-preview')
                ->where('products.1.demo.kind', 'calibration')
                ->where('products.1.demo.simulation', true)
                ->where('products.2.slug', 'kmj-forge')
                ->where('products.2.lifecycle', 'early-development')
                ->where('products.2.demo.kind', 'none')
                ->where('products.2.demo.simulation', false)
                ->where('products.3.slug', 'kmj-connect')
                ->where('products.3.lifecycle', 'planned')
                ->where('products.3.demo.kind', 'none')
                ->where('products.3.demo.simulation', false)
                ->where('products.4.slug', 'kmj-cloud-nexus')
                ->where('products.4.lifecycle', 'development')
                ->where('products.4.demo.kind', 'none')
                ->where('products.4.demo.simulation', false)
                ->where('products.5.slug', 'kmj-agent')
                ->where('products.5.lifecycle', 'development')
                ->where('products.5.demo.kind', 'none')
                ->where('products.5.demo.simulation', false)
                ->where('products.6.slug', 'kmj-creative-studio')
                ->where('products.6.lifecycle', 'roadmap')
                ->where('products.6.demo.kind', 'none')
                ->where('products.6.demo.simulation', false)
                ->where('products.7.slug', 'kmj-cinema-platform')
                ->where('products.7.lifecycle', 'development')
                ->where('products.7.category', 'Media & Immersive Experience')
                ->where('products.7.demo.kind', 'none')
                ->where('products.7.demo.simulation', false)
                ->where('products.7.variants.0', '5D')
                ->where('products.7.variants.1', '7D')
                ->where('products.7.variants.2', '9D')
                ->where('products.7.variants.3', '12D')
                ->where('products.7.variants.4', '14D')
                ->where('products.7.variants.5', '16D')
                ->where('products.7.variants.6', '5DX')
                ->where('products.8.slug', 'kmj-360-dome')
                ->where('products.8.lifecycle', 'roadmap')
                ->where('products.9.slug', 'kmj-cinema-player')
                ->where('products.9.category', 'Media & Immersive Experience')
                ->where('products.10.slug', 'kmj-licensing-hub')
                ->where('products.10.category', 'Commerce & Licensing')
                ->where('products.10.lifecycle', 'roadmap'));
    }

    public function test_cloudos_detail_exposes_simulation_and_commercial_cta_state(): void
    {
        $this->get('/products/kmj-cloudos')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/show')
                ->where('product.slug', 'kmj-cloudos')
                ->where('product.lifecycle', 'active')
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
                ->where('product.lifecycle', 'development-preview')
                ->where('product.purchase_enabled', false)
                ->where('product.demo.kind', 'calibration')
                ->where('product.demo.simulation', true)
                ->where('product.truth.physical_capability_certified', false));
    }

    public function test_development_products_remain_non_commercial_and_without_fake_demo(): void
    {
        foreach ([
            'kmj-forge' => 'early-development',
            'kmj-connect' => 'planned',
            'kmj-cloud-nexus' => 'development',
            'kmj-agent' => 'development',
            'kmj-creative-studio' => 'roadmap',
            'kmj-cinema-platform' => 'development',
            'kmj-360-dome' => 'roadmap',
            'kmj-cinema-player' => 'roadmap',
            'kmj-licensing-hub' => 'roadmap',
        ] as $slug => $lifecycle) {
            $this->get('/products/'.$slug)
                ->assertOk()
                ->assertInertia(fn (Assert $page) => $page
                    ->component('products/show')
                    ->where('product.slug', $slug)
                    ->where('product.lifecycle', $lifecycle)
                    ->where('product.purchase_enabled', false)
                    ->where('product.demo.kind', 'none')
                    ->where('product.demo.simulation', false));
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
