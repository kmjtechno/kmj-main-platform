<?php

namespace Tests\Feature;

use App\Services\Commerce\KmjProductCatalog;
use App\Services\Commerce\PublicProductCatalog;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class ProductDiscoveryContentTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
        app(KmjProductCatalog::class)->syncAll();
        config()->set('app.url', 'https://kmjtechno.example');
    }

    public function test_available_product_publishes_visible_answers_prices_and_breadcrumbs(): void
    {
        config()->set('services.kmj_signup_trial.enabled', true);

        $this->get('/products/kmj-cloudos')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('access', 'trial')
                ->where('answers.0.question', 'What is KMJ CloudOS?')
                ->where('answers.2.question', 'How much does KMJ CloudOS cost?'))
            ->assertSee('<noscript>', false)
            ->assertSee('₹499 + GST per organization per month')
            ->assertSee('"@type":"FAQPage"', false)
            ->assertSee('"@type":"BreadcrumbList"', false)
            ->assertDontSee('"@type":"Offer"', false);
    }

    public function test_trial_is_not_promised_when_it_is_switched_off(): void
    {
        config()->set('services.kmj_signup_trial.enabled', false);

        $this->get('/products/kmj-cloudos')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page->where('access', 'request'))
            ->assertDontSee('30-day free trial');
    }

    public function test_unreleased_product_never_reads_as_on_sale(): void
    {
        $this->get('/products/kmj-codebridge')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page->where('access', 'preregister'))
            ->assertSee('Planned prices, not on sale yet')
            ->assertSee('is not on sale');

        $this->get('/llms.txt')
            ->assertOk()
            ->assertSee('Planned prices (not on sale), GST extra')
            ->assertSee('Summary: ');
    }

    public function test_product_list_publishes_every_public_product_with_prices(): void
    {
        $this->get('/products')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/index')
                ->where('pricing.kmj-cloudos.plans.0.name', 'Professional'))
            ->assertSee('"@type":"ItemList"', false)
            ->assertSee('https://kmjtechno.example/products/kmj-omnidesk', false)
            ->assertSee('<noscript>', false);
    }

    public function test_catalog_wording_stays_short_and_free_of_internal_terms(): void
    {
        $products = app(PublicProductCatalog::class)->all();
        $this->assertNotEmpty($products);

        foreach ($products as $product) {
            $text = $product['headline'].' '.$product['summary'].' '.$product['truth']['status'].' '.json_encode($product['proof']);
            $this->assertDoesNotMatchRegularExpression('/canonical|fail-closed behavior|governed|authority/i', (string) preg_replace('/"state":"[^"]*"/', '', $text), $product['slug']);
            $this->assertLessThanOrEqual(170, mb_strlen($product['summary']), $product['slug']);
        }
    }
}
