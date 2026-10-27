<?php

namespace Tests\Feature;

use App\Services\Commerce\KmjProductCatalog;
use App\Services\Seo\PublicInitialMetadata;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class PublicInitialMetadataTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
        app(KmjProductCatalog::class)->syncAll();
        config()->set('app.url', 'https://kmjtechno.example/');
    }

    public function test_public_home_has_crawlable_initial_metadata_before_javascript(): void
    {
        config()->set('app.public_indexing', true);

        $this->get('/')
            ->assertOk()
            ->assertSee('<title>KMJ TECHNO — Software, Mobile Apps, Cloud &amp; AI Engineering</title>', false)
            ->assertSee('<link rel="canonical" href="https://kmjtechno.example/">', false)
            ->assertSee('<meta property="og:url" content="https://kmjtechno.example/">', false)
            ->assertSee('<meta name="twitter:card" content="summary_large_image">', false)
            ->assertSee('<script type="application/ld+json">', false)
            ->assertDontSee('<meta name="robots" content="noindex,nofollow">', false);
    }

    public function test_product_metadata_comes_from_authoritative_public_catalog(): void
    {
        config()->set('app.public_indexing', true);

        $this->get('/products/kmj-cloudos')
            ->assertOk()
            ->assertSee('<link rel="canonical" href="https://kmjtechno.example/products/kmj-cloudos">', false)
            ->assertSee('<meta property="og:title" content="KMJ CloudOS — KMJ TECHNO">', false)
            ->assertSee('<meta property="og:image" content="https://kmjtechno.example/assets/products/kmj-cloudos.webp">', false);
    }

    public function test_legal_pages_have_server_metadata_and_staging_stays_noindex(): void
    {
        config()->set('app.public_indexing', false);

        $this->get('/privacy')
            ->assertOk()
            ->assertSee('<link rel="canonical" href="https://kmjtechno.example/privacy">', false)
            ->assertSee('<meta property="og:title" content="Privacy Policy — KMJ TECHNO">', false)
            ->assertSee('<meta name="robots" content="noindex,nofollow">', false);
    }

    public function test_private_pages_never_inherit_public_fallback_head(): void
    {
        config()->set('app.public_indexing', true);

        $this->get('/login')
            ->assertOk()
            ->assertDontSee('<link rel="canonical" href="https://kmjtechno.example/login">', false)
            ->assertDontSee('<meta property="og:url" content="https://kmjtechno.example/login">', false)
            ->assertSee('<meta name="robots" content="noindex,nofollow">', false);
    }

    public function test_unknown_and_untrusted_product_routes_fail_closed(): void
    {
        $seo = app(PublicInitialMetadata::class);

        $this->assertNull($seo->forPage([
            'component' => 'operator',
        ], 'https://kmjtechno.example'));

        $this->assertNull($seo->forPage([
            'component' => 'products/show',
            'props' => ['product' => ['slug' => '../dashboard', 'name' => 'X', 'summary' => 'Test']],
        ], 'https://kmjtechno.example'));

        $this->assertNull($seo->forPage([
            'component' => 'products/show',
            'props' => ['product' => ['slug' => 'kmj-test', 'name' => '', 'summary' => 'Test']],
        ], 'https://kmjtechno.example'));

        $safe = $seo->forPage([
            'component' => 'products/show',
            'props' => [
                'product' => [
                    'slug' => 'kmj-test',
                    'name' => '</script><img src=x onerror=alert(1)>',
                    'summary' => 'A public product description.',
                    'lifecycle_label' => 'Research',
                ],
            ],
        ], 'https://kmjtechno.example');

        $this->assertIsArray($safe);
        $this->assertStringNotContainsString('</script>', $safe['json_ld']);
        $this->assertStringContainsString('\\u003C', $safe['json_ld']);
        $this->assertStringNotContainsString('aggregateRating', $safe['json_ld']);
    }
}
