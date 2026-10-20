<?php

namespace Tests\Feature;

use App\Services\Commerce\KmjProductCatalog;
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
        self::assertStringContainsString('KMJ 360 Dome | Cinema & Immersive | Research', $body);
        self::assertStringContainsString(
            'KMJ Cinema Platform | Cinema & Immersive | Research | Configurations: 5D, 7D, 9D, 12D, 14D, 16D, 5DX',
            $body,
        );
        self::assertStringContainsString('KMJ Cinema Player | Cinema & Immersive | Research', $body);
        self::assertStringContainsString('KMJ Licensing Hub | Business & Platform | Research', $body);
        self::assertStringNotContainsString('KMJ Desktop Commander |', $body);
        self::assertStringContainsString('https://kmjtechno.com/products/kmj-codebridge/terms', $body);
        self::assertStringContainsString('https://kmjtechno.com/products/kmj-codebridge/privacy', $body);
        self::assertStringContainsString('https://kmjtechno.com/products/kmj-codebridge/support', $body);
        self::assertSame(17, substr_count($body, 'https://kmjtechno.com/products/'));
    }
}
