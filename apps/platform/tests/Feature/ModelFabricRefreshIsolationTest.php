<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiProvider;
use App\Services\AiProviders\EndpointGuard;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Tests\TestCase;

final class ModelFabricRefreshIsolationTest extends TestCase
{
    use RefreshDatabase;

    public function test_unreadable_provider_credential_does_not_stop_healthy_provider_refresh(): void
    {
        $org = (string) Str::uuid();
        DB::table('organizations')->insert(['id' => $org, 'name' => 'Org', 'created_at' => now(), 'updated_at' => now()]);
        $this->app->instance(EndpointGuard::class, new EndpointGuard(fn (): array => ['93.184.216.34']));

        $broken = $this->provider($org, 'Broken', '00000000-0000-4000-8000-000000000001');
        $healthy = $this->provider($org, 'Healthy', '00000000-0000-4000-8000-000000000002');
        DB::table('ai_providers')->where('id', $broken->id)->update(['api_key' => 'unreadable-test-ciphertext']);

        Http::fake(['api.groq.com/*' => Http::response(['data' => [['id' => 'test-model']]])]);

        $this->artisan('modelfabric:refresh')->assertSuccessful();

        Http::assertSentCount(1);
        Http::assertSent(fn ($request): bool => $request->method() === 'GET' && $request->body() === '');
        $this->assertSame('auth_failed', $broken->refresh()->health);
        $this->assertSame('credential_decrypt_failed', $broken->last_error_code);
        $this->assertNull($broken->models_cache);
        $this->assertNull($broken->models_checked_at);
        $this->assertSame('ok', $healthy->refresh()->health);
        $this->assertSame(['test-model'], $healthy->models_cache);
    }

    private function provider(string $org, string $name, string $id): AiProvider
    {
        return AiProvider::query()->create([
            'id' => $id,
            'organization_id' => $org,
            'name' => $name,
            'preset' => 'groq',
            'kind' => 'openai-compatible',
            'base_url' => 'https://api.groq.com/openai/v1',
            'api_key' => 'test-only-api-key',
            'key_last4' => '-key',
            'enabled' => true,
            'free_only' => true,
            'health' => 'ok',
            'models_cache' => ['old-model'],
            'models_checked_at' => now(),
        ]);
    }
}
