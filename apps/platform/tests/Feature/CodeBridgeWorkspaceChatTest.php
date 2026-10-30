<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiProvider;
use App\Models\User;
use App\Services\AiProviders\EndpointGuard;
use App\Services\AiProviders\ResolvesAiProviderScope;
use DateTimeInterface;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Illuminate\Testing\TestResponse;
use Inertia\Testing\AssertableInertia;
use Tests\Support\FakeAiProviderScope;
use Tests\TestCase;

final class CodeBridgeWorkspaceChatTest extends TestCase
{
    use RefreshDatabase;

    private const KEY = 'gsk_test_0123456789abcdef';

    private const MODEL = 'llama-3.1-8b-instant';

    private const URL = 'https://api.groq.com/openai/v1/chat/completions';

    private string $tenantA;

    private string $tenantB;

    private User $alice;

    private User $bob;

    private User $mallory;

    private string $providerA;

    protected function setUp(): void
    {
        parent::setUp();
        config()->set('ai_providers.free_models.groq', [self::MODEL]);
        $this->app->instance(EndpointGuard::class, new EndpointGuard(fn (): array => ['93.184.216.34']));
        $this->tenantA = $this->tenant('desk-a', 'proj-a');
        $this->tenantB = $this->tenant('desk-b', 'proj-b');
        $this->alice = User::factory()->create(['email_verified_at' => now()]);
        $this->bob = User::factory()->create(['email_verified_at' => now()]);
        $this->mallory = User::factory()->create(['email_verified_at' => now()]);
        $this->app->instance(ResolvesAiProviderScope::class, new FakeAiProviderScope([
            $this->alice->id => ['organization_id' => $this->tenantA, 'can_manage' => true],
            $this->bob->id => ['organization_id' => $this->tenantA, 'can_manage' => false],
            $this->mallory->id => ['organization_id' => $this->tenantB, 'can_manage' => true],
        ]));
        $this->providerA = $this->provider($this->tenantA)->id;
    }

    public function test_guest_cannot_use_chat_routes(): void
    {
        $this->post('/services/kmj-codebridge/workspace/conversations', [])->assertRedirect('/login');
    }

    public function test_send_persists_both_messages_with_real_events_and_never_leaks_the_key(): void
    {
        Http::fake([self::URL => Http::sequence()
            ->push(['choices' => [['message' => ['content' => 'Hello from the model']]]], 200)
            ->push(['choices' => [['message' => ['content' => 'Second']]]], 200)]);
        $id = $this->start($this->alice, 'desk-a', 'proj-a');

        $this->send($this->alice, $id, 'Hi there')->assertRedirect();

        Http::assertSent(fn (Request $request): bool => $request->hasHeader('Authorization', 'Bearer '.self::KEY)
            && $request['model'] === self::MODEL
            && $request['stream'] === false
            && $request['messages'][0]['role'] === 'system'
            && $request['messages'][1] === ['role' => 'user', 'content' => 'Hi there']);
        $this->assertDatabaseHas('codebridge_workspace_messages', ['conversation_id' => $id, 'role' => 'user', 'content' => 'Hi there', 'status' => 'complete']);
        $this->assertDatabaseHas('codebridge_workspace_messages', [
            'conversation_id' => $id, 'role' => 'assistant', 'content' => 'Hello from the model',
            'status' => 'complete', 'model' => self::MODEL, 'provider_id' => $this->providerA,
        ]);
        self::assertSame(['inference_started', 'inference_completed'], DB::table('codebridge_workspace_events')->orderBy('id')->pluck('kind')->all());

        $page = $this->actingAs($this->alice)->get($this->pageUrl('desk-a', 'proj-a', $id));
        $page->assertOk()->assertInertia(fn (AssertableInertia $inertia) => $inertia
            ->component('services/codebridge-workspace')
            ->where('activeConversation.id', $id)
            ->where('transcript.messages.0.role', 'user')
            ->where('transcript.messages.1.status', 'complete')
            ->where('transcript.events.1.kind', 'inference_completed')
            ->has('transcript.events.1.at')
            ->has('transcript.messages.1.elapsed_seconds')
            ->where('capabilities.chat_executor.available', true));
        self::assertStringNotContainsString(self::KEY, $page->getContent());

        // The second turn carries the stored history, oldest first.
        $this->send($this->alice, $id, 'And again')->assertRedirect();
        Http::assertSent(fn (Request $request): bool => count($request['messages']) === 4
            && $request['messages'][1]['content'] === 'Hi there'
            && $request['messages'][2]['content'] === 'Hello from the model'
            && $request['messages'][3]['content'] === 'And again');
    }

    public function test_provider_failure_is_recorded_truthfully_and_retry_creates_a_new_attempt(): void
    {
        Http::fake([self::URL => Http::sequence()
            ->push('slow down', 429)
            ->push(['choices' => [['message' => ['content' => 'Recovered']]]], 200)]);
        $id = $this->start($this->alice, 'desk-a', 'proj-a');
        $this->send($this->alice, $id, 'Hi')->assertRedirect();

        $failed = DB::table('codebridge_workspace_messages')->where('role', 'assistant')->first();
        self::assertSame('failed', $failed->status);
        self::assertSame('rate_limited', $failed->error_code);
        self::assertSame('', $failed->content);
        self::assertSame(['inference_started', 'inference_failed'], DB::table('codebridge_workspace_events')->orderBy('id')->pluck('kind')->all());

        $this->retry($this->alice, $id, $failed->id)->assertRedirect();
        $this->assertDatabaseHas('codebridge_workspace_messages', ['role' => 'assistant', 'content' => 'Recovered', 'status' => 'complete', 'retry_of' => $failed->id]);
        // The user message was not duplicated, and the failed attempt stays on record.
        self::assertSame(1, DB::table('codebridge_workspace_messages')->where('role', 'user')->count());
        self::assertSame(2, DB::table('codebridge_workspace_messages')->where('role', 'assistant')->count());

        // A completed attempt can no longer be retried.
        $done = DB::table('codebridge_workspace_messages')->where('status', 'complete')->where('role', 'assistant')->value('id');
        $this->retry($this->alice, $id, $done)->assertSessionHas('chat_error', 'retry_not_allowed');
    }

    public function test_models_that_fail_the_zero_spend_rule_are_blocked_without_any_request(): void
    {
        Http::fake();
        $id = $this->start($this->alice, 'desk-a', 'proj-a');
        DB::table('ai_providers')->where('id', $this->providerA)->update(['models_cache' => json_encode([self::MODEL, 'paid-model'])]);

        $this->send($this->alice, $id, 'Hi', 'paid-model')->assertRedirect();
        Http::assertNothingSent();
        $assistant = DB::table('codebridge_workspace_messages')->where('role', 'assistant')->first();
        self::assertSame('failed', $assistant->status);
        self::assertNotNull($assistant->error_code);

        DB::table('ai_providers')->where('id', $this->providerA)->update(['enabled' => false]);
        $this->send($this->alice, $id, 'Hi again')->assertRedirect();
        Http::assertNothingSent();
        self::assertSame('provider_disabled', DB::table('codebridge_workspace_messages')->where('role', 'assistant')->orderByDesc('id')->value('error_code'));
    }

    public function test_a_cancel_that_lands_during_the_request_wins_and_late_output_is_discarded(): void
    {
        Http::fake(function () {
            DB::table('codebridge_workspace_messages')->where('status', 'running')
                ->update(['status' => 'cancelled', 'error_code' => 'cancelled_by_user', 'finished_at' => now()]);

            return Http::response(['choices' => [['message' => ['content' => 'Too late']]]], 200);
        });
        $id = $this->start($this->alice, 'desk-a', 'proj-a');
        $this->send($this->alice, $id, 'Hi')->assertRedirect();

        $assistant = DB::table('codebridge_workspace_messages')->where('role', 'assistant')->first();
        self::assertSame('cancelled', $assistant->status);
        self::assertSame('', $assistant->content);
        self::assertNotContains('inference_completed', DB::table('codebridge_workspace_events')->pluck('kind')->all());
    }

    public function test_cancel_endpoint_only_cancels_a_running_message(): void
    {
        $id = $this->start($this->alice, 'desk-a', 'proj-a');
        $running = $this->seedAssistant($id, 'running', now());

        $this->actingAs($this->alice)->post($this->cancelUrl($id, $running))->assertRedirect();
        $this->assertDatabaseHas('codebridge_workspace_messages', ['id' => $running, 'status' => 'cancelled', 'error_code' => 'cancelled_by_user']);
        $this->assertDatabaseHas('codebridge_workspace_events', ['message_id' => $running, 'kind' => 'cancelled']);

        $this->actingAs($this->alice)->post($this->cancelUrl($id, $running))->assertSessionHas('chat_error', 'not_running');
    }

    public function test_one_request_at_a_time_and_abandoned_requests_are_expired_honestly(): void
    {
        Http::fake([self::URL => Http::response(['choices' => [['message' => ['content' => 'ok']]]], 200)]);
        $id = $this->start($this->alice, 'desk-a', 'proj-a');
        $running = $this->seedAssistant($id, 'running', now());

        $this->send($this->alice, $id, 'Hi')->assertSessionHas('chat_error', 'conversation_busy');
        Http::assertNothingSent();
        self::assertSame(0, DB::table('codebridge_workspace_messages')->where('role', 'user')->count());

        DB::table('codebridge_workspace_messages')->where('id', $running)->update(['started_at' => now()->subMinutes(5)]);
        $this->send($this->alice, $id, 'Hi')->assertRedirect()->assertSessionMissing('chat_error');
        $this->assertDatabaseHas('codebridge_workspace_messages', ['id' => $running, 'status' => 'failed', 'error_code' => 'abandoned']);
        $this->assertDatabaseHas('codebridge_workspace_events', ['message_id' => $running, 'kind' => 'inference_failed', 'detail' => 'abandoned']);
    }

    public function test_conversations_are_scoped_to_tenant_user_and_paired_project(): void
    {
        Http::fake();
        $id = $this->start($this->alice, 'desk-a', 'proj-a');

        // Same organization, different user: not found, never forbidden.
        $this->actingAs($this->bob)->get($this->pageUrl('desk-a', 'proj-a', $id))->assertNotFound();
        $this->send($this->bob, $id, 'peek')->assertNotFound();
        $this->actingAs($this->bob)->post($this->cancelUrl($id, (string) Str::ulid()))->assertNotFound();
        // Another organization.
        // Not paired for that tenant: the selection is ignored and nothing of the conversation is returned.
        $this->actingAs($this->mallory)->get($this->pageUrl('desk-a', 'proj-a', $id))->assertOk()
            ->assertInertia(fn (AssertableInertia $inertia) => $inertia->where('activeConversation', null)->where('selected', null)->where('transcript.messages', []));
        $this->send($this->mallory, $id, 'peek')->assertNotFound();
        // Starting a conversation on a project the tenant has not paired.
        $this->actingAs($this->mallory)->post('/services/kmj-codebridge/workspace/conversations', ['device_id' => 'desk-a', 'project_id' => 'proj-a'])->assertNotFound();
        $this->actingAs($this->alice)->post('/services/kmj-codebridge/workspace/conversations', ['device_id' => 'desk-a', 'project_id' => 'unknown'])->assertNotFound();
        self::assertSame(1, DB::table('codebridge_workspace_conversations')->count());
        self::assertSame(0, DB::table('codebridge_workspace_messages')->count());
        Http::assertNothingSent();

        // The list for the right project shows only the caller's own conversations.
        $this->actingAs($this->alice)->get($this->pageUrl('desk-a', 'proj-a'))->assertInertia(fn (AssertableInertia $inertia) => $inertia->has('conversations', 1));
        $this->actingAs($this->bob)->get($this->pageUrl('desk-a', 'proj-a'))->assertInertia(fn (AssertableInertia $inertia) => $inertia->has('conversations', 0));

        // A revoked device removes access to its conversations.
        DB::table('codebridge_device_credentials')->where('tenant_id', $this->tenantA)->update(['revoked_at' => now()]);
        $this->actingAs($this->alice)->get($this->pageUrl('desk-a', 'proj-a', $id))->assertOk()
            ->assertInertia(fn (AssertableInertia $inertia) => $inertia->where('activeConversation', null)->where('selected', null));
        $this->send($this->alice, $id, 'late')->assertNotFound();
    }

    public function test_every_unfit_provider_state_refuses_with_a_specific_code_and_no_paid_fallback(): void
    {
        Http::fake();
        $id = $this->start($this->alice, 'desk-a', 'proj-a');
        $good = ['enabled' => true, 'health' => 'ok', 'models_cache' => json_encode([self::MODEL, 'paid-model']), 'models_checked_at' => now(), 'fallback_models' => json_encode(['paid-model'])];
        $cases = [
            'provider_disabled' => [['enabled' => false], self::MODEL],
            'provider_unhealthy' => [['health' => 'error'], self::MODEL],
            'model_discovery_stale' => [['models_checked_at' => now()->subDays(30)], self::MODEL],
            'model_discovery_stale ' => [['models_checked_at' => null], self::MODEL],
            'model_not_discovered' => [[], 'never-listed-model'],
            'zero_spend_blocked' => [[], 'paid-model'],
        ];
        $expected = [];
        foreach ($cases as $code => [$override, $model]) {
            DB::table('ai_providers')->where('id', $this->providerA)->update([...$good, ...$override]);
            $this->send($this->alice, $id, 'try '.$code, $model)->assertRedirect();
            $expected[] = trim($code);
        }
        // A configured fallback model must never be used to rescue a refused request.
        Http::assertNothingSent();
        $codes = DB::table('codebridge_workspace_messages')->where('role', 'assistant')->orderBy('id')->pluck('error_code')->all();
        self::assertSame($expected, $codes);
        self::assertSame(0, DB::table('codebridge_workspace_messages')->where('role', 'assistant')->where('status', '!=', 'failed')->count());
    }

    public function test_malformed_conversation_ids_are_a_clean_404_and_never_a_database_error(): void
    {
        Http::fake();
        $valid = $this->start($this->alice, 'desk-a', 'proj-a');
        $bad = ['not-a-uuid', '12345', "'%20OR%201=1", str_repeat('a', 200), '00000000-0000-0000-0000-00000000000g'];

        foreach ($bad as $id) {
            $this->actingAs($this->alice)->get($this->pageUrl('desk-a', 'proj-a', rawurlencode($id)))->assertNotFound();
            $this->actingAs($this->alice)->post('/services/kmj-codebridge/workspace/conversations/'.rawurlencode($id).'/messages', ['content' => 'x'])->assertNotFound();
        }
        // Well-formed but unknown id: same answer, and cross-tenant still hides existence.
        $this->actingAs($this->alice)->get($this->pageUrl('desk-a', 'proj-a', (string) Str::uuid()))->assertNotFound();
        $this->actingAs($this->mallory)->get($this->pageUrl('desk-a', 'proj-a', $valid))->assertOk()
            ->assertInertia(fn (AssertableInertia $inertia) => $inertia->where('activeConversation', null));
        // The page without ?c, and with a valid id, is unchanged.
        $this->actingAs($this->alice)->get($this->pageUrl('desk-a', 'proj-a'))->assertOk();
        $this->actingAs($this->alice)->get($this->pageUrl('desk-a', 'proj-a', $valid))->assertOk()
            ->assertInertia(fn (AssertableInertia $inertia) => $inertia->where('activeConversation.id', $valid));
        Http::assertNothingSent();
    }

    public function test_another_organizations_provider_and_bad_input_are_rejected_before_any_write(): void
    {
        Http::fake();
        $id = $this->start($this->alice, 'desk-a', 'proj-a');
        $foreign = $this->provider($this->tenantB)->id;

        $this->send($this->alice, $id, 'Hi', self::MODEL, $foreign)->assertSessionHas('chat_error', 'provider_not_found');
        $this->send($this->alice, $id, str_repeat('x', 4001))->assertSessionHasErrors('content');
        $this->send($this->alice, $id, '')->assertSessionHasErrors('content');
        $this->send($this->alice, $id, 'Hi', 'bad model!')->assertSessionHasErrors('model');
        self::assertSame(0, DB::table('codebridge_workspace_messages')->count());
        Http::assertNothingSent();
    }

    public function test_transcript_shows_the_latest_200_messages_in_order_so_new_turns_never_disappear(): void
    {
        $id = $this->start($this->alice, 'desk-a', 'proj-a');
        $rows = [];
        for ($i = 0; $i < 250; $i++) {
            $rows[] = [
                'id' => (string) Str::ulid(), 'conversation_id' => $id, 'role' => 'user', 'content' => 'm'.$i,
                'status' => 'complete', 'created_at' => now(), 'updated_at' => now(),
            ];
        }
        DB::table('codebridge_workspace_messages')->insert($rows);
        $running = $this->seedAssistant($id, 'running', now());

        $this->actingAs($this->alice)->get($this->pageUrl('desk-a', 'proj-a', $id))->assertOk()
            ->assertInertia(fn (AssertableInertia $inertia) => $inertia
                ->has('transcript.messages', 200)
                ->where('transcript.messages.0.content', 'm51')
                ->where('transcript.messages.198.content', 'm249')
                ->where('transcript.messages.199.id', $running)
                ->where('transcript.messages.199.status', 'running'));
    }

    private function start(User $user, string $device, string $project): string
    {
        $this->actingAs($user)->post('/services/kmj-codebridge/workspace/conversations', ['device_id' => $device, 'project_id' => $project, 'title' => 'T'])->assertRedirect();

        return (string) DB::table('codebridge_workspace_conversations')->orderByDesc('created_at')->value('id');
    }

    private function send(User $user, string $conversation, string $content, string $model = self::MODEL, ?string $provider = null): TestResponse
    {
        return $this->actingAs($user)->post("/services/kmj-codebridge/workspace/conversations/{$conversation}/messages", [
            'content' => $content, 'provider_id' => $provider ?? $this->providerA, 'model' => $model,
        ]);
    }

    private function retry(User $user, string $conversation, string $message): TestResponse
    {
        return $this->actingAs($user)->post("/services/kmj-codebridge/workspace/conversations/{$conversation}/messages/{$message}/retry", [
            'provider_id' => $this->providerA, 'model' => self::MODEL,
        ]);
    }

    private function cancelUrl(string $conversation, string $message): string
    {
        return "/services/kmj-codebridge/workspace/conversations/{$conversation}/messages/{$message}/cancel";
    }

    private function pageUrl(string $device, string $project, ?string $conversation = null): string
    {
        return '/services/kmj-codebridge/workspace?device='.$device.'&project='.$project.($conversation !== null ? '&c='.$conversation : '');
    }

    private function seedAssistant(string $conversation, string $status, DateTimeInterface $startedAt): string
    {
        $id = (string) Str::ulid();
        DB::table('codebridge_workspace_messages')->insert([
            'id' => $id, 'conversation_id' => $conversation, 'role' => 'assistant', 'content' => '', 'status' => $status,
            'provider_id' => $this->providerA, 'model' => self::MODEL, 'started_at' => $startedAt,
            'created_at' => now(), 'updated_at' => now(),
        ]);

        return $id;
    }

    private function provider(string $tenant): AiProvider
    {
        $provider = new AiProvider;
        $provider->forceFill([
            'organization_id' => $tenant, 'created_by' => User::factory()->create()->id, 'name' => 'Groq '.Str::random(4),
            'preset' => 'groq', 'kind' => 'openai-compatible', 'base_url' => 'https://api.groq.com/openai/v1',
            'api_key' => self::KEY, 'key_last4' => 'cdef', 'enabled' => true, 'free_only' => true,
            'health' => 'ok', 'models_cache' => [self::MODEL], 'models_checked_at' => now(),
        ])->save();

        return $provider;
    }

    private function tenant(string $device, string $project): string
    {
        $tenant = (string) Str::uuid();
        $license = (string) Str::uuid();
        $activation = (string) Str::uuid();
        $now = now();
        DB::table('organizations')->insert(['id' => $tenant, 'name' => 'Org '.$device, 'created_at' => $now, 'updated_at' => $now]);
        DB::table('kslp_licenses')->insert([
            'id' => $license, 'customer_id' => $tenant, 'product' => 'KMJ_CODEBRIDGE', 'plan' => 'professional',
            'status' => 'active', 'sequence' => 1, 'starts_at' => $now->copy()->subDay(), 'expires_at' => $now->copy()->addYear(),
            'grace_until' => $now->copy()->addYear()->addDays(2), 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('kslp_activations')->insert([
            'id' => $activation, 'license_id' => $license, 'server_identity' => 'codebridge-device:'.$device,
            'machine_identity_hash' => hash('sha256', $device), 'idempotency_key' => 'workspace-chat-test:'.$device,
            'activated_at' => $now, 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('codebridge_device_credentials')->insert([
            'id' => (string) Str::uuid(), 'license_id' => $license, 'activation_id' => $activation, 'tenant_id' => $tenant,
            'device_id' => $device, 'server_identity' => 'codebridge-device:'.$device,
            'token_hash' => hash('sha256', 'test-token-'.$device), 'lease_sequence' => 0, 'expires_at_epoch' => time() + 3600,
        ]);
        DB::table('codebridge_device_pairings')->insert([
            'id' => (string) Str::uuid(), 'device_code_hash' => hash('sha256', 'device-code:'.$device),
            'user_code_hash' => hash('sha256', 'user-code:'.$device), 'device_id' => $device, 'device_name' => $device,
            'platform' => 'win32', 'arch' => 'x64', 'project_id' => $project, 'project_name' => $project,
            'requested_permissions' => json_encode(['read', 'write', 'execute']), 'code_challenge' => str_repeat('x', 43),
            'status' => 'consumed', 'tenant_id' => $tenant, 'license_id' => $license, 'activation_id' => $activation,
            'expires_at' => $now->copy()->addMinutes(5), 'consumed_at' => $now, 'created_at' => $now, 'updated_at' => $now,
        ]);

        return $tenant;
    }
}
