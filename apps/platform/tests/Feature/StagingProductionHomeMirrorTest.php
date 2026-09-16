<?php

namespace Tests\Feature;

use App\Services\Staging\ProductionHomeMirror;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class StagingProductionHomeMirrorTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        Cache::flush();
        config()->set('services.kmj_staging_home_mirror.enabled', true);
        config()->set('services.kmj_staging_home_mirror.origin', 'https://kmjtechno.com');
        config()->set('services.kmj_staging_home_mirror.origin_ip', '138.252.200.74');
        config()->set('services.kmj_staging_home_mirror.cache_seconds', 30);
    }

    public function test_exact_staging_home_mirrors_production_html_without_upstream_headers(): void
    {
        Http::fake([
            'https://kmjtechno.com/' => Http::response(
                '<html><head><title>Production KMJ</title></head><body>LIVE-PRODUCTION-HOME <a href="/about">About</a></body></html>',
                200,
                ['Set-Cookie' => 'production-secret=cookie', 'X-Upstream-Secret' => 'hidden'],
            ),
        ]);

        $response = $this->get('https://staging.kmjtechno.com/');

        $response->assertOk();
        $response->assertSee('LIVE-PRODUCTION-HOME', false);
        $response->assertSee('<base href="https://staging.kmjtechno.com/">', false);
        $response->assertSee('<meta name="kmj-staging-mirror" content="production-home">', false);
        $response->assertHeader('X-Robots-Tag', 'noindex, nofollow');
        $response->assertHeaderMissing('X-Upstream-Secret');
        self::assertStringNotContainsString('production-secret=cookie', (string) $response->headers->get('Set-Cookie'));
    }

    public function test_non_staging_host_keeps_native_main_platform_home(): void
    {
        Http::preventStrayRequests();

        $this->get('https://kmjtechno.com/')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page->component('welcome'));
    }

    public function test_last_known_good_html_is_used_after_transient_origin_failure(): void
    {
        Http::fake([
            'https://kmjtechno.com/' => Http::response('<html><head></head><body>LAST-GOOD-HOME</body></html>'),
        ]);

        $this->get('https://staging.kmjtechno.com/')->assertOk()->assertSee('LAST-GOOD-HOME', false);

        Cache::forget(ProductionHomeMirror::FRESH_CACHE_KEY);
        Http::fake([
            'https://kmjtechno.com/' => Http::response('upstream unavailable', 503),
        ]);

        $this->get('https://staging.kmjtechno.com/')
            ->assertOk()
            ->assertSee('LAST-GOOD-HOME', false);
    }

    public function test_origin_failure_without_cached_copy_returns_safe_503(): void
    {
        Http::fake([
            'https://kmjtechno.com/' => Http::response('upstream unavailable', 503),
        ]);

        $this->get('https://staging.kmjtechno.com/')
            ->assertStatus(503)
            ->assertSee('Production homepage mirror is temporarily unavailable.');
    }

    public function test_unmatched_public_staging_path_mirrors_production_page(): void
    {
        Http::fake([
            'https://kmjtechno.com/about' => Http::response(
                '<html><head></head><body>PRODUCTION-ABOUT <a href="https://kmjtechno.com/contact">Contact</a></body></html>',
            ),
        ]);

        $this->get('https://staging.kmjtechno.com/about')
            ->assertOk()
            ->assertSee('PRODUCTION-ABOUT', false)
            ->assertSee('href="https://staging.kmjtechno.com/contact"', false)
            ->assertHeader('X-Robots-Tag', 'noindex, nofollow');
    }
}

// Temporary production-facing staging domain keeps public navigation on staging.
// Defined Main Platform routes (including /info) are registered before this fallback.
