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
        config()->set('kmj.ops.provider_policy', []);
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
            $this->assertFalse($snapshot['free_ai_router']['live_route_observed']);
            $this->assertFalse($snapshot['free_ai_router']['paid_fallback']);
            $this->assertSame('warning', $snapshot['compliance_guard']['status']);
            $this->assertSame('unconfigured', $snapshot['compliance_guard']['provider_policy_status']);
            $this->assertSame('not_enabled', $snapshot['compliance_guard']['provider_policy_enforcement']);
            $this->assertSame('not_enabled', $snapshot['compliance_guard']['provider_rule_status']);
            $this->assertSame([], $snapshot['compliance_guard']['provider_rule_signals']);
            $this->assertFalse($snapshot['compliance_guard']['provider_mitigation_allowed']);
            $this->assertFalse($snapshot['compliance_guard']['legal_interpretation']);
        } finally {
            File::deleteDirectory($directory);
        }
    }

    public function test_snapshot_evaluates_only_explicitly_approved_provider_rules(): void
    {
        $directory = sys_get_temp_dir().DIRECTORY_SEPARATOR.'kmj-ops-provider-'.bin2hex(random_bytes(6));
        File::ensureDirectoryExists($directory, 0700, true);

        config()->set('kmj.ops.backup_status_dir', $directory);
        config()->set('kmj.ops.provider_policy', [
            'provider_id' => 'web-host-example',
            'policy_version' => '2026-09-22',
            'approved' => true,
            'reviewed_at' => now()->toIso8601String(),
            'max_age_days' => 90,
            'sources' => [[
                'id' => 'resource-policy',
                'url' => 'https://provider.example/policy',
                'sha256' => str_repeat('a', 64),
            ]],
            'rules' => [[
                'code' => 'resource.cpu.warning',
                'source_id' => 'resource-policy',
                'metric' => 'cpu.load_percent_estimate',
                'operator' => 'gte',
                'value' => 80,
            ]],
        ]);

        try {
            $snapshot = app(OperationalReadinessSnapshot::class)->capture([
                'deployed_sha' => str_repeat('a', 40),
                'database' => ['status' => 'healthy'],
                'cpu' => ['load_percent_estimate' => 85],
                'memory' => ['used_percent' => 30],
                'disk' => ['used_percent' => 40],
                'failed_jobs' => 0,
            ]);

            $this->assertSame('active', $snapshot['compliance_guard']['provider_policy_status']);
            $this->assertSame('approved_rules_registered', $snapshot['compliance_guard']['provider_policy_enforcement']);
            $this->assertMatchesRegularExpression('/^[0-9a-f]{64}$/', $snapshot['compliance_guard']['policy_fingerprint']);
            $this->assertSame('breach', $snapshot['compliance_guard']['provider_rule_status']);
            $this->assertSame('resource.cpu.warning', $snapshot['compliance_guard']['provider_rule_signals'][0]['code']);
            $this->assertFalse($snapshot['compliance_guard']['provider_mitigation_allowed']);
            $this->assertFalse($snapshot['compliance_guard']['legal_interpretation']);
        } finally {
            File::deleteDirectory($directory);
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
