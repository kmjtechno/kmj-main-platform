<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiModelEvidence;
use App\Models\AiProvider;
use App\Models\User;
use App\Services\AiProviders\ModelFabricRouter;
use App\Services\AiProviders\ResolvesAiProviderScope;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\Support\FakeAiProviderScope;
use Tests\TestCase;

final class ModelFabricRoutingTest extends TestCase
{
    use RefreshDatabase;

    private const BASE = '/operator/modelfabric';

    private string $org;

    private User $owner;

    private User $member;

    protected function setUp(): void
    {
        parent::setUp();
        $this->org = $this->organization();
        $this->owner = $this->platformOwner();
        $this->member = $this->platformOwner();
        $this->app->instance(ResolvesAiProviderScope::class, new FakeAiProviderScope([
            $this->owner->id => ['organization_id' => $this->org, 'can_manage' => true],
            $this->member->id => ['organization_id' => $this->org, 'can_manage' => false],
        ]));
    }

    public function test_no_provider_means_no_free_route_and_never_a_fallback(): void
    {
        $plan = app(ModelFabricRouter::class)->plan($this->org);

        $this->assertSame('NO_FREE_ROUTE_AVAILABLE', $plan['status']);
        $this->assertSame([], $plan['routes']);
    }

    public function test_healthy_provider_without_evidence_or_env_allowlist_has_no_route(): void
    {
        $this->provider('groq', ['llama-free-1']);

        $plan = app(ModelFabricRouter::class)->plan($this->org);

        $this->assertSame('NO_FREE_ROUTE_AVAILABLE', $plan['status']);
        $this->assertSame('no_verified_free_model', $plan['reasons'][0]['reason']);
    }

    public function test_current_evidence_admits_the_model_and_revocation_or_expiry_removes_it(): void
    {
        $provider = $this->provider('groq', ['llama-free-1']);

        $this->confirmed($this->owner)->post(self::BASE.'/evidence', $this->evidenceInput($provider))->assertSessionHasNoErrors();
        $plan = app(ModelFabricRouter::class)->plan($this->org);
        $this->assertSame('ROUTE_AVAILABLE', $plan['status']);
        $this->assertSame('llama-free-1', $plan['routes'][0]['model']);
        $this->assertSame('owner-price-evidence', $plan['routes'][0]['source']);

        $row = AiModelEvidence::query()->firstOrFail();
        $row->expires_at = now()->subMinute();
        $row->save();
        $this->assertSame('NO_FREE_ROUTE_AVAILABLE', app(ModelFabricRouter::class)->plan($this->org)['status']);

        $row->expires_at = now()->addDay();
        $row->save();
        $this->assertSame('ROUTE_AVAILABLE', app(ModelFabricRouter::class)->plan($this->org)['status']);

        $this->confirmed($this->owner)->delete(self::BASE.'/evidence/'.$row->id)->assertSessionHasNoErrors();
        $this->assertSame('NO_FREE_ROUTE_AVAILABLE', app(ModelFabricRouter::class)->plan($this->org)['status']);
    }

    public function test_private_source_needs_documented_no_training_evidence(): void
    {
        $provider = $this->provider('groq', ['llama-free-1']);
        $this->confirmed($this->owner)->post(self::BASE.'/evidence', $this->evidenceInput($provider, ['capabilities' => ['chat', 'code']]))
            ->assertSessionHasNoErrors();

        $unknown = app(ModelFabricRouter::class)->plan($this->org, 'code', true);
        $this->assertSame('NO_FREE_ROUTE_AVAILABLE', $unknown['status']);

        $this->confirmed($this->owner)->post(self::BASE.'/evidence', $this->evidenceInput($provider, [
            'capabilities' => ['chat', 'code'],
            'data_handling' => 'no-training-documented',
        ]))->assertSessionHasNoErrors();

        $this->assertSame('ROUTE_AVAILABLE', app(ModelFabricRouter::class)->plan($this->org, 'code', true)['status']);
    }

    public function test_evidence_cannot_unlock_a_provider_with_no_free_tier_or_an_undiscovered_model(): void
    {
        $paid = $this->provider('openai', ['gpt-x']);
        $this->confirmed($this->owner)->post(self::BASE.'/evidence', $this->evidenceInput($paid, ['model_id' => 'gpt-x']))
            ->assertSessionHasErrors('model_id');
        $this->assertSame(0, AiModelEvidence::query()->count());

        $groq = $this->provider('groq', ['llama-free-1'], 'Groq Two');
        $this->confirmed($this->owner)->post(self::BASE.'/evidence', $this->evidenceInput($groq, ['model_id' => 'not-listed']))
            ->assertSessionHasErrors('model_id');
        $this->assertSame(0, AiModelEvidence::query()->count());
    }

    public function test_evidence_must_be_https_and_at_most_thirty_days(): void
    {
        $provider = $this->provider('groq', ['llama-free-1']);

        $this->confirmed($this->owner)->post(self::BASE.'/evidence', $this->evidenceInput($provider, ['price_evidence_url' => 'http://example.com/p']))
            ->assertSessionHasErrors('price_evidence_url');
        $this->confirmed($this->owner)->post(self::BASE.'/evidence', $this->evidenceInput($provider, ['valid_days' => 31]))
            ->assertSessionHasErrors('valid_days');
        $this->assertSame(0, AiModelEvidence::query()->count());
    }

    public function test_only_a_platform_owner_manager_can_write_and_the_page_is_owner_only(): void
    {
        $provider = $this->provider('groq', ['llama-free-1']);
        $regular = User::factory()->create(['email_verified_at' => now()]);

        $this->confirmed($regular)->get(self::BASE)->assertForbidden();
        $this->confirmed($regular)->post(self::BASE.'/evidence', $this->evidenceInput($provider))->assertForbidden();
        $this->confirmed($this->member)->post(self::BASE.'/evidence', $this->evidenceInput($provider))->assertForbidden();
        $this->assertSame(0, AiModelEvidence::query()->count());
    }

    public function test_codebridge_token_entry_is_owner_protected_and_whitelisted(): void
    {
        $this->confirmed($this->owner)->get(self::BASE.'?tab=tokens')
            ->assertOk()->assertInertia(fn (Assert $page) => $page
            ->component('operator-modelfabric')
            ->where('initialTab', 'tokens')
            ->where('canManage', true)
            ->where('newToken', null));

        $this->confirmed($this->owner)->get(self::BASE.'?tab=unknown')
            ->assertOk()->assertInertia(fn (Assert $page) => $page->where('initialTab', 'start'));

        $regular = User::factory()->create(['email_verified_at' => now()]);
        $this->confirmed($regular)->get(self::BASE.'?tab=tokens')->assertForbidden();

        $this->confirmed($this->member)->get(self::BASE.'?tab=tokens')
            ->assertOk()->assertInertia(fn (Assert $page) => $page
            ->where('initialTab', 'tokens')
            ->where('canManage', false));
        $this->confirmed($this->member)->post(self::BASE.'/tokens', [
            'name' => 'denied-worker',
            'valid_days' => 1,
            'private_source' => true,
        ])->assertForbidden();
    }

    public function test_legacy_provider_page_redirects_platform_owners_to_canonical_workspace(): void
    {
        $this->confirmed($this->owner)->get('/services/kmj-codebridge/ai-providers')
            ->assertRedirect(self::BASE.'?tab=providers');
        $this->confirmed($this->member)->get('/services/kmj-codebridge/ai-providers')
            ->assertRedirect(self::BASE.'?tab=providers');
        $this->confirmed($this->member)->get(self::BASE.'?tab=providers')
            ->assertOk()->assertInertia(fn (Assert $page) => $page
            ->component('operator-modelfabric')
            ->where('canManage', false));
    }

    public function test_owner_page_renders_plans_without_secrets(): void
    {
        $provider = $this->provider('groq', ['llama-free-1']);
        $this->confirmed($this->owner)->post(self::BASE.'/evidence', $this->evidenceInput($provider))->assertSessionHasNoErrors();

        $response = $this->confirmed($this->owner)->get(self::BASE);

        $response->assertOk()->assertInertia(fn (Assert $page) => $page
            ->component('operator-modelfabric')
            ->where('plans.chat.status', 'ROUTE_AVAILABLE')
            ->where('plans.privateSource.status', 'NO_FREE_ROUTE_AVAILABLE')
            ->has('evidence', 1)
            ->has('providers', 1));
        $this->assertStringNotContainsString('sk-test-secret-key', $response->getContent());
    }

    /**
     * @param  list<string>  $models
     */
    private function provider(string $preset, array $models, string $name = 'Groq One'): AiProvider
    {
        return AiProvider::query()->create([
            'organization_id' => $this->org,
            'name' => $name,
            'preset' => $preset,
            'kind' => 'openai-compatible',
            'base_url' => 'https://api.example.test/v1',
            'api_key' => 'sk-test-secret-key',
            'key_last4' => '-key',
            'enabled' => true,
            'free_only' => true,
            'health' => 'ok',
            'health_checked_at' => now(),
            'models_cache' => $models,
            'models_checked_at' => now(),
        ]);
    }

    /**
     * @param  array<string, mixed>  $overrides
     * @return array<string, mixed>
     */
    private function evidenceInput(AiProvider $provider, array $overrides = []): array
    {
        return $overrides + [
            'provider_id' => $provider->id,
            'model_id' => 'llama-free-1',
            'price_evidence_url' => 'https://example.com/pricing',
            'price_evidence_note' => 'Pricing page lists this model at zero cost on the free tier.',
            'valid_days' => 14,
            'data_handling' => 'unknown',
            'capabilities' => ['chat'],
        ];
    }

    private function confirmed(User $user): static
    {
        return $this->actingAs($user)->withSession(['auth.password_confirmed_at' => time()]);
    }

    private function organization(): string
    {
        $id = (string) Str::uuid();
        DB::table('organizations')->insert(['id' => $id, 'name' => 'Org '.Str::random(5), 'created_at' => now(), 'updated_at' => now()]);

        return $id;
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
