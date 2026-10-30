<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Services\CodeBridge\Workspace\WorkspaceJobService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;
use Throwable;

/**
 * Real overlap on PostgreSQL with separate PROCESSES: concurrent device polls must never hold two
 * jobs, and concurrent enqueues must never exceed the per-project active limit. Skipped (never
 * faked) where PostgreSQL or pcntl is unavailable.
 */
final class CodeBridgeWorkspaceJobConcurrencyTest extends TestCase
{
    use RefreshDatabase;

    /** Data must be committed so forked connections can see it; the test cleans up itself. */
    protected array $connectionsToTransact = [];

    private const PROCESSES = 8;

    public function test_overlapping_claims_hand_out_one_job_and_enqueues_respect_the_limit(): void
    {
        if (DB::connection()->getDriverName() !== 'pgsql') {
            $this->markTestSkipped('Requires a real PostgreSQL connection.');
        }
        if (! function_exists('pcntl_fork') || ! function_exists('posix_kill')) {
            $this->markTestSkipped('Requires pcntl and posix.');
        }
        config()->set('codebridge.workspace_jobs_enabled', true);
        $tenant = $this->seedTenant('race-desk', 'race-proj');
        try {
            // A: eight overlapping enqueues against a limit of five.
            $enq = $this->overlap(fn (int $i) => app(WorkspaceJobService::class)->enqueue($tenant, 1, 'race-desk', 'race-proj', 'git_status', [], 'race-key-0000000'.sprintf('%02d', $i)) ? 0 : 1);
            self::assertSame(WorkspaceJobService::MAX_ACTIVE_PER_PROJECT, DB::table('codebridge_workspace_jobs')->where('tenant_id', $tenant)->count(), 'limit holds under overlap: '.json_encode($enq));

            // B: eight overlapping device polls; exactly one job may be claimed.
            $claims = $this->overlap(fn (int $i) => app(WorkspaceJobService::class)->claim($tenant, 'race-desk') === null ? 1 : 0);
            self::assertSame(1, count(array_keys($claims, 0, true)), 'exactly one claim succeeds: '.json_encode($claims));
            self::assertSame(1, DB::table('codebridge_workspace_jobs')->where('tenant_id', $tenant)->where('status', 'claimed')->count());
            self::assertSame(WorkspaceJobService::MAX_ACTIVE_PER_PROJECT - 1, DB::table('codebridge_workspace_jobs')->where('tenant_id', $tenant)->where('status', 'queued')->count());
        } finally {
            DB::table('codebridge_workspace_jobs')->where('tenant_id', $tenant)->delete();
            DB::table('codebridge_device_pairings')->where('tenant_id', $tenant)->delete();
            DB::table('codebridge_device_credentials')->where('tenant_id', $tenant)->delete();
            $licenses = DB::table('kslp_licenses')->where('customer_id', $tenant)->pluck('id');
            DB::table('kslp_activations')->whereIn('license_id', $licenses)->delete();
            DB::table('kslp_licenses')->where('customer_id', $tenant)->delete();
            DB::table('organizations')->where('id', $tenant)->delete();
        }
    }

    /**
     * @param  callable(int): int  $work  returns 0 on success-like outcome, 1 otherwise
     * @return list<int> 0 success, 1 refused/none, 4 domain refusal (limit), 9 error
     */
    private function overlap(callable $work): array
    {
        $dir = sys_get_temp_dir().'/kmj-job-race-'.bin2hex(random_bytes(6));
        mkdir($dir, 0700);
        DB::purge(); // no connection may be shared across fork()
        $pids = [];
        for ($i = 0; $i < self::PROCESSES; $i++) {
            $pid = pcntl_fork();
            self::assertNotSame(-1, $pid, 'fork failed');
            if ($pid === 0) {
                $code = 9;
                try {
                    while (! file_exists($dir.'/go')) {
                        usleep(1000);
                    }
                    try {
                        $code = $work($i);
                    } catch (\RuntimeException) {
                        $code = 4;
                    }
                } catch (Throwable) {
                    $code = 9;
                }
                file_put_contents($dir.'/result-'.$i, (string) $code);
                posix_kill(posix_getpid(), SIGKILL); // skip PHPUnit/Laravel shutdown in the child
            }
            $pids[] = $pid;
        }
        usleep(300000);
        touch($dir.'/go');
        foreach ($pids as $pid) {
            pcntl_waitpid($pid, $status);
        }
        DB::reconnect();

        $codes = [];
        for ($i = 0; $i < self::PROCESSES; $i++) {
            $codes[] = (int) @file_get_contents($dir.'/result-'.$i);
        }
        array_map('unlink', glob($dir.'/*') ?: []);
        rmdir($dir);

        return $codes;
    }

    private function seedTenant(string $device, string $project, array $permissions = ['read', 'write', 'execute']): string
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
            'token_hash' => hash('sha256', 'race-token-'.$device), 'lease_sequence' => 0, 'expires_at_epoch' => time() + 3600,
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
