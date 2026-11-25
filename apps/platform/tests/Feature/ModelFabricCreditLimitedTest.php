<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiModelEvidence;
use App\Models\AiProvider;
use App\Models\User;
use App\Services\AiProviders\EndpointGuard;
use App\Services\AiProviders\ModelFabricGateway;
use App\Services\AiProviders\ResolvesAiProviderScope;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Tests\Support\FakeAiProviderScope;
use Tests\TestCase;

/** ADR-004 revision 2: credit-limited approvals carry a KMJ-side daily cap the gateway enforces. */
final class ModelFabricCreditLimitedTest extends TestCase
{
    use RefreshDatabase;

    private string $org;

    private User $owner;

    protected function setUp(): void
    {
        parent::setUp();
        Cache::flush();
        $this->org = (string) Str::uuid();
        DB::table('organizations')->insert(['id' => $this->org, 'name' => 'Org', 'created_at' => now(), 'updated_at' => now()]);
        $this->app->instance(EndpointGuard::class, new EndpointGuard(fn (): array => ['93.184.216.34']));
        $this->owner = $this->platformOwner();
        $this->app->instance(ResolvesAiProviderScope::class, new FakeAiProviderScope([
            $this->owner->id => ['organization_id' => $this->org, 'can_manage' => true],
        ]));
    }

    public function test_a_credit_limited_approval_needs_a_cap_and_the_hard_cap_attestation(): void
    {
        $provider = $this->provider('Credit', 'models/credit-a');
        $base = $this->payload($provider, 'models/credit-a');

        $this->confirmed()->post('/operator/modelfabric/evidence', $base)->assertSessionHasErrors('credit_daily_cap');
        $this->confirmed()->post('/operator/modelfabric/evidence', [...$base, 'credit_daily_cap' => 100])->assertSessionHasErrors('credit_hard_cap_attested');
        $this->confirmed()->post('/operator/modelfabric/evidence', [...$base, 'credit_daily_cap' => 0, 'credit_hard_cap_attested' => true])->assertSessionHasErrors('credit_daily_cap');
        $this->assertSame(0, AiModelEvidence::query()->count());

        $this->confirmed()->post('/operator/modelfabric/evidence', [...$base, 'credit_daily_cap' => 100, 'credit_hard_cap_attested' => true])
            ->assertSessionHasNoErrors();

        $row = AiModelEvidence::query()->firstOrFail();
        $this->assertSame('credit-limited', $row->cost_class);
        $this->assertSame(100, $row->credit_daily_cap);
        $this->assertNotNull($row->credit_hard_cap_attested_at);
    }

    public function test_a_free_approval_stays_free_and_drops_any_credit_fields(): void
    {
        $provider = $this->provider('Free', 'models/free-a');
        $payload = [...$this->payload($provider, 'models/free-a'), 'cost_class' => 'free', 'credit_daily_cap' => 5];

        $this->confirmed()->post('/operator/modelfabric/evidence', $payload)->assertSessionHasNoErrors();

        $row = AiModelEvidence::query()->firstOrFail();
        $this->assertSame('free', $row->cost_class);
        $this->assertNull($row->credit_daily_cap);
        $this->assertNull($row->credit_hard_cap_attested_at);
    }

    public function test_a_credit_limited_row_without_a_cap_is_never_called(): void
    {
        $provider = $this->provider('Credit', 'models/credit-a');
        AiModelEvidence::query()->create([...$this->evidenceRow($provider, 'models/credit-a'), 'cost_class' => 'credit-limited']);
        Http::fake();

        $result = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'hi']]);

        $this->assertFalse($result['ok']);
        $this->assertSame('credit_cap_reached', $result['error_code']);
        Http::assertNothingSent();
    }

    public function test_the_gateway_never_calls_a_credit_route_at_its_daily_cap(): void
    {
        $provider = $this->provider('Credit', 'models/credit-a');
        $this->credit($provider, 'models/credit-a', 2);
        $this->logRequests($provider, 'models/credit-a', 2);
        Http::fake();

        $result = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'hi']]);

        $this->assertFalse($result['ok']);
        $this->assertSame('credit_cap_reached', $result['error_code']);
        Http::assertNothingSent();
    }

    public function test_a_credit_route_under_its_cap_is_used_and_counts_toward_it(): void
    {
        $provider = $this->provider('Credit', 'models/credit-a');
        $this->credit($provider, 'models/credit-a', 3);
        Http::fake(['generativelanguage.googleapis.com/*' => Http::response(['choices' => [['message' => ['content' => 'pong']]]], 200)]);

        foreach ([1, 2, 3] as $ignored) {
            $this->assertTrue(app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'ping']])['ok']);
        }
        $fourth = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'ping']]);

        $this->assertFalse($fourth['ok']);
        $this->assertSame('credit_cap_reached', $fourth['error_code']);
        Http::assertSentCount(3);
    }

    public function test_inflight_credit_attempt_consumes_the_last_slot_before_inference(): void
    {
        $provider = $this->provider('Credit', 'models/credit-a');
        $this->credit($provider, 'models/credit-a', 1);
        $nested = null;
        Http::fake(['generativelanguage.googleapis.com/*' => function () use (&$nested, $provider) {
            $this->assertSame(1, DB::table('ai_model_requests')->where('ai_provider_id', $provider->id)->where('error_code', 'attempt_reserved')->count());
            $nested = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'concurrent request']]);

            return Http::response(['choices' => [['message' => ['content' => 'pong']]]], 200);
        }]);

        $result = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'ping']]);

        $this->assertTrue($result['ok']);
        $this->assertFalse($nested['ok']);
        $this->assertSame('credit_cap_reached', $nested['error_code']);
        Http::assertSentCount(1);
        $this->assertSame(1, DB::table('ai_model_requests')->where('ai_provider_id', $provider->id)->where('outcome', 'ok')->count());
    }

    public function test_interrupted_reservation_is_not_refunded_or_replayed(): void
    {
        $provider = $this->provider('Credit', 'models/credit-a');
        $this->credit($provider, 'models/credit-a', 1);
        DB::table('ai_model_requests')->insert([
            'id' => (string) Str::uuid(),
            'organization_id' => $this->org,
            'ai_provider_id' => $provider->id,
            'model_id' => 'models/credit-a',
            'outcome' => 'failed',
            'error_code' => 'attempt_reserved',
            'latency_ms' => 0,
            'created_at' => now(),
        ]);
        Http::fake();

        $result = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'ping']]);

        $this->assertFalse($result['ok']);
        $this->assertSame('credit_cap_reached', $result['error_code']);
        Http::assertNothingSent();
    }

    public function test_a_credit_route_at_eighty_percent_sinks_behind_a_free_route(): void
    {
        $credit = $this->provider('A Credit', 'models/credit-a');
        $free = $this->provider('B Free', 'models/free-a');
        $this->credit($credit, 'models/credit-a', 5);
        $this->free($free, 'models/free-a');
        $this->logRequests($credit, 'models/credit-a', 4);
        Http::fake(['generativelanguage.googleapis.com/*' => Http::response(['choices' => [['message' => ['content' => 'pong']]]], 200)]);

        $result = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'ping']]);

        $this->assertTrue($result['ok']);
        $this->assertSame('B Free', $result['provider']);
        $this->assertSame(1, $result['attempts']);
    }

    public function test_renewing_a_credit_row_needs_a_fresh_hard_cap_attestation(): void
    {
        $provider = $this->provider('Credit', 'models/credit-a');
        $row = $this->credit($provider, 'models/credit-a', 10);

        $this->confirmed()->post('/operator/modelfabric/evidence/'.$row->id.'/renew', ['attest_pricing' => true])->assertSessionHasErrors('evidence');
        $before = $row->refresh()->credit_hard_cap_attested_at;

        $this->confirmed()->post('/operator/modelfabric/evidence/'.$row->id.'/renew', ['attest_pricing' => true, 'credit_hard_cap_attested' => true])
            ->assertSessionHasNoErrors();

        $this->assertTrue($row->refresh()->credit_hard_cap_attested_at->greaterThanOrEqualTo($before));
        $this->assertSame('credit-limited', $row->cost_class);
    }

    public function test_bulk_approval_is_free_only_and_resets_the_class(): void
    {
        $provider = $this->provider('Credit', 'models/credit-a');
        $row = $this->credit($provider, 'models/credit-a', 10);

        $this->confirmed()->post('/operator/modelfabric/evidence/bulk', [
            'provider_id' => $provider->id,
            'model_ids' => ['models/credit-a'],
            'price_evidence_url' => 'https://example.com/free',
            'price_evidence_note' => 'Pricing page lists this model as free.',
            'valid_days' => 14,
            'data_handling' => 'unknown',
            'capabilities' => ['chat'],
            'attest_pricing' => true,
        ])->assertSessionHasNoErrors();

        $row->refresh();
        $this->assertSame('free', $row->cost_class);
        $this->assertNull($row->credit_daily_cap);
        $this->assertNull($row->credit_hard_cap_attested_at);
    }

    /** @return array<string, mixed> */
    private function payload(AiProvider $provider, string $model): array
    {
        return [
            'provider_id' => $provider->id,
            'model_id' => $model,
            'price_evidence_url' => 'https://example.com/credits',
            'price_evidence_note' => 'Page shows free credits and no payment method on file.',
            'valid_days' => 14,
            'data_handling' => 'unknown',
            'capabilities' => ['chat'],
            'cost_class' => 'credit-limited',
        ];
    }

    /** @return array<string, mixed> */
    private function evidenceRow(AiProvider $provider, string $model): array
    {
        return [
            'organization_id' => $this->org,
            'ai_provider_id' => $provider->id,
            'model_id' => $model,
            'price_evidence_url' => 'https://example.com/credits',
            'price_evidence_note' => 'Page shows free credits and no payment method on file.',
            'verified_at' => now(),
            'expires_at' => now()->addDays(10),
            'data_handling' => 'unknown',
            'capabilities' => ['chat'],
        ];
    }

    private function credit(AiProvider $provider, string $model, int $cap): AiModelEvidence
    {
        return AiModelEvidence::query()->create([
            ...$this->evidenceRow($provider, $model),
            'cost_class' => 'credit-limited',
            'credit_daily_cap' => $cap,
            'credit_hard_cap_attested_at' => now(),
        ]);
    }

    private function free(AiProvider $provider, string $model): AiModelEvidence
    {
        return AiModelEvidence::query()->create($this->evidenceRow($provider, $model));
    }

    private function logRequests(AiProvider $provider, string $model, int $count): void
    {
        for ($i = 0; $i < $count; $i++) {
            DB::table('ai_model_requests')->insert([
                'id' => (string) Str::uuid(),
                'organization_id' => $this->org,
                'ai_provider_id' => $provider->id,
                'model_id' => $model,
                'outcome' => 'ok',
                'latency_ms' => 10,
                'created_at' => now(),
            ]);
        }
    }

    private function provider(string $name, string $model): AiProvider
    {
        return AiProvider::query()->create([
            'organization_id' => $this->org,
            'name' => $name,
            'preset' => 'gemini',
            'kind' => 'openai-compatible',
            'base_url' => 'https://generativelanguage.googleapis.com/v1beta/openai',
            'api_key' => 'sk-test-key-123456',
            'key_last4' => '3456',
            'enabled' => true,
            'free_only' => true,
            'health' => 'ok',
            'health_checked_at' => now(),
            'models_cache' => [$model],
            'models_checked_at' => now(),
        ]);
    }

    private function confirmed(): static
    {
        return $this->actingAs($this->owner)->withSession(['auth.password_confirmed_at' => time()]);
    }

    private function platformOwner(): User
    {
        $user = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $user->id,
            'name' => 'ModelFabric test passkey',
            'credential_id' => 'mf-'.Str::random(12),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $user;
    }
}
