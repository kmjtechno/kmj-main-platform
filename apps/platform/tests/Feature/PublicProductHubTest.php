<?php

namespace Tests\Feature;

use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class PublicProductHubTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_products_hub_leads_with_calibration_preview(): void
    {
        $this->get('/products')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/index')
                ->has('products', 1)
                ->where('products.0.slug', 'kmj-calibration-pro')
                ->where('products.0.name', 'KMJ Calibration Pro')
                ->where('products.0.lifecycle', 'development-preview')
                ->where('products.0.purchase_enabled', false)
                ->where('products.0.demo.kind', 'calibration')
                ->where('products.0.demo.simulation', true));
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
