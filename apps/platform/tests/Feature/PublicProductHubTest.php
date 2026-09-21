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

    public function test_products_hub_exposes_cloudos_and_calibration_with_truthful_lifecycle(): void
    {
        $this->get('/products')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/index')
                ->has('products', 2)
                ->where('products.0.slug', 'kmj-cloudos')
                ->where('products.0.lifecycle', 'active')
                ->where('products.0.purchase_enabled', true)
                ->where('products.0.demo.kind', 'cloudos')
                ->where('products.0.demo.simulation', true)
                ->where('products.1.slug', 'kmj-calibration-pro')
                ->where('products.1.lifecycle', 'development-preview')
                ->where('products.1.purchase_enabled', false)
                ->where('products.1.demo.kind', 'calibration')
                ->where('products.1.demo.simulation', true));
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

    public function test_unknown_product_is_not_found(): void
    {
        $this->get('/products/not-a-kmj-product')->assertNotFound();
    }
}
