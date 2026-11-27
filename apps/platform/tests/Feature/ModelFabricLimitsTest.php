<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiModelEvidence;
use App\Models\AiModelRequest;
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

final class ModelFabricLimitsTest extends TestCase
{
    use RefreshDatabase;

    private string $org;

    private User $owner;

    private User $member;

    protected function setUp(): void
    {
        parent::setUp();
        Cache::flush();
        $this->org = (string) Str::uuid();
        DB::table('organizations')->insert(['id' => $this->org, 'name' => 'Org', 'created_at' => now(), 'updated_at' => now()]);
        $this->app->instance(EndpointGuard::class, new EndpointGuard(fn (): array => ['93.184.216.34']));
        $this->owner = $this->platformOwner();
        $this->member = $this->platformOwner();
        $this->app->instance(ResolvesAiProviderScope::class, new FakeAiProviderScope([
            $this->owner->id => ['organization_id' => $this->org, 'can_manage' => true],
            $this->member->id => ['organization_id' => $this->org, 'can_manage' => false],
        ]));
    }

    public function test_provider_at_its_daily_cap_is_skipped_and_work_shifts_to_the_next_provider(): void
    {
        $groq = $this->provider('groq', 'A Groq', 'https://api.groq.com/openai/v1', 'llama-free');
        $this->provider('gemini', 'B Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', 'gemini-free');
        $groq->daily_request_cap = 2;
        $groq->save();
        foreach ([1, 2] as $_) {
            AiModelRequest::query()->create(['organization_id' => $this->org, 'ai_provider_id' => $groq->id, 'model_id' => 'llama-free', 'outcome' => 'ok', 'latency_ms' => 5]);
        }
        Http::fake([
            'api.groq.com/*' => Http::response(['choices' => [['message' => ['content' => 'groq']]]], 200),
            'generativelanguage.googleapis.com/*' => Http::response(['choices' => [['message' => ['content' => 'gemini']]]], 200),
        ]);

        $result = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'hi']]);

        $this->assertSame('gemini', $result['content']);
        Http::assertNotSent(fn ($request): bool => str_contains((string) $request->url(), 'api.groq.com'));
    }

    public function test_only_capped_provider_left_means_daily_cap_reached_and_no_call(): void
    {
        $groq = $this->provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'llama-free');
        $groq->daily_request_cap = 1;
        $groq->save();
        AiModelRequest::query()->create(['organization_id' => $this->org, 'ai_provider_id' => $groq->id, 'model_id' => 'llama-free', 'outcome' => 'ok', 'latency_ms' => 5]);
        Http::fake();

        $result = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'hi']]);

        $this->assertFalse($result['ok']);
        $this->assertSame('daily_cap_reached', $result['error_code']);
        Http::assertNothingSent();
    }

    public function test_lower_priority_number_is_preferred_when_task_fit_is_equal(): void
    {
        $a = $this->provider('groq', 'A Groq', 'https://api.groq.com/openai/v1', 'same-model');
        $b = $this->provider('gemini', 'B Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', 'same-model');
        $b->priority = 10;
        $b->save();
        $a->priority = 200;
        $a->save();
        Http::fake([
            'api.groq.com/*' => Http::response(['choices' => [['message' => ['content' => 'groq']]]], 200),
            'generativelanguage.googleapis.com/*' => Http::response(['choices' => [['message' => ['content' => 'gemini']]]], 200),
        ]);

        $result = app(ModelFabricGateway::class)->complete($this->org, [['role' => 'user', 'content' => 'hi']]);

        $this->assertSame('B Gemini', $result['provider']);
    }

    public function test_owner_can_explicitly_verify_one_public_inference_without_bypassing_quota(): void
    {
        $provider = $this->provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'llama-free');
        $url = '/operator/modelfabric/providers/'.$provider->id.'/inference-check';
        Http::fake(['api.groq.com/*' => Http::response(['choices' => [['message' => ['content' => 'KMJ-OK']]]], 200)]);

        $this->confirmed($this->owner)->post($url)->assertSessionHasErrors('public_prompts_confirmed');
        $this->confirmed($this->member)->post($url, ['public_prompts_confirmed' => true])->assertForbidden();
        Http::assertNothingSent();

        $this->confirmed($this->owner)->post($url, ['public_prompts_confirmed' => true])
            ->assertSessionHasNoErrors()->assertSessionHas('status');
        Http::assertSentCount(1);
        Http::assertSent(fn ($request): bool => str_contains((string) $request->body(), 'Reply with KMJ-OK.')
            && ! str_contains((string) $request->body(), 'private-source'));
        $this->assertSame(1, AiModelRequest::query()->where('outcome', 'ok')->count());

        $provider->daily_request_cap = 1;
        $provider->save();
        $this->confirmed($this->owner)->post($url, ['public_prompts_confirmed' => true])
            ->assertSessionHasErrors('provider');
        Http::assertSentCount(1);
    }

    public function test_owner_manager_can_save_limits_and_members_cannot(): void
    {
        $provider = $this->provider('groq', 'Groq', 'https://api.groq.com/openai/v1', 'llama-free');

        $this->confirmed($this->member)->patch('/operator/modelfabric/providers/'.$provider->id, ['priority' => 50, 'daily_request_cap' => 100])->assertForbidden();
        $this->confirmed($this->owner)->patch('/operator/modelfabric/providers/'.$provider->id, ['priority' => 50, 'daily_request_cap' => 100])->assertSessionHasNoErrors();

        $fresh = $provider->fresh();
        $this->assertSame(50, (int) $fresh?->priority);
        $this->assertSame(100, (int) $fresh?->daily_request_cap);
        $this->confirmed($this->owner)->patch('/operator/modelfabric/providers/'.$provider->id, ['priority' => 0])->assertSessionHasErrors('priority');
    }

    private function provider(string $preset, string $name, string $baseUrl, string $model): AiProvider
    {
        $provider = AiProvider::query()->create([
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
        ]);
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

    private function confirmed(User $user): static
    {
        return $this->actingAs($user)->withSession(['auth.password_confirmed_at' => time()]);
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
