<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class PublishedPriceTest extends TestCase
{
    use RefreshDatabase;

    public function test_public_product_page_receives_only_the_owner_approved_price_list(): void
    {
        $this->withoutVite();

        $this->get('/products/kmj-codebridge')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/show')
                ->where('pricing.plans.1.name', 'Pro')
                ->where('pricing.plans.1.monthly_minor', 29900));

        $this->get('/products/kmj-licensing-hub')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page->where('pricing', null));
    }
}
