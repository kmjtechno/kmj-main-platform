<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\AiProviders\ResolvesAiProviderScope;
use App\Services\CodeBridge\Workspace\WorkspaceJobService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Illuminate\Testing\TestResponse;
use Inertia\Testing\AssertableInertia;
use Tests\Support\FakeAiProviderScope;
use Tests\TestCase;

final class CodeBridgeWorkspaceJobsTest extends TestCase
{
    use RefreshDatabase;

    private string $tenantA;

    private string $tenantB;

    private User $alice;

    private User $bob;

    private User $mallory;

    protected function setUp(): void
    {
        parent::setUp();
        config()->set('codebridge.enabled', true);
        config()->set('codebridge.workspace_jobs_enabled', true);
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
    }

    public function test_feature_is_off_by_default_and_fails_closed_for_both_sides(): void
    {
        config()->set('codebridge.workspace_jobs_enabled', false);
        $this->enqueue($this->alice, 'git_status')->assertRedirect();
        self::assertSame(0, DB::table('codebridge_workspace_jobs')->count());
        $this->withToken(self::token('desk-a'))->postJson('/api/codebridge/v1/jobs/claim')->assertStatus(503);
        $this->actingAs($this->alice)->get($this->page('desk-a', 'proj-a'))
            ->assertInertia(fn (AssertableInertia $page) => $page->where('capabilities.job_events.available', false));
    }

    public function test_a_named_tool_runs_through_real_transitions_with_durable_events_and_evidence(): void
    {
        $this->enqueue($this->alice, 'quality_gate', 'fast')->assertRedirect();
        $job = DB::table('codebridge_workspace_jobs')->first();
        self::assertSame('queued', $job->status);
        self::assertSame('{"gate":"fast"}', $job->arguments);

        // Nothing is "running" until the device says so.
        $this->actingAs($this->alice)->get($this->page('desk-a', 'proj-a', $job->id))->assertInertia(
            fn (AssertableInertia $page) => $page->where('capabilities.job_events.available', true)
                ->where('jobs.0.status', 'queued')->where('jobEvents.0.kind', 'queued')->has('tools', 3),
        );

        $claim = $this->device('desk-a')->postJson('/api/codebridge/v1/jobs/claim')->assertOk()->json('job');
        self::assertSame($job->id, $claim['id']);
        self::assertSame('quality_gate', $claim['tool']);
        self::assertSame(['gate' => 'fast'], $claim['arguments']);
        $this->device('desk-a')->postJson('/api/codebridge/v1/jobs/claim')->assertOk()->assertJson(['job' => null]);

        $this->report($job->id, $claim['claim_token'], ['kind' => 'progress', 'progress' => 10])->assertStatus(422);
        $this->report($job->id, $claim['claim_token'], ['kind' => 'started'])->assertOk()->assertJson(['status' => 'running']);
        $this->report($job->id, $claim['claim_token'], ['kind' => 'progress', 'progress' => 60, 'detail' => 'lint done'])->assertOk();
        $this->report($job->id, $claim['claim_token'], ['kind' => 'progress', 'progress' => 20])->assertOk();
        self::assertSame(60, (int) DB::table('codebridge_workspace_jobs')->value('progress'));
        $this->report($job->id, $claim['claim_token'], [
            'kind' => 'succeeded', 'summary' => 'fast gate passed',
            'evidence' => ['commit_sha' => str_repeat('a', 40), 'gate' => 'fast', 'exit_code' => 0, 'duration_ms' => 4200, 'result' => 'pass'],
        ])->assertOk()->assertJson(['status' => 'succeeded']);

        $this->actingAs($this->alice)->get($this->page('desk-a', 'proj-a', $job->id))->assertInertia(
            fn (AssertableInertia $page) => $page->where('jobs.0.status', 'succeeded')->where('jobs.0.progress', 100)
                ->where('jobs.0.evidence.result', 'pass')->where('jobs.0.summary', 'fast gate passed')
                ->where('jobEvents.0.seq', 1)
                ->where('jobEvents', fn ($events) => collect($events)->pluck('kind')->all() === ['queued', 'claimed', 'started', 'progress', 'progress', 'succeeded']),
        );
        // A finished job cannot be reported on again.
        $this->report($job->id, $claim['claim_token'], ['kind' => 'failed'])->assertStatus(409)->assertJson(['error' => 'job_not_active']);
    }

    public function test_only_catalogued_tools_with_closed_arguments_are_accepted(): void
    {
        foreach ([['rm_rf', null], ['git_status', 'fast'], ['quality_gate', null], ['quality_gate', '../../etc'], ['quality_gate', 'Fast;rm'], ['bash', 'ls']] as [$tool, $gate]) {
            $this->enqueue($this->alice, $tool, $gate)->assertRedirect();
        }
        self::assertSame(0, DB::table('codebridge_workspace_jobs')->count());
        $this->enqueue($this->alice, 'quality_gate', 'fast')->assertSessionMissing('chat_error');
        self::assertSame(1, DB::table('codebridge_workspace_jobs')->count());
    }

    public function test_grants_projects_tenants_and_users_are_enforced(): void
    {
        // Read-only pairing: execute tools are 403, read tools are fine.
        $tenantR = $this->tenant('desk-r', 'proj-r', ['read']);
        $reader = User::factory()->create(['email_verified_at' => now()]);
        $this->app->instance(ResolvesAiProviderScope::class, new FakeAiProviderScope([
            $this->alice->id => ['organization_id' => $this->tenantA, 'can_manage' => true],
            $this->bob->id => ['organization_id' => $this->tenantA, 'can_manage' => false],
            $this->mallory->id => ['organization_id' => $this->tenantB, 'can_manage' => true],
            $reader->id => ['organization_id' => $tenantR, 'can_manage' => true],
        ]));
        $this->enqueue($reader, 'quality_gate', 'fast', 'desk-r', 'proj-r')->assertForbidden();
        $this->enqueue($reader, 'git_status', null, 'desk-r', 'proj-r')->assertRedirect();
        self::assertSame(1, DB::table('codebridge_workspace_jobs')->count());

        // Wrong project, another tenant's device, unknown device.
        $this->enqueue($this->alice, 'git_status', null, 'desk-a', 'proj-b')->assertNotFound();
        $this->enqueue($this->alice, 'git_status', null, 'desk-b', 'proj-b')->assertNotFound();
        $this->enqueue($this->mallory, 'git_status', null, 'desk-a', 'proj-a')->assertNotFound();
        self::assertSame(1, DB::table('codebridge_workspace_jobs')->count());

        // Jobs are private to the requesting user and tenant, never forbidden-vs-missing leaky.
        $this->enqueue($this->alice, 'git_status')->assertRedirect();
        $id = (string) DB::table('codebridge_workspace_jobs')->where('tenant_id', $this->tenantA)->value('id');
        $this->actingAs($this->bob)->post($this->cancelUrl($id))->assertNotFound();
        $this->actingAs($this->mallory)->post($this->cancelUrl($id))->assertNotFound();
        $this->actingAs($this->bob)->get($this->page('desk-a', 'proj-a', $id))->assertInertia(fn (AssertableInertia $page) => $page->has('jobs', 0)->has('jobEvents', 0));
        $this->actingAs($this->mallory)->get($this->page('desk-a', 'proj-a', $id))->assertInertia(fn (AssertableInertia $page) => $page->where('selected', null)->has('jobs', 0));
        self::assertSame('queued', DB::table('codebridge_workspace_jobs')->where('id', $id)->value('status'));
    }

    public function test_duplicate_requests_are_idempotent_and_conflicting_reuse_is_rejected(): void
    {
        $key = Str::random(24);
        $this->enqueue($this->alice, 'quality_gate', 'fast', 'desk-a', 'proj-a', $key)->assertRedirect();
        $this->enqueue($this->alice, 'quality_gate', 'fast', 'desk-a', 'proj-a', $key)->assertRedirect();
        self::assertSame(1, DB::table('codebridge_workspace_jobs')->count());
        self::assertSame(1, DB::table('codebridge_workspace_job_events')->count());
        $this->enqueue($this->alice, 'quality_gate', 'full', 'desk-a', 'proj-a', $key)->assertSessionHas('chat_error', 'idempotency_conflict');
        self::assertSame(1, DB::table('codebridge_workspace_jobs')->count());
        $this->enqueue($this->alice, 'git_status', null, 'desk-a', 'proj-a', 'short')->assertSessionHas('chat_error', 'invalid_idempotency_key');
    }

    public function test_cancel_wins_over_a_late_device_report_and_is_idempotent(): void
    {
        $this->enqueue($this->alice, 'git_status');
        $id = (string) DB::table('codebridge_workspace_jobs')->value('id');
        $claim = $this->device('desk-a')->postJson('/api/codebridge/v1/jobs/claim')->json('job');
        $this->report($id, $claim['claim_token'], ['kind' => 'started'])->assertOk();

        $this->actingAs($this->alice)->post($this->cancelUrl($id))->assertRedirect();
        $this->actingAs($this->alice)->post($this->cancelUrl($id))->assertRedirect();
        self::assertSame('cancelled', DB::table('codebridge_workspace_jobs')->where('id', $id)->value('status'));
        self::assertSame(1, DB::table('codebridge_workspace_job_events')->where('job_id', $id)->where('kind', 'cancelled')->count());
        $this->report($id, $claim['claim_token'], ['kind' => 'succeeded'])->assertStatus(409)->assertJson(['error' => 'job_not_active']);
        self::assertSame('cancelled', DB::table('codebridge_workspace_jobs')->where('id', $id)->value('status'));
    }

    public function test_unclaimed_and_silent_jobs_expire_honestly(): void
    {
        $this->enqueue($this->alice, 'git_status');
        DB::table('codebridge_workspace_jobs')->update(['created_at' => now()->subSeconds(WorkspaceJobService::QUEUE_TTL_SECONDS + 5)]);
        $this->actingAs($this->alice)->get($this->page('desk-a', 'proj-a'))->assertInertia(
            fn (AssertableInertia $page) => $page->where('jobs.0.status', 'expired')->where('jobs.0.error_code', 'not_claimed_by_device'),
        );

        $this->enqueue($this->alice, 'git_status');
        $id = (string) DB::table('codebridge_workspace_jobs')->where('status', 'queued')->value('id');
        $claim = $this->device('desk-a')->postJson('/api/codebridge/v1/jobs/claim')->json('job');
        $this->report($id, $claim['claim_token'], ['kind' => 'started'])->assertOk();
        DB::table('codebridge_workspace_jobs')->where('id', $id)->update(['lease_expires_at' => now()->subSeconds(5)]);
        $this->actingAs($this->alice)->get($this->page('desk-a', 'proj-a'))->assertInertia(
            fn (AssertableInertia $page) => $page->where('jobs.0.status', 'failed')->where('jobs.0.error_code', 'lease_expired'),
        );
        $this->report($id, $claim['claim_token'], ['kind' => 'succeeded'])->assertStatus(409);
    }

    public function test_device_credentials_claim_tokens_and_evidence_are_validated(): void
    {
        $this->enqueue($this->alice, 'git_status');
        $id = (string) DB::table('codebridge_workspace_jobs')->value('id');

        $this->postJson('/api/codebridge/v1/jobs/claim')->assertUnauthorized();
        $this->withToken('short')->postJson('/api/codebridge/v1/jobs/claim')->assertUnauthorized();
        // Another tenant's device sees nothing of this queue.
        $this->device('desk-b')->postJson('/api/codebridge/v1/jobs/claim')->assertOk()->assertJson(['job' => null]);

        $claim = $this->device('desk-a')->postJson('/api/codebridge/v1/jobs/claim')->json('job');
        $this->withToken(self::token('desk-a'))->postJson('/api/codebridge/v1/jobs/'.$id.'/events', ['kind' => 'started'])->assertUnauthorized();
        $this->report($id, str_repeat('0', 48), ['kind' => 'started'])->assertForbidden();
        $this->withToken(self::token('desk-b'))->withHeader('X-KMJ-Claim', $claim['claim_token'])
            ->postJson('/api/codebridge/v1/jobs/'.$id.'/events', ['kind' => 'started'])->assertNotFound();
        $this->report($id, $claim['claim_token'], ['kind' => 'started'])->assertOk();
        $this->report($id, $claim['claim_token'], ['kind' => 'started'])->assertStatus(422);
        foreach ([
            ['kind' => 'rm'], ['kind' => 'progress', 'progress' => 101], ['kind' => 'progress', 'progress' => 'x'],
            ['kind' => 'succeeded', 'evidence' => ['token' => 'secret']],
            ['kind' => 'succeeded', 'evidence' => ['ci_url' => 'https://evil.example/actions/runs/1']],
            ['kind' => 'succeeded', 'evidence' => ['commit_sha' => 'nothex']],
            ['kind' => 'succeeded', 'summary' => str_repeat('x', 2001)],
        ] as $bad) {
            $this->report($id, $claim['claim_token'], $bad)->assertStatus(422);
        }
        $this->report($id, $claim['claim_token'], ['kind' => 'succeeded', 'evidence' => ['ci_url' => 'https://github.com/kmjtechno/kmj-main-platform/actions/runs/123']])->assertOk();

        DB::table('codebridge_device_credentials')->where('device_id', 'desk-a')->update(['revoked_at' => now()]);
        $this->device('desk-a')->postJson('/api/codebridge/v1/jobs/claim')->assertUnauthorized();
    }

    public function test_a_revoked_grant_after_queueing_is_never_handed_to_the_device_and_limits_apply(): void
    {
        $this->enqueue($this->alice, 'quality_gate', 'fast');
        DB::table('codebridge_device_pairings')->where('device_id', 'desk-a')->update(['requested_permissions' => json_encode(['read'])]);
        $this->device('desk-a')->postJson('/api/codebridge/v1/jobs/claim')->assertOk()->assertJson(['job' => null]);
        $row = DB::table('codebridge_workspace_jobs')->first();
        self::assertSame('failed', $row->status);
        self::assertSame('grant_revoked', $row->error_code);

        DB::table('codebridge_workspace_jobs')->delete();
        for ($i = 0; $i < WorkspaceJobService::MAX_ACTIVE_PER_PROJECT; $i++) {
            $this->enqueue($this->alice, 'git_status');
        }
        $this->enqueue($this->alice, 'git_status')->assertSessionHas('chat_error', 'too_many_active_jobs');
        self::assertSame(WorkspaceJobService::MAX_ACTIVE_PER_PROJECT, DB::table('codebridge_workspace_jobs')->count());
    }

    public function test_guests_cannot_queue_or_cancel(): void
    {
        $this->post('/services/kmj-codebridge/workspace/tools', [])->assertRedirect('/login');
        $this->post('/services/kmj-codebridge/workspace/tools/'.Str::ulid().'/cancel')->assertRedirect('/login');
    }

    private function enqueue(User $user, string $tool, ?string $gate = null, string $device = 'desk-a', string $project = 'proj-a', ?string $key = null): TestResponse
    {
        return $this->actingAs($user)->post('/services/kmj-codebridge/workspace/tools', array_filter([
            'device_id' => $device, 'project_id' => $project, 'tool' => $tool, 'gate' => $gate,
            'idempotency_key' => $key ?? Str::random(24),
        ], fn ($value) => $value !== null));
    }

    private function device(string $device): self
    {
        return $this->withToken(self::token($device));
    }

    /** @param array<string, mixed> $payload */
    private function report(string $job, string $claim, array $payload): TestResponse
    {
        return $this->withToken(self::token('desk-a'))->withHeader('X-KMJ-Claim', $claim)
            ->postJson('/api/codebridge/v1/jobs/'.$job.'/events', $payload);
    }

    private function cancelUrl(string $job): string
    {
        return '/services/kmj-codebridge/workspace/tools/'.$job.'/cancel';
    }

    private function page(string $device, string $project, ?string $job = null): string
    {
        return '/services/kmj-codebridge/workspace?device='.$device.'&project='.$project.($job !== null ? '&j='.$job : '');
    }

    private static function token(string $device): string
    {
        return 'test-device-token-'.str_repeat('x', 24).'-'.$device;
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
