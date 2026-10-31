<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiProvider;
use App\Models\User;
use App\Services\AiProviders\EndpointGuard;
use App\Services\AiProviders\ResolvesAiProviderScope;
use App\Services\CodeBridge\Workspace\WorkspaceToolProposalService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Illuminate\Testing\TestResponse;
use Inertia\Testing\AssertableInertia;
use Tests\Support\FakeAiProviderScope;
use Tests\TestCase;

/** Consent bridge: assistant reply -> pending proposal -> explicit same-user confirm -> real job. */
final class CodeBridgeWorkspaceToolProposalTest extends TestCase
{
    use RefreshDatabase;

    private const KEY = 'gsk_test_0123456789abcdef';

    private const MODEL = 'llama-3.1-8b-instant';

    private const URL = 'https://api.groq.com/openai/v1/chat/completions';

    private const BLOCK = "Let me check.\n```kmj-tool-proposal\n{\"tool\":\"git_status\",\"arguments\":{}}\n```";

    private string $tenantA;

    private string $tenantB;

    private string $providerA;

    private User $alice;

    private User $bob;

    private User $mallory;

    protected function setUp(): void
    {
        parent::setUp();
        config()->set('codebridge.enabled', true);
        config()->set('codebridge.workspace_jobs_enabled', true);
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

    public function test_a_valid_proposal_is_stored_pending_and_nothing_is_queued(): void
    {
        $id = $this->chatWith(self::BLOCK);

        $row = (array) DB::table('codebridge_workspace_tool_proposals')->first();
        self::assertSame(['git_status', [], 'pending', null], [$row['tool'], json_decode((string) $row['arguments'], true), $row['status'], $row['job_id']]);
        self::assertSame([$this->tenantA, $this->alice->id, 'desk-a', 'proj-a'], [$row['tenant_id'], (int) $row['user_id'], $row['device_id'], $row['project_id']]);
        self::assertSame(0, DB::table('codebridge_workspace_jobs')->count()); // no bypassed approval
        self::assertContains('tool_proposed', DB::table('codebridge_workspace_events')->pluck('kind')->all());
        $this->actingAs($this->alice)->get($this->page($id))->assertInertia(fn (AssertableInertia $page) => $page
            ->where('transcript.proposals.0.status', 'pending')
            ->where('transcript.proposals.0.tool', 'git_status')
            ->where('transcript.proposals.0.job_status', null));
    }

    public function test_only_closed_catalog_proposals_are_ever_stored(): void
    {
        foreach ([
            'no block at all',
            "```kmj-tool-proposal\n{\"tool\":\"shell\",\"arguments\":{\"cmd\":\"rm -rf /\"}}\n```",
            "```kmj-tool-proposal\n{\"tool\":\"git_status\",\"arguments\":{\"cmd\":\"id\"}}\n```",
            "```kmj-tool-proposal\n{\"tool\":\"quality_gate\",\"arguments\":{\"gate\":\"x; rm -rf /\"}}\n```",
            "```kmj-tool-proposal\n{\"tool\":\"git_status\",\"arguments\":{},\"device_id\":\"desk-b\"}\n```",
            "```kmj-tool-proposal\nnot json\n```",
            "```kmj-tool-proposal\n{\"tool\":[\"git_status\"]}\n```",
        ] as $reply) {
            self::assertNull(WorkspaceToolProposalService::parse($reply), $reply);
        }
        self::assertSame(['tool' => 'quality_gate', 'arguments' => ['gate' => 'fast']], WorkspaceToolProposalService::parse("```kmj-tool-proposal\n{\"tool\":\"quality_gate\",\"arguments\":{\"gate\":\"fast\"}}\n```"));
        $this->chatWith("```kmj-tool-proposal\n{\"tool\":\"shell\",\"arguments\":{}}\n```");
        self::assertSame(0, DB::table('codebridge_workspace_tool_proposals')->count());
    }

    public function test_feature_flag_off_stores_nothing_and_the_prompt_never_offers_tools(): void
    {
        config()->set('codebridge.workspace_jobs_enabled', false);
        $this->chatWith(self::BLOCK);
        self::assertSame(0, DB::table('codebridge_workspace_tool_proposals')->count());
        Http::assertSent(fn (Request $request): bool => ! str_contains((string) $request['messages'][0]['content'], 'kmj-tool-proposal'));
    }

    public function test_enabled_prompt_lists_only_catalog_tools_and_states_consent(): void
    {
        $this->chatWith('plain answer');
        Http::assertSent(function (Request $request): bool {
            $system = (string) $request['messages'][0]['content'];

            return str_contains($system, 'kmj-tool-proposal') && str_contains($system, 'git_status')
                && str_contains($system, 'quality_gate') && str_contains($system, 'user must press Confirm');
        });
    }

    public function test_confirm_queues_exactly_one_real_job_and_is_idempotent(): void
    {
        $conversation = $this->chatWith(self::BLOCK);
        $proposal = $this->proposalId();

        $this->confirm($this->alice, $proposal)->assertRedirect();
        $this->confirm($this->alice, $proposal)->assertRedirect(); // double click

        self::assertSame(1, DB::table('codebridge_workspace_jobs')->count());
        $job = (array) DB::table('codebridge_workspace_jobs')->first();
        self::assertSame(['git_status', 'queued', $this->tenantA, $this->alice->id, 'desk-a', 'proj-a'], [$job['tool'], $job['status'], $job['tenant_id'], (int) $job['user_id'], $job['device_id'], $job['project_id']]);
        $stored = (array) DB::table('codebridge_workspace_tool_proposals')->first();
        self::assertSame(['confirmed', $job['id']], [$stored['status'], $stored['job_id']]);
        $this->actingAs($this->alice)->get($this->page($conversation))->assertInertia(fn (AssertableInertia $page) => $page
            ->where('transcript.proposals.0.status', 'confirmed')
            ->where('transcript.proposals.0.job_id', $job['id'])
            ->where('transcript.proposals.0.job_status', 'queued'));
    }

    public function test_the_real_job_status_and_cancel_flow_through_the_existing_pipeline(): void
    {
        $conversation = $this->chatWith(self::BLOCK);
        $this->confirm($this->alice, $this->proposalId())->assertRedirect();
        $job = (string) DB::table('codebridge_workspace_jobs')->value('id');

        $this->actingAs($this->alice)->post('/services/kmj-codebridge/workspace/tools/'.$job.'/cancel')->assertRedirect();

        self::assertSame('cancelled', DB::table('codebridge_workspace_jobs')->where('id', $job)->value('status'));
        $this->actingAs($this->alice)->get($this->page($conversation))
            ->assertInertia(fn (AssertableInertia $page) => $page->where('transcript.proposals.0.job_status', 'cancelled'));
    }

    public function test_reject_blocks_confirm_and_a_confirmed_proposal_cannot_be_rejected(): void
    {
        $this->chatWith(self::BLOCK);
        $proposal = $this->proposalId();
        $this->reject($this->alice, $proposal)->assertRedirect();
        $this->confirm($this->alice, $proposal)->assertRedirect()->assertSessionHas('chat_error', 'proposal_rejected');
        self::assertSame(0, DB::table('codebridge_workspace_jobs')->count());
        self::assertSame('rejected', DB::table('codebridge_workspace_tool_proposals')->value('status'));

        $this->chatWith(self::BLOCK, 'second');
        $second = (string) DB::table('codebridge_workspace_tool_proposals')->where('status', 'pending')->value('id');
        $this->confirm($this->alice, $second)->assertRedirect();
        $this->reject($this->alice, $second)->assertRedirect()->assertSessionHas('chat_error', 'proposal_already_confirmed');
        self::assertSame('confirmed', DB::table('codebridge_workspace_tool_proposals')->where('id', $second)->value('status'));
        self::assertSame(1, DB::table('codebridge_workspace_jobs')->count());
    }

    public function test_other_tenant_and_other_user_get_404_and_nothing_changes(): void
    {
        $this->chatWith(self::BLOCK);
        $proposal = $this->proposalId();
        foreach ([$this->mallory, $this->bob] as $intruder) {
            $this->confirm($intruder, $proposal)->assertNotFound();
            $this->reject($intruder, $proposal)->assertNotFound();
        }
        self::assertSame('pending', DB::table('codebridge_workspace_tool_proposals')->value('status'));
        self::assertSame(0, DB::table('codebridge_workspace_jobs')->count());
        $this->actingAs($this->alice)->post('/services/kmj-codebridge/workspace/proposals/not-a-ulid/confirm')->assertNotFound();
    }

    public function test_guests_cannot_decide_proposals(): void
    {
        $this->chatWith(self::BLOCK);
        auth()->logout(); // chatWith authenticated Alice; the guest request must clear that guard.
        $this->post('/services/kmj-codebridge/workspace/proposals/'.$this->proposalId().'/confirm')->assertRedirect('/login');
        self::assertSame('pending', DB::table('codebridge_workspace_tool_proposals')->value('status'));
    }

    public function test_missing_device_permission_is_a_403_and_the_proposal_stays_pending(): void
    {
        DB::table('codebridge_device_pairings')->where('tenant_id', $this->tenantA)->update(['requested_permissions' => json_encode(['read'])]);
        $this->chatWith("```kmj-tool-proposal\n{\"tool\":\"quality_gate\",\"arguments\":{\"gate\":\"fast\"}}\n```");
        $this->confirm($this->alice, $this->proposalId())->assertForbidden();
        self::assertSame(0, DB::table('codebridge_workspace_jobs')->count());
        self::assertSame('pending', DB::table('codebridge_workspace_tool_proposals')->value('status'));
    }

    public function test_revoked_pairing_is_a_404_at_confirm_time(): void
    {
        $this->chatWith(self::BLOCK);
        DB::table('codebridge_device_credentials')->where('tenant_id', $this->tenantA)->update(['revoked_at' => now()]);
        $this->confirm($this->alice, $this->proposalId())->assertNotFound();
        self::assertSame(0, DB::table('codebridge_workspace_jobs')->count());
        self::assertSame('pending', DB::table('codebridge_workspace_tool_proposals')->value('status'));
    }

    public function test_jobs_disabled_at_confirm_time_degrades_gracefully(): void
    {
        $conversation = $this->chatWith(self::BLOCK);
        config()->set('codebridge.workspace_jobs_enabled', false);
        $this->confirm($this->alice, $this->proposalId())->assertRedirect()->assertSessionHas('chat_error', 'jobs_disabled');
        self::assertSame(0, DB::table('codebridge_workspace_jobs')->count());
        self::assertSame('pending', DB::table('codebridge_workspace_tool_proposals')->value('status'));
        $this->actingAs($this->alice)->get($this->page($conversation))
            ->assertInertia(fn (AssertableInertia $page) => $page->where('capabilities.job_events.available', false));
    }

    public function test_an_expired_proposal_cannot_be_confirmed_and_stays_expired(): void
    {
        $this->chatWith(self::BLOCK);
        DB::table('codebridge_workspace_tool_proposals')->update(['created_at' => now()->subSeconds(WorkspaceToolProposalService::TTL_SECONDS + 5)]);
        $this->confirm($this->alice, $this->proposalId())->assertRedirect()->assertSessionHas('chat_error', 'proposal_expired');
        self::assertSame('expired', DB::table('codebridge_workspace_tool_proposals')->value('status'));
        self::assertSame(0, DB::table('codebridge_workspace_jobs')->count());
    }

    public function test_the_active_job_cap_still_applies_to_confirmed_proposals(): void
    {
        $this->chatWith(self::BLOCK);
        for ($i = 0; $i < 5; $i++) {
            DB::table('codebridge_workspace_jobs')->insert([
                'id' => (string) Str::ulid(), 'tenant_id' => $this->tenantA, 'device_id' => 'desk-a', 'project_id' => 'proj-a',
                'user_id' => $this->alice->id, 'tool' => 'git_status', 'arguments' => '[]', 'idempotency_key' => 'cap-'.$i.str_repeat('x', 16),
                'status' => 'queued', 'created_at' => now(), 'updated_at' => now(),
            ]);
        }
        $this->confirm($this->alice, $this->proposalId())->assertRedirect()->assertSessionHas('chat_error', 'too_many_active_jobs');
        self::assertSame('pending', DB::table('codebridge_workspace_tool_proposals')->value('status'));
        self::assertSame(5, DB::table('codebridge_workspace_jobs')->count());
    }

    private function chatWith(string $reply, string $title = 'T'): string
    {
        Http::fake([self::URL => Http::response(['choices' => [['message' => ['content' => $reply]]]], 200)]);
        $this->actingAs($this->alice)->post('/services/kmj-codebridge/workspace/conversations', ['device_id' => 'desk-a', 'project_id' => 'proj-a', 'title' => $title])->assertRedirect();
        $id = (string) DB::table('codebridge_workspace_conversations')->orderByDesc('created_at')->orderByDesc('id')->value('id');
        $this->actingAs($this->alice)->post("/services/kmj-codebridge/workspace/conversations/{$id}/messages", [
            'content' => 'status please', 'provider_id' => $this->providerA, 'model' => self::MODEL,
        ])->assertRedirect();

        return $id;
    }

    private function proposalId(): string
    {
        return (string) DB::table('codebridge_workspace_tool_proposals')->orderByDesc('id')->value('id');
    }

    private function confirm(User $user, string $proposal): TestResponse
    {
        return $this->actingAs($user)->post("/services/kmj-codebridge/workspace/proposals/{$proposal}/confirm");
    }

    private function reject(User $user, string $proposal): TestResponse
    {
        return $this->actingAs($user)->post("/services/kmj-codebridge/workspace/proposals/{$proposal}/reject");
    }

    private function page(string $conversation): string
    {
        return '/services/kmj-codebridge/workspace?device=desk-a&project=proj-a&c='.$conversation;
    }

    private static function token(string $device): string
    {
        return 'test-device-token-'.str_repeat('x', 24).'-'.$device;
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

    private function tenant(string $device, string $project, array $permissions = ['read', 'write', 'execute']): string
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
            'machine_identity_hash' => hash('sha256', $device), 'idempotency_key' => 'workspace-jobs-test:'.$device,
            'activated_at' => $now, 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('codebridge_device_credentials')->insert([
            'id' => (string) Str::uuid(), 'license_id' => $license, 'activation_id' => $activation, 'tenant_id' => $tenant,
            'device_id' => $device, 'server_identity' => 'codebridge-device:'.$device,
            'token_hash' => hash('sha256', self::token($device)), 'lease_sequence' => 0, 'expires_at_epoch' => time() + 3600,
        ]);
        DB::table('codebridge_device_pairings')->insert([
            'id' => (string) Str::uuid(), 'device_code_hash' => hash('sha256', 'device-code:'.$device),
            'user_code_hash' => hash('sha256', 'user-code:'.$device), 'device_id' => $device, 'device_name' => $device,
            'platform' => 'win32', 'arch' => 'x64', 'project_id' => $project, 'project_name' => $project,
            'requested_permissions' => json_encode($permissions), 'code_challenge' => str_repeat('x', 43),
            'status' => 'consumed', 'tenant_id' => $tenant, 'license_id' => $license, 'activation_id' => $activation,
            'expires_at' => $now->copy()->addMinutes(5), 'consumed_at' => $now, 'created_at' => $now, 'updated_at' => $now,
        ]);

        return $tenant;
    }
}
