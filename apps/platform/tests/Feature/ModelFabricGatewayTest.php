<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiModelEvidence;
use App\Models\AiModelRequest;
use App\Models\AiProvider;
use App\Services\AiProviders\EndpointGuard;
use App\Services\AiProviders\ModelFabricGateway;
use App\Services\AiProviders\ProviderManager;
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

    public function test_quota_observations_are_from_fresh_headers_only_and_never_imply_credits(): void
    {
        $provider = $this->provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'model-a');
        $key = 'modelfabric:rate:'.hash('sha256', $provider->id.'|model-a');
        $gateway = app(ModelFabricGateway::class);

        $this->assertSame([], $gateway->quotaObservations($provider, ['model-a']));
        Cache::put($key, [
            'requests' => 13,
            'tokens' => 4500,
            'max_requests' => 20,
            'observed_at' => now()->toIso8601String(),
        ], 120);
        $observations = $gateway->quotaObservations($provider, ['model-a']);
        $this->assertCount(1, $observations);
        $this->assertSame(13, $observations[0]['requests_remaining']);
        $this->assertSame(4500, $observations[0]['tokens_remaining']);
        $this->assertNull($observations[0]['daily_reset_at']);
        $this->assertArrayNotHasKey('credit_balance', $observations[0]);
        Cache::forget($key);
        $this->assertSame([], $gateway->quotaObservations($provider, ['model-a']));
    }

    public function test_model_429_honours_provider_retry_after_and_shows_cooldown_without_quota_headers(): void
    {
        $provider = $this->provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'model-a');
        Http::fake([
            'api.groq.com/*' => Http::sequence()
                ->push(['error' => 'limit'], 429, [
                    'x-ratelimit-remaining-requests' => '0',
                    'Retry-After' => '600',
                ])
                ->push(['choices' => [['message' => ['content' => 'recovered']]]], 200),
        ]);

        $gateway = app(ModelFabricGateway::class);
        $result = $gateway->complete($this->org, [['role' => 'user', 'content' => 'ping']]);
        $this->assertFalse($result['ok']);
        $this->assertSame('rate_limited', $result['error_code']);
        $this->assertNull(ModelFabricGateway::coolingUntil($provider->id));

        // A 429 cooldown is local admission state, not a reported billing balance.
        Cache::forget('modelfabric:rate:'.hash('sha256', $provider->id.'|model-a'));
        $observations = $gateway->quotaObservations($provider, ['model-a']);
        $this->assertCount(1, $observations);
        $this->assertSame('model', $observations[0]['cooldown_scope']);
        $this->assertNull($observations[0]['requests_remaining']);
        $this->assertGreaterThanOrEqual(now()->addSeconds(580)->timestamp, strtotime($observations[0]['cooling_until']));
        $this->assertArrayNotHasKey('credit_balance', $observations[0]);
        $this->assertSame(0, $gateway->complete($this->org, [['role' => 'user', 'content' => 'again']])['attempts']);
        Http::assertSentCount(1);

        // After the provider reset, this same independently verified-free route
        // becomes eligible without requiring another account connection.
        $this->travel(601)->seconds();
        $recovered = $gateway->complete($this->org, [['role' => 'user', 'content' => 'resume']]);
        $this->assertTrue($recovered['ok']);
        $this->assertSame('recovered', $recovered['content']);
        Http::assertSentCount(2);
    }

    public function test_provider_429_honours_retry_after_and_does_not_attempt_while_cooling(): void
    {
        $provider = $this->provider('gemini', 'Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', 'model-a');
        Http::fake([
            'generativelanguage.googleapis.com/*' => Http::sequence()
                ->push(['error' => 'limit'], 429, ['Retry-After' => '900'])
                ->push(['choices' => [['message' => ['content' => 'recovered']]]], 200),
        ]);

        $gateway = app(ModelFabricGateway::class);
        $this->assertSame('rate_limited', $gateway->complete($this->org, [['role' => 'user', 'content' => 'ping']])['error_code']);
        $this->assertGreaterThanOrEqual(now()->addSeconds(880)->timestamp, ModelFabricGateway::coolingUntil($provider->id));
        $observations = $gateway->quotaObservations($provider, ['model-a']);
        $this->assertCount(1, $observations);
        $this->assertSame('provider', $observations[0]['cooldown_scope']);
        $this->assertNull($observations[0]['observed_at']);
        $this->assertSame(0, $gateway->complete($this->org, [['role' => 'user', 'content' => 'again']])['attempts']);
        Http::assertSentCount(1);

        $this->travel(901)->seconds();
        $recovered = $gateway->complete($this->org, [['role' => 'user', 'content' => 'resume']]);
        $this->assertTrue($recovered['ok']);
        $this->assertSame('recovered', $recovered['content']);
        Http::assertSentCount(2);
    }

    public function test_provider_daily_retry_after_86400_is_not_shortened_to_one_hour(): void
    {
        $provider = $this->provider('gemini', 'Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', 'model-a');
        Http::fake([
            'generativelanguage.googleapis.com/*' => Http::sequence()
                ->push(['error' => 'daily free tier exhausted'], 429, ['Retry-After' => '86400'])
                ->push(['choices' => [['message' => ['content' => 'after daily reset']]]], 200),
        ]);

        $gateway = app(ModelFabricGateway::class);
        $first = $gateway->complete($this->org, [['role' => 'user', 'content' => 'public smoke']]);
        $this->assertSame('rate_limited', $first['error_code']);
        $this->assertGreaterThanOrEqual(now()->addSeconds(86390)->timestamp, ModelFabricGateway::coolingUntil($provider->id));
        $this->assertGreaterThanOrEqual(86390, $first['retry_after_seconds'] ?? 0);
        $this->travel(3601)->seconds();
        $this->assertSame(0, $gateway->complete($this->org, [['role' => 'user', 'content' => 'early retry']])['attempts']);
        Http::assertSentCount(1);

        $this->travel(82800)->seconds();
        // Model discovery itself expires after 24 hours. The normal refresh job
        // must requalify that catalog independently before resuming inference.
        $provider->models_checked_at = now();
        $provider->save();
        $result = $gateway->complete($this->org, [['role' => 'user', 'content' => 'after reset']]);
        $this->assertTrue($result['ok']);
        $this->assertSame('after daily reset', $result['content']);
        Http::assertSentCount(2);
    }

    public function test_quota_directory_prioritizes_selected_admitted_model_beyond_first_twelve(): void
    {
        $provider = $this->provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'model-z');
        $provider->default_model = 'model-z';
        $provider->save();
        Cache::put('modelfabric:rate:'.hash('sha256', $provider->id.'|model-z'), [
            'requests' => 7,
            'tokens' => 1234,
            'max_requests' => 10,
            'observed_at' => now()->toIso8601String(),
        ], 120);
        $models = [...array_map(fn (int $n): string => 'model-'.$n, range(1, 13)), 'model-z'];

        $observations = app(ModelFabricGateway::class)->quotaObservations($provider, $models);
        $this->assertCount(1, $observations);
        $this->assertSame('model-z', $observations[0]['model']);
        $this->assertSame(7, $observations[0]['requests_remaining']);
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
        $groq = $this->provider('groq', 'A Groq', 'https://api.groq.com/openai/v1', 'llama-free');
        $gemini = $this->provider('gemini', 'B Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', 'gemini-free');
        Http::fake([
            'api.groq.com/*' => Http::response(['error' => 'slow down'], 429),
            'generativelanguage.googleapis.com/*' => Http::response(['choices' => [['message' => ['content' => 'pong']]]], 200),
        ]);

        $result = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'ping']]);

        $this->assertTrue($result['ok']);
        $this->assertSame('pong', $result['content']);
        $this->assertSame('B Gemini', $result['provider']);
        $this->assertSame(2, $result['attempts']);
        $this->assertNotNull(ModelFabricGateway::coolingUntil($groq->id));
        $this->assertNull(ModelFabricGateway::coolingUntil($gemini->id));
        $this->assertSame(2, AiModelRequest::query()->count());
        $this->assertSame(1, AiModelRequest::query()->where('error_code', 'rate_limited')->count());

        // The cooled provider is skipped next time: only one more request is sent, to Gemini.
        $second = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'ping']]);
        $this->assertSame('pong', $second['content']);
        $this->assertSame('B Gemini', $second['provider']);
        $this->assertSame(1, $second['attempts']);
        $this->assertSame(1, AiModelRequest::query()->where('error_code', 'rate_limited')->count());
    }

    public function test_groq_model_specific_daily_quota_falls_back_within_same_provider(): void
    {
        $groq = $this->provider('groq', 'A Groq', 'https://api.groq.com/openai/v1', 'model-a');
        $groq->models_cache = ['model-a', 'model-b'];
        $groq->save();
        AiModelEvidence::query()->create([
            'organization_id' => $this->org,
            'ai_provider_id' => $groq->id,
            'model_id' => 'model-b',
            'price_evidence_url' => 'https://example.com/pricing',
            'price_evidence_note' => 'Second model independently verified free.',
            'verified_at' => now(),
            'expires_at' => now()->addDays(10),
            'data_handling' => 'unknown',
            'capabilities' => ['chat'],
        ]);

        Http::fake([
            'api.groq.com/*' => Http::sequence()
                ->push(['error' => 'model-a quota exhausted'], 429, [
                    'x-ratelimit-remaining-requests' => '0',
                    'Retry-After' => '90',
                ])
                ->push(['choices' => [['message' => ['content' => 'model-b reply']]]], 200)
                ->push(['choices' => [['message' => ['content' => 'model-b again']]]], 200),
        ]);

        $first = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'hi']]);

        $this->assertTrue($first['ok']);
        $this->assertSame(2, $first['attempts']);
        $this->assertSame('model-b', $first['model']);
        $this->assertNull(ModelFabricGateway::coolingUntil($groq->id));

        // Model-a is cooling down, but another already-attested Groq model is still usable.
        $second = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'hi again']]);
        $this->assertSame('model-b', $second['model']);
        $this->assertSame(1, $second['attempts']);
        $this->assertSame(3, AiModelRequest::query()->count());
    }

    public function test_provider_is_deprioritised_before_its_limit_runs_out(): void
    {
        $this->provider('groq', 'A Groq', 'https://api.groq.com/openai/v1', 'llama-3.3-70b');
        $this->provider('gemini', 'B Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', 'gemini-2.5-flash');
        Http::fake([
            'api.groq.com/*' => Http::response(['choices' => [['message' => ['content' => 'a']]]], 200, ['x-ratelimit-remaining-requests' => '1']),
            'generativelanguage.googleapis.com/*' => Http::response(['choices' => [['message' => ['content' => 'b']]]], 200),
        ]);

        $first = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'hello']]);
        $second = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'hello']]);

        $this->assertSame('A Groq', $first['provider']);
        $this->assertSame('simple', $first['profile']);
        $this->assertSame('B Gemini', $second['provider']);
    }

    public function test_sticky_session_shifts_before_model_quota_is_exhausted(): void
    {
        $groq = $this->provider('groq', 'A Groq', 'https://api.groq.com/openai/v1', 'model-a');
        $groq->models_cache = ['model-a', 'model-b'];
        $groq->save();
        AiModelEvidence::query()->create([
            'organization_id' => $this->org,
            'ai_provider_id' => $groq->id,
            'model_id' => 'model-b',
            'price_evidence_url' => 'https://example.com/pricing',
            'price_evidence_note' => 'Second model independently verified free.',
            'verified_at' => now(),
            'expires_at' => now()->addDays(10),
            'data_handling' => 'unknown',
            'capabilities' => ['chat'],
        ]);

        Http::fake([
            'api.groq.com/*' => Http::sequence()
                ->push(['choices' => [['message' => ['content' => 'a']]]], 200, ['x-ratelimit-remaining-requests' => '1'])
                ->push(['choices' => [['message' => ['content' => 'b']]]], 200),
        ]);

        $gateway = app(ModelFabricGateway::class);
        $messages = [['role' => 'user', 'content' => 'hello']];
        $first = $gateway->complete($this->org, $messages, sessionKey: 'conversation');
        $second = $gateway->complete($this->org, $messages, sessionKey: 'conversation');

        $this->assertSame('model-a', $first['model']);
        $this->assertSame('model-b', $second['model']);
        $this->assertSame(1, $second['attempts']);
        Http::assertSentCount(2);
        $this->assertSame(0, AiModelRequest::query()->where('outcome', 'failed')->count());
    }

    public function test_sticky_session_shifts_at_eighty_percent_of_owner_daily_cap(): void
    {
        $groq = $this->provider('groq', 'A Groq', 'https://api.groq.com/openai/v1', 'model-a');
        $this->provider('gemini', 'B Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', 'model-b');
        $groq->daily_request_cap = 5;
        $groq->save();

        Http::fake([
            'api.groq.com/*' => Http::response(['choices' => [['message' => ['content' => 'a']]]], 200),
            'generativelanguage.googleapis.com/*' => Http::response(['choices' => [['message' => ['content' => 'b']]]], 200),
        ]);

        $gateway = app(ModelFabricGateway::class);
        $messages = [['role' => 'user', 'content' => 'hello']];
        for ($i = 0; $i < 4; $i++) {
            $result = $gateway->complete($this->org, $messages, sessionKey: 'conversation');
            $this->assertSame('A Groq', $result['provider']);
        }

        $shifted = $gateway->complete($this->org, $messages, sessionKey: 'conversation');
        $this->assertSame('B Gemini', $shifted['provider']);
        $this->assertSame(1, $shifted['attempts']);
        $this->assertSame(4, AiModelRequest::query()->where('ai_provider_id', $groq->id)->count());
        Http::assertSentCount(5);
    }

    public function test_documented_groq_daily_quota_outlives_short_rate_signal(): void
    {
        $this->provider('groq', 'A Groq', 'https://api.groq.com/openai/v1', 'model-a');
        $this->provider('gemini', 'B Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', 'model-b');
        Http::fake([
            'api.groq.com/*' => Http::response(['choices' => [['message' => ['content' => 'a']]]], 200, [
                'x-ratelimit-limit-requests' => '100',
                'x-ratelimit-remaining-requests' => '19',
                'x-ratelimit-reset-requests' => '10m0.5s',
            ]),
            'generativelanguage.googleapis.com/*' => Http::response(['choices' => [['message' => ['content' => 'b']]]], 200),
        ]);

        $gateway = app(ModelFabricGateway::class);
        $messages = [['role' => 'user', 'content' => 'hello']];
        $first = $gateway->complete($this->org, $messages, sessionKey: 'conversation');
        $this->assertSame('A Groq', $first['provider']);

        $this->travel(3)->minutes();
        $shifted = $gateway->complete($this->org, $messages, sessionKey: 'conversation');
        $this->assertSame('B Gemini', $shifted['provider']);
        $this->assertSame(1, $shifted['attempts']);
        Http::assertSentCount(2);
    }

    public function test_reported_zero_daily_quota_blocks_until_documented_reset(): void
    {
        $this->provider('groq', 'A Groq', 'https://api.groq.com/openai/v1', 'model-a');
        Http::fake([
            'api.groq.com/*' => Http::sequence()
                ->push(['choices' => [['message' => ['content' => 'last']]]], 200, [
                    'x-ratelimit-limit-requests' => '100',
                    'x-ratelimit-remaining-requests' => '0',
                    'x-ratelimit-reset-requests' => '10m0.5s',
                ])
                ->push(['choices' => [['message' => ['content' => 'renewed']]]], 200),
        ]);

        $gateway = app(ModelFabricGateway::class);
        $messages = [['role' => 'user', 'content' => 'hello']];
        $this->assertTrue($gateway->complete($this->org, $messages)['ok']);
        $this->travel(3)->minutes();
        $blocked = $gateway->complete($this->org, $messages);
        $this->assertSame('provider_daily_quota_exhausted', $blocked['error_code']);
        $this->assertSame(0, $blocked['attempts']);
        Http::assertSentCount(1);

        $this->travel(8)->minutes();
        $this->assertTrue($gateway->complete($this->org, $messages)['ok']);
        Http::assertSentCount(2);
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

    public function test_direct_provider_call_requires_single_use_gateway_reservation(): void
    {
        $provider = $this->provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'model-a');
        $messages = [['role' => 'user', 'content' => 'hi']];
        Http::fake(['api.groq.com/*' => Http::response(['choices' => [['message' => ['content' => 'ok']]]])]);
        $manager = app(ProviderManager::class);

        $this->assertSame('gateway_reservation_required', $manager->complete($provider, 'model-a', $messages)['error_code']);
        Http::assertNothingSent();

        $this->assertTrue(app(ModelFabricGateway::class)->completeSelected($provider, 'model-a', $messages)['ok']);
        $attempt = AiModelRequest::query()->firstOrFail();
        $this->assertSame('gateway_reservation_required', $manager->complete($provider, 'model-a', $messages, attempt: $attempt)['error_code']);
        Http::assertSentCount(1);
    }

    public function test_kilo_shared_hourly_cap_skips_route_without_sending_a_request(): void
    {
        $kilo = AiProvider::query()->create(array_replace(
            $this->providerRow('kilo-free', 'Kilo', 'https://ai-gateway.kilo.ai/api/v1', 'sample/public:free'),
            ['api_key' => '', 'key_last4' => ''],
        ));
        for ($i = 0; $i < 200; $i++) {
            AiModelRequest::query()->create([
                'organization_id' => $this->org,
                'ai_provider_id' => $kilo->id,
                'model_id' => 'sample/public:free',
                'outcome' => 'failed',
                'error_code' => 'attempt_reserved',
                'latency_ms' => 0,
            ]);
        }

        Http::fake();
        $result = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'hi']], publicPromptsConfirmed: true);

        $this->assertFalse($result['ok']);
        $this->assertSame('keyless_hourly_quota_exhausted', $result['error_code']);
        Http::assertNothingSent();
    }

    public function test_shared_keyless_quota_survives_connection_deletion_and_expires(): void
    {
        $row = array_replace(
            $this->providerRow('kilo-free', 'Kilo', 'https://ai-gateway.kilo.ai/api/v1', 'sample/public:free'),
            ['api_key' => '', 'key_last4' => ''],
        );
        $provider = AiProvider::query()->create($row);
        for ($i = 0; $i < 199; $i++) {
            DB::table('ai_shared_quota_reservations')->insert([
                'id' => (string) Str::uuid(),
                'scope' => 'kilo-free',
                'created_at' => now(),
            ]);
        }
        Http::fake(['ai-gateway.kilo.ai/*' => Http::response(['choices' => [['message' => ['content' => 'pong']]]], 200)]);
        $gateway = app(ModelFabricGateway::class);
        $messages = [['role' => 'user', 'content' => 'ping']];

        $this->assertTrue($gateway->complete($this->org, $messages, publicPromptsConfirmed: true)['ok']);
        $this->assertSame(200, ModelFabricGateway::kiloQuotaSnapshot()['used']);
        $provider->delete();
        AiProvider::query()->create($row);
        $this->assertSame(200, ModelFabricGateway::kiloQuotaSnapshot()['used']);
        $this->assertSame('keyless_hourly_quota_exhausted', $gateway->complete($this->org, $messages, publicPromptsConfirmed: true)['error_code']);
        Http::assertSentCount(1);

        DB::table('ai_shared_quota_reservations')->update(['created_at' => now()->subHours(3)]);
        $this->assertSame(0, ModelFabricGateway::kiloQuotaSnapshot()['used']);
        $this->assertTrue($gateway->complete($this->org, $messages, publicPromptsConfirmed: true)['ok']);
        $this->assertSame(1, ModelFabricGateway::kiloQuotaSnapshot()['used']);
        $this->assertDatabaseCount('ai_shared_quota_reservations', 1);
        Http::assertSentCount(2);
    }

    public function test_internal_private_source_invocation_requires_native_ticket_route_before_any_ledger_or_http(): void
    {
        $provider = $this->provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'model-a');
        Http::fake(['api.groq.com/*' => Http::response([
            'choices' => [['message' => ['content' => 'should never be dispatched']]],
        ], 200)]);
        $gateway = app(ModelFabricGateway::class);
        $messages = [['role' => 'user', 'content' => 'confidential code']];

        $this->assertSame('native_admission_required', $gateway->complete(
            $this->org, $messages, capability: 'code', privateSource: true,
        )['error_code']);
        $this->assertSame('native_admission_required', $gateway->complete(
            $this->org, $messages, capability: 'code', privateSource: true, strictFreeCloud: true,
        )['error_code']);
        $this->assertSame('native_admission_required', $gateway->complete(
            $this->org, $messages, capability: 'code', privateSource: true,
            nativeRoute: ['provider_id' => $provider->id, 'model' => 'model-a'],
        )['error_code']);

        Http::assertNothingSent();
        $this->assertSame(0, AiModelRequest::query()->count());
    }

    public function test_internal_mail_consent_requires_private_chat_and_never_authorizes_coding(): void
    {
        $provider = $this->provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'model-a');
        Http::fake(['api.groq.com/*' => Http::response([
            'choices' => [['message' => ['content' => 'consented editable mail reply']]],
        ], 200)]);
        $gateway = app(ModelFabricGateway::class);
        $messages = [['role' => 'user', 'content' => 'consented private correspondence']];

        $this->assertSame('native_admission_required', $gateway->complete(
            $this->org, $messages, capability: 'chat', privateSource: true,
        )['error_code']);
        $this->assertSame('native_admission_required', $gateway->complete(
            $this->org, $messages, capability: 'code', privateSource: true,
            strictFreeCloud: true, privateMailConsent: true,
            nativeRoute: ['provider_id' => $provider->id, 'model' => 'model-a'],
        )['error_code']);
        $this->assertSame('invalid_private_mail_policy', $gateway->complete(
            $this->org, $messages, privateMailConsent: true,
        )['error_code']);
        Http::assertNothingSent();
        $this->assertSame(0, AiModelRequest::query()->count());

        $result = $gateway->complete(
            $this->org, $messages, capability: 'chat',
            privateSource: true, privateMailConsent: true,
        );
        $this->assertTrue($result['ok']);
        $this->assertSame('consented editable mail reply', $result['content']);
        Http::assertSentCount(1);
        $this->assertDatabaseCount('ai_model_requests', 1);
    }

    public function test_consent_does_not_unlock_mail_content_when_no_training_evidence_is_missing(): void
    {
        $provider = $this->provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'model-a');
        AiModelEvidence::query()->where('ai_provider_id', $provider->id)
            ->update(['data_handling' => 'unknown']);
        Http::fake(['api.groq.com/*' => Http::response([
            'choices' => [['message' => ['content' => 'must stay private']]],
        ], 200)]);

        $result = app(ModelFabricGateway::class)->complete(
            $this->org,
            [['role' => 'user', 'content' => 'private mail']],
            capability: 'chat',
            privateSource: true,
            privateMailConsent: true,
        );
        $this->assertFalse($result['ok']);
        $this->assertSame('NO_FREE_ROUTE_AVAILABLE', $result['error_code']);
        $this->assertSame(0, AiModelRequest::query()->count());
        Http::assertNothingSent();
    }

    public function test_keyless_inference_requires_explicit_public_prompt_confirmation(): void
    {
        AiProvider::query()->create(array_replace(
            $this->providerRow('kilo-free', 'Kilo', 'https://ai-gateway.kilo.ai/api/v1', 'sample/public:free'),
            ['api_key' => '', 'key_last4' => ''],
        ));
        Http::fake(['ai-gateway.kilo.ai/*' => Http::response(['choices' => [['message' => ['content' => 'pong']]]], 200)]);
        $gateway = app(ModelFabricGateway::class);
        $messages = [['role' => 'user', 'content' => 'ping']];

        $this->assertSame('NO_FREE_ROUTE_AVAILABLE', $gateway->complete($this->org, $messages)['error_code']);
        $this->assertSame('native_admission_required', $gateway->complete($this->org, $messages, privateSource: true, publicPromptsConfirmed: true)['error_code']);
        Http::assertNothingSent();

        $this->assertTrue($gateway->complete($this->org, $messages, publicPromptsConfirmed: true)['ok']);
        Http::assertSentCount(1);
        Http::assertSent(fn ($request): bool => ! $request->hasHeader('Authorization'));
    }

    public function test_credit_models_share_the_lowest_daily_connection_cap(): void
    {
        $provider = $this->provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'model-a');
        $provider->models_cache = ['model-a', 'model-b'];
        $provider->save();
        AiModelEvidence::query()->where('ai_provider_id', $provider->id)->update([
            'cost_class' => 'credit-limited',
            'credit_daily_cap' => 1,
            'credit_hard_cap_attested_at' => now(),
        ]);
        AiModelEvidence::query()->create([
            'organization_id' => $this->org,
            'ai_provider_id' => $provider->id,
            'model_id' => 'model-b',
            'price_evidence_url' => 'https://example.com/pricing',
            'price_evidence_note' => 'Hard no-overage protection independently attested.',
            'verified_at' => now(),
            'expires_at' => now()->addDays(10),
            'data_handling' => 'unknown',
            'capabilities' => ['chat'],
            'cost_class' => 'credit-limited',
            'credit_daily_cap' => 5,
            'credit_hard_cap_attested_at' => now(),
        ]);
        AiModelRequest::query()->create([
            'organization_id' => $this->org,
            'ai_provider_id' => $provider->id,
            'model_id' => 'model-a',
            'outcome' => 'ok',
            'latency_ms' => 0,
        ]);

        Http::fake();
        $result = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'hi']]);

        $this->assertFalse($result['ok']);
        $this->assertSame('credit_cap_reached', $result['error_code']);
        Http::assertNothingSent();
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
