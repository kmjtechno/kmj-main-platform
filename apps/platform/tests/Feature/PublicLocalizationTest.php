<?php

namespace Tests\Feature;

use App\Services\Commerce\KmjProductCatalog;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class PublicLocalizationTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
        app(KmjProductCatalog::class)->syncAll();
    }

    public function test_supported_hindi_locale_is_shared_and_persisted(): void
    {
        $this->get('/hi/products')
            ->assertOk()
            ->assertCookie('kmj_locale')
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/index')
                ->where('localization.locale', 'hi')
                ->where('localization.switch_locale', 'en')
                ->where('localization.switch_label', 'English')
                ->where('localization.switch_url', '/en/products'));
    }

    public function test_legacy_query_locale_remains_supported(): void
    {
        $this->get('/products?lang=hi')
            ->assertOk()
            ->assertCookie('kmj_locale')
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/index')
                ->where('localization.locale', 'hi')
                ->where('localization.switch_url', '/en/products'));
    }

    public function test_localized_corporate_surfaces_receive_hindi_locale(): void
    {
        foreach ([
            '/hi/' => 'welcome',
            '/hi/company' => 'company',
            '/hi/capabilities' => 'capabilities',
            '/hi/trust' => 'trust',
            '/hi/products/kmj-cloudos' => 'products/show',
        ] as $path => $component) {
            $this->get($path)
                ->assertOk()
                ->assertCookie('kmj_locale')
                ->assertInertia(fn (Assert $page) => $page
                    ->component($component)
                    ->where('localization.locale', 'hi')
                    ->where('localization.switch_locale', 'en'));
        }
    }

    public function test_unsupported_locale_fails_closed_to_supported_default(): void
    {
        $this->get('/products?lang=ur')
            ->assertOk()
            ->assertCookieMissing('kmj_locale')
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/index')
                ->where('localization.locale', 'en')
                ->where('localization.switch_locale', 'hi')
                ->where('localization.switch_label', 'हिंदी'));
    }
}
