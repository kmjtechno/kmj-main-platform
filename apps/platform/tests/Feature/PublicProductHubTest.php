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
                ->has('products', 8)
                ->where('products.0.slug', 'kmj-cloudos')
                ->where('products.0.purchase_enabled', true)
                ->where('products.1.slug', 'kmj-calibration-pro')
                ->where('products.1.purchase_enabled', false)
                ->where('products.2.slug', 'kmj-forge')
                ->where('products.2.lifecycle', 'early-development')
                ->where('products.2.purchase_enabled', false)
                ->where('products.3.slug', 'kmj-connect')
                ->where('products.3.lifecycle', 'planned')
                ->where('products.3.purchase_enabled', false)
                ->where('products.4.slug', 'kmj-cloud-nexus')
                ->where('products.4.lifecycle', 'development')
                ->where('products.4.purchase_enabled', false)
                ->where('products.5.slug', 'kmj-agent')
                ->where('products.5.lifecycle', 'development')
                ->where('products.5.purchase_enabled', false)
                ->where('products.6.slug', 'kmj-creative-studio')
                ->where('products.6.lifecycle', 'roadmap')
                ->where('products.6.purchase_enabled', false)
                ->where('products.7.slug', 'kmj-cinema-platform')
                ->where('products.7.lifecycle', 'development')
                ->where('products.7.purchase_enabled', false));
    }

    public function test_products_hub_exposes_truthful_lifecycle_for_all_roadmap_products(): void
    {
        $this->get('/products')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/index')
                ->has('products', 17)
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
                ->where('products.8.slug', 'kmj-360-dome')
                ->where('products.8.lifecycle', 'roadmap')
                ->where('products.9.slug', 'kmj-5d-cinema')
                ->where('products.10.slug', 'kmj-7d-cinema')
                ->where('products.11.slug', 'kmj-9d-cinema')
                ->where('products.12.slug', 'kmj-12d-cinema')
                ->where('products.13.slug', 'kmj-14d-cinema')
                ->where('products.14.slug', 'kmj-16d-cinema')
                ->where('products.15.slug', 'kmj-5dx-cinema')
                ->where('products.16.slug', 'kmj-cinema-player')
                ->where('products.16.category', 'Media & Immersive Experience'));
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
            'kmj-5d-cinema' => 'roadmap',
            'kmj-7d-cinema' => 'roadmap',
            'kmj-9d-cinema' => 'roadmap',
            'kmj-12d-cinema' => 'roadmap',
            'kmj-14d-cinema' => 'roadmap',
            'kmj-16d-cinema' => 'roadmap',
            'kmj-5dx-cinema' => 'roadmap',
            'kmj-cinema-player' => 'roadmap',
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

    public function test_unknown_product_is_not_found(): void
    {
        $this->get('/products/not-a-kmj-product')->assertNotFound();
    }
}
