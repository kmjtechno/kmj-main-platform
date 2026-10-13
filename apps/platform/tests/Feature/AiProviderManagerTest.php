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
use Illuminate\Testing\TestResponse;
use Inertia\Testing\AssertableInertia;
use InvalidArgumentException;
use RuntimeException;
use Tests\Support\FakeAiProviderScope;
use Tests\TestCase;

final class AiProviderManagerTest extends TestCase
{
    use RefreshDatabase;

    private const KEY = 'gsk_test_0123456789abcdef';

    private string $orgA;

    private string $orgB;

    private User $owner;

    private User $member;

    private User $outsider;

    protected function setUp(): void
    {
        parent::setUp();
        $this->orgA = $this->organization();
        $this->orgB = $this->organization();
        $this->owner = User::factory()->create(['email_verified_at' => now()]);
        $this->member = User::factory()->create(['email_verified_at' => now()]);
        $this->outsider = User::factory()->create(['email_verified_at' => now()]);

        $scopes = [
            $this->owner->id => ['organization_id' => $this->orgA, 'can_manage' => true],
            $this->member->id => ['organization_id' => $this->orgA, 'can_manage' => false],
            $this->outsider->id => ['organization_id' => $this->orgB, 'can_manage' => true],
        ];
        $this->app->instance(ResolvesAiProviderScope::class, new FakeAiProviderScope($scopes));
        $this->app->instance(EndpointGuard::class, new EndpointGuard(fn (): array => ['93.184.216.34']));
    }

    public function test_owner_adds_a_provider_and_the_key_is_encrypted_and_never_returned(): void
    {
        $this->add('Groq main')->assertRedirect();

        $provider = AiProvider::query()->firstOrFail();
        $this->assertSame(self::KEY, $provider->api_key);
        $this->assertNotSame(self::KEY, DB::table('ai_providers')->value('api_key'));
        $this->assertStringNotContainsString(self::KEY, (string) DB::table('ai_providers')->value('api_key'));
        $this->assertTrue($provider->free_only);

        $page = $this->confirmed($this->owner)->get('/services/kmj-codebridge/ai-providers');
        $page->assertOk();
        $this->assertStringNotContainsString(self::KEY, $page->getContent());
        $page->assertInertia(fn (AssertableInertia $inertia) => $inertia
            ->component('services/ai-providers')
            ->where('providers.0.key_mask', '••••cdef')
            ->where('canManage', true));
        $this->assertArrayNotHasKey('api_key', app(ProviderManager::class)->present($provider));
    }

    public function test_members_can_view_but_not_change_and_outsiders_cannot_see_other_tenants(): void
    {
        $this->add('Groq main');
        $id = AiProvider::query()->value('id');

        $this->confirmed($this->member)->get('/services/kmj-codebridge/ai-providers')->assertOk();
        $this->confirmed($this->member)->post('/services/kmj-codebridge/ai-providers', $this->payload('Other'))->assertForbidden();
        $this->confirmed($this->member)->post("/services/kmj-codebridge/ai-providers/{$id}/test")->assertForbidden();

        foreach ([
            ['patch', "/services/kmj-codebridge/ai-providers/{$id}", ['enabled' => false]],
            ['post', "/services/kmj-codebridge/ai-providers/{$id}/test", []],
            ['delete', "/services/kmj-codebridge/ai-providers/{$id}", ['confirm' => 'DELETE']],
        ] as [$method, $url, $data]) {
            $this->confirmed($this->outsider)->{$method}($url, $data)->assertNotFound();
        }
        $this->assertDatabaseCount('ai_providers', 1);
        $this->assertTrue(AiProvider::query()->findOrFail($id)->enabled);
    }

    public function test_connection_test_discovers_models_without_sending_a_prompt_and_reports_verified_limits(): void
    {
        Http::fake(['api.groq.com/*' => Http::response(
            ['data' => [['id' => 'llama-3.1-8b-instant'], ['id' => 'bad id!'], ['id' => 'gemma2-9b-it']]],
            200,
            ['x-ratelimit-remaining-requests' => '900'],
        )]);
        $this->add('Groq main');
        $id = AiProvider::query()->value('id');

        $this->confirmed($this->owner)->post("/services/kmj-codebridge/ai-providers/{$id}/test")->assertRedirect();

        Http::assertSent(fn ($request): bool => $request->url() === 'https://api.groq.com/openai/v1/models'
            && $request->method() === 'GET'
            && $request->hasHeader('Authorization', 'Bearer '.self::KEY)
            && $request->body() === '');
        $provider = AiProvider::query()->findOrFail($id);
        $this->assertSame('ok', $provider->health);
        $this->assertSame(['gemma2-9b-it', 'llama-3.1-8b-instant'], $provider->models_cache);
        $this->assertSame('verified', $provider->rate_limit['status']);
        $this->assertSame(900, $provider->rate_limit['requests_remaining']);
        $this->assertNull($provider->rate_limit['tokens_remaining']);
    }

    public function test_provider_failures_are_classified_and_never_echo_the_key(): void
    {
        $this->add('Groq main');
        $id = AiProvider::query()->value('id');

        // A single fake with a response sequence: later Http::fake() calls would not override the first.
        Http::fake(['api.groq.com/*' => Http::sequence()
            ->push(['error' => self::KEY], 401)
            ->push(['error' => self::KEY], 429, ['Retry-After' => '30'])
            ->push(['error' => self::KEY], 503)]);

        foreach (['auth_failed', 'rate_limited', 'unreachable'] as $health) {
            $this->confirmed($this->owner)->post("/services/kmj-codebridge/ai-providers/{$id}/test")->assertRedirect();
            $provider = AiProvider::query()->findOrFail($id);
            $this->assertSame($health, $provider->health);
            $this->assertStringNotContainsString(self::KEY, json_encode($provider->only(['last_error_code', 'rate_limit']), JSON_THROW_ON_ERROR));
        }
        $this->assertSame('unknown', AiProvider::query()->findOrFail($id)->rate_limit['status']);
    }

    public function test_unapproved_or_private_endpoints_are_rejected_before_any_request(): void
    {
        Http::fake();
        $this->confirmed($this->owner)->post('/services/kmj-codebridge/ai-providers', [
            'preset' => 'custom', 'name' => 'Evil', 'api_key' => self::KEY, 'base_url' => 'https://metadata.example.com/v1',
        ])->assertSessionHasErrors('base_url');

        $this->app->instance(EndpointGuard::class, new EndpointGuard(fn (): array => ['10.0.0.5']));
        $this->confirmed($this->owner)->post('/services/kmj-codebridge/ai-providers', [
            'preset' => 'custom', 'name' => 'Evil', 'api_key' => self::KEY, 'base_url' => 'http://127.0.0.1:11434/v1',
        ])->assertSessionHasErrors('base_url');

        $this->assertDatabaseCount('ai_providers', 0);
        Http::assertNothingSent();
    }

    public function test_default_and_fallback_models_must_be_discovered_and_replacing_the_key_resets_evidence(): void
    {
        Http::fake(['api.groq.com/*' => Http::response(['data' => [['id' => 'a-model'], ['id' => 'b-model'], ['id' => 'c-model']]], 200)]);
        $this->add('Groq main');
        $id = AiProvider::query()->value('id');
        $url = "/services/kmj-codebridge/ai-providers/{$id}";

        $this->confirmed($this->owner)->patch($url, ['default_model' => 'a-model'])->assertSessionHasErrors('provider');
        $this->confirmed($this->owner)->post("{$url}/test");
        $this->confirmed($this->owner)->patch($url, ['default_model' => 'ghost'])->assertSessionHasErrors('provider');
        $this->confirmed($this->owner)->patch($url, ['default_model' => 'a-model', 'fallback_models' => ['b-model', 'a-model', 'b-model']])->assertSessionHasNoErrors();

        $provider = AiProvider::query()->findOrFail($id);
        $this->assertSame('a-model', $provider->default_model);
        $this->assertSame(['b-model'], $provider->fallback_models);

        $this->confirmed($this->owner)->patch($url, ['api_key' => 'new-key-0123456789'])->assertSessionHasNoErrors();
        $provider = AiProvider::query()->findOrFail($id);
        $this->assertSame('new-key-0123456789', $provider->api_key);
        $this->assertSame('6789', $provider->key_last4);
        $this->assertNull($provider->default_model);
        $this->assertSame('unknown', $provider->health);
    }

    public function test_delete_requires_confirmation_and_removes_the_stored_key(): void
    {
        $this->add('Groq main');
        $id = AiProvider::query()->value('id');
        $url = "/services/kmj-codebridge/ai-providers/{$id}";

        $this->confirmed($this->owner)->delete($url)->assertSessionHasErrors('confirm');
        $this->assertDatabaseCount('ai_providers', 1);
        $this->confirmed($this->owner)->delete($url, ['confirm' => 'DELETE'])->assertRedirect();
        $this->assertDatabaseCount('ai_providers', 0);
    }

    public function test_zero_spend_guard_has_no_paid_override_and_requires_fresh_healthy_discovery(): void
    {
        config(['ai_providers.free_models.groq' => ['verified-model']]);
        $manager = app(ProviderManager::class);
        $openai = $this->provider('openai', ['gpt-4o']);
        $router = $this->provider('openrouter', ['meta/llama-3', 'meta/llama-3:free']);
        $groq = $this->provider('groq', ['verified-model', 'other-model']);

        foreach ([
            [$openai, 'gpt-4o'],
            [$router, 'meta/llama-3'],
            [$groq, 'other-model'],
            [$groq, 'undiscovered-model'],
            [$this->provider('groq', ['verified-model'], ['enabled' => false]), 'verified-model'],
            [$this->provider('groq', ['verified-model'], ['health' => 'auth_failed']), 'verified-model'],
            [$this->provider('groq', ['verified-model'], ['models_checked_at' => now()->subHours(25)]), 'verified-model'],
            [$this->provider('groq', ['verified-model'], ['models_checked_at' => null]), 'verified-model'],
        ] as [$provider, $model]) {
            try {
                $manager->assertInferenceAllowed($provider, $model);
                $this->fail('inference was admitted');
            } catch (RuntimeException|InvalidArgumentException) {
                $this->addToAssertionCount(1);
            }
        }

        $manager->assertInferenceAllowed($router, 'meta/llama-3:free');
        $manager->assertInferenceAllowed($groq, 'verified-model');
    }

    public function test_billed_inference_cannot_be_enabled_from_the_dashboard(): void
    {
        $this->add('Groq main')->assertSessionHasNoErrors();
        $id = AiProvider::query()->value('id');

        $this->confirmed($this->owner)->post('/services/kmj-codebridge/ai-providers', $this->payload('Paid') + ['free_only' => false])
            ->assertSessionHasErrors('free_only');
        $this->confirmed($this->owner)->patch("/services/kmj-codebridge/ai-providers/{$id}", ['free_only' => false])
            ->assertSessionHasErrors('free_only');
        $this->assertDatabaseCount('ai_providers', 1);
        $this->assertTrue(AiProvider::query()->findOrFail($id)->free_only);
    }

    public function test_credit_balance_is_always_unknown_and_secrets_are_not_presented(): void
    {
        $presented = app(ProviderManager::class)->present($this->provider('groq', ['m']));

        $this->assertSame('unknown', $presented['credit_balance']);
        $this->assertTrue($presented['zero_spend']);
        $this->assertStringNotContainsString(self::KEY, json_encode($presented, JSON_THROW_ON_ERROR));
    }

    public function test_redirects_are_never_followed(): void
    {
        Http::fake(['api.groq.com/*' => Http::response('', 302, ['Location' => 'http://169.254.169.254/latest'])]);
        $this->add('Groq main');
        $id = AiProvider::query()->value('id');

        $this->confirmed($this->owner)->post("/services/kmj-codebridge/ai-providers/{$id}/test")->assertRedirect();

        Http::assertSentCount(1);
        $this->assertSame('unreachable', AiProvider::query()->findOrFail($id)->health);
    }

    public function test_duplicate_names_are_rejected_without_a_server_error(): void
    {
        $this->add('Groq main')->assertSessionHasNoErrors();
        $this->add('Groq main')->assertSessionHasErrors('name');
        $this->assertDatabaseCount('ai_providers', 1);
    }

    public function test_changes_require_a_recent_password_confirmation(): void
    {
        $this->add('Groq main');
        $id = AiProvider::query()->value('id');

        $this->actingAs($this->owner)->post('/services/kmj-codebridge/ai-providers', $this->payload('Second'))->assertRedirect();
        $this->actingAs($this->owner)->patch("/services/kmj-codebridge/ai-providers/{$id}", ['enabled' => false])->assertRedirect();
        $this->actingAs($this->owner)->delete("/services/kmj-codebridge/ai-providers/{$id}", ['confirm' => 'DELETE'])->assertRedirect();

        $this->assertDatabaseCount('ai_providers', 1);
        $this->assertTrue(AiProvider::query()->findOrFail($id)->enabled);
    }

    public function test_a_successful_models_probe_does_not_authorize_inference(): void
    {
        Http::fake(['api.groq.com/*' => Http::response(['data' => [['id' => 'some-model']]], 200)]);
        $this->add('Groq main');
        $id = AiProvider::query()->value('id');
        $this->actingAs($this->owner)->post("/services/kmj-codebridge/ai-providers/{$id}/test");

        $provider = AiProvider::query()->findOrFail($id);
        $this->assertSame('ok', $provider->health);
        $this->expectException(RuntimeException::class);
        app(ProviderManager::class)->assertInferenceAllowed($provider, 'some-model');
    }

    private function confirmed(User $user): static
    {
        return $this->actingAs($user)->withSession(['auth.password_confirmed_at' => time()]);
    }

    private function add(string $name): TestResponse
    {
        return $this->confirmed($this->owner)->post('/services/kmj-codebridge/ai-providers', $this->payload($name));
    }

    /** @return array<string, mixed> */
    private function payload(string $name): array
    {
        return ['preset' => 'groq', 'name' => $name, 'api_key' => self::KEY];
    }

    /**
     * @param  list<string>  $models
     * @param  array<string, mixed>  $overrides
     */
    private function provider(string $preset, array $models = [], array $overrides = []): AiProvider
    {
        return AiProvider::query()->create($overrides + [
            'organization_id' => $this->orgA, 'name' => $preset.Str::random(4), 'preset' => $preset,
            'base_url' => config("ai_providers.presets.{$preset}.base_url"), 'api_key' => self::KEY,
            'key_last4' => 'cdef', 'free_only' => true, 'enabled' => true, 'models_cache' => $models,
            'health' => 'ok', 'models_checked_at' => now(),
        ]);
    }

    private function organization(): string
    {
        $id = (string) Str::uuid();
        DB::table('organizations')->insert(['id' => $id, 'name' => 'Org '.Str::random(5), 'created_at' => now(), 'updated_at' => now()]);

        return $id;
    }
}
