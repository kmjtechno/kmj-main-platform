<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiModelEvidence;
use App\Models\AiModelToken;
use App\Models\AiProvider;
use App\Services\AiProviders\EndpointGuard;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Tests\TestCase;

final class ModelFabricApiTest extends TestCase
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

    public function test_requests_without_a_valid_token_are_rejected_and_nothing_is_sent(): void
    {
        Http::fake();
        $body = ['messages' => [['role' => 'user', 'content' => 'hi']]];

        $this->postJson('/api/modelfabric/v1/chat/completions', $body)->assertStatus(401);
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, ['Authorization' => 'Bearer nope'])->assertStatus(401);
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, ['Authorization' => 'Bearer '.AiModelToken::PREFIX.'unknown'])->assertStatus(401);
        Http::assertNothingSent();
    }

    public function test_expired_and_revoked_tokens_stop_working(): void
    {
        $expired = $this->token(['expires_at' => now()->subMinute()]);
        $revoked = $this->token(['revoked_at' => now()]);
        $body = ['messages' => [['role' => 'user', 'content' => 'hi']]];

        $this->postJson('/api/modelfabric/v1/chat/completions', $body, ['Authorization' => 'Bearer '.$expired])->assertStatus(401);
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, ['Authorization' => 'Bearer '.$revoked])->assertStatus(401);
    }

    public function test_no_evidence_means_503_no_free_route_and_no_provider_call(): void
    {
        Http::fake();
        $plain = $this->token();
        AiProvider::query()->create($this->providerRow());

        $this->postJson('/api/modelfabric/v1/chat/completions', ['messages' => [['role' => 'user', 'content' => 'hi']]], ['Authorization' => 'Bearer '.$plain])
            ->assertStatus(503)
            ->assertJsonPath('error.code', 'NO_FREE_ROUTE_AVAILABLE');
        Http::assertNothingSent();
    }

    public function test_verified_route_answers_in_openai_shape_and_ignores_requested_model(): void
    {
        $plain = $this->token(['private_source' => false]);
        $this->evidenced('llama-free');
        Http::fake(['api.groq.com/*' => Http::response(['choices' => [['message' => ['content' => 'pong']]]], 200)]);

        $response = $this->postJson('/api/modelfabric/v1/chat/completions', [
            'model' => 'gpt-5-paid-premium',
            'messages' => [['role' => 'user', 'content' => 'ping']],
        ], ['Authorization' => 'Bearer '.$plain]);

        $response->assertOk()
            ->assertJsonPath('object', 'chat.completion')
            ->assertJsonPath('model', 'llama-free')
            ->assertJsonPath('choices.0.message.content', 'pong');
        Http::assertSent(fn ($request): bool => ! str_contains((string) json_encode($request->data()), 'gpt-5-paid-premium'));
    }

    public function test_private_source_token_needs_no_training_evidence(): void
    {
        $plain = $this->token(['private_source' => true]);
        $this->evidenced('llama-free', 'unknown');
        Http::fake();

        $this->postJson('/api/modelfabric/v1/chat/completions', ['messages' => [['role' => 'user', 'content' => 'secret code']]], ['Authorization' => 'Bearer '.$plain])
            ->assertStatus(503);
        Http::assertNothingSent();
    }

    public function test_streaming_replays_the_verified_answer_as_sse_and_errors_stay_json(): void
    {
        $plain = $this->token(['private_source' => false]);
        $headers = ['Authorization' => 'Bearer '.$plain];
        $this->evidenced('llama-free');
        Http::fake(['api.groq.com/*' => Http::response(['choices' => [['message' => ['content' => str_repeat('pong ', 30)]]]], 200)]);

        $response = $this->postJson('/api/modelfabric/v1/chat/completions', ['stream' => true, 'model' => 'gpt-5-paid-premium', 'messages' => [['role' => 'user', 'content' => 'ping']]], $headers);
        $response->assertOk();
        $this->assertStringStartsWith('text/event-stream', (string) $response->headers->get('Content-Type'));
        $body = $response->streamedContent();
        $this->assertStringContainsString('"object":"chat.completion.chunk"', $body);
        $this->assertStringContainsString('"finish_reason":"stop"', $body);
        $this->assertStringEndsWith("data: [DONE]\n\n", $body);
        $text = '';
        foreach (explode("\n\n", trim($body)) as $event) {
            $json = json_decode(substr($event, 6), true);
            $text .= is_array($json) ? (string) ($json['choices'][0]['delta']['content'] ?? '') : '';
        }
        $this->assertSame(str_repeat('pong ', 30), $text);
        Http::assertSentCount(1);
        Http::assertSent(fn ($request): bool => ! str_contains((string) json_encode($request->data()), 'gpt-5-paid-premium'));

        Cache::flush();
        DB::table('ai_model_evidence')->delete();
        Http::fake();
        $this->postJson('/api/modelfabric/v1/chat/completions', ['stream' => true, 'messages' => [['role' => 'user', 'content' => 'x']]], $headers)
            ->assertStatus(503)->assertJsonPath('error.code', 'NO_FREE_ROUTE_AVAILABLE');
    }

    public function test_sticky_session_prefers_the_last_answering_route_but_never_admits_anything(): void
    {
        $plain = $this->token(['private_source' => false]);
        $headers = ['Authorization' => 'Bearer '.$plain, 'X-ModelFabric-Session' => 'conv-1'];
        $this->evidenced('llama-free');
        Http::fake(['api.groq.com/*' => Http::response(['choices' => [['message' => ['content' => 'pong']]]], 200)]);
        $body = ['messages' => [['role' => 'user', 'content' => 'ping']]];

        $this->postJson('/api/modelfabric/v1/chat/completions', $body, $headers)->assertOk();
        $this->assertNotNull(Cache::get('modelfabric:sticky:'.hash('sha256', $this->org.'|conv-1')));
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, ['Authorization' => 'Bearer '.$plain, 'X-ModelFabric-Session' => 'bad session!'])->assertOk();
        $this->assertNull(Cache::get('modelfabric:sticky:'.hash('sha256', $this->org.'|bad session!')));

        DB::table('ai_model_evidence')->delete();
        Http::fake();
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, $headers)->assertStatus(503)->assertJsonPath('error.code', 'NO_FREE_ROUTE_AVAILABLE');
        Http::assertNothingSent();
    }

    public function test_unsupported_protocol_controls_never_send_a_provider_request(): void
    {
        $headers = ['Authorization' => 'Bearer '.$this->token(['private_source' => false])];
        $this->evidenced('llama-free');
        Http::fake();
        $body = ['messages' => [['role' => 'user', 'content' => 'ping']]];

        foreach (['tools' => [], 'max_tokens' => 10, 'response_format' => ['type' => 'json_object'], 'n' => 2] as $field => $value) {
            $this->postJson('/api/modelfabric/v1/chat/completions', [...$body, $field => $value], $headers)
                ->assertStatus(400)->assertJsonPath('error.code', 'unsupported_parameter');
        }
        $this->postJson('/api/modelfabric/v1/chat/completions', ['messages' => [['role' => 'assistant', 'content' => 'x', 'tool_calls' => []]]], $headers)
            ->assertStatus(422);
        Http::assertNothingSent();
    }

    public function test_private_source_model_preflight_requires_coding_capability(): void
    {
        $this->evidenced('llama-free');
        AiModelEvidence::query()->firstOrFail()->update(['capabilities' => ['chat']]);
        Http::fake();

        $this->getJson('/api/modelfabric/v1/models', ['Authorization' => 'Bearer '.$this->token()])
            ->assertOk()->assertJsonPath('modelfabric.status', 'NO_FREE_ROUTE_AVAILABLE')->assertJsonPath('modelfabric.routes', 0);
        $this->getJson('/api/modelfabric/v1/models', ['Authorization' => 'Bearer '.$this->token(['private_source' => false])])
            ->assertOk()->assertJsonPath('modelfabric.status', 'ROUTE_AVAILABLE')->assertJsonPath('modelfabric.routes', 1);
        Http::assertNothingSent();
    }

    public function test_invalid_roles_fail_validation(): void
    {
        $headers = ['Authorization' => 'Bearer '.$this->token()];

        $this->postJson('/api/modelfabric/v1/chat/completions', ['messages' => [['role' => 'tool', 'content' => 'x']]], $headers)->assertStatus(422);
    }

    public function test_token_is_rate_limited_per_minute(): void
    {
        $plain = $this->token();
        $headers = ['Authorization' => 'Bearer '.$plain];

        for ($i = 0; $i < 60; $i++) {
            $this->getJson('/api/modelfabric/v1/models', $headers)->assertOk();
        }
        $this->getJson('/api/modelfabric/v1/models', $headers)->assertStatus(429)->assertHeader('Retry-After');
    }

    public function test_only_the_hash_of_the_token_is_stored(): void
    {
        $plain = $this->token();

        $row = (string) json_encode(DB::table('ai_model_tokens')->get()->all());
        $this->assertStringNotContainsString($plain, $row);
        $this->assertSame(AiModelToken::hash($plain), AiModelToken::query()->firstOrFail()->token_hash);
    }

    /** @param array<string, mixed> $overrides */
    private function token(array $overrides = []): string
    {
        $plain = AiModelToken::PREFIX.Str::random(48);
        AiModelToken::query()->create($overrides + [
            'organization_id' => $this->org,
            'name' => 'worker',
            'token_hash' => AiModelToken::hash($plain),
            'token_prefix' => substr($plain, 0, 12),
            'private_source' => true,
            'expires_at' => now()->addDays(5),
        ]);

        return $plain;
    }

    private function evidenced(string $model, string $handling = 'no-training-documented'): void
    {
        $provider = AiProvider::query()->create($this->providerRow());
        AiModelEvidence::query()->create([
            'organization_id' => $this->org,
            'ai_provider_id' => $provider->id,
            'model_id' => $model,
            'price_evidence_url' => 'https://example.com/pricing',
            'price_evidence_note' => 'Pricing page lists this model at zero cost.',
            'verified_at' => now(),
            'expires_at' => now()->addDays(10),
            'data_handling' => $handling,
            'capabilities' => ['chat', 'code'],
        ]);
    }

    /** @return array<string, mixed> */
    private function providerRow(): array
    {
        return [
            'organization_id' => $this->org,
            'name' => 'Groq',
            'preset' => 'groq',
            'kind' => 'openai-compatible',
            'base_url' => 'https://api.groq.com/openai/v1',
            'api_key' => 'sk-test-key-123456',
            'key_last4' => '3456',
            'enabled' => true,
            'free_only' => true,
            'health' => 'ok',
            'health_checked_at' => now(),
            'models_cache' => ['llama-free'],
            'models_checked_at' => now(),
        ];
    }
}
