<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiModelEvidence;
use App\Models\AiModelRule;
use App\Models\AiProvider;
use App\Models\User;
use App\Services\AiProviders\EndpointGuard;
use App\Services\AiProviders\ModelFabricRuleApplier;
use App\Services\AiProviders\ResolvesAiProviderScope;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\Support\FakeAiProviderScope;
use Tests\TestCase;

final class ModelFabricAutoApproveRulesTest extends TestCase
{
    use RefreshDatabase;

    private string $org;

    private User $owner;

    private User $member;

    protected function setUp(): void
    {
        parent::setUp();
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

    public function test_pattern_rules_reject_broad_or_odd_patterns(): void
    {
        $this->assertNotNull(ModelFabricRuleApplier::patternError('*'));
        $this->assertNotNull(ModelFabricRuleApplier::patternError('gem*'));
        $this->assertNotNull(ModelFabricRuleApplier::patternError('models/gemini-2.5-flash'));
        $this->assertNotNull(ModelFabricRuleApplier::patternError('models/gemini;rm*'));
        $this->assertNull(ModelFabricRuleApplier::patternError('models/gemini-2.5-flash*'));
    }

    public function test_matching_skips_non_chat_models(): void
    {
        $matched = ModelFabricRuleApplier::matches('models/gemini-2.5-flash*', [
            'models/gemini-2.5-flash',
            'models/gemini-2.5-flash-lite',
            'models/gemini-2.5-flash-preview-tts',
            'models/gemini-2.5-flash-image',
            'models/gemini-2.5-flash-live',
            'models/gemini-2.5-pro',
        ]);

        $this->assertSame(['models/gemini-2.5-flash', 'models/gemini-2.5-flash-lite'], $matched);
    }

    public function test_saving_a_rule_approves_matching_models_and_a_later_apply_adds_new_ones(): void
    {
        $provider = $this->provider('gemini', ['models/gemini-2.5-flash', 'models/gemini-2.5-pro']);

        $this->confirmed($this->owner)->post('/operator/modelfabric/rules', $this->payload($provider))->assertSessionHasNoErrors();

        $evidence = AiModelEvidence::query()->where('ai_provider_id', $provider->id)->get();
        $this->assertSame(['models/gemini-2.5-flash'], $evidence->pluck('model_id')->all());
        $this->assertNotNull($evidence->first()->ai_model_rule_id);
        $this->assertTrue($evidence->first()->expires_at->lessThanOrEqualTo(now()->addDays(30)));

        $provider->models_cache = ['models/gemini-2.5-flash', 'models/gemini-2.5-flash-lite'];
        $provider->save();
        $this->app->make(ModelFabricRuleApplier::class)->apply();

        $this->assertSame(2, AiModelEvidence::query()->where('ai_provider_id', $provider->id)->whereNull('revoked_at')->count());
    }

    public function test_a_revoked_model_is_never_revived_by_a_rule(): void
    {
        $provider = $this->provider('gemini', ['models/gemini-2.5-flash']);
        AiModelEvidence::query()->create([
            'organization_id' => $this->org,
            'ai_provider_id' => $provider->id,
            'model_id' => 'models/gemini-2.5-flash',
            'price_evidence_url' => 'https://example.com/p',
            'price_evidence_note' => 'Revoked by the owner.',
            'verified_at' => now()->subDay(),
            'expires_at' => now()->addDays(5),
            'data_handling' => 'unknown',
            'capabilities' => ['chat'],
            'revoked_at' => now(),
        ]);

        $this->confirmed($this->owner)->post('/operator/modelfabric/rules', $this->payload($provider))->assertSessionHasNoErrors();

        $this->assertNotNull(AiModelEvidence::query()->where('model_id', 'models/gemini-2.5-flash')->firstOrFail()->revoked_at);
    }

    public function test_revoking_a_rule_revokes_only_the_models_it_approved(): void
    {
        $provider = $this->provider('gemini', ['models/gemini-2.5-flash']);
        $this->confirmed($this->owner)->post('/operator/modelfabric/rules', $this->payload($provider))->assertSessionHasNoErrors();
        $rule = AiModelRule::query()->firstOrFail();

        $this->confirmed($this->owner)->delete('/operator/modelfabric/rules/'.$rule->id)->assertSessionHasNoErrors();

        $this->assertNotNull($rule->refresh()->revoked_at);
        $this->assertSame(0, AiModelEvidence::query()->whereNull('revoked_at')->count());
        $this->app->make(ModelFabricRuleApplier::class)->apply();
        $this->assertSame(0, AiModelEvidence::query()->whereNull('revoked_at')->count());
        $this->confirmed($this->owner)->post('/operator/modelfabric/rules/'.$rule->id.'/renew', ['attest_pricing' => true])->assertSessionHasErrors('rule');
    }

    public function test_it_needs_attestation_an_allowlist_provider_and_a_narrow_match(): void
    {
        $provider = $this->provider('gemini', ['models/gemini-2.5-flash']);
        $payload = $this->payload($provider);

        $this->confirmed($this->owner)->post('/operator/modelfabric/rules', array_diff_key($payload, ['attest_pricing' => 1]))->assertSessionHasErrors('attest_pricing');
        $this->confirmed($this->owner)->post('/operator/modelfabric/rules', [...$payload, 'model_pattern' => 'models/*'])->assertSessionHasErrors('model_pattern');
        $this->confirmed($this->owner)->post('/operator/modelfabric/rules', [...$payload, 'model_pattern' => 'models/nothing-here*'])->assertSessionHasErrors('model_pattern');
        $custom = $this->provider('custom', ['models/gemini-2.5-flash']);
        $this->confirmed($this->owner)->post('/operator/modelfabric/rules', $this->payload($custom))->assertSessionHasErrors('model_pattern');

        $this->assertSame(0, AiModelRule::query()->count());
        $this->assertSame(0, AiModelEvidence::query()->count());
    }

    public function test_only_organization_managers_can_manage_rules(): void
    {
        $provider = $this->provider('gemini', ['models/gemini-2.5-flash']);

        $this->confirmed($this->member)->post('/operator/modelfabric/rules', $this->payload($provider))->assertForbidden();

        $this->assertSame(0, AiModelRule::query()->count());
    }

    public function test_an_expired_rule_approves_nothing_new(): void
    {
        $provider = $this->provider('gemini', ['models/gemini-2.5-flash']);
        AiModelRule::query()->create([
            'organization_id' => $this->org,
            'ai_provider_id' => $provider->id,
            'model_pattern' => 'models/gemini-2.5-flash*',
            'price_evidence_url' => 'https://example.com/p',
            'price_evidence_note' => 'Expired attestation.',
            'data_handling' => 'unknown',
            'capabilities' => ['chat'],
            'attested_by' => $this->owner->id,
            'attested_at' => now()->subDays(40),
            'expires_at' => now()->subDays(10),
        ]);

        $this->app->make(ModelFabricRuleApplier::class)->apply();

        $this->assertSame(0, AiModelEvidence::query()->count());
    }

    /** @return array<string, mixed> */
    private function payload(AiProvider $provider): array
    {
        return [
            'provider_id' => $provider->id,
            'model_pattern' => 'models/gemini-2.5-flash*',
            'price_evidence_url' => 'https://ai.google.dev/pricing',
            'price_evidence_note' => 'Free tier lists these models as free of charge.',
            'valid_days' => 30,
            'data_handling' => 'unknown',
            'capabilities' => ['chat'],
            'attest_pricing' => true,
        ];
    }

    /** @param  list<string>  $models */
    private function provider(string $preset, array $models): AiProvider
    {
        return AiProvider::query()->create([
            'organization_id' => $this->org,
            'name' => ucfirst($preset).' '.Str::random(4),
            'preset' => $preset,
            'kind' => 'openai-compatible',
            'base_url' => 'https://generativelanguage.googleapis.com/v1beta/openai',
            'api_key' => 'sk-test-key-123456',
            'key_last4' => '3456',
            'enabled' => true,
            'free_only' => true,
            'health' => 'ok',
            'health_checked_at' => now(),
            'models_cache' => $models,
            'models_checked_at' => now(),
        ]);
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
