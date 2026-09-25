<?php

namespace Tests\Feature;

use App\Services\Commerce\KmjProductCatalog;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class PublicSitemapTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
        app(KmjProductCatalog::class)->syncAll();
    }

    public function test_sitemap_fails_closed_when_public_indexing_is_disabled(): void
    {
        config()->set('app.public_indexing', false);

        $this->get('/sitemap.xml')->assertNotFound();
    }

    public function test_sitemap_exposes_canonical_public_and_product_urls(): void
    {
        config()->set('app.url', 'https://kmjtechno.example/');
        config()->set('app.public_indexing', true);

        $response = $this->get('/sitemap.xml');

        $response
            ->assertOk()
            ->assertHeader('content-type', 'application/xml; charset=UTF-8');

        $xml = $response->getContent();

        $this->assertIsString($xml);
        $this->assertStringContainsString(
            '<loc>https://kmjtechno.example/</loc>',
            $xml,
        );
        $this->assertStringContainsString(
            '<loc>https://kmjtechno.example/company</loc>',
            $xml,
        );
        $this->assertStringContainsString(
            '<loc>https://kmjtechno.example/capabilities</loc>',
            $xml,
        );
        $this->assertStringContainsString(
            '<loc>https://kmjtechno.example/products</loc>',
            $xml,
        );
        $this->assertStringContainsString(
            '<loc>https://kmjtechno.example/trust</loc>',
            $xml,
        );
        $this->assertStringContainsString(
            '<loc>https://kmjtechno.example/products/kmj-cloudos</loc>',
            $xml,
        );
        $this->assertStringContainsString(
            '<loc>https://kmjtechno.example/products/kmj-calibration-pro</loc>',
            $xml,
        );
        $this->assertSame(13, substr_count($xml, '<url>'));
    }
}
