<?php

namespace Tests\Feature;

use App\Services\Commerce\KmjProductCatalog;
use App\Services\Commerce\PublicProductCatalog;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class PublicAiDiscoveryTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        app(KmjProductCatalog::class)->syncAll();
    }

    public function test_llms_txt_exposes_verified_product_authority_and_lifecycle_boundaries(): void
    {
        $response = $this->get('/llms.txt');

        $response
            ->assertOk()
            ->assertHeader('content-type', 'text/plain; charset=UTF-8');

        $body = $response->getContent();

        self::assertIsString($body);
        self::assertStringContainsString('# KMJ TECHNO', $body);
        self::assertStringContainsString('INNOVATE | BUILD | SCALE', $body);
        self::assertStringContainsString('Roadmap, development and preview labels must not be interpreted as production availability.', $body);
        // Canonical public categories and lifecycle labels are resolved from
        // owner-managed product records. Assert the rendered public discovery
        // lines against that authority, not stale hard-coded labels.
        $publicProducts = app(PublicProductCatalog::class)->all();
        self::assertCount(15, $publicProducts);

        $slugs = array_column($publicProducts, 'slug');
        foreach ([
            KmjProductCatalog::DOME_SLUG,
            KmjProductCatalog::CINEMA_PLATFORM_SLUG,
            KmjProductCatalog::CINEMA_PLAYER_SLUG,
            KmjProductCatalog::IMMERSIVE_CINEMA_SUITE_SLUG,
            KmjProductCatalog::LICENSING_HUB_SLUG,
            KmjProductCatalog::DESKTOP_COMMANDER_SLUG,
        ] as $slug) {
            self::assertContains($slug, $slugs);
        }

        foreach ($publicProducts as $product) {
            $variants = isset($product['variants']) && is_array($product['variants'])
                ? ' | Configurations: '.implode(', ', $product['variants'])
                : '';

            self::assertStringContainsString(
                sprintf(
                    '- %s | %s | %s%s | https://kmjtechno.com/products/%s',
                    $product['name'],
                    $product['category'],
                    $product['lifecycle_label'],
                    $variants,
                    $product['slug'],
                ),
                $body,
            );
        }

        self::assertStringContainsString('https://kmjtechno.com/products/kmj-codebridge/terms', $body);
        self::assertStringContainsString('https://kmjtechno.com/products/kmj-codebridge/privacy', $body);
        self::assertStringContainsString('https://kmjtechno.com/products/kmj-codebridge/support', $body);
        self::assertSame(count($publicProducts) + 3, substr_count($body, 'https://kmjtechno.com/products/'));
    }
}
