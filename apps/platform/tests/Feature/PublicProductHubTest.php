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
                ->has('products', 6)
                ->where('products.0.slug', 'kmj-cloudos')
                ->where('products.0.purchase_enabled', true)
                ->where('products.1.slug', 'kmj-calibration-pro')
                ->where('products.2.slug', 'kmj-cloud-nexus')
                ->where('products.3.slug', 'kmj-forge')
                ->where('products.4.slug', 'kmj-agent')
                ->where('products.5.slug', 'kmj-connect'));
    }

    public function test_products_hub_exposes_the_full_truthful_portfolio(): void
    {
        $this->get('/products')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/index')
                ->has('products', 6)
                ->where('products.0.slug', 'kmj-cloudos')
                ->where('products.0.lifecycle', 'active')
                ->where('products.0.purchase_enabled', true)
                ->where('products.0.demo.kind', 'cloudos')
                ->where('products.1.slug', 'kmj-calibration-pro')
                ->where('products.1.lifecycle', 'development-preview')
                ->where('products.1.purchase_enabled', false)
                ->where('products.1.demo.kind', 'calibration')
                ->where('products.2.slug', 'kmj-cloud-nexus')
                ->where('products.2.lifecycle', 'development')
                ->where('products.2.demo.kind', 'none')
                ->where('products.3.slug', 'kmj-forge')
                ->where('products.3.lifecycle', 'early-development')
                ->where('products.4.slug', 'kmj-agent')
                ->where('products.4.lifecycle', 'development')
                ->where('products.5.slug', 'kmj-connect')
                ->where('products.5.lifecycle', 'planned-development'));
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

    public function test_development_products_publish_status_without_fake_demo_or_purchase(): void
    {
        foreach ([
            'kmj-cloud-nexus' => 'development',
            'kmj-forge' => 'early-development',
            'kmj-agent' => 'development',
            'kmj-connect' => 'planned-development',
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