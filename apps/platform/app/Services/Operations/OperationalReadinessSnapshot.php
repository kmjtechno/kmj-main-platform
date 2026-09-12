<?php

namespace App\Services\Operations;

use Carbon\CarbonImmutable;
use Throwable;

final class OperationalReadinessSnapshot
{
    /** @param array<string, mixed> $server */
    public function capture(array $server): array
    {
        $backups = $this->backupFreshness();

        return [
            'deployment' => $this->deployment($server),
            'backups' => $backups,
            'autonomous_worker' => $this->autonomousWorkerPosture(),
            'free_ai_router' => $this->freeAiRouterPosture(),
            'compliance_guard' => $this->complianceGuard($server, $backups),
        ];
    }

    /** @param array<string, mixed> $server */
    private function deployment(array $server): array
    {
        $sha = $server['deployed_sha'] ?? null;
        $databaseStatus = $server['database']['status'] ?? 'unknown';
        $healthy = is_string($sha) && $sha !== '' && $databaseStatus === 'healthy';

        return [
            'status' => $healthy ? 'healthy' : 'degraded',
            'deployed_sha' => is_string($sha) ? $sha : null,
            'database_status' => is_string($databaseStatus) ? $databaseStatus : 'unknown',
            'evidence' => 'local_runtime',
        ];
    }

    /** @return array<string, array<string, mixed>> */
    private function backupFreshness(): array
    {
        $thresholds = (array) config('kmj.ops.backup_freshness_hours', []);
        $directory = (string) config('kmj.ops.backup_status_dir', storage_path('app/private/ops'));
        $result = [];

        foreach (['daily', 'weekly', 'monthly'] as $tier) {
            $maxAgeHours = max(1, (int) ($thresholds[$tier] ?? 36));
            $result[$tier] = $this->backupTier($directory, $tier, $maxAgeHours);
        }

        return $result;
    }

    /** @return array<string, mixed> */
    private function backupTier(string $directory, string $tier, int $maxAgeHours): array
    {
        $path = rtrim($directory, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR."backup-status-{$tier}.status";

        if (! is_file($path)) {
            return [
                'status' => 'missing',
                'completed_at' => null,
                'age_hours' => null,
                'max_age_hours' => $maxAgeHours,
                'git_sha' => null,
            ];
        }

        $values = $this->parseStatusFile($path);
        $completedAt = $values['completed_at_utc'] ?? null;

        try {
            $completed = is_string($completedAt) ? CarbonImmutable::parse($completedAt)->utc() : null;
        } catch (Throwable) {
            $completed = null;
        }

        if ($completed === null) {
            return [
                'status' => 'invalid',
                'completed_at' => null,
                'age_hours' => null,
                'max_age_hours' => $maxAgeHours,
                'git_sha' => $this->safeSha($values['git_sha'] ?? null),
            ];
        }

        $ageHours = max(0, round($completed->diffInSeconds(now()->utc(), true) / 3600, 1));
        $success = ($values['status'] ?? null) === 'success';

        return [
            'status' => $success && $ageHours <= $maxAgeHours ? 'fresh' : 'stale',
            'completed_at' => $completed->toIso8601String(),
            'age_hours' => $ageHours,
            'max_age_hours' => $maxAgeHours,
            'git_sha' => $this->safeSha($values['git_sha'] ?? null),
        ];
    }

    /** @return array<string, string> */
    private function parseStatusFile(string $path): array
    {
        $contents = @file_get_contents($path);
        if (! is_string($contents)) {
            return [];
        }

        $values = [];
        foreach (preg_split('/\R/', $contents) ?: [] as $line) {
            if (! str_contains($line, '=')) {
                continue;
            }

            [$key, $value] = explode('=', $line, 2);
            $key = trim($key);
            if (preg_match('/^[a-z0-9_]+$/', $key) !== 1) {
                continue;
            }

            $values[$key] = trim($value);
        }

        return $values;
    }

    private function safeSha(mixed $value): ?string
    {
        return is_string($value) && preg_match('/^[0-9a-f]{40}$/', $value) === 1 ? $value : null;
    }

    /** @return array<string, mixed> */
    private function autonomousWorkerPosture(): array
    {
        $execution = config('kmj.ops.worker_execution_enabled');
        $write = config('kmj.ops.worker_write_enabled');

        if (! is_bool($execution) || ! is_bool($write)) {
            $status = 'external_unobserved';
        } elseif ($execution && $write) {
            $status = 'enabled';
        } else {
            $status = 'guarded';
        }

        return [
            'status' => $status,
            'source' => 'github_actions',
            'execution_gate' => is_bool($execution) ? ($execution ? 'enabled' : 'disabled') : 'unknown',
            'write_gate' => is_bool($write) ? ($write ? 'enabled' : 'disabled') : 'unknown',
            'live_run_observed' => false,
        ];
    }

    /** @return array<string, mixed> */
    private function freeAiRouterPosture(): array
    {
        $providers = (array) config('kmj.ops.free_ai_provider_credentials', []);
        $configured = [];

        foreach ($providers as $provider => $credential) {
            if (is_string($provider) && is_string($credential) && trim($credential) !== '') {
                $configured[] = $provider;
            }
        }

        sort($configured);

        return [
            'status' => $configured === [] ? 'dormant_no_credentials' : 'configured_not_probed',
            'policy' => 'verified_zero_only',
            'configured_provider_count' => count($configured),
            'configured_providers' => $configured,
            'live_route_observed' => false,
            'paid_fallback' => false,
        ];
    }

    /**
     * @param array<string, mixed> $server
     * @param array<string, array<string, mixed>> $backups
     * @return array<string, mixed>
     */
    private function complianceGuard(array $server, array $backups): array
    {
        $guardrails = (array) config('kmj.ops.guardrails', []);
        $warning = max(1, (float) ($guardrails['resource_warning_percent'] ?? 85));
        $critical = max($warning, (float) ($guardrails['resource_critical_percent'] ?? 95));
        $signals = [];

        foreach (['cpu', 'memory', 'disk'] as $resource) {
            $key = $resource === 'cpu' ? 'load_percent_estimate' : 'used_percent';
            $value = (float) ($server[$resource][$key] ?? 0);
            $signals[] = [
                'code' => "resource.{$resource}",
                'status' => $value >= $critical ? 'critical' : ($value >= $warning ? 'warning' : 'healthy'),
                'value' => round($value, 1),
                'unit' => 'percent',
                'warning_threshold' => $warning,
                'critical_threshold' => $critical,
            ];
        }

        $failedJobs = max(0, (int) ($server['failed_jobs'] ?? 0));
        $signals[] = [
            'code' => 'queue.failed_jobs',
            'status' => $failedJobs > 0 ? 'warning' : 'healthy',
            'value' => $failedJobs,
            'unit' => 'count',
        ];

        foreach ($backups as $tier => $backup) {
            $signals[] = [
                'code' => "backup.{$tier}",
                'status' => ($backup['status'] ?? 'missing') === 'fresh' ? 'healthy' : 'warning',
                'value' => $backup['age_hours'] ?? null,
                'unit' => 'hours',
            ];
        }

        $statuses = array_column($signals, 'status');
        $status = in_array('critical', $statuses, true)
            ? 'critical'
            : (in_array('warning', $statuses, true) ? 'warning' : 'healthy');

        return [
            'status' => $status,
            'mode' => 'internal_operational_guardrails',
            'provider_policy_enforcement' => 'not_enabled',
            'legal_interpretation' => false,
            'signals' => $signals,
        ];
    }
}
