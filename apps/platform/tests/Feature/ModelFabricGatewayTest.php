<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiModelEvidence;
use App\Models\AiModelRequest;
use App\Models\AiProvider;
use App\Services\AiProviders\EndpointGuard;
use App\Services\AiProviders\ModelFabricGateway;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Tests\TestCase;

final class ModelFabricGatewayTest extends TestCase
{
    use RefreshDatabase;

    private string $org;

    protected function setUp(): void
    {
        parent::setUp();
        Cache::flush();
        $this->org = (string) Str::uuid();
        DB::table('organizations')->insert(['id' => $this->org, 'name' => 'Org', 'created_at' => now(), 'updated_at' => now()]);
        $this->app->instance(EndpointGuard::class, new EndpointGuard(fn (): array => ['93.184.216.34']));
    }

    public function test_no_route_means_no_provider_call_at_all(): void
    {
        Http::fake();

        $result = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'hi']]);

        $this->assertFalse($result['ok']);
        $this->assertSame('NO_FREE_ROUTE_AVAILABLE', $result['error_code']);
        Http::assertNothingSent();
        $this->assertSame(0, AiModelRequest::query()->count());
    }

    public function test_rate_limit_fails_over_to_the_next_verified_route_and_cools_the_first(): void
    {
        $groq = $this->provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'llama-free');
        $gemini = $this->provider('gemini', 'Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', 'gemini-free');
        Http::fake([
            'api.groq.com/*' => Http::response(['error' => 'slow down'], 429),
            'generativelanguage.googleapis.com/*' => Http::response(['choices' => [['message' => ['content' => 'pong']]]], 200),
        ]);

        $result = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'ping']]);

        $this->assertTrue($result['ok']);
        $this->assertSame('pong', $result['content']);
        $this->assertSame('Gemini', $result['provider']);
        $this->assertSame(2, $result['attempts']);
        $this->assertNotNull(ModelFabricGateway::coolingUntil($groq->id));
        $this->assertNull(ModelFabricGateway::coolingUntil($gemini->id));
        $this->assertSame(2, AiModelRequest::query()->count());
        $this->assertSame(1, AiModelRequest::query()->where('error_code', 'rate_limited')->count());

        // The cooled provider is skipped next time: no second request reaches it.
        Http::fake([
            'generativelanguage.googleapis.com/*' => Http::response(['choices' => [['message' => ['content' => 'again']]]], 200),
        ]);
        $second = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'ping']]);
        $this->assertSame('again', $second['content']);
        $this->assertSame(1, $second['attempts']);
    }

    public function test_unevidenced_model_is_never_sent_even_when_a_provider_is_healthy(): void
    {
        Http::fake();
        AiProvider::query()->create($this->providerRow('groq', 'Groq', 'https://api.groq.com/openai/v1', 'llama-free'));

        $result = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'x']]);

        $this->assertSame('NO_FREE_ROUTE_AVAILABLE', $result['error_code']);
        Http::assertNothingSent();
    }

    public function test_rejected_key_stops_routing_until_the_owner_retests(): void
    {
        $groq = $this->provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'llama-free');
        Http::fake(['api.groq.com/*' => Http::response([], 401)]);

        $first = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'x']]);

        $this->assertSame('auth_failed', $first['error_code']);
        $this->assertSame('auth_failed', $groq->fresh()->health);
        $second = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'x']]);
        $this->assertSame('NO_FREE_ROUTE_AVAILABLE', $second['error_code']);
    }

    public function test_request_ledger_stores_metadata_only(): void
    {
        $this->provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'llama-free');
        Http::fake(['api.groq.com/*' => Http::response(['choices' => [['message' => ['content' => 'secret-answer']]]], 200)]);

        app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'secret-prompt']]);

        $row = (string) json_encode(AiModelRequest::query()->firstOrFail()->toArray());
        $this->assertStringNotContainsString('secret-prompt', $row);
        $this->assertStringNotContainsString('secret-answer', $row);
        $this->assertStringNotContainsString('sk-test', $row);
    }

    private function provider(string $preset, string $name, string $baseUrl, string $model): AiProvider
    {
        $provider = AiProvider::query()->create($this->providerRow($preset, $name, $baseUrl, $model));
        AiModelEvidence::query()->create([
            'organization_id' => $this->org,
            'ai_provider_id' => $provider->id,
            'model_id' => $model,
            'price_evidence_url' => 'https://example.com/pricing',
            'price_evidence_note' => 'Pricing page lists this model at zero cost.',
            'verified_at' => now(),
            'expires_at' => now()->addDays(10),
            'data_handling' => 'unknown',
            'capabilities' => ['chat'],
        ]);

        return $provider;
    }

    /** @return array<string, mixed> */
    private function providerRow(string $preset, string $name, string $baseUrl, string $model): array
    {
        return [
            'organization_id' => $this->org,
            'name' => $name,
            'preset' => $preset,
            'kind' => 'openai-compatible',
            'base_url' => $baseUrl,
            'api_key' => 'sk-test-key-123456',
            'key_last4' => '3456',
            'enabled' => true,
            'free_only' => true,
            'health' => 'ok',
            'health_checked_at' => now(),
            'models_cache' => [$model],
            'models_checked_at' => now(),
        ];
    }
}
