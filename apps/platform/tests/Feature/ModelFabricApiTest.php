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

    public function test_models_exposes_authenticated_scope_without_inference(): void
    {
        $this->evidenced('llama-free');
        Http::fake();

        $this->getJson('/api/modelfabric/v1/models', ['Authorization' => 'Bearer '.$this->token()])
            ->assertOk()->assertJsonPath('modelfabric.scope', 'private-source-coding')->assertJsonPath('modelfabric.free_routes', 1);
        $this->getJson('/api/modelfabric/v1/models', ['Authorization' => 'Bearer '.$this->token(['private_source' => false])])
            ->assertOk()->assertJsonPath('modelfabric.scope', 'general-chat')->assertJsonPath('modelfabric.free_routes', 1);
        Http::assertNothingSent();
    }

    public function test_strict_free_cloud_rejects_credit_routes_without_outbound_request(): void
    {
        $this->evidenced('llama-free');
        AiModelEvidence::query()->firstOrFail()->update(['cost_class' => 'credit-limited', 'credit_daily_cap' => 20]);
        Http::fake();
        $headers = ['Authorization' => 'Bearer '.$this->token(), 'X-ModelFabric-Policy' => 'strict-free-cloud'];

        $this->getJson('/api/modelfabric/v1/models', $headers)->assertOk()
            ->assertJsonPath('modelfabric.policy', 'strict-free-cloud')
            ->assertJsonPath('modelfabric.routes', 0);
        $this->postJson('/api/modelfabric/v1/chat/completions', ['messages' => [['role' => 'user', 'content' => 'ping']]], $headers)
            ->assertStatus(503)->assertJsonPath('error.code', 'NO_FREE_ROUTE_AVAILABLE');
        Http::assertNothingSent();
    }

    public function test_strict_free_cloud_requires_private_token_and_admitted_free_route(): void
    {
        $this->evidenced('vendor/model:free', 'no-training-documented', [
            'name' => 'OpenRouter', 'preset' => 'openrouter', 'base_url' => 'https://openrouter.ai/api/v1', 'models_cache' => ['vendor/model:free'],
        ]);
        $this->fakeNativeOpenRouter('pong');
        $body = ['messages' => [['role' => 'user', 'content' => 'ping']]];
        $headers = ['Authorization' => 'Bearer '.$this->token(), 'X-ModelFabric-Policy' => 'strict-free-cloud'];

        $this->getJson('/api/modelfabric/v1/models', $headers)->assertOk()
            ->assertJsonPath('modelfabric.free_routes', 1);
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, [...$headers, 'Authorization' => 'Bearer '.$this->token(['private_source' => false])])
            ->assertStatus(403);
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, [...$headers, 'X-ModelFabric-Policy' => 'unknown'])
            ->assertStatus(400);
        Http::assertNothingSent();
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, $headers)->assertOk()
            ->assertJsonPath('modelfabric.policy', 'strict-free-cloud')
            ->assertJsonPath('choices.0.message.content', 'pong');
        Http::assertSentCount(3);
        Http::assertSent(fn ($request): bool => $request->method() === 'POST'
            && $request['provider']['max_price']['prompt'] === 0
            && $request['provider']['max_price']['completion'] === 0
            && $request['provider']['allow_fallbacks'] === false
            && $request['provider']['data_collection'] === 'deny'
            && $request['provider']['zdr'] === true);
    }

    public function test_strict_coding_rejects_incomplete_provider_output(): void
    {
        $this->evidenced('vendor/model:free', 'no-training-documented', [
            'name' => 'OpenRouter', 'preset' => 'openrouter', 'base_url' => 'https://openrouter.ai/api/v1', 'models_cache' => ['vendor/model:free'],
        ]);
        $headers = ['Authorization' => 'Bearer '.$this->token(), 'X-ModelFabric-Policy' => 'strict-free-cloud'];
        $body = ['messages' => [['role' => 'user', 'content' => 'patch']], 'max_tokens' => 4096];
        $this->fakeNativeOpenRouter('partial patch', 'length');

        $this->postJson('/api/modelfabric/v1/chat/completions', [...$body, 'stream' => true], $headers)->assertStatus(400);
        $this->postJson('/api/modelfabric/v1/chat/completions', [...$body, 'max_tokens' => 4097], $headers)->assertStatus(422);
        Http::assertNothingSent();
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, $headers)
            ->assertStatus(502)->assertJsonPath('error.code', 'incomplete_coding_output');
        Http::assertSentCount(3);
        Http::assertSent(fn ($request): bool => $request->method() === 'POST' && $request['max_tokens'] === 4096);
    }

    public function test_strict_coding_does_not_silently_clip_a_complete_patch(): void
    {
        $this->evidenced('vendor/model:free', 'no-training-documented', [
            'name' => 'OpenRouter', 'preset' => 'openrouter', 'base_url' => 'https://openrouter.ai/api/v1', 'models_cache' => ['vendor/model:free'],
        ]);
        $headers = ['Authorization' => 'Bearer '.$this->token(), 'X-ModelFabric-Policy' => 'strict-free-cloud'];
        $content = str_repeat('x', 9000);
        $this->fakeNativeOpenRouter($content);

        $this->postJson('/api/modelfabric/v1/chat/completions', ['messages' => [['role' => 'user', 'content' => 'patch']], 'max_tokens' => 4096], $headers)
            ->assertOk()->assertJsonPath('choices.0.message.content', $content);
        Http::assertSentCount(3);
    }

    public function test_invalid_roles_fail_validation(): void
    {
        $headers = ['Authorization' => 'Bearer '.$this->token()];

        $this->postJson('/api/modelfabric/v1/chat/completions', ['messages' => [['role' => 'tool', 'content' => 'x']]], $headers)->assertStatus(422);
    }

    public function test_openrouter_general_chat_enforces_zero_price_ceiling_even_with_owner_evidence(): void
    {
        $plain = $this->token(['private_source' => false]);
        $this->evidenced('vendor/model:free', 'unknown', [
            'name' => 'OpenRouter',
            'preset' => 'openrouter',
            'base_url' => 'https://openrouter.ai/api/v1',
            'models_cache' => ['vendor/model:free'],
        ]);
        Http::fake([
            'openrouter.ai/*' => Http::response(['choices' => [['message' => ['content' => 'public reply']]]], 200),
        ]);

        $this->postJson('/api/modelfabric/v1/chat/completions', [
            'messages' => [['role' => 'user', 'content' => 'public synthetic prompt']],
        ], ['Authorization' => 'Bearer '.$plain])
            ->assertOk()->assertJsonPath('choices.0.message.content', 'public reply');

        Http::assertSentCount(1);
        Http::assertSent(fn ($request): bool =>
            (string) $request['model'] === 'vendor/model:free'
            && $request['provider']['allow_fallbacks'] === false
            && $request['provider']['max_price'] === [
                'prompt' => 0, 'completion' => 0, 'request' => 0, 'image' => 0,
            ]);
    }

    public function test_shared_api_automatically_fails_over_from_429_to_another_verified_free_provider(): void
    {
        $plain = $this->token(['private_source' => false]);
        $this->evidenced('model-a', 'unknown', [
            'name' => 'A Groq',
            'preset' => 'groq',
            'base_url' => 'https://api.groq.com/openai/v1',
            'models_cache' => ['model-a'],
        ]);
        $this->evidenced('model-b', 'unknown', [
            'name' => 'B Gemini',
            'preset' => 'gemini',
            'base_url' => 'https://generativelanguage.googleapis.com/v1beta/openai',
            'models_cache' => ['model-b'],
        ]);
        Http::fake([
            'api.groq.com/*' => Http::response(['error' => 'rate-limited'], 429, ['Retry-After' => '600']),
            'generativelanguage.googleapis.com/*' => Http::response([
                'choices' => [['message' => ['content' => 'free fallback succeeded']]],
            ], 200),
        ]);

        $this->postJson('/api/modelfabric/v1/chat/completions', [
            'messages' => [['role' => 'user', 'content' => 'public synthetic prompt']],
        ], ['Authorization' => 'Bearer '.$plain])
            ->assertOk()
            ->assertJsonPath('choices.0.message.content', 'free fallback succeeded')
            ->assertJsonPath('modelfabric.attempts', 2)
            ->assertJsonPath('modelfabric.provider', 'B Gemini');
        Http::assertSentCount(2);
        Http::assertNotSent(fn ($request): bool =>
            ! str_contains((string) $request->url(), 'api.groq.com')
            && ! str_contains((string) $request->url(), 'generativelanguage.googleapis.com'));
    }

    public function test_all_free_routes_rate_limited_returns_429_without_paid_fallback_and_resumes_after_reset(): void
    {
        $plain = $this->token(['private_source' => false]);
        $this->evidenced('llama-free');
        Http::fake([
            'api.groq.com/*' => Http::sequence()
                ->push(['error' => 'quota'], 429, ['Retry-After' => '900'])
                ->push(['choices' => [['message' => ['content' => 'resumed']]]], 200),
        ]);
        $headers = ['Authorization' => 'Bearer '.$plain];
        $body = ['messages' => [['role' => 'user', 'content' => 'public smoke']]];

        $this->postJson('/api/modelfabric/v1/chat/completions', $body, $headers)
            ->assertStatus(429)->assertJsonPath('error.code', 'rate_limited')
            ->assertHeader('Content-Type', 'application/json');
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, $headers)
            ->assertStatus(429)->assertJsonPath('error.code', 'all_routes_cooling_down');
        Http::assertSentCount(1);

        $this->travel(901)->seconds();
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, $headers)
            ->assertOk()->assertJsonPath('choices.0.message.content', 'resumed');
        Http::assertSentCount(2);
    }

    public function test_owner_daily_request_cap_reports_429_without_an_extra_provider_call(): void
    {
        $plain = $this->token(['private_source' => false]);
        $this->evidenced('llama-free');
        $provider = AiProvider::query()->firstOrFail();
        $provider->daily_request_cap = 1;
        $provider->save();
        Http::fake([
            'api.groq.com/*' => Http::response(['choices' => [['message' => ['content' => 'ok']]]], 200),
        ]);
        $headers = ['Authorization' => 'Bearer '.$plain];
        $body = ['messages' => [['role' => 'user', 'content' => 'public smoke']]];

        $this->postJson('/api/modelfabric/v1/chat/completions', $body, $headers)->assertOk();
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, $headers)
            ->assertStatus(429)->assertJsonPath('error.code', 'daily_cap_reached');
        Http::assertSentCount(1);
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

    public function test_native_coding_never_posts_to_an_unverified_provider(): void
    {
        $this->evidenced('llama-free');
        Http::fake();
        $headers = ['Authorization' => 'Bearer '.$this->token(), 'X-ModelFabric-Policy' => 'strict-free-cloud'];
        $this->postJson('/api/modelfabric/v1/chat/completions', ['messages' => [['role' => 'user', 'content' => 'private source']]], $headers)
            ->assertStatus(502)->assertJsonPath('error.code', 'native_account_unverified');
        Http::assertNothingSent();
    }

    public function test_native_coding_exhausted_quota_never_posts_source(): void
    {
        $this->evidenced('vendor/model:free', 'no-training-documented', [
            'name' => 'OpenRouter', 'preset' => 'openrouter', 'base_url' => 'https://openrouter.ai/api/v1', 'models_cache' => ['vendor/model:free'],
        ]);
        $this->fakeNativeOpenRouter('unused', 'stop', 0);
        $headers = ['Authorization' => 'Bearer '.$this->token(), 'X-ModelFabric-Policy' => 'strict-free-cloud'];
        $this->postJson('/api/modelfabric/v1/chat/completions', ['messages' => [['role' => 'user', 'content' => 'private source']]], $headers)
            ->assertStatus(502)->assertJsonPath('error.code', 'native_account_unverified');
        Http::assertSentCount(1);
        Http::assertNotSent(fn ($request): bool => $request->method() === 'POST');
    }

    public function test_native_ticket_is_bound_to_request_token_and_consumed_once(): void
    {
        $this->evidenced('vendor/model:free', 'no-training-documented', [
            'name' => 'OpenRouter', 'preset' => 'openrouter', 'base_url' => 'https://openrouter.ai/api/v1', 'models_cache' => ['vendor/model:free'],
        ]);
        $this->fakeNativeOpenRouter('complete patch');
        $token = $this->token();
        $headers = ['Authorization' => 'Bearer '.$token, 'X-ModelFabric-Policy' => 'strict-free-cloud'];
        $body = ['model' => 'modelfabric-auto', 'messages' => [['role' => 'user', 'content' => 'synthetic patch']], 'max_tokens' => 1024, 'stream' => false];
        $digest = hash('sha256', "https://kmjtechno.com/api/modelfabric/v1/chat/completions\n".$token."\n".json_encode($body, JSON_THROW_ON_ERROR));
        $response = $this->getJson('/api/modelfabric/v1/models', [...$headers, 'X-ModelFabric-Request-Digest' => $digest])->assertOk()
            ->assertJsonPath('modelfabric.native_admission.source', 'kmj_native_provider_admission')
            ->assertJsonPath('modelfabric.native_admission.request_digest', $digest)
            ->assertJsonPath('modelfabric.native_admission.requests_remaining', 5);
        $ticket = $response->json('modelfabric.native_admission.ticket');
        $this->assertIsString($ticket);
        $ticketHeaders = [...$headers, 'X-ModelFabric-Admission-Ticket' => $ticket];
        Http::assertSentCount(2);
        $this->postJson('/api/modelfabric/v1/chat/completions', [...$body, 'max_tokens' => 512], $ticketHeaders)->assertStatus(403);
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, [...$ticketHeaders, 'Authorization' => 'Bearer '.$this->token()])->assertStatus(403);
        Http::assertSentCount(2);
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, $ticketHeaders)->assertOk()->assertJsonPath('choices.0.message.content', 'complete patch');
        Http::assertSentCount(5);
        $this->postJson('/api/modelfabric/v1/chat/completions', $body, $ticketHeaders)->assertStatus(403);
        Http::assertSentCount(5);
    }

    public function test_native_ticket_is_not_issued_when_provider_remaining_quota_is_unknown(): void
    {
        $this->evidenced('vendor/model:free', 'no-training-documented', [
            'name' => 'OpenRouter', 'preset' => 'openrouter', 'base_url' => 'https://openrouter.ai/api/v1', 'models_cache' => ['vendor/model:free'],
        ]);
        Http::fake(['https://openrouter.ai/api/v1/key' => Http::response(['data' => ['is_free_tier' => true]])]);
        $headers = ['Authorization' => 'Bearer '.$this->token(), 'X-ModelFabric-Policy' => 'strict-free-cloud', 'X-ModelFabric-Request-Digest' => str_repeat('a', 64)];
        $this->getJson('/api/modelfabric/v1/models', $headers)->assertOk()
            ->assertJsonPath('modelfabric.native_admission', null);
        Http::assertSentCount(1);
        Http::assertNotSent(fn ($request): bool => $request->method() === 'POST');
    }

    private function fakeNativeOpenRouter(string $content, string $finish = 'stop', int $remaining = 5): void
    {
        $account = array_fill_keys(['usage', 'usage_daily', 'usage_weekly', 'usage_monthly', 'byok_usage', 'byok_usage_daily', 'byok_usage_weekly', 'byok_usage_monthly'], 0);
        Http::fake([
            'https://openrouter.ai/api/v1/key' => Http::response(['data' => $account + [
                'is_free_tier' => true,
                'is_management_key' => false,
                'is_provisioning_key' => false,
                'free_model_daily_requests' => ['limit' => 50, 'used' => 50 - $remaining, 'remaining' => $remaining],
            ]]),
            'https://openrouter.ai/api/v1/models*' => Http::response(['data' => [['id' => 'vendor/model:free', 'pricing' => ['prompt' => '0', 'completion' => '0', 'request' => '0']]]]),
            'https://openrouter.ai/api/v1/chat/completions' => Http::response(['choices' => [['message' => ['content' => $content], 'finish_reason' => $finish]]]),
        ]);
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

    /** @param array<string, mixed> $overrides */
    private function evidenced(string $model, string $handling = 'no-training-documented', array $overrides = []): void
    {
        $provider = AiProvider::query()->create($overrides + $this->providerRow());
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
