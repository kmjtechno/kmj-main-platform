<?php

namespace Tests\Unit;

use App\Services\Operations\OperationalReadinessSnapshot;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

final class OperationalReadinessSnapshotTest extends TestCase
{
    public function test_snapshot_never_invents_external_health_and_tracks_backup_freshness(): void
    {
        $directory = sys_get_temp_dir().DIRECTORY_SEPARATOR.'kmj-ops-'.bin2hex(random_bytes(6));
        File::ensureDirectoryExists($directory, 0700, true);

        config()->set('kmj.ops.backup_status_dir', $directory);
        config()->set('kmj.ops.backup_freshness_hours', [
            'daily' => 36,
            'weekly' => 216,
            'monthly' => 840,
        ]);
        config()->set('kmj.ops.worker_execution_enabled', null);
        config()->set('kmj.ops.worker_write_enabled', null);
        config()->set('kmj.ops.free_ai_provider_credentials', [
            'openrouter' => null,
            'groq' => null,
        ]);

        file_put_contents(
            $directory.DIRECTORY_SEPARATOR.'backup-status-daily.status',
            $this->marker(now()->subHours(2)->toIso8601String()),
        );
        file_put_contents(
            $directory.DIRECTORY_SEPARATOR.'backup-status-weekly.status',
            $this->marker(now()->subHours(300)->toIso8601String()),
        );

        try {
            $snapshot = app(OperationalReadinessSnapshot::class)->capture([
                'deployed_sha' => str_repeat('a', 40),
                'database' => ['status' => 'healthy'],
                'cpu' => ['load_percent_estimate' => 20],
                'memory' => ['used_percent' => 30],
                'disk' => ['used_percent' => 40],
                'failed_jobs' => 0,
            ]);

            $this->assertSame('healthy', $snapshot['deployment']['status']);
            $this->assertSame('fresh', $snapshot['backups']['daily']['status']);
            $this->assertSame('stale', $snapshot['backups']['weekly']['status']);
            $this->assertSame('missing', $snapshot['backups']['monthly']['status']);
            $this->assertSame('external_unobserved', $snapshot['autonomous_worker']['status']);
            $this->assertFalse($snapshot['autonomous_worker']['live_run_observed']);
            $this->assertSame('dormant_no_credentials', $snapshot['free_ai_router']['status']);
            $this->assertFalse($snapshot['free_ai_router']['opencode_client_ready']);
            $this->assertFalse($snapshot['free_ai_router']['cloudflare_pair_ready']);
            $this->assertFalse($snapshot['free_ai_router']['live_route_observed']);
            $this->assertFalse($snapshot['free_ai_router']['paid_fallback']);
            $this->assertSame('warning', $snapshot['compliance_guard']['status']);
            $this->assertSame('not_enabled', $snapshot['compliance_guard']['provider_policy_enforcement']);
            $this->assertFalse($snapshot['compliance_guard']['legal_interpretation']);
        } finally {
            File::deleteDirectory($directory);
        }
    }

    public function test_free_ai_posture_requires_complete_cloudflare_pair_and_real_opencode_binary(): void
    {
        $binary = tempnam(sys_get_temp_dir(), 'kmj-opencode-');
        file_put_contents($binary, '#!/bin/sh'.PHP_EOL.'exit 0'.PHP_EOL);

        config()->set('kmj.ops.free_ai_provider_credentials', [
            'groq' => 'configured',
            'openrouter' => null,
        ]);
        config()->set('kmj.ops.cloudflare_ai_token', 'configured');
        config()->set('kmj.ops.cloudflare_ai_account_id', 'account');
        config()->set('kmj.ops.opencode_free_enabled', true);
        config()->set('kmj.ops.opencode_binary', $binary);

        try {
            $snapshot = app(OperationalReadinessSnapshot::class)->capture([
                'deployed_sha' => str_repeat('a', 40),
                'database' => ['status' => 'healthy'],
                'cpu' => ['load_percent_estimate' => 10],
                'memory' => ['used_percent' => 10],
                'disk' => ['used_percent' => 10],
                'failed_jobs' => 0,
            ]);

            $this->assertSame('configured_not_probed', $snapshot['free_ai_router']['status']);
            $this->assertSame(
                ['cloudflare', 'groq', 'opencode-client'],
                $snapshot['free_ai_router']['configured_providers'],
            );
            $this->assertTrue($snapshot['free_ai_router']['cloudflare_pair_ready']);
            $this->assertTrue($snapshot['free_ai_router']['opencode_client_ready']);
            $this->assertFalse($snapshot['free_ai_router']['live_route_observed']);
        } finally {
            @unlink($binary);
        }
    }

    private function marker(string $completedAt): string
    {
        return implode("\n", [
            'status=success',
            'tier=test',
            "completed_at_utc={$completedAt}",
            'git_sha='.str_repeat('b', 40),
            '',
        ]);
    }
}
