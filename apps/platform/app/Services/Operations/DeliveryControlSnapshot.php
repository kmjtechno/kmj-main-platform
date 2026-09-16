<?php

namespace App\Services\Operations;

use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\File;
use Throwable;

final class DeliveryControlSnapshot
{
    /** @return array<string, mixed> */
    public function capture(): array
    {
        $path = (string) config(
            'kmj.ops.delivery_status_path',
            storage_path('app/monitoring/delivery-control.json'),
        );

        if ($path === '' || ! File::isFile($path)) {
            return $this->emptySnapshot('unavailable');
        }

        try {
            $payload = json_decode(File::get($path), true, 64, JSON_THROW_ON_ERROR);
        } catch (Throwable) {
            return $this->emptySnapshot('unavailable');
        }

        if (! is_array($payload) || ($payload['version'] ?? null) !== 1) {
            return $this->emptySnapshot('unavailable');
        }

        $capturedAt = $payload['captured_at'] ?? null;
        if (! is_string($capturedAt) || $capturedAt === '') {
            return $this->emptySnapshot('unavailable');
        }

        try {
            $captured = CarbonImmutable::parse($capturedAt);
        } catch (Throwable) {
            return $this->emptySnapshot('unavailable');
        }

        $maxAgeSeconds = max(30, (int) config('kmj.ops.delivery_status_max_age_seconds', 600));
        $isStale = $captured->diffInSeconds(now(), false) > $maxAgeSeconds;

        return [
            'status' => $isStale
                ? 'stale'
                : $this->enum($payload['status'] ?? null, ['active', 'idle', 'blocked', 'degraded'], 'degraded'),
            'captured_at' => $captured->toIso8601String(),
            'current_worker' => $this->pick(
                $payload['current_worker'] ?? null,
                ['status', 'run_id', 'run_number', 'phase', 'retry_count', 'started_at'],
                ['status' => 'unknown'],
            ),
            'current_task' => $this->nullablePick(
                $payload['current_task'] ?? null,
                ['issue_number', 'title', 'state'],
            ),
            'runners' => $this->listOfPicks(
                $payload['runners'] ?? null,
                ['name', 'status', 'busy'],
                8,
            ),
            'pull_request' => $this->nullablePick(
                $payload['pull_request'] ?? null,
                ['number', 'title', 'state', 'head_sha'],
            ),
            'ci' => $this->pick(
                $payload['ci'] ?? null,
                ['status', 'run_id', 'failed_checks'],
                ['status' => 'unknown'],
            ),
            'staging' => $this->pick(
                $payload['staging'] ?? null,
                ['approved_sha', 'deployed_sha', 'status'],
                ['status' => 'unknown'],
            ),
            'pipeline' => $this->listOfPicks(
                $payload['pipeline'] ?? null,
                ['key', 'label', 'status'],
                10,
            ),
            'blocker' => $this->pick(
                $payload['blocker'] ?? null,
                ['code', 'message', 'recoverable'],
                ['code' => null, 'message' => null, 'recoverable' => false],
            ),
            'recent_worker_runs' => $this->listOfPicks(
                $payload['recent_worker_runs'] ?? null,
                ['run_number', 'status', 'conclusion'],
                10,
            ),
        ];
    }

    /** @return array<string, mixed> */
    private function emptySnapshot(string $status): array
    {
        return [
            'status' => $status,
            'captured_at' => null,
            'current_worker' => ['status' => 'unknown'],
            'current_task' => null,
            'runners' => [],
            'pull_request' => null,
            'ci' => ['status' => 'unknown'],
            'staging' => ['status' => 'unknown'],
            'pipeline' => [],
            'blocker' => ['code' => null, 'message' => null, 'recoverable' => false],
            'recent_worker_runs' => [],
        ];
    }

    /**
     * @param  list<string>  $keys
     * @param  array<string, mixed>  $fallback
     * @return array<string, mixed>
     */
    private function pick(mixed $value, array $keys, array $fallback = []): array
    {
        if (! is_array($value)) {
            return $fallback;
        }

        $result = $fallback;
        foreach ($keys as $key) {
            if (array_key_exists($key, $value) && $this->isSafeScalar($value[$key])) {
                $result[$key] = $value[$key];
            }
        }

        return $result;
    }

    /**
     * @param  list<string>  $keys
     * @return array<string, mixed>|null
     */
    private function nullablePick(mixed $value, array $keys): ?array
    {
        if (! is_array($value)) {
            return null;
        }

        $result = $this->pick($value, $keys);

        return $result === [] ? null : $result;
    }

    /**
     * @param  list<string>  $keys
     * @return list<array<string, mixed>>
     */
    private function listOfPicks(mixed $value, array $keys, int $limit): array
    {
        if (! is_array($value)) {
            return [];
        }

        $result = [];
        foreach (array_slice($value, 0, $limit) as $item) {
            if (! is_array($item)) {
                continue;
            }

            $sanitized = $this->pick($item, $keys);
            if ($sanitized !== []) {
                $result[] = $sanitized;
            }
        }

        return $result;
    }

    private function isSafeScalar(mixed $value): bool
    {
        return is_null($value) || is_string($value) || is_int($value) || is_bool($value) || is_float($value);
    }

    /** @param list<string> $allowed */
    private function enum(mixed $value, array $allowed, string $fallback): string
    {
        return is_string($value) && in_array($value, $allowed, true) ? $value : $fallback;
    }
}
