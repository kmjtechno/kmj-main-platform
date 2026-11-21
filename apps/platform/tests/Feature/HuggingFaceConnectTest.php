<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiProvider;
use App\Models\User;
use App\Services\AiProviders\EndpointGuard;
use App\Services\AiProviders\ResolvesAiProviderScope;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Tests\Support\FakeAiProviderScope;
use Tests\TestCase;

final class HuggingFaceConnectTest extends TestCase
{
    use RefreshDatabase;

    private const TOKEN = 'hf_oauth_'.'0123456789abcdef0123';

    private const START = '/services/kmj-codebridge/ai-providers/connect/huggingface';

    private const CALLBACK = '/services/kmj-codebridge/ai-providers/connect/huggingface/callback';

    private User $owner;

    private User $member;

    private User $outsider;

    protected function setUp(): void
    {
        parent::setUp();
        $orgA = $this->organization();
        $orgB = $this->organization();
        $this->owner = User::factory()->create(['email_verified_at' => now()]);
        $this->member = User::factory()->create(['email_verified_at' => now()]);
        $this->outsider = User::factory()->create(['email_verified_at' => now()]);
        $this->app->instance(ResolvesAiProviderScope::class, new FakeAiProviderScope([
            $this->owner->id => ['organization_id' => $orgA, 'can_manage' => true],
            $this->member->id => ['organization_id' => $orgA, 'can_manage' => false],
            $this->outsider->id => ['organization_id' => $orgB, 'can_manage' => true],
        ]));
        $this->app->instance(EndpointGuard::class, new EndpointGuard(fn (): array => ['93.184.216.34']));
    }

    public function test_public_metadata_is_a_secretless_pkce_client_with_the_exact_callback(): void
    {
        $json = $this->getJson('/.well-known/oauth-cimd')->assertOk()->json();

        $this->assertSame('https://localhost/.well-known/oauth-cimd', $json['client_id']);
        $this->assertSame('none', $json['token_endpoint_auth_method']);
        $this->assertSame(['https://localhost'.self::CALLBACK], $json['redirect_uris']);
        $this->assertArrayNotHasKey('client_secret', $json);
    }

    public function test_start_needs_the_free_account_attestation_and_sends_pkce_s256_with_inference_scope_only(): void
    {
        $this->confirmed($this->owner)->post(self::START)->assertSessionHasErrors('free_account_confirmed');

        $response = $this->confirmed($this->owner)->post(self::START, ['free_account_confirmed' => true]);

        $response->assertRedirect();
        $location = (string) $response->headers->get('Location');
        parse_str((string) parse_url($location, PHP_URL_QUERY), $query);
        $verifier = (string) session('ai_provider_hf_oauth.verifier');
        $this->assertSame('huggingface.co', parse_url($location, PHP_URL_HOST));
        $this->assertSame('inference-api', $query['scope']);
        $this->assertSame('S256', $query['code_challenge_method']);
        $this->assertSame('code', $query['response_type']);
        $this->assertSame('https://localhost/.well-known/oauth-cimd', $query['client_id']);
        $this->assertSame(rtrim(strtr(base64_encode(hash('sha256', $verifier, true)), '+/', '-_'), '='), $query['code_challenge']);
        $this->assertStringNotContainsString($verifier, $location);
    }

    public function test_only_confirmed_owner_managers_can_start(): void
    {
        $this->confirmed($this->member)->post(self::START, ['free_account_confirmed' => true])->assertForbidden();
    }

    public function test_callback_stores_an_encrypted_provider_audits_it_and_is_single_use(): void
    {
        Http::fake([
            'huggingface.co/oauth/token' => Http::response(['access_token' => self::TOKEN, 'token_type' => 'Bearer'], 200),
            'router.huggingface.co/*' => Http::response(['data' => [['id' => 'org/model-a']]], 200),
        ]);
        $this->confirmed($this->owner)->post(self::START, ['free_account_confirmed' => true]);
        $verifier = (string) session('ai_provider_hf_oauth.verifier');

        $this->actingAs($this->owner)->get($this->callbackUrl())->assertRedirect(route('ai-providers.index'));

        Http::assertSent(fn ($request): bool => $request->url() === 'https://huggingface.co/oauth/token'
            && $request['grant_type'] === 'authorization_code'
            && $request['code_verifier'] === $verifier
            && $request['client_id'] === 'https://localhost/.well-known/oauth-cimd');
        $provider = AiProvider::query()->firstOrFail();
        $this->assertSame('huggingface', $provider->preset);
        $this->assertSame(self::TOKEN, $provider->api_key);
        $this->assertNotSame(self::TOKEN, DB::table('ai_providers')->value('api_key'));
        $this->assertStringNotContainsString(self::TOKEN, (string) session('status'));
        $this->assertDatabaseHas('operator_action_audits', ['action' => 'model_fabric.huggingface_connected']);

        $this->actingAs($this->owner)->get($this->callbackUrl())->assertSessionHasErrors('provider');
        $this->assertDatabaseCount('ai_providers', 1);
    }

    public function test_reconnecting_replaces_the_key_instead_of_creating_a_duplicate(): void
    {
        Http::fake([
            'huggingface.co/oauth/token' => Http::response(['access_token' => self::TOKEN], 200),
            'router.huggingface.co/*' => Http::response(['data' => []], 200),
        ]);
        foreach ([1, 2] as $_) {
            $this->confirmed($this->owner)->post(self::START, ['free_account_confirmed' => true]);
            $this->actingAs($this->owner)->get($this->callbackUrl());
        }

        $this->assertDatabaseCount('ai_providers', 1);
    }

    public function test_declined_or_bad_exchange_creates_no_provider(): void
    {
        Http::fake(['huggingface.co/*' => Http::response(['error' => 'bad'], 401)]);
        $this->confirmed($this->owner)->post(self::START, ['free_account_confirmed' => true]);
        $this->actingAs($this->owner)->get($this->callbackUrl())->assertSessionHasErrors('provider');

        $this->confirmed($this->owner)->post(self::START, ['free_account_confirmed' => true]);
        $this->actingAs($this->owner)->get(self::CALLBACK.'?error=access_denied')->assertSessionHasErrors('provider');

        $this->assertDatabaseCount('ai_providers', 0);
    }

    public function test_a_pending_sign_in_cannot_be_redeemed_by_another_organization(): void
    {
        Http::fake();
        $this->confirmed($this->owner)->post(self::START, ['free_account_confirmed' => true]);
        $pending = session('ai_provider_hf_oauth');

        $this->actingAs($this->outsider)->withSession(['ai_provider_hf_oauth' => $pending])
            ->get($this->callbackUrl())->assertSessionHasErrors('provider');

        Http::assertNothingSent();
        $this->assertDatabaseCount('ai_providers', 0);
    }

    private function callbackUrl(string $code = 'abcdefgh12345'): string
    {
        return self::CALLBACK.'?'.http_build_query(['code' => $code, 'state' => (string) session('ai_provider_hf_oauth.state')]);
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
}
