<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiProvider;
use App\Services\AiProviders\EndpointGuard;
use App\Services\AiProviders\ProviderManager;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Tests\TestCase;

final class ModelFabricGithubModelsTest extends TestCase
{
    use RefreshDatabase;

    private string $org;

    protected function setUp(): void
    {
        parent::setUp();
        $this->org = (string) Str::uuid();
        DB::table('organizations')->insert(['id' => $this->org, 'name' => 'Org', 'created_at' => now(), 'updated_at' => now()]);
        $this->app->instance(EndpointGuard::class, new EndpointGuard(fn (): array => ['93.184.216.34']));
    }

    public function test_github_is_retired_and_never_admits_inference(): void
    {
        $presets = app(ProviderManager::class)->presets();

        $this->assertSame('none', $presets['github']['free_tier']);
        $this->assertTrue($presets['github']['retired']);
        $this->assertSame('https://models.github.ai/inference', $presets['github']['base_url']);
    }

    public function test_retired_provider_skips_network_and_clears_discovery(): void
    {
        Http::fake(['models.github.ai/*' => Http::response([
            ['id' => 'openai/gpt-4.1'],
            ['id' => 'meta/llama-3.3-70b-instruct'],
            ['id' => 'bad id!'],
        ], 200)]);
        $provider = AiProvider::query()->create([
            'organization_id' => $this->org,
            'name' => 'GitHub',
            'preset' => 'github',
            'kind' => 'openai-compatible',
            'base_url' => 'https://models.github.ai/inference',
            'api_key' => 'github_pat_test_key_123456',
            'key_last4' => '3456',
            'enabled' => true,
            'free_only' => true,
        ]);

        $tested = app(ProviderManager::class)->test($provider);

        Http::assertNothingSent();
        $this->assertSame('blocked', $tested->health);
        $this->assertSame('provider_retired', $tested->last_error_code);
        $this->assertNull($tested->models_cache);
        $this->assertSame([], app(ProviderManager::class)->admittedFreeModels($tested));
    }

    public function test_retired_provider_never_sends_credentials_even_if_catalog_returns_success(): void
    {
        Http::fake(['models.github.ai/*' => Http::response('OK', 200, ['Content-Type' => 'text/plain'])]);
        $provider = AiProvider::query()->create([
            'organization_id' => $this->org,
            'name' => 'GitHub',
            'preset' => 'github',
            'kind' => 'openai-compatible',
            'base_url' => 'https://models.github.ai/inference',
            'api_key' => 'github_pat_test_key_123456',
            'key_last4' => '3456',
            'enabled' => true,
            'free_only' => true,
        ]);

        $tested = app(ProviderManager::class)->test($provider);

        Http::assertNothingSent();
        $this->assertSame('blocked', $tested->health);
        $this->assertSame('provider_retired', $tested->last_error_code);
    }
}
