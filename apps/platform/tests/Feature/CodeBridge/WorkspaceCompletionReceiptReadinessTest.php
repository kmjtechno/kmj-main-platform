<?php

declare(strict_types=1);

namespace Tests\Feature\CodeBridge;

use App\Services\CodeBridge\Workspace\WorkspaceCompletionReceiptReadiness;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use InvalidArgumentException;
use Tests\TestCase;

final class WorkspaceCompletionReceiptReadinessTest extends TestCase
{
    use RefreshDatabase;

    private string $jobId;

    private const TENANT = 'org-test-a';

    private const DEVICE = 'desk-a';

    private const USER = 17;

    protected function setUp(): void
    {
        parent::setUp();
        $this->jobId = (string) Str::ulid();
    }

    public function test_started_and_finished_server_report_is_consistent_but_never_a_signed_or_billable_proof(): void
    {
        $this->seedTerminal('succeeded');
        $witness = app(WorkspaceCompletionReceiptReadiness::class)
            ->inspectTrusted(self::TENANT, self::USER, self::DEVICE, $this->jobId);

        $this->assertSame('server_report_consistent_not_attested', $witness['status']);
        $this->assertTrue($witness['recorded_terminal']);
        $this->assertSame('succeeded', $witness['outcome']);
        $this->assertFalse($witness['signature_verified']);
        $this->assertFalse($witness['quota_settlement_authorized']);
        $this->assertDatabaseCount('codebridge_usage_periods', 0);
        $this->assertDatabaseCount('codebridge_usage_executions', 0);
    }

    public function test_device_reported_tool_failure_after_start_is_consistent_but_not_billable(): void
    {
        $this->seedTerminal('failed', 'device_reported_failure');
        $witness = app(WorkspaceCompletionReceiptReadiness::class)
            ->inspectTrusted(self::TENANT, self::USER, self::DEVICE, $this->jobId);

        $this->assertTrue($witness['recorded_terminal']);
        $this->assertSame('failed', $witness['outcome']);
        $this->assertFalse($witness['quota_settlement_authorized']);
    }

    public function test_wrong_tenant_user_device_and_job_never_disclose_another_report(): void
    {
        $this->seedTerminal('succeeded');
        $inspector = app(WorkspaceCompletionReceiptReadiness::class);

        foreach ([
            ['org-other', self::USER, self::DEVICE, $this->jobId],
            [self::TENANT, self::USER + 1, self::DEVICE, $this->jobId],
            [self::TENANT, self::USER, 'other-device', $this->jobId],
            [self::TENANT, self::USER, self::DEVICE, (string) Str::ulid()],
        ] as [$tenant, $user, $device, $job]) {
            $this->assertSame(
                'not_proven',
                $inspector->inspectTrusted($tenant, $user, $device, $job)['status'],
            );
        }
        $this->assertFalse(
            $inspector->inspectTrusted('org-other', self::USER, self::DEVICE, $this->jobId)['quota_settlement_authorized'],
        );
    }

    public function test_pre_start_refusal_is_never_a_completed_tool_call(): void
    {
        $this->seedTerminal('failed', 'device_reported_failure', false);
        $this->assertNotProven();
    }

    public function test_expiry_grant_revocation_and_cancellation_cannot_settle_a_call(): void
    {
        foreach (['lease_expired', 'grant_revoked', 'cancelled_by_user'] as $error) {
            DB::table('codebridge_workspace_job_events')->delete();
            DB::table('codebridge_workspace_jobs')->delete();
            $this->seedTerminal('failed', $error);
            $this->assertNotProven();
        }
    }

    public function test_unexpected_event_order_missing_claim_and_missing_terminal_event_fail_closed(): void
    {
        $this->seedTerminal('succeeded');
        DB::table('codebridge_workspace_job_events')->where('kind', 'claimed')->delete();
        $this->assertNotProven();

        DB::table('codebridge_workspace_job_events')->where('kind', 'succeeded')->delete();
        $this->assertNotProven();

        DB::table('codebridge_workspace_job_events')->insert([
            'job_id' => $this->jobId,
            'seq' => 6,
            'kind' => 'succeeded',
            'detail' => null,
            'created_at' => now(),
        ]);
        $this->assertNotProven();
    }

    public function test_missing_claim_hash_and_incorrect_finish_time_fail_closed(): void
    {
        $this->seedTerminal('succeeded');
        DB::table('codebridge_workspace_jobs')->where('id', $this->jobId)->update(['claim_hash' => null]);
        $this->assertNotProven();
        DB::table('codebridge_workspace_jobs')->where('id', $this->jobId)->update([
            'claim_hash' => str_repeat('a', 64),
            'started_at' => now()->addMinute(),
            'finished_at' => now(),
        ]);
        $this->assertNotProven();
    }

    public function test_reordered_or_duplicate_events_are_not_terminal_evidence(): void
    {
        $this->seedTerminal('succeeded');
        DB::table('codebridge_workspace_job_events')->where('seq', 2)->update(['kind' => 'started']);
        DB::table('codebridge_workspace_job_events')->where('seq', 3)->update(['kind' => 'claimed']);
        $this->assertNotProven();
    }

    public function test_invalid_scope_is_rejected_without_accessing_a_job(): void
    {
        $this->expectException(InvalidArgumentException::class);
        app(WorkspaceCompletionReceiptReadiness::class)
            ->inspectTrusted('..', self::USER, self::DEVICE, $this->jobId);
    }

    private function assertNotProven(): void
    {
        $witness = app(WorkspaceCompletionReceiptReadiness::class)
            ->inspectTrusted(self::TENANT, self::USER, self::DEVICE, $this->jobId);
        $this->assertSame('not_proven', $witness['status']);
        $this->assertFalse($witness['recorded_terminal']);
        $this->assertFalse($witness['signature_verified']);
        $this->assertFalse($witness['quota_settlement_authorized']);
    }

    private function seedTerminal(string $status, ?string $error = null, bool $started = true): void
    {
        $now = now();
        DB::table('codebridge_workspace_jobs')->insert([
            'id' => $this->jobId,
            'tenant_id' => self::TENANT,
            'device_id' => self::DEVICE,
            'project_id' => 'project-one',
            'user_id' => self::USER,
            'tool' => 'quality_gate',
            'arguments' => '{"gate":"fast"}',
            'idempotency_key' => 'fixed-test-key-123456',
            'status' => $status,
            'claim_hash' => str_repeat('a', 64),
            'claimed_at' => $now->copy()->subSeconds(20),
            'started_at' => $started ? $now->copy()->subSeconds(10) : null,
            'finished_at' => $now,
            'error_code' => $error,
            'created_at' => $now->copy()->subSeconds(30),
            'updated_at' => $now,
        ]);
        $events = ['queued', 'claimed', ...($started ? ['started'] : []), $status];
        foreach ($events as $i => $kind) {
            DB::table('codebridge_workspace_job_events')->insert([
                'job_id' => $this->jobId,
                'seq' => $i + 1,
                'kind' => $kind,
                'detail' => null,
                'created_at' => $now,
            ]);
        }
    }
}
