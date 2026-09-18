<?php

namespace Tests\Feature;

use Illuminate\Support\Facades\Http;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class StagingNativeMainPlatformTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
        config()->set('services.kmj_staging_home_mirror.enabled', true);
        config()->set('services.kmj_staging_home_mirror.origin', 'https://kmjtechno.com');
    }

    public function test_staging_root_serves_native_main_platform_instead_of_legacy_site(): void
    {
        Http::fake(['https://kmjtechno.com/' => Http::response('<html>LEGACY-KMJ-SITE</html>')]);

        $this->get('https://staging.kmjtechno.com/')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page->component('welcome'));
    }


    public function test_live_public_surface_does_not_expose_operations_monitor(): void
    {
        $this->get('https://staging.kmjtechno.com/info')->assertNotFound();
        $this->get('https://staging.kmjtechno.com/info/status')->assertNotFound();
    }

    public function test_unknown_staging_public_path_does_not_fall_back_to_legacy_site(): void
    {
        Http::fake(['https://kmjtechno.com/*' => Http::response('<html>LEGACY-KMJ-SITE</html>')]);

        $this->get('https://staging.kmjtechno.com/legacy-only-page')
            ->assertNotFound();
    }
}
