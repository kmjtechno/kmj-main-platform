<?php

namespace Tests\Unit;

use App\Services\Operations\DeliveryControlSnapshot;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

final class DeliveryControlSnapshotTest extends TestCase
{
    private string $path;

    protected function setUp(): void
    {
        parent::setUp();

        $this->path = storage_path('framework/testing/delivery-control.json');
        File::ensureDirectoryExists(dirname($this->path));
        File::delete($this->path);
        config([
            'kmj.ops.delivery_status_path' => $this->path,
            'kmj.ops.delivery_status_max_age_seconds' => 600,
        ]);
    }

    protected function tearDown(): void
    {
        File::delete($this->path);
        parent::tearDown();
    }

    public function test_missing_delivery_evidence_fails_closed(): void
    {
        $snapshot = app(DeliveryControlSnapshot::class)->capture();

        $this->assertSame('unavailable', $snapshot['status']);
        $this->assertSame('unknown', $snapshot['current_worker']['status']);
        $this->assertSame([], $snapshot['pipeline']);
        $this->assertSame([], $snapshot['recent_worker_runs']);
    }

    public function test_fresh_delivery_evidence_exposes_only_sanitized_operational_state(): void
    {
        File::put($this->path, json_encode([
            'version' => 1,
            'captured_at' => now()->toIso8601String(),
            'status' => 'active',
            'current_worker' => [
                'status' => 'in_progress',
                'run_id' => 12345,
                'run_number' => 108,
                'phase' => 'Run guarded worker cycle',
                'retry_count' => 1,
                'started_at' => now()->subMinute()->toIso8601String(),
            ],
            'current_task' => [
                'issue_number' => 142,
                'title' => 'Expose the current sidebar page to assistive technology',
                'state' => 'running',
            ],
            'runners' => [
                ['name' => 'runner-1', 'status' => 'online', 'busy' => true],
                ['name' => 'runner-2', 'status' => 'online', 'busy' => false],
            ],
            'pull_request' => [
                'number' => 148,
                'title' => 'agent: accessibility fix',
                'state' => 'open',
                'head_sha' => str_repeat('a', 40),
            ],
            'ci' => [
                'status' => 'in_progress',
                'run_id' => 999,
                'failed_checks' => 0,
            ],
            'staging' => [
                'approved_sha' => str_repeat('b', 40),
                'deployed_sha' => str_repeat('c', 40),
                'status' => 'deploying',
            ],
            'pipeline' => [
                ['key' => 'task', 'label' => 'Task', 'status' => 'complete'],
                ['key' => 'worker', 'label' => 'AI Worker', 'status' => 'active'],
                ['key' => 'pr', 'label' => 'PR', 'status' => 'waiting'],
            ],
            'blocker' => [
                'code' => null,
                'message' => null,
                'recoverable' => false,
            ],
            'recent_worker_runs' => [
                ['run_number' => 108, 'status' => 'in_progress', 'conclusion' => null],
                ['run_number' => 107, 'status' => 'completed', 'conclusion' => 'success'],
            ],
            'secret' => 'must-not-leak',
        ], JSON_THROW_ON_ERROR));

        $snapshot = app(DeliveryControlSnapshot::class)->capture();

        $this->assertSame('active', $snapshot['status']);
        $this->assertSame(108, $snapshot['current_worker']['run_number']);
        $this->assertSame(142, $snapshot['current_task']['issue_number']);
        $this->assertCount(2, $snapshot['runners']);
        $this->assertSame(148, $snapshot['pull_request']['number']);
        $this->assertSame('in_progress', $snapshot['ci']['status']);
        $this->assertSame(str_repeat('c', 40), $snapshot['staging']['deployed_sha']);
        $this->assertCount(3, $snapshot['pipeline']);
        $this->assertCount(2, $snapshot['recent_worker_runs']);
        $this->assertArrayNotHasKey('secret', $snapshot);
    }

    public function test_stale_delivery_evidence_preserves_sanitized_last_known_state(): void
    {
        $capturedAt = now()->subMinutes(20)->toIso8601String();

        File::put($this->path, json_encode([
            'version' => 1,
            'captured_at' => $capturedAt,
            'status' => 'active',
            'current_worker' => [
                'status' => 'in_progress',
                'run_number' => 136,
                'phase' => 'Run guarded worker cycle',
                'private_note' => 'must-not-leak',
            ],
            'current_task' => [
                'issue_number' => 162,
                'title' => 'Preserve stale delivery evidence',
                'state' => 'running',
                'private_note' => 'must-not-leak',
            ],
            'runners' => [
                ['name' => 'runner-1', 'status' => 'online', 'busy' => true, 'token' => 'must-not-leak'],
                ['name' => 'runner-2', 'status' => 'online', 'busy' => false],
            ],
            'pull_request' => [
                'number' => 164,
                'title' => 'fix stale evidence',
                'state' => 'open',
                'head_sha' => str_repeat('d', 40),
            ],
            'ci' => [
                'status' => 'in_progress',
                'run_id' => 1001,
                'failed_checks' => 0,
            ],
            'staging' => [
                'approved_sha' => str_repeat('e', 40),
                'deployed_sha' => str_repeat('f', 40),
                'status' => 'healthy',
            ],
            'pipeline' => [
                ['key' => 'worker', 'label' => 'AI Worker', 'status' => 'active', 'secret' => 'must-not-leak'],
                ['key' => 'ci', 'label' => 'CI', 'status' => 'waiting'],
            ],
            'blocker' => [
                'code' => 'NO_FREE_ROUTE_AVAILABLE',
                'message' => 'Waiting for a verified zero-cost route.',
                'recoverable' => true,
                'secret' => 'must-not-leak',
            ],
            'recent_worker_runs' => [
                ['run_number' => 136, 'status' => 'completed', 'conclusion' => 'success', 'secret' => 'must-not-leak'],
            ],
            'secret' => 'must-not-leak',
        ], JSON_THROW_ON_ERROR));

        $snapshot = app(DeliveryControlSnapshot::class)->capture();

        $this->assertSame('stale', $snapshot['status']);
        $this->assertSame($capturedAt, $snapshot['captured_at']);
        $this->assertSame(136, $snapshot['current_worker']['run_number']);
        $this->assertSame(162, $snapshot['current_task']['issue_number']);
        $this->assertCount(2, $snapshot['runners']);
        $this->assertSame(164, $snapshot['pull_request']['number']);
        $this->assertSame('in_progress', $snapshot['ci']['status']);
        $this->assertSame(str_repeat('f', 40), $snapshot['staging']['deployed_sha']);
        $this->assertCount(2, $snapshot['pipeline']);
        $this->assertSame('NO_FREE_ROUTE_AVAILABLE', $snapshot['blocker']['code']);
        $this->assertCount(1, $snapshot['recent_worker_runs']);
        $this->assertArrayNotHasKey('private_note', $snapshot['current_worker']);
        $this->assertArrayNotHasKey('token', $snapshot['runners'][0]);
        $this->assertArrayNotHasKey('secret', $snapshot['blocker']);
        $this->assertArrayNotHasKey('secret', $snapshot);
    }
}
