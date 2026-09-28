<?php

namespace Tests\Feature;

use Tests\TestCase;

use App\Services\Commerce\DesktopCommanderCommercialPolicy;

final class DesktopCommanderBootstrapTest extends TestCase
{
    public function test_static_bootstrap_matches_the_canonical_commercial_policy(): void
    {
        $path = public_path('commander/bootstrap.json');
        self::assertFileExists($path);
        self::assertSame(
            app(DesktopCommanderCommercialPolicy::class)->publicBootstrap(),
            json_decode((string) file_get_contents($path), true, flags: JSON_THROW_ON_ERROR),
        );
    }

    public function test_public_bootstrap_is_cacheable_local_first_and_free_by_default(): void
    {
        $this->getJson('/api/public/commander/bootstrap')
            ->assertOk()
            ->assertHeader('Cache-Control', 'public, max-age=3600, stale-while-revalidate=86400')
            ->assertJsonPath('schema', 1)
            ->assertJsonPath('product', 'kmj-desktop-commander')
            ->assertJsonPath('channel', 'public-beta')
            ->assertJsonPath('default_plan', 'free')
            ->assertJsonPath('billing_enabled', false)
            ->assertJsonPath('execution_model', 'local-first')
            ->assertJsonPath('entitlement_refresh_seconds', 604800)
            ->assertJsonPath('plans.free.manual_operations', 'unlimited')
            ->assertJsonPath('plans.free.autopilot_runs_per_month', 50)
            ->assertJsonPath('platform_support.windows', 'full')
            ->assertJsonPath('platform_support.linux', 'full')
            ->assertJsonPath('platform_support.macos', 'full')
            ->assertJsonPath('platform_support.android', 'companion')
            ->assertJsonPath('platform_support.ios', 'companion');
    }
}
