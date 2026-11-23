<?php

declare(strict_types=1);

namespace App\Services\CodeBridge\Workspace;

use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use InvalidArgumentException;

/**
 * Read-only consistency check for the existing, authenticated device job
 * report journal. This is NOT a cryptographic device signature verification,
 * quota settlement, plan authorization or a live billing proof.
 *
 * The future adapter MUST derive all arguments from an already authorized
 * tenant/seat/device/job, not customer-supplied query parameters. The current
 * report endpoint separately authenticates the bearer credential and claim
 * token; this class only checks what the server persisted afterward.
 */
final class WorkspaceCompletionReceiptReadiness
{
    /** @return array{status: string, recorded_terminal: bool, signature_verified: false, quota_settlement_authorized: false, outcome: ?string} */
    public function inspectTrusted(string $tenantId, int $userId, string $deviceId, string $jobId): array
    {
        if (preg_match('/\\A[A-Za-z0-9_-]{1,64}\\z/D', $tenantId) !== 1
            || preg_match('/\\A[A-Za-z0-9_-]{1,64}\\z/D', $deviceId) !== 1
            || $userId < 1 || ! Str::isUlid($jobId)) {
            throw new InvalidArgumentException('CODEBRIDGE_RECEIPT_SCOPE_INVALID');
        }

        // Never distinguish an unknown job from another customer's job.
        // No summaries, event details, tokens or device identifiers are returned.
        $row = DB::table('codebridge_workspace_jobs')
            ->where('id', $jobId)
            ->where('tenant_id', $tenantId)
            ->where('user_id', $userId)
            ->where('device_id', $deviceId)
            ->first(['status', 'claimed_at', 'started_at', 'finished_at',
                'claim_hash', 'error_code']);
        if ($row === null) {
            return $this->notProven();
        }

        $status = (string) $row->status;
        if (! in_array($status, ['succeeded', 'failed'], true)
            || ! is_string($row->claim_hash)
            || preg_match('/\\A[a-f0-9]{64}\\z/D', $row->claim_hash) !== 1
            || $row->claimed_at === null
            || $row->started_at === null
            || $row->finished_at === null
            || Carbon::parse((string) $row->started_at)->gt(Carbon::parse((string) $row->finished_at))
            || ($status === 'succeeded' && $row->error_code !== null)
            || ($status === 'failed' && $row->error_code !== 'device_reported_failure')) {
            // Pre-start refusal, expiry, grant revocation and cancellation
            // must not masquerade as a completed remote execution.
            return $this->notProven();
        }

        $events = DB::table('codebridge_workspace_job_events')
            ->where('job_id', $jobId)
            ->orderBy('seq')
            ->pluck('kind')
            ->map(static fn ($kind): string => (string) $kind)
            ->all();

        $last = array_pop($events);
        if ($last !== $status
            || ! in_array('queued', $events, true)
            || ! in_array('claimed', $events, true)
            || ! in_array('started', $events, true)
            || in_array('cancelled', $events, true)
            || in_array('expired', $events, true)
            || in_array('failed', $events, true)
            || in_array('succeeded', $events, true)) {
            return $this->notProven();
        }

        // This only establishes that a credential/claim-protected report
        // made an internally consistent transition. A separate signed
        // device receipt, KSLP plan/seat grant and idempotent reservation
        // are mandatory before settling any hosted monthly call.
        return [
            'status' => 'server_report_consistent_not_attested',
            'recorded_terminal' => true,
            'signature_verified' => false,
            'quota_settlement_authorized' => false,
            'outcome' => $status,
        ];
    }

    /** @return array{status: string, recorded_terminal: false, signature_verified: false, quota_settlement_authorized: false, outcome: null} */
    private function notProven(): array
    {
        return [
            'status' => 'not_proven',
            'recorded_terminal' => false,
            'signature_verified' => false,
            'quota_settlement_authorized' => false,
            'outcome' => null,
        ];
    }
}
