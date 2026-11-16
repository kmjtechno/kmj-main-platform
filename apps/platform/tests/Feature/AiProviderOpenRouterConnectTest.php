<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiProvider;
use App\Models\User;
use App\Services\AiProviders\EndpointGuard;
use App\Services\AiProviders\ProviderManager;
use App\Services\AiProviders\ResolvesAiProviderScope;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use RuntimeException;
use Tests\Support\FakeAiProviderScope;
use Tests\TestCase;

final class AiProviderOpenRouterConnectTest extends TestCase
{
    use RefreshDatabase;

    private const KEY = 'sk-or-v1-'.'0123456789abcdef0123';

    private const START = '/services/kmj-codebridge/ai-providers/connect/openrouter';

    private const CALLBACK = '/services/kmj-codebridge/ai-providers/connect/openrouter/callback';

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

    public function test_start_sends_a_pkce_s256_challenge_and_keeps_only_the_verifier_server_side(): void
    {
        $response = $this->confirmed($this->owner)->post(self::START);

        $response->assertRedirect();
        $location = (string) $response->headers->get('Location');
        parse_str((string) parse_url($location, PHP_URL_QUERY), $query);
        $verifier = (string) session('ai_provider_oauth.verifier');
        $state = (string) session('ai_provider_oauth.state');

        $this->assertSame($state, $query['state']);
        $this->assertMatchesRegularExpression('/\A[A-Za-z0-9_-]{43}\z/', $state);
        $this->assertNotSame($verifier, $state);
        $this->assertSame('openrouter.ai', parse_url($location, PHP_URL_HOST));
        $this->assertSame('S256', $query['code_challenge_method']);
        $this->assertStringStartsWith('https://', $query['callback_url']);
        $this->assertSame(rtrim(strtr(base64_encode(hash('sha256', $verifier, true)), '+/', '-_'), '='), $query['code_challenge']);
        $this->assertStringNotContainsString($verifier, $location);
    }

    public function test_only_confirmed_owners_can_start(): void
    {
        $this->confirmed($this->member)->post(self::START)->assertForbidden();
        $this->flushSession();
        $this->actingAs($this->owner)->post(self::START)->assertRedirect();
        $this->assertNull(session('ai_provider_oauth'));
    }

    public function test_callback_exchanges_the_code_creates_an_encrypted_zero_spend_provider_and_is_single_use(): void
    {
        $this->fakeOpenRouter();
        $this->confirmed($this->owner)->post(self::START);
        $verifier = (string) session('ai_provider_oauth.verifier');

        $this->actingAs($this->owner)->get($this->callbackUrl())->assertRedirect(route('ai-providers.index'));

        Http::assertSent(fn ($request): bool => str_ends_with($request->url(), '/api/v1/auth/keys')
            && $request['code'] === 'abcdefgh12345' && $request['code_verifier'] === $verifier);
        $provider = AiProvider::query()->firstOrFail();
        $this->assertSame(self::KEY, $provider->api_key);
        $this->assertNotSame(self::KEY, DB::table('ai_providers')->value('api_key'));
        $this->assertSame('openrouter', $provider->preset);
        $this->assertSame('ok', $provider->health);
        $this->assertSame(['meta/llama-3:free', 'x/paid-model'], $provider->models_cache);
        $this->assertSame('meta/llama-3:free', $provider->default_model);
        $this->assertNull(session('ai_provider_oauth'));
        $this->assertStringNotContainsString(self::KEY, (string) session('status'));

        $manager = app(ProviderManager::class);
        $manager->assertInferenceAllowed($provider, 'meta/llama-3:free');
        $this->expectException(RuntimeException::class);
        $manager->assertInferenceAllowed($provider, 'x/paid-model');
    }

    public function test_a_replayed_or_unstarted_callback_redeems_nothing(): void
    {
        $this->fakeOpenRouter();
        $this->actingAs($this->owner)->get($this->callbackUrl())->assertSessionHasErrors('provider');
        Http::assertNothingSent();

        $this->confirmed($this->owner)->post(self::START);
        $this->actingAs($this->owner)->get($this->callbackUrl());
        $this->actingAs($this->owner)->get($this->callbackUrl())->assertSessionHasErrors('provider');

        Http::assertSentCount(2);
        $this->assertDatabaseCount('ai_providers', 1);
    }

    public function test_failed_exchange_or_bad_code_creates_no_provider(): void
    {
        Http::fake(['openrouter.ai/*' => Http::response(['error' => 'bad'], 401)]);
        $this->confirmed($this->owner)->post(self::START);
        $this->actingAs($this->owner)->get($this->callbackUrl())->assertSessionHasErrors('provider');

        $this->confirmed($this->owner)->post(self::START);
        $this->actingAs($this->owner)->get($this->callbackUrl('<script>'))->assertSessionHasErrors('provider');

        $this->assertDatabaseCount('ai_providers', 0);
        Http::assertSentCount(1);
    }

    public function test_a_pending_sign_in_cannot_be_redeemed_by_another_organization(): void
    {
        Http::fake();
        $this->confirmed($this->owner)->post(self::START);
        $pending = session('ai_provider_oauth');

        $this->actingAs($this->outsider)->withSession(['ai_provider_oauth' => $pending])
            ->get($this->callbackUrl())->assertSessionHasErrors('provider');

        $this->assertDatabaseCount('ai_providers', 0);
        Http::assertNothingSent();
    }

    public function test_denied_oauth_callback_never_exchanges_a_code_or_adds_a_provider(): void
    {
        Http::fake();
        $this->confirmed($this->owner)->post(self::START);

        $this->actingAs($this->owner)->get(self::CALLBACK.'?error=access_denied')
            ->assertSessionHasErrors('provider');

        $this->assertNull(session('ai_provider_oauth'));
        $this->assertDatabaseCount('ai_providers', 0);
        Http::assertNothingSent();
    }

    public function test_only_paid_catalog_models_leave_free_default_unset(): void
    {
        Http::fake([
            'openrouter.ai/api/v1/auth/keys' => Http::response(['key' => self::KEY], 200),
            'openrouter.ai/api/v1/models?max_price=0' => Http::response(['data' => [['id' => 'x/paid-model']]], 200),
        ]);
        $this->confirmed($this->owner)->post(self::START);
        $this->actingAs($this->owner)->get($this->callbackUrl())->assertRedirect();

        $provider = AiProvider::query()->firstOrFail();
        $this->assertNull($provider->default_model);
        $this->assertTrue($provider->free_only);
        $this->assertStringContainsString('0 ":free" model', (string) session('status'));
    }

    public function test_unreachable_free_model_catalog_does_not_claim_a_verified_connection(): void
    {
        Http::fake([
            'openrouter.ai/api/v1/auth/keys' => Http::response(['key' => self::KEY], 200),
            'openrouter.ai/api/v1/models?max_price=0' => Http::response(['error' => 'temporarily unavailable'], 503),
        ]);
        $this->confirmed($this->owner)->post(self::START);
        $this->actingAs($this->owner)->get($this->callbackUrl())->assertRedirect();

        $provider = AiProvider::query()->firstOrFail();
        $this->assertSame('unreachable', $provider->health);
        $this->assertNull($provider->default_model);
        $this->assertStringContainsString('verification is pending', (string) session('status'));
        $this->assertStringNotContainsString(self::KEY, (string) session('status'));
        Http::assertSentCount(2);
    }

    public function test_missing_wrong_or_stale_callback_state_never_redeems_a_code(): void
    {
        Http::fake();

        $this->confirmed($this->owner)->post(self::START);
        $original = (string) session('ai_provider_oauth.state');
        $this->actingAs($this->owner)->get(self::CALLBACK.'?code=abcdefgh12345')
            ->assertSessionHasErrors('provider');
        $this->assertNull(session('ai_provider_oauth'));

        $this->confirmed($this->owner)->post(self::START);
        $this->actingAs($this->owner)->get(self::CALLBACK.'?code=abcdefgh12345&state=forged')
            ->assertSessionHasErrors('provider');
        $this->assertNull(session('ai_provider_oauth'));

        $this->confirmed($this->owner)->post(self::START);
        $this->actingAs($this->owner)->get(self::CALLBACK.'?code=abcdefgh12345&state%5B%5D=malformed')
            ->assertSessionHasErrors('provider');
        $this->assertNull(session('ai_provider_oauth'));

        $this->confirmed($this->owner)->post(self::START);
        $stale = (string) session('ai_provider_oauth.state');
        $this->confirmed($this->owner)->post(self::START);
        $fresh = (string) session('ai_provider_oauth.state');
        $this->assertNotSame($stale, $fresh);
        $this->assertNotSame($original, $fresh);
        $this->actingAs($this->owner)->get(self::CALLBACK.'?code=abcdefgh12345&state='.$stale)
            ->assertSessionHasErrors('provider');

        Http::assertNothingSent();
        $this->assertDatabaseCount('ai_providers', 0);
    }

    public function test_array_valued_oauth_code_is_rejected_without_network_or_provider_creation(): void
    {
        Http::fake();
        $this->confirmed($this->owner)->post(self::START);
        $state = (string) session('ai_provider_oauth.state');

        $this->actingAs($this->owner)->get(self::CALLBACK.'?state='.$state.'&code%5B%5D=abcdefgh12345')
            ->assertRedirect(route('ai-providers.index'))
            ->assertSessionHasErrors('provider');

        $this->assertNull(session('ai_provider_oauth'));
        $this->assertDatabaseCount('ai_providers', 0);
        Http::assertNothingSent();
    }

    public function test_malformed_session_verifier_is_rejected_without_network_or_provider_creation(): void
    {
        Http::fake();
        $this->confirmed($this->owner)->post(self::START);
        $pending = session('ai_provider_oauth');
        $pending['verifier'] = ['forged'];
        $this->actingAs($this->owner)->withSession(['ai_provider_oauth' => $pending])
            ->get(self::CALLBACK.'?code=abcdefgh12345&state='.$pending['state'])
            ->assertRedirect(route('ai-providers.index'))
            ->assertSessionHasErrors('provider');

        $this->assertNull(session('ai_provider_oauth'));
        $this->assertDatabaseCount('ai_providers', 0);
        Http::assertNothingSent();
    }

    private function callbackUrl(string $code = 'abcdefgh12345'): string
    {
        return self::CALLBACK.'?'.http_build_query([
            'code' => $code,
            'state' => (string) session('ai_provider_oauth.state'),
        ]);
    }

    private function fakeOpenRouter(): void
    {
        Http::fake([
            'openrouter.ai/api/v1/auth/keys' => Http::response(['key' => self::KEY], 200),
            'openrouter.ai/api/v1/models?max_price=0' => Http::response(['data' => [['id' => 'meta/llama-3:free'], ['id' => 'x/paid-model']]], 200),
        ]);
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
