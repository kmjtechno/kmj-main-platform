<?php

declare(strict_types=1);

namespace App\Services\CodeBridge\Workspace;

use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use InvalidArgumentException;
use RuntimeException;

/**
 * Durable, tenant/device/project-scoped queue of APPROVED NAMED tool requests.
 *
 * Main Platform is only the request queue and the record of what a device reported. It never
 * runs a command itself. A job is `running` only after the device agent that holds the
 * claim token says so, and every state and event is written by a real transition.
 * Cancel wins over any later device report; lost devices are expired, not pretended alive.
 */
final class WorkspaceJobService
{
    public const QUEUE_TTL_SECONDS = 900;

    public const LEASE_SECONDS = 120;

    public const MAX_ACTIVE_PER_PROJECT = 5;

    private const ACTIVE = ['queued', 'claimed', 'running'];

    private const DEVICE_KINDS = ['started', 'progress', 'succeeded', 'failed'];

    public static function enabled(): bool
    {
        return config('codebridge.workspace_jobs_enabled', false) === true;
    }

    /** @return list<string> permissions granted to the paired project (pairing is the source of truth) */
    public function grantedPermissions(string $tenantId, string $deviceId, string $projectId): array
    {
        $row = DB::table('codebridge_device_credentials as c')
            ->join('kslp_activations as a', 'a.id', '=', 'c.activation_id')
            ->join('kslp_licenses as l', 'l.id', '=', 'c.license_id')
            ->join('codebridge_device_pairings as p', function ($join): void {
                $join->on('p.activation_id', '=', 'c.activation_id')->on('p.tenant_id', '=', 'c.tenant_id');
            })
            ->where('c.tenant_id', $tenantId)->where('c.device_id', $deviceId)
            ->whereNull('c.revoked_at')->where('c.expires_at_epoch', '>', time())
            ->whereColumn('a.license_id', 'l.id')->whereNull('a.deactivated_at')
            ->where('l.product', 'KMJ_CODEBRIDGE')->where('l.status', 'active')
            ->whereNull('l.revoked_at')->where('l.starts_at', '<=', now())
            ->where('l.expires_at', '>', now())
            ->where('p.project_id', $projectId)->where('p.status', 'consumed')
            ->first(['p.requested_permissions']);
        if ($row === null) {
            return [];
        }
        $decoded = json_decode((string) ((array) $row)['requested_permissions'], true);

        return is_array($decoded) ? array_values(array_filter($decoded, 'is_string')) : [];
    }

    /**
     * @param  array<mixed>  $arguments
     * @return array{id: string, created: bool}
     */
    public function enqueue(string $tenantId, int $userId, string $deviceId, string $projectId, string $tool, array $arguments, string $idempotencyKey): array
    {
        if (! self::enabled()) {
            throw new RuntimeException('jobs_disabled');
        }
        if (preg_match('/\A[A-Za-z0-9_-]{16,64}\z/', $idempotencyKey) !== 1) {
            throw new InvalidArgumentException('invalid_idempotency_key');
        }
        $arguments = WorkspaceToolCatalog::validate($tool, $arguments);
        $granted = $this->grantedPermissions($tenantId, $deviceId, $projectId);
        abort_if($granted === [], 404);
        if (! $this->permits($granted, $tool)) {
            abort(403);
        }

        return DB::transaction(function () use ($tenantId, $userId, $deviceId, $projectId, $tool, $arguments, $idempotencyKey): array {
            $this->lockDevice($tenantId, $deviceId);
            $existing = DB::table('codebridge_workspace_jobs')
                ->where('tenant_id', $tenantId)->where('user_id', $userId)->where('idempotency_key', $idempotencyKey)->lockForUpdate()->first();
            if ($existing !== null) {
                $row = (array) $existing;
                $same = $row['device_id'] === $deviceId && $row['project_id'] === $projectId && $row['tool'] === $tool
                    && json_decode((string) $row['arguments'], true) === $arguments;
                if (! $same) {
                    throw new InvalidArgumentException('idempotency_conflict');
                }

                return ['id' => (string) $row['id'], 'created' => false];
            }
            $this->expireStale($tenantId);
            $active = DB::table('codebridge_workspace_jobs')
                ->where('tenant_id', $tenantId)->where('device_id', $deviceId)->where('project_id', $projectId)
                ->whereIn('status', self::ACTIVE)->count();
            if ($active >= self::MAX_ACTIVE_PER_PROJECT) {
                throw new RuntimeException('too_many_active_jobs');
            }
            $id = (string) Str::ulid();
            try {
                DB::table('codebridge_workspace_jobs')->insert([
                    'id' => $id, 'tenant_id' => $tenantId, 'device_id' => $deviceId, 'project_id' => $projectId,
                    'user_id' => $userId, 'tool' => $tool, 'arguments' => json_encode($arguments, JSON_THROW_ON_ERROR),
                    'idempotency_key' => $idempotencyKey, 'status' => 'queued', 'created_at' => now(), 'updated_at' => now(),
                ]);
            } catch (UniqueConstraintViolationException) {
                throw new InvalidArgumentException('idempotency_conflict');
            }
            $this->event($id, 'queued', 'Waiting for the paired device agent to claim this request.');

            return ['id' => $id, 'created' => true];
        });
    }

    /** @return array{cancelled: bool} */
    public function cancel(string $tenantId, int $userId, string $jobId): array
    {
        $job = DB::table('codebridge_workspace_jobs')->where('id', $jobId)->where('tenant_id', $tenantId)->where('user_id', $userId)->first();
        abort_if($job === null, 404);
        $changed = DB::transaction(function () use ($jobId): int {
            $changed = DB::table('codebridge_workspace_jobs')->where('id', $jobId)->whereIn('status', self::ACTIVE)
                ->update(['status' => 'cancelled', 'error_code' => 'cancelled_by_user', 'finished_at' => now(), 'updated_at' => now()]);
            if ($changed === 1) {
                $this->event($jobId, 'cancelled', 'Cancelled by the requesting user. A device that already started may still be finishing its local run.');
            }

            return $changed;
        });

        return ['cancelled' => $changed === 1];
    }

    /** @return list<array<string, mixed>> */
    public function list(string $tenantId, int $userId, string $deviceId, string $projectId): array
    {
        $this->expireStale($tenantId);

        return array_values(DB::table('codebridge_workspace_jobs')
            ->where('tenant_id', $tenantId)->where('user_id', $userId)
            ->where('device_id', $deviceId)->where('project_id', $projectId)
            ->orderByDesc('id')->limit(30)->get()
            ->map(fn (object $record): array => $this->present((array) $record))->all());
    }

    /**
     * @return list<array<string, mixed>>
     */
    public function events(string $tenantId, int $userId, string $jobId, int $afterSeq = 0): array
    {
        $owned = DB::table('codebridge_workspace_jobs')->where('id', $jobId)->where('tenant_id', $tenantId)->where('user_id', $userId)->exists();
        abort_unless($owned, 404);

        return array_values(DB::table('codebridge_workspace_job_events')
            ->where('job_id', $jobId)->where('seq', '>', max(0, $afterSeq))->orderBy('seq')->limit(100)
            ->get(['seq', 'kind', 'detail', 'created_at'])
            ->map(fn (object $row): array => [
                'seq' => (int) ((array) $row)['seq'], 'kind' => ((array) $row)['kind'], 'detail' => ((array) $row)['detail'],
                'at' => Carbon::parse((string) ((array) $row)['created_at'])->toIso8601String(),
            ])->all());
    }

    /**
     * Device side. Returns at most one request and only while the device has none in flight.
     *
     * @return array{id: string, tool: string, arguments: array<string, string>|\stdClass, project_id: string, lease_expires_at: string, claim_token: string}|null
     */
    public function claim(string $tenantId, string $deviceId): ?array
    {
        $this->expireStale($tenantId);

        return DB::transaction(function () use ($tenantId, $deviceId): ?array {
            // Serialize claims per device: two concurrent polls must never hold two jobs.
            $this->lockDevice($tenantId, $deviceId);
            $busy = DB::table('codebridge_workspace_jobs')->where('tenant_id', $tenantId)->where('device_id', $deviceId)
                ->whereIn('status', ['claimed', 'running'])->exists();
            if ($busy) {
                return null;
            }
            $job = DB::table('codebridge_workspace_jobs')->where('tenant_id', $tenantId)->where('device_id', $deviceId)
                ->where('status', 'queued')->orderBy('id')->lock('for update skip locked')->first();
            if ($job === null) {
                return null;
            }
            $row = (array) $job;
            // The grant may have been revoked or narrowed after the request was queued.
            $granted = $this->grantedPermissions($tenantId, $deviceId, (string) $row['project_id']);
            if (! $this->permits($granted, (string) $row['tool'])) {
                $this->finish((string) $row['id'], 'failed', 'grant_revoked', 'The device grant no longer allows this tool.', 'queued');

                return null;
            }
            $token = bin2hex(random_bytes(24));
            $lease = now()->addSeconds(self::LEASE_SECONDS);
            $changed = DB::table('codebridge_workspace_jobs')->where('id', $row['id'])->where('status', 'queued')->update([
                'status' => 'claimed', 'claim_hash' => hash('sha256', $token), 'claimed_at' => now(),
                'lease_expires_at' => $lease, 'updated_at' => now(),
            ]);
            if ($changed !== 1) {
                return null;
            }
            $this->event((string) $row['id'], 'claimed', 'Claimed by the paired device agent.');
            $arguments = json_decode((string) $row['arguments'], true);

            return [
                'id' => (string) $row['id'], 'tool' => (string) $row['tool'],
                // An empty PHP array would serialize as a JSON array; the device contract requires an object.
                'arguments' => is_array($arguments) && $arguments !== [] ? $arguments : (object) [], 'project_id' => (string) $row['project_id'],
                'lease_expires_at' => $lease->toIso8601String(), 'claim_token' => $token,
            ];
        });
    }

    /**
     * Device side report. Throws RuntimeException('job_not_active') when cancelled, expired or finished,
     * which tells the agent to stop.
     *
     * @param  array<string, mixed>  $report
     * @return array{status: string}
     */
    public function report(string $tenantId, string $deviceId, string $jobId, string $claimToken, array $report): array
    {
        $kind = $report['kind'] ?? null;
        if (! is_string($kind) || ! in_array($kind, self::DEVICE_KINDS, true)) {
            throw new InvalidArgumentException('invalid_kind');
        }
        $detail = $this->text($report['detail'] ?? null, 500);
        $progress = $report['progress'] ?? null;
        if ($progress !== null && (! is_int($progress) || $progress < 0 || $progress > 100)) {
            throw new InvalidArgumentException('invalid_progress');
        }
        $summary = $this->text($report['summary'] ?? null, 2000);
        $evidence = $this->evidence($report['evidence'] ?? null);

        return DB::transaction(function () use ($tenantId, $deviceId, $jobId, $claimToken, $kind, $detail, $progress, $summary, $evidence): array {
            $job = DB::table('codebridge_workspace_jobs')->where('id', $jobId)->where('tenant_id', $tenantId)
                ->where('device_id', $deviceId)->lockForUpdate()->first();
            abort_if($job === null, 404);
            $row = (array) $job;
            if (! $this->claimMatches($row['claim_hash'] ?? null, $claimToken)) {
                abort(403);
            }
            $status = (string) $row['status'];
            if (! in_array($status, ['claimed', 'running'], true)) {
                throw new RuntimeException('job_not_active');
            }
            $lease = now()->addSeconds(self::LEASE_SECONDS);
            if ($kind === 'started') {
                if ($status !== 'claimed') {
                    throw new InvalidArgumentException('already_started');
                }
                DB::table('codebridge_workspace_jobs')->where('id', $jobId)->where('status', 'claimed')
                    ->update(['status' => 'running', 'started_at' => now(), 'lease_expires_at' => $lease, 'updated_at' => now()]);
                $this->event($jobId, 'started', $detail ?? 'The device agent started the run.');

                return ['status' => 'running'];
            }
            // A device may refuse a claimed job before running anything (unknown gate, project not
            // enabled locally, dirty checkout): that is a final failure and needs no start.
            if ($status !== 'running' && ! ($status === 'claimed' && $kind === 'failed')) {
                throw new InvalidArgumentException('not_started');
            }
            if ($kind === 'progress') {
                $previous = $row['progress'] === null ? 0 : (int) $row['progress'];
                $value = max($previous, $progress ?? $previous);
                DB::table('codebridge_workspace_jobs')->where('id', $jobId)
                    ->update(['progress' => $value, 'lease_expires_at' => $lease, 'updated_at' => now()]);
                $this->event($jobId, 'progress', $detail ?? 'Progress reported by the device.');

                return ['status' => 'running'];
            }
            $final = $kind === 'succeeded' ? 'succeeded' : 'failed';
            DB::table('codebridge_workspace_jobs')->where('id', $jobId)->update([
                'status' => $final, 'progress' => $final === 'succeeded' ? 100 : $row['progress'],
                'summary' => $summary, 'evidence' => $evidence === null ? null : json_encode($evidence, JSON_THROW_ON_ERROR),
                'error_code' => $final === 'failed' ? 'device_reported_failure' : null, 'finished_at' => now(), 'updated_at' => now(),
            ]);
            $this->event($jobId, $final, $detail ?? ($final === 'succeeded' ? 'The device reported success.' : 'The device reported failure.'));

            return ['status' => $final];
        });
    }

    public function expireStale(string $tenantId): void
    {
        $now = now();
        $stale = DB::table('codebridge_workspace_jobs')->where('tenant_id', $tenantId)
            ->where(function ($query) use ($now): void {
                $query->where(fn ($q) => $q->where('status', 'queued')->where('created_at', '<', $now->copy()->subSeconds(self::QUEUE_TTL_SECONDS)))
                    ->orWhere(fn ($q) => $q->whereIn('status', ['claimed', 'running'])->where('lease_expires_at', '<', $now));
            })->limit(100)->get(['id', 'status']);
        foreach ($stale as $record) {
            $row = (array) $record;
            if ($row['status'] === 'queued') {
                $this->finish((string) $row['id'], 'expired', 'not_claimed_by_device', 'No device agent claimed this request in time.', 'queued');
            } else {
                $this->finish((string) $row['id'], 'failed', 'lease_expired', 'The device stopped reporting; the run is not known to have finished.', (string) $row['status']);
            }
        }
    }

    private function lockDevice(string $tenantId, string $deviceId): void
    {
        DB::table('codebridge_device_credentials')->where('tenant_id', $tenantId)->where('device_id', $deviceId)->lockForUpdate()->first(['id']);
    }

    /** @param list<string> $granted */
    private function permits(array $granted, string $tool): bool
    {
        return in_array(WorkspaceToolCatalog::permission($tool), $granted, true);
    }

    private function claimMatches(mixed $stored, string $token): bool
    {
        return is_string($stored) && hash_equals($stored, hash('sha256', $token));
    }

    private function finish(string $jobId, string $status, string $code, string $detail, string $from): void
    {
        $changed = DB::table('codebridge_workspace_jobs')->where('id', $jobId)->where('status', $from)
            ->update(['status' => $status, 'error_code' => $code, 'finished_at' => now(), 'updated_at' => now()]);
        if ($changed === 1) {
            $this->event($jobId, $status, $detail);
        }
    }

    private function event(string $jobId, string $kind, ?string $detail): void
    {
        $next = (int) DB::table('codebridge_workspace_job_events')->where('job_id', $jobId)->max('seq') + 1;
        DB::table('codebridge_workspace_job_events')->insert([
            'job_id' => $jobId, 'seq' => $next, 'kind' => $kind, 'detail' => $detail === null ? null : mb_substr($detail, 0, 500),
            'created_at' => now(),
        ]);
    }

    private function text(mixed $value, int $max): ?string
    {
        if ($value === null) {
            return null;
        }
        if (! is_string($value) || mb_strlen($value) > $max) {
            throw new InvalidArgumentException('invalid_text');
        }

        return $value;
    }

    /**
     * Only structured, non-secret evidence keys are accepted from a device.
     *
     * @return array<string, int|string>|null
     */
    private function evidence(mixed $value): ?array
    {
        if ($value === null) {
            return null;
        }
        if (! is_array($value) || count($value) > 6) {
            throw new InvalidArgumentException('invalid_evidence');
        }
        $out = [];
        foreach ($value as $key => $item) {
            $valid = match ($key) {
                'commit_sha' => is_string($item) && preg_match('/\A[0-9a-f]{40}\z/', $item) === 1,
                'gate' => is_string($item) && preg_match('/\A[a-z][a-z0-9_-]{0,39}\z/', $item) === 1,
                'ci_url' => is_string($item) && strlen($item) <= 300 && preg_match('#\Ahttps://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/[0-9]+\z#', $item) === 1,
                'exit_code' => is_int($item) && $item >= 0 && $item <= 255,
                'duration_ms' => is_int($item) && $item >= 0 && $item <= 86_400_000,
                'result' => is_string($item) && in_array($item, ['pass', 'fail'], true),
                default => false,
            };
            if (! $valid) {
                throw new InvalidArgumentException('invalid_evidence');
            }
            $out[(string) $key] = $item;
        }

        return $out;
    }

    /**
     * @param  array<string, mixed>  $row
     * @return array<string, mixed>
     */
    private function present(array $row): array
    {
        $iso = static fn (mixed $value): ?string => $value === null ? null : Carbon::parse((string) $value)->toIso8601String();
        $arguments = json_decode((string) $row['arguments'], true);
        $evidence = $row['evidence'] === null ? null : json_decode((string) $row['evidence'], true);

        return [
            'id' => (string) $row['id'], 'tool' => (string) $row['tool'], 'arguments' => is_array($arguments) ? $arguments : [],
            'status' => (string) $row['status'], 'progress' => $row['progress'] === null ? null : (int) $row['progress'],
            'error_code' => $row['error_code'], 'summary' => $row['summary'], 'evidence' => $evidence,
            'created_at' => $iso($row['created_at']), 'claimed_at' => $iso($row['claimed_at']),
            'started_at' => $iso($row['started_at']), 'finished_at' => $iso($row['finished_at']),
        ];
    }
}
