<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiModelEvidence;
use App\Models\AiProvider;
use App\Models\User;
use App\Services\AiProviders\EndpointGuard;
use App\Services\AiProviders\ResolvesAiProviderScope;
use Carbon\CarbonInterface;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\Support\FakeAiProviderScope;
use Tests\TestCase;

final class ModelFabricBulkEvidenceTest extends TestCase
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

    public function test_one_attestation_approves_many_listed_models_and_audits_once(): void
    {
        $provider = $this->provider('groq', ['m-a', 'm-b', 'm-c']);

        $this->confirmed($this->owner)->post('/operator/modelfabric/evidence/bulk', $this->payload($provider, ['m-a', 'm-b', 'm-c']))
            ->assertSessionHasNoErrors();

        $this->assertSame(3, AiModelEvidence::query()->where('ai_provider_id', $provider->id)->count());
        $row = AiModelEvidence::query()->where('model_id', 'm-b')->firstOrFail();
        $this->assertSame(['chat'], $row->capabilities);
        $this->assertSame('unknown', $row->data_handling);
        $this->assertNull($row->revoked_at);
        $this->assertSame(1, DB::table('operator_action_audits')->where('action', 'model_fabric.evidence_bulk_saved')->count());
    }

    public function test_it_needs_the_attestation_https_evidence_and_models_from_the_last_discovery(): void
    {
        $provider = $this->provider('groq', ['m-a']);
        $payload = $this->payload($provider, ['m-a']);

        $this->confirmed($this->owner)->post('/operator/modelfabric/evidence/bulk', array_diff_key($payload, ['attest_pricing' => 1]))
            ->assertSessionHasErrors('attest_pricing');
        $this->confirmed($this->owner)->post('/operator/modelfabric/evidence/bulk', [...$payload, 'price_evidence_url' => 'http://example.com/p'])
            ->assertSessionHasErrors('price_evidence_url');
        $this->confirmed($this->owner)->post('/operator/modelfabric/evidence/bulk', [...$payload, 'model_ids' => ['m-a', 'invented']])
            ->assertSessionHasErrors('model_ids');

        $this->assertSame(0, AiModelEvidence::query()->count());
    }

    public function test_it_is_capped_at_fifty_models_and_never_unlocks_non_allowlist_providers(): void
    {
        $many = array_map(fn (int $i): string => 'm-'.$i, range(1, 51));
        $provider = $this->provider('groq', $many);
        $this->confirmed($this->owner)->post('/operator/modelfabric/evidence/bulk', $this->payload($provider, $many))
            ->assertSessionHasErrors('model_ids');

        $custom = $this->provider('custom', ['x']);
        $this->confirmed($this->owner)->post('/operator/modelfabric/evidence/bulk', $this->payload($custom, ['x']))
            ->assertSessionHasErrors('model_ids');

        $this->assertSame(0, AiModelEvidence::query()->count());
    }

    public function test_only_organization_managers_can_bulk_approve(): void
    {
        $provider = $this->provider('groq', ['m-a']);

        $this->confirmed($this->member)->post('/operator/modelfabric/evidence/bulk', $this->payload($provider, ['m-a']))->assertForbidden();

        $this->assertSame(0, AiModelEvidence::query()->count());
    }

    public function test_renew_extends_expired_evidence_but_never_revives_revoked_evidence(): void
    {
        $provider = $this->provider('groq', ['m-a', 'm-b']);
        $expired = $this->evidence($provider, 'm-a', now()->subDay(), null);
        $revoked = $this->evidence($provider, 'm-b', now()->addDays(5), now());

        $this->confirmed($this->owner)->post('/operator/modelfabric/evidence/'.$expired->id.'/renew')->assertSessionHasErrors('attest_pricing');
        $this->confirmed($this->owner)->post('/operator/modelfabric/evidence/'.$expired->id.'/renew', ['attest_pricing' => true])->assertSessionHasNoErrors();
        $this->confirmed($this->owner)->post('/operator/modelfabric/evidence/'.$revoked->id.'/renew', ['attest_pricing' => true])->assertSessionHasErrors('evidence');

        $this->assertTrue($expired->refresh()->expires_at->greaterThan(now()->addDays(29)));
        $this->assertNotNull($revoked->refresh()->revoked_at);
        $this->assertSame(1, DB::table('operator_action_audits')->where('action', 'model_fabric.evidence_renewed')->count());
    }

    public function test_evidence_of_another_organization_cannot_be_renewed(): void
    {
        $otherOrg = (string) Str::uuid();
        DB::table('organizations')->insert(['id' => $otherOrg, 'name' => 'Other', 'created_at' => now(), 'updated_at' => now()]);
        $provider = $this->provider('groq', ['m-a']);
        $foreign = $this->evidence($provider, 'm-a', now()->subDay(), null);
        $foreign->organization_id = $otherOrg;
        $foreign->save();

        $this->confirmed($this->owner)->post('/operator/modelfabric/evidence/'.$foreign->id.'/renew', ['attest_pricing' => true])->assertSessionHasErrors('evidence');

        $this->assertTrue($foreign->refresh()->expires_at->isPast());
    }

    /**
     * @param  list<string>  $models
     * @return array<string, mixed>
     */
    private function payload(AiProvider $provider, array $models): array
    {
        return [
            'provider_id' => $provider->id,
            'model_ids' => $models,
            'price_evidence_url' => 'https://example.com/free-tier',
            'price_evidence_note' => 'Free tier page lists these models at zero cost.',
            'valid_days' => 14,
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
            'base_url' => 'https://api.groq.com/openai/v1',
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

    private function evidence(AiProvider $provider, string $model, CarbonInterface $expires, ?CarbonInterface $revokedAt): AiModelEvidence
    {
        return AiModelEvidence::query()->create([
            'organization_id' => $this->org,
            'ai_provider_id' => $provider->id,
            'model_id' => $model,
            'price_evidence_url' => 'https://example.com/pricing',
            'price_evidence_note' => 'Pricing page lists this model at zero cost.',
            'verified_at' => now()->subDays(20),
            'expires_at' => $expires,
            'data_handling' => 'unknown',
            'capabilities' => ['chat'],
            'revoked_at' => $revokedAt,
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
