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
        $this->app->instance(ResolvesAiProviderScope::class, new class($scopes) implements ResolvesAiProviderScope
        {
            /** @param array<int, array{organization_id: string, can_manage: bool}> $scopes */
            public function __construct(private readonly array $scopes) {}

            public function for(User $user): array
            {
                return $this->scopes[$user->id] ?? abort(404);
            }
        });
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

        $page = $this->actingAs($this->owner)->get('/services/kmj-codebridge/ai-providers');
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

        $this->actingAs($this->member)->get('/services/kmj-codebridge/ai-providers')->assertOk();
        $this->actingAs($this->member)->post('/services/kmj-codebridge/ai-providers', $this->payload('Other'))->assertForbidden();
        $this->actingAs($this->member)->post("/services/kmj-codebridge/ai-providers/{$id}/test")->assertForbidden();

        foreach ([
            ['patch', "/services/kmj-codebridge/ai-providers/{$id}", ['enabled' => false]],
            ['post', "/services/kmj-codebridge/ai-providers/{$id}/test", []],
            ['delete', "/services/kmj-codebridge/ai-providers/{$id}", ['confirm' => 'DELETE']],
        ] as [$method, $url, $data]) {
            $this->actingAs($this->outsider)->{$method}($url, $data)->assertNotFound();
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

        $this->actingAs($this->owner)->post("/services/kmj-codebridge/ai-providers/{$id}/test")->assertRedirect();

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

        foreach ([[401, 'auth_failed'], [429, 'rate_limited'], [503, 'unreachable']] as [$status, $health]) {
            Http::fake(['api.groq.com/*' => Http::response(['error' => self::KEY], $status, ['Retry-After' => '30'])]);
            $this->actingAs($this->owner)->post("/services/kmj-codebridge/ai-providers/{$id}/test")->assertRedirect();
            $provider = AiProvider::query()->findOrFail($id);
            $this->assertSame($health, $provider->health);
            $this->assertStringNotContainsString(self::KEY, json_encode($provider->only(['last_error_code', 'rate_limit']), JSON_THROW_ON_ERROR));
        }
        $this->assertSame('unknown', AiProvider::query()->findOrFail($id)->rate_limit['status']);
    }

    public function test_unapproved_or_private_endpoints_are_rejected_before_any_request(): void
    {
        Http::fake();
        $this->actingAs($this->owner)->post('/services/kmj-codebridge/ai-providers', [
            'preset' => 'custom', 'name' => 'Evil', 'api_key' => self::KEY, 'base_url' => 'https://metadata.example.com/v1',
        ])->assertSessionHasErrors('base_url');

        $this->app->instance(EndpointGuard::class, new EndpointGuard(fn (): array => ['10.0.0.5']));
        $this->actingAs($this->owner)->post('/services/kmj-codebridge/ai-providers', [
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

        $this->actingAs($this->owner)->patch($url, ['default_model' => 'a-model'])->assertSessionHasErrors('provider');
        $this->actingAs($this->owner)->post("{$url}/test");
        $this->actingAs($this->owner)->patch($url, ['default_model' => 'ghost'])->assertSessionHasErrors('provider');
        $this->actingAs($this->owner)->patch($url, ['default_model' => 'a-model', 'fallback_models' => ['b-model', 'a-model', 'b-model']])->assertSessionHasNoErrors();

        $provider = AiProvider::query()->findOrFail($id);
        $this->assertSame('a-model', $provider->default_model);
        $this->assertSame(['b-model'], $provider->fallback_models);

        $this->actingAs($this->owner)->patch($url, ['api_key' => 'new-key-0123456789'])->assertSessionHasNoErrors();
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

        $this->actingAs($this->owner)->delete($url)->assertSessionHasErrors('confirm');
        $this->assertDatabaseCount('ai_providers', 1);
        $this->actingAs($this->owner)->delete($url, ['confirm' => 'DELETE'])->assertRedirect();
        $this->assertDatabaseCount('ai_providers', 0);
    }

    public function test_zero_spend_guard_blocks_paid_inference_unless_explicitly_opted_in(): void
    {
        $manager = app(ProviderManager::class);
        $openai = $this->provider('openai', true);
        $router = $this->provider('openrouter', true);

        foreach ([[$openai, 'gpt-4o'], [$router, 'meta/llama-3'], [$this->provider('groq', true, false), 'x']] as [$provider, $model]) {
            try {
                $manager->assertInferenceAllowed($provider, $model);
                $this->fail('paid inference was allowed');
            } catch (RuntimeException|InvalidArgumentException) {
                $this->addToAssertionCount(1);
            }
        }

        $manager->assertInferenceAllowed($router, 'meta/llama-3:free');
        $manager->assertInferenceAllowed($this->provider('groq', true), 'llama');
        $manager->assertInferenceAllowed($this->provider('openai', false), 'gpt-4o');
    }

    private function add(string $name): TestResponse
    {
        return $this->actingAs($this->owner)->post('/services/kmj-codebridge/ai-providers', $this->payload($name));
    }

    /** @return array<string, mixed> */
    private function payload(string $name): array
    {
        return ['preset' => 'groq', 'name' => $name, 'api_key' => self::KEY];
    }

    private function provider(string $preset, bool $freeOnly, bool $enabled = true): AiProvider
    {
        return AiProvider::query()->create([
            'organization_id' => $this->orgA, 'name' => $preset.Str::random(4), 'preset' => $preset,
            'base_url' => config("ai_providers.presets.{$preset}.base_url"), 'api_key' => self::KEY,
            'key_last4' => 'cdef', 'free_only' => $freeOnly, 'enabled' => $enabled,
        ]);
    }

    private function organization(): string
    {
        $id = (string) Str::uuid();
        DB::table('organizations')->insert(['id' => $id, 'name' => 'Org '.Str::random(5), 'created_at' => now(), 'updated_at' => now()]);

        return $id;
    }
}
