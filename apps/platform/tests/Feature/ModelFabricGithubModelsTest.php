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

    public function test_github_is_an_allowlist_preset_so_nothing_is_free_without_owner_evidence(): void
    {
        $presets = app(ProviderManager::class)->presets();

        $this->assertSame('allowlist', $presets['github']['free_tier']);
        $this->assertSame('https://models.github.ai/inference', $presets['github']['base_url']);
    }

    public function test_discovery_reads_the_bare_list_catalog_with_a_get_and_no_prompt(): void
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

        Http::assertSent(fn ($request): bool => $request->url() === 'https://models.github.ai/catalog/models'
            && $request->method() === 'GET'
            && $request->body() === '');
        $this->assertSame('ok', $tested->health);
        $this->assertSame(['meta/llama-3.3-70b-instruct', 'openai/gpt-4.1'], $tested->models_cache);
    }
}
