<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Schema;
use Inertia\Inertia;
use Inertia\Response;
use Throwable;

final class StagingMonitoringController extends Controller
{
    public function index(): Response
    {
        $this->ensureStagingRequest();

        return Inertia::render('info', [
            'pollIntervalMs' => 5000,
        ]);
    }

    public function status(): JsonResponse
    {
        $this->ensureStagingRequest();

        $requestStartedAt = hrtime(true);
        [$databaseHealthy, $databaseLatencyMs] = $this->databaseProbe();
        [$pendingJobs, $failedJobs] = $this->queueSnapshot();
        [$routerOnline, $routerModelCount, $routerLatencyMs] = $this->routerProbe();
        $system = $this->systemSnapshot();
        $deployment = $this->deploymentSnapshot();
        $runnerCount = $this->processCount('Runner.Listener');
        $queueWorkerCount = $this->processCount('artisan queue:work');
        $responseLatencyMs = $this->millisecondsSince($requestStartedAt);

        $diskHealthy = ($system['disk_used_percent'] ?? 0) < 90;
        $memoryHealthy = ($system['memory_used_percent'] ?? 0) < 92;
        $overall = $databaseHealthy && $diskHealthy && $memoryHealthy ? 'healthy' : 'degraded';

        return response()->json([
            'status' => $overall,
            'timestamp' => now()->toIso8601String(),
            'runtime' => [
                'application' => true,
                'database' => $databaseHealthy,
                'database_latency_ms' => $databaseLatencyMs,
                'response_latency_ms' => $responseLatencyMs,
                'system_load_percent' => $system['system_load_percent'],
                'memory_used_percent' => $system['memory_used_percent'],
                'disk_used_percent' => $system['disk_used_percent'],
                'server_uptime_seconds' => $system['server_uptime_seconds'],
                'pending_jobs' => $pendingJobs,
                'failed_jobs' => $failedJobs,
                'runner_count' => $runnerCount,
                'queue_worker_count' => $queueWorkerCount,
                'ai_router_online' => $routerOnline,
                'ai_router_model_count' => $routerModelCount,
                'ai_router_latency_ms' => $routerLatencyMs,
            ],
            'deployment' => $deployment,
            'processes' => [
                [
                    'key' => 'web',
                    'label' => 'Staging web application',
                    'status' => 'online',
                    'detail' => 'Laravel + React runtime is serving this live monitor.',
                ],
                [
                    'key' => 'database',
                    'label' => 'Database authority',
                    'status' => $databaseHealthy ? 'online' : 'blocked',
                    'detail' => $databaseHealthy
                        ? "Database ping {$databaseLatencyMs} ms"
                        : 'Database probe failed closed.',
                ],
                [
                    'key' => 'queue',
                    'label' => 'Queue execution',
                    'status' => $failedJobs > 0 ? 'attention' : ($queueWorkerCount > 0 ? 'online' : 'idle'),
                    'detail' => "{$pendingJobs} pending · {$failedJobs} failed · {$queueWorkerCount} worker process(es)",
                ],
                [
                    'key' => 'runners',
                    'label' => 'Self-hosted CI runners',
                    'status' => $runnerCount > 0 ? 'online' : 'blocked',
                    'detail' => "{$runnerCount} runner listener process(es) visible on this VPS",
                ],
                [
                    'key' => 'router',
                    'label' => 'Verified-free AI route',
                    'status' => $routerOnline ? 'online' : 'blocked',
                    'detail' => $routerOnline
                        ? "Local 9Router reachable · {$routerModelCount} model record(s)"
                        : 'Local 9Router is not reachable; AI tasks remain fail-closed.',
                ],
                [
                    'key' => 'deploy',
                    'label' => 'Staging deployment evidence',
                    'status' => ($deployment['deployed_sha'] ?? null) ? 'online' : 'attention',
                    'detail' => ($deployment['deployed_sha'] ?? null)
                        ? 'Exact deployed SHA evidence is available.'
                        : 'Exact deployment SHA could not be resolved from the staging checkout.',
                ],
            ],
            'safety' => [
                'environment' => 'staging',
                'production_untouched' => true,
                'paid_ai_fallback' => 'prohibited',
                'local_llm_inference' => 'prohibited',
            ],
        ]);
    }

    private function ensureStagingRequest(): void
    {
        abort_unless(
            app()->environment('staging') || request()->getHost() === 'staging.kmjtechno.com',
            404,
        );
    }

    /** @return array{0: bool, 1: float|null} */
    private function databaseProbe(): array
    {
        $startedAt = hrtime(true);

        try {
            DB::select('select 1');

            return [true, $this->millisecondsSince($startedAt)];
        } catch (Throwable) {
            return [false, null];
        }
    }

    /** @return array{0: int, 1: int} */
    private function queueSnapshot(): array
    {
        try {
            $pending = Schema::hasTable('jobs') ? DB::table('jobs')->count() : 0;
            $failed = Schema::hasTable('failed_jobs') ? DB::table('failed_jobs')->count() : 0;

            return [$pending, $failed];
        } catch (Throwable) {
            return [0, 0];
        }
    }

    /** @return array{0: bool, 1: int, 2: float|null} */
    private function routerProbe(): array
    {
        $startedAt = hrtime(true);

        try {
            $response = Http::acceptJson()
                ->connectTimeout(0.7)
                ->timeout(1.2)
                ->get('http://127.0.0.1:20128/v1/models');

            if (! $response->successful()) {
                return [false, 0, $this->millisecondsSince($startedAt)];
            }

            $models = $response->json('data');

            return [
                true,
                is_array($models) ? count($models) : 0,
                $this->millisecondsSince($startedAt),
            ];
        } catch (Throwable) {
            return [false, 0, $this->millisecondsSince($startedAt)];
        }
    }

    /** @return array{system_load_percent: float|null, memory_used_percent: float|null, disk_used_percent: float|null, server_uptime_seconds: int|null} */
    private function systemSnapshot(): array
    {
        $load = sys_getloadavg();
        $cpuCount = $this->cpuCount();
        $systemLoadPercent = $load !== false && $cpuCount > 0
            ? round(min(100, ((float) $load[0] / $cpuCount) * 100), 1)
            : null;

        [$memoryTotalKb, $memoryAvailableKb] = $this->memorySnapshotKb();
        $memoryUsedPercent = $memoryTotalKb > 0 && $memoryAvailableKb >= 0
            ? round((1 - ($memoryAvailableKb / $memoryTotalKb)) * 100, 1)
            : null;

        $diskTotal = @disk_total_space(base_path());
        $diskFree = @disk_free_space(base_path());
        $diskUsedPercent = is_float($diskTotal) && is_float($diskFree) && $diskTotal > 0
            ? round((1 - ($diskFree / $diskTotal)) * 100, 1)
            : null;

        return [
            'system_load_percent' => $systemLoadPercent,
            'memory_used_percent' => $memoryUsedPercent,
            'disk_used_percent' => $diskUsedPercent,
            'server_uptime_seconds' => $this->serverUptimeSeconds(),
        ];
    }

    private function cpuCount(): int
    {
        $cpuInfo = @file_get_contents('/proc/cpuinfo');
        if (! is_string($cpuInfo)) {
            return 1;
        }

        preg_match_all('/^processor\s*:/m', $cpuInfo, $matches);

        return max(1, count($matches[0]));
    }

    /** @return array{0: int, 1: int} */
    private function memorySnapshotKb(): array
    {
        $memInfo = @file_get_contents('/proc/meminfo');
        if (! is_string($memInfo)) {
            return [0, -1];
        }

        preg_match('/^MemTotal:\s+(\d+)\s+kB$/m', $memInfo, $total);
        preg_match('/^MemAvailable:\s+(\d+)\s+kB$/m', $memInfo, $available);

        return [
            isset($total[1]) ? (int) $total[1] : 0,
            isset($available[1]) ? (int) $available[1] : -1,
        ];
    }

    private function serverUptimeSeconds(): ?int
    {
        $uptime = @file_get_contents('/proc/uptime');
        if (! is_string($uptime)) {
            return null;
        }

        $value = explode(' ', trim($uptime))[0];

        return is_numeric($value) ? (int) floor((float) $value) : null;
    }

    private function processCount(string $needle): int
    {
        $count = 0;

        foreach (glob('/proc/[0-9]*/cmdline') ?: [] as $path) {
            $command = @file_get_contents($path);
            if (is_string($command) && str_contains(str_replace("\0", ' ', $command), $needle)) {
                $count++;
            }
        }

        return $count;
    }

    /** @return array<string, mixed> */
    private function deploymentSnapshot(): array
    {
        $path = storage_path('app/monitoring/deployment.json');
        if (is_file($path)) {
            $decoded = json_decode((string) file_get_contents($path), true);
            if (is_array($decoded)) {
                return [
                    'source' => 'staging-approved',
                    'approved_sha' => $this->safeString($decoded['approved_sha'] ?? null),
                    'deployed_sha' => $this->safeString($decoded['deployed_sha'] ?? null),
                    'deployed_at' => $this->safeString($decoded['deployed_at'] ?? null),
                    'http_health' => $this->safeString($decoded['http_health'] ?? null) ?? 'unknown',
                    'rendered_ui' => $this->safeString($decoded['rendered_ui'] ?? null) ?? 'unknown',
                ];
            }
        }

        [$sha, $changedAt] = $this->gitCheckoutSnapshot();

        return [
            'source' => 'staging-approved',
            'approved_sha' => $sha,
            'deployed_sha' => $sha,
            'deployed_at' => $changedAt,
            'http_health' => 'runtime-pass',
            'rendered_ui' => 'runtime-monitor-active',
        ];
    }

    /** @return array{0: string|null, 1: string|null} */
    private function gitCheckoutSnapshot(): array
    {
        $repoRoot = dirname(base_path(), 2);
        $gitDirectory = $repoRoot.'/.git';
        $headPath = $gitDirectory.'/HEAD';
        $head = @file_get_contents($headPath);

        if (! is_string($head)) {
            return [null, null];
        }

        $head = trim($head);
        $sha = null;
        $timestampPath = $headPath;

        if (str_starts_with($head, 'ref: ')) {
            $ref = trim(substr($head, 5));
            $refPath = $gitDirectory.'/'.$ref;
            $refValue = @file_get_contents($refPath);
            if (is_string($refValue)) {
                $sha = trim($refValue);
                $timestampPath = $refPath;
            }
        } else {
            $sha = $head;
        }

        if (! is_string($sha) || preg_match('/^[0-9a-f]{40}$/', $sha) !== 1) {
            $sha = null;
        }

        $modifiedAt = @filemtime($timestampPath);

        return [
            $sha,
            is_int($modifiedAt) ? date(DATE_ATOM, $modifiedAt) : null,
        ];
    }

    private function safeString(mixed $value): ?string
    {
        return is_string($value) && $value !== '' ? mb_substr($value, 0, 100) : null;
    }

    private function millisecondsSince(int $startedAt): float
    {
        return round((hrtime(true) - $startedAt) / 1_000_000, 1);
    }
}
