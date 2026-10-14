<?php

declare(strict_types=1);

namespace App\Services\Licensing\CodeBridge;

use Illuminate\Support\Facades\Cache;

/**
 * Agent-authenticated, bounded, tenant-scoped observations.
 *
 * This is not an inference proxy. Device-side Ollama and journals are only
 * sampled by the paired agent; the platform caches the sanitized counters.
 * Device registration alone never establishes an online device.
 */
final class CodeBridgeLocalTelemetry
{
    private const CACHE_SECONDS = 120;

    private const FRESH_SECONDS = 90;

    private function key(string $tenant, string $device): string
    {
        return 'codebridge:local-telemetry:'.hash('sha256', $tenant."\0".$device);
    }

    /** @param array<string, mixed> $observation */
    public function record(string $tenant, string $device, string $project, array $observation): void
    {
        Cache::put($this->key($tenant, $device), [
            'device_id' => $device,
            'project_id' => $project,
            'reported_at_epoch' => time(),
            'ollama' => $observation['ollama'] ?? null,
            'queue' => $observation['queue'] ?? null,
        ], self::CACHE_SECONDS);
    }

    /**
     * @param list<string> $authorizedDevices Only active licensed, nonrevoked devices.
     * @return array<string, mixed>
     */
    public function snapshot(string $tenant, array $authorizedDevices): array
    {
        $now = time();
        $fresh = [];
        foreach (array_slice(array_values(array_unique($authorizedDevices)), 0, 100) as $device) {
            $report = Cache::get($this->key($tenant, $device));
            if (! is_array($report)
                || ($report['device_id'] ?? null) !== $device
                || ! is_int($report['reported_at_epoch'] ?? null)
                || $report['reported_at_epoch'] > $now
                || $report['reported_at_epoch'] <= $now - self::FRESH_SECONDS) {
                continue;
            }
            $fresh[] = $report;
        }

        $models = [];
        $modelSampled = 0;
        $ollamaOnline = 0;
        $queue = ['queued' => 0, 'running' => 0, 'waiting' => 0];
        $queueSampled = 0;

        foreach ($fresh as $report) {
            $ollama = $report['ollama'] ?? null;
            if (is_array($ollama) && is_bool($ollama['reachable'] ?? null)) {
                $modelSampled++;
                if ($ollama['reachable']) {
                    $ollamaOnline++;
                    foreach (($ollama['models'] ?? []) as $name) {
                        if (is_string($name)) {
                            $models[] = $name;
                        }
                    }
                }
            }

            $tasks = $report['queue'] ?? null;
            if (is_array($tasks)
                && is_int($tasks['queued'] ?? null)
                && is_int($tasks['running'] ?? null)
                && is_int($tasks['waiting'] ?? null)) {
                $queueSampled++;
                foreach ($queue as $name => $count) {
                    $queue[$name] = $count + $tasks[$name];
                }
            }
        }

        return [
            'source' => 'authenticated_agent_reports',
            'observed_at' => gmdate(DATE_ATOM, $now),
            // null means no fresh evidence: do not turn absence into zero.
            'active_devices' => $fresh === [] && $authorizedDevices !== [] ? null : count($fresh),
            'authorized_devices' => count($authorizedDevices),
            'ollama' => [
                'reachable' => $modelSampled === 0 ? null : $ollamaOnline > 0,
                'sampled_devices' => $modelSampled,
                'models' => array_slice(array_values(array_unique($models)), 0, 12),
            ],
            'autopilot' => [
                'queued' => $queueSampled === 0 ? null : $queue['queued'],
                'running' => $queueSampled === 0 ? null : $queue['running'],
                'waiting' => $queueSampled === 0 ? null : $queue['waiting'],
                'sampled_devices' => $queueSampled,
                'partial' => $queueSampled !== count($authorizedDevices),
            ],
        ];
    }
}
