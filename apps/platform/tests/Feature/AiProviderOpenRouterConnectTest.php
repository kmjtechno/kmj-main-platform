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

    private const KEY = 'sk-or-v1-0123456789abcdef0123';

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

        $this->actingAs($this->owner)->get(self::CALLBACK.'?code=abcdefgh12345')->assertRedirect(route('ai-providers.index'));

        Http::assertSent(fn ($request): bool => str_ends_with($request->url(), '/api/v1/auth/keys')
            && $request['code'] === 'abcdefgh12345' && $request['code_verifier'] === $verifier);
        $provider = AiProvider::query()->firstOrFail();
        $this->assertSame(self::KEY, $provider->api_key);
        $this->assertNotSame(self::KEY, DB::table('ai_providers')->value('api_key'));
        $this->assertSame('openrouter', $provider->preset);
        $this->assertSame('ok', $provider->health);
        $this->assertSame(['meta/llama-3:free', 'x/paid-model'], $provider->models_cache);
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
        $this->actingAs($this->owner)->get(self::CALLBACK.'?code=abcdefgh12345')->assertSessionHasErrors('provider');
        Http::assertNothingSent();

        $this->confirmed($this->owner)->post(self::START);
        $this->actingAs($this->owner)->get(self::CALLBACK.'?code=abcdefgh12345');
        $this->actingAs($this->owner)->get(self::CALLBACK.'?code=abcdefgh12345')->assertSessionHasErrors('provider');

        Http::assertSentCount(2);
        $this->assertDatabaseCount('ai_providers', 1);
    }

    public function test_failed_exchange_or_bad_code_creates_no_provider(): void
    {
        Http::fake(['openrouter.ai/*' => Http::response(['error' => 'bad'], 401)]);
        $this->confirmed($this->owner)->post(self::START);
        $this->actingAs($this->owner)->get(self::CALLBACK.'?code=abcdefgh12345')->assertSessionHasErrors('provider');

        $this->confirmed($this->owner)->post(self::START);
        $this->actingAs($this->owner)->get(self::CALLBACK.'?code=%3Cscript%3E')->assertSessionHasErrors('provider');

        $this->assertDatabaseCount('ai_providers', 0);
        Http::assertSentCount(1);
    }

    public function test_a_pending_sign_in_cannot_be_redeemed_by_another_organization(): void
    {
        Http::fake();
        $this->confirmed($this->owner)->post(self::START);
        $pending = session('ai_provider_oauth');

        $this->actingAs($this->outsider)->withSession(['ai_provider_oauth' => $pending])
            ->get(self::CALLBACK.'?code=abcdefgh12345')->assertSessionHasErrors('provider');

        $this->assertDatabaseCount('ai_providers', 0);
        Http::assertNothingSent();
    }

    private function fakeOpenRouter(): void
    {
        Http::fake([
            'openrouter.ai/api/v1/auth/keys' => Http::response(['key' => self::KEY], 200),
            'openrouter.ai/api/v1/models' => Http::response(['data' => [['id' => 'meta/llama-3:free'], ['id' => 'x/paid-model']]], 200),
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
