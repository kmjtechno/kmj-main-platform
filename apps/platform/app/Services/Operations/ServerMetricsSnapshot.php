<?php

namespace App\Services\Operations;

use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Throwable;

final class ServerMetricsSnapshot
{
    /** @return array<string, mixed> */
    public function capture(): array
    {
        $load = sys_getloadavg() ?: [0.0, 0.0, 0.0];
        $cores = $this->cpuCores();
        $memory = $this->memory();
        $disk = $this->disk();

        return [
            'captured_at' => now()->toIso8601String(),
            'environment' => app()->environment(),
            'deployed_sha' => $this->deployedSha(),
            'cpu' => [
                'cores' => $cores,
                'load_1m' => round((float) ($load[0] ?? 0), 2),
                'load_5m' => round((float) ($load[1] ?? 0), 2),
                'load_15m' => round((float) ($load[2] ?? 0), 2),
                'load_percent_estimate' => round(min(100, max(0, ((float) ($load[0] ?? 0) / $cores) * 100)), 1),
            ],
            'memory' => $memory,
            'disk' => $disk,
            'uptime_seconds' => $this->uptimeSeconds(),
            'php' => [
                'memory_usage_bytes' => memory_get_usage(true),
                'memory_peak_bytes' => memory_get_peak_usage(true),
                'memory_limit' => (string) ini_get('memory_limit'),
            ],
            'database' => $this->databaseHealth(),
            'failed_jobs' => $this->failedJobs(),
            'queue_restart_at' => $this->queueRestartAt(),
        ];
    }

    /** @return array{total_bytes:int, used_bytes:int, available_bytes:int, used_percent:float} */
    private function memory(): array
    {
        $contents = @file_get_contents('/proc/meminfo');
        $values = [];

        if (is_string($contents)) {
            foreach (explode("\n", $contents) as $line) {
                if (preg_match('/^([A-Za-z_()]+):\s+(\d+)\s+kB$/', $line, $matches) === 1) {
                    $values[$matches[1]] = (int) $matches[2] * 1024;
                }
            }
        }

        $total = (int) ($values['MemTotal'] ?? 0);
        $available = (int) ($values['MemAvailable'] ?? $values['MemFree'] ?? 0);
        $used = max(0, $total - $available);

        return [
            'total_bytes' => $total,
            'used_bytes' => $used,
            'available_bytes' => $available,
            'used_percent' => $total > 0 ? round(($used / $total) * 100, 1) : 0.0,
        ];
    }

    /** @return array{total_bytes:int, used_bytes:int, free_bytes:int, used_percent:float} */
    private function disk(): array
    {
        $path = base_path();
        $total = (int) (@disk_total_space($path) ?: 0);
        $free = (int) (@disk_free_space($path) ?: 0);
        $used = max(0, $total - $free);

        return [
            'total_bytes' => $total,
            'used_bytes' => $used,
            'free_bytes' => $free,
            'used_percent' => $total > 0 ? round(($used / $total) * 100, 1) : 0.0,
        ];
    }

    private function cpuCores(): int
    {
        $contents = @file_get_contents('/proc/cpuinfo');

        if (is_string($contents)) {
            $count = preg_match_all('/^processor\s*:/m', $contents);
            if (is_int($count) && $count > 0) {
                return $count;
            }
        }

        return 1;
    }

    private function uptimeSeconds(): ?int
    {
        $contents = @file_get_contents('/proc/uptime');
        if (! is_string($contents)) {
            return null;
        }

        $seconds = (float) explode(' ', trim($contents))[0];

        return $seconds >= 0 ? (int) floor($seconds) : null;
    }

    /** @return array{status:string} */
    private function databaseHealth(): array
    {
        try {
            DB::select('select 1');

            return ['status' => 'healthy'];
        } catch (Throwable) {
            return ['status' => 'degraded'];
        }
    }

    private function failedJobs(): int
    {
        try {
            return Schema::hasTable('failed_jobs') ? DB::table('failed_jobs')->count() : 0;
        } catch (Throwable) {
            return 0;
        }
    }

    private function queueRestartAt(): ?int
    {
        $value = Cache::get('illuminate:queue:restart');

        return is_numeric($value) ? (int) $value : null;
    }

    private function deployedSha(): ?string
    {
        $gitDir = dirname(base_path(), 2).DIRECTORY_SEPARATOR.'.git';
        $head = @file_get_contents($gitDir.DIRECTORY_SEPARATOR.'HEAD');
        if (! is_string($head)) {
            return null;
        }

        $head = trim($head);
        if (preg_match('/^[0-9a-f]{40}$/', $head) === 1) {
            return $head;
        }

        if (! str_starts_with($head, 'ref: ')) {
            return null;
        }

        $ref = substr($head, 5);
        $refValue = @file_get_contents($gitDir.DIRECTORY_SEPARATOR.str_replace('/', DIRECTORY_SEPARATOR, $ref));
        if (is_string($refValue) && preg_match('/^[0-9a-f]{40}$/', trim($refValue)) === 1) {
            return trim($refValue);
        }

        $packed = @file_get_contents($gitDir.DIRECTORY_SEPARATOR.'packed-refs');
        if (is_string($packed) && preg_match('/^([0-9a-f]{40})\s+'.preg_quote($ref, '/').'$/m', $packed, $matches) === 1) {
            return $matches[1];
        }

        return null;
    }
}
