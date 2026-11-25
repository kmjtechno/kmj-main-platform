<?php

declare(strict_types=1);

namespace App\Services\CodeBridge;

use Carbon\CarbonImmutable;
use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use InvalidArgumentException;

/**
 * Source-only quota primitive. NOT wired to MCP, OAuth, pricing, checkout,
 * entitlement issuance or a production feature flag. No live quotas exist.
 *
 * All identifiers and plan codes MUST come from a future authenticated KSLP
 * authorization/seat resolver, never from an AI tool request or browser input.
 * Every real device completion MUST carry separately verified signed or
 * gateway-authenticated device evidence; this class verifies no signatures.
 */
final class MonthlyHostedUsageLedger
{
    private const LIMITS = [
        'community' => 10000,
        'pro' => 100000,
        'team' => 300000,
    ];

    /**
     * @return array{period: string, limit: int, completed: int, reserved: int, remaining: int, state: string}
     */
    public function reserveTrusted(
        string $organizationId,
        string $subjectKey,
        string $executionId,
        string $planCode,
        ?CarbonImmutable $at = null,
    ): array {
        $this->validateIdentity($organizationId, $subjectKey, $executionId);
        $limit = self::LIMITS[$planCode] ?? null;
        if ($limit === null) {
            // Business contract and paid trial require an approved plan
            // snapshot. Never guess an unlimited hosted allowance.
            throw new DomainException('CODEBRIDGE_MONTHLY_PLAN_UNAVAILABLE');
        }

        $period = ($at ?? CarbonImmutable::now('UTC'))->utc()->startOfMonth()->toDateString();

        return DB::transaction(function () use ($organizationId, $subjectKey, $executionId, $planCode, $limit, $period): array {
            DB::table('codebridge_usage_periods')->insertOrIgnore([
                'organization_id' => $organizationId,
                'subject_key' => $subjectKey,
                'period_start_utc' => $period,
                'plan_code' => $planCode,
                'monthly_limit' => $limit,
                'reserved_calls' => 0,
                'completed_calls' => 0,
                'created_at' => now(),
                'updated_at' => now(),
            ]);

            // Lock a single account/seat/month row before checking +1,
            // so two remote chats cannot both claim the last free slot.
            $counter = DB::table('codebridge_usage_periods')
                ->where('organization_id', $organizationId)
                ->where('subject_key', $subjectKey)
                ->where('period_start_utc', $period)
                ->lockForUpdate()
                ->first();

            if ($counter === null || $counter->plan_code !== $planCode || (int) $counter->monthly_limit !== $limit) {
                // Mid-period changes need a separate reviewed KSLP policy.
                throw new DomainException('CODEBRIDGE_MONTHLY_PLAN_SNAPSHOT_CONFLICT');
            }

            $completed = (int) $counter->completed_calls;
            $reserved = (int) $counter->reserved_calls;
            if ($completed < 0 || $reserved < 0 || $completed > $limit || $reserved > $limit - $completed) {
                throw new DomainException('CODEBRIDGE_MONTHLY_COUNTER_CONFLICT');
            }

            $existing = DB::table('codebridge_usage_executions')
                ->where('organization_id', $organizationId)
                ->where('execution_id', $executionId)
                ->first();

            if ($existing !== null) {
                if ($existing->subject_key !== $subjectKey || $existing->period_start_utc !== $period) {
                    throw new DomainException('CODEBRIDGE_MONTHLY_EXECUTION_REPLAY_CONFLICT');
                }

                return $this->summary(
                    $period,
                    $limit,
                    (int) $counter->completed_calls,
                    (int) $counter->reserved_calls,
                    (string) $existing->state,
                );
            }

            if ($completed + $reserved >= $limit) {
                throw new DomainException('CODEBRIDGE_MONTHLY_REMOTE_TOOL_CALL_LIMIT_REACHED');
            }

            $inserted = DB::table('codebridge_usage_executions')->insertOrIgnore([
                'organization_id' => $organizationId,
                'subject_key' => $subjectKey,
                'execution_id' => $executionId,
                'period_start_utc' => $period,
                'state' => 'reserved',
                'created_at' => now(),
                'updated_at' => now(),
            ]);
            if ($inserted !== 1) {
                // Two different seat/month locks can race on the global execution
                // uniqueness key. Never increment a losing reservation.
                $existing = DB::table('codebridge_usage_executions')
                    ->where('organization_id', $organizationId)
                    ->where('execution_id', $executionId)
                    ->first();
                if ($existing === null || $existing->subject_key !== $subjectKey || $existing->period_start_utc !== $period) {
                    throw new DomainException('CODEBRIDGE_MONTHLY_EXECUTION_REPLAY_CONFLICT');
                }

                return $this->summary($period, $limit, $completed, $reserved, (string) $existing->state);
            }
            DB::table('codebridge_usage_periods')->where('id', $counter->id)
                ->update(['reserved_calls' => $reserved + 1, 'updated_at' => now()]);

            return $this->summary($period, $limit, $completed, $reserved + 1, 'reserved');
        }, 3);
    }

    /**
     * May only be called AFTER independent verification of the device's
     * execution receipt. The boolean is a private service precondition,
     * NOT evidence validation or a public API. An uncertain/failed delivery
     * stays reserved and must be reconciled separately, never double counted.
     *
     * @return array{period: string, limit: int, completed: int, reserved: int, remaining: int, state: string}
     */
    public function completeTrusted(
        string $organizationId,
        string $subjectKey,
        string $executionId,
        bool $verifiedDeviceReceipt,
    ): array {
        $this->validateIdentity($organizationId, $subjectKey, $executionId);
        if (! $verifiedDeviceReceipt) {
            throw new DomainException('CODEBRIDGE_MONTHLY_COMPLETION_PROOF_REQUIRED');
        }

        return DB::transaction(function () use ($organizationId, $subjectKey, $executionId): array {
            $entry = DB::table('codebridge_usage_executions')
                ->where('organization_id', $organizationId)
                ->where('execution_id', $executionId)
                ->first();
            if ($entry === null || $entry->subject_key !== $subjectKey) {
                throw new DomainException('CODEBRIDGE_MONTHLY_EXECUTION_NOT_FOUND');
            }

            $counter = DB::table('codebridge_usage_periods')
                ->where('organization_id', $organizationId)
                ->where('subject_key', $subjectKey)
                ->where('period_start_utc', $entry->period_start_utc)
                ->lockForUpdate()->first();

            if ($counter === null) {
                throw new DomainException('CODEBRIDGE_MONTHLY_COUNTER_MISSING');
            }
            $current = DB::table('codebridge_usage_executions')
                ->where('id', $entry->id)->lockForUpdate()->first();

            if ($current === null || ! in_array($current->state, ['reserved', 'completed'], true)) {
                throw new DomainException('CODEBRIDGE_MONTHLY_EXECUTION_STATE_INVALID');
            }

            $completed = (int) $counter->completed_calls;
            $reserved = (int) $counter->reserved_calls;
            $limit = (int) $counter->monthly_limit;
            if ($completed < 0 || $reserved < 0 || $completed > $limit || $reserved > $limit - $completed) {
                throw new DomainException('CODEBRIDGE_MONTHLY_COUNTER_CONFLICT');
            }
            if ($current->state === 'completed') {
                return $this->summary($entry->period_start_utc, (int) $counter->monthly_limit, $completed, $reserved, 'completed');
            }
            if ($reserved < 1 || $completed >= (int) $counter->monthly_limit) {
                throw new DomainException('CODEBRIDGE_MONTHLY_COUNTER_CONFLICT');
            }

            DB::table('codebridge_usage_executions')->where('id', $entry->id)
                ->update(['state' => 'completed', 'updated_at' => now()]);
            DB::table('codebridge_usage_periods')->where('id', $counter->id)
                ->update([
                    'completed_calls' => $completed + 1,
                    'reserved_calls' => $reserved - 1,
                    'updated_at' => now(),
                ]);

            return $this->summary($entry->period_start_utc, (int) $counter->monthly_limit, $completed + 1, $reserved - 1, 'completed');
        }, 3);
    }

    /**
     * Internal snapshot for an already resolved trusted account/seat.
     * Recorded counters are NOT independently attested or customer billable.
     * Missing period rows are unknown; this method never creates a reservation.
     *
     * @return array<string, mixed>
     */
    public function snapshotTrusted(string $organizationId, string $subjectKey, string $planCode, ?CarbonImmutable $at = null): array
    {
        if (! Str::isUuid($organizationId) || preg_match('/\\A[a-zA-Z0-9:_-]{1,64}\\z/D', $subjectKey) !== 1) {
            throw new InvalidArgumentException('CODEBRIDGE_MONTHLY_TRUSTED_IDENTITY_INVALID');
        }

        $limit = self::LIMITS[$planCode] ?? null;
        $month = ($at ?? CarbonImmutable::now('UTC'))->utc()->startOfMonth();
        $snapshot = [
            'status' => 'unverified',
            'meter_live' => false,
            'billable' => false,
            'period' => $month->toDateString(),
            'recorded_completed' => null,
            'recorded_reserved' => null,
            'recorded_remaining' => null,
            'policy_reset_at' => $month->addMonth()->toIso8601String(),
        ];
        if ($limit === null) {
            return $snapshot;
        }

        $row = DB::table('codebridge_usage_periods')
            ->where('organization_id', $organizationId)
            ->where('subject_key', $subjectKey)
            ->where('period_start_utc', $month->toDateString())
            ->first();
        if ($row === null || $row->plan_code !== $planCode || (int) $row->monthly_limit !== $limit) {
            return $snapshot;
        }

        $completed = (int) $row->completed_calls;
        $reserved = (int) $row->reserved_calls;
        if ($completed < 0 || $reserved < 0 || $completed > $limit || $reserved > $limit - $completed) {
            return $snapshot;
        }

        return [
            ...$snapshot,
            'status' => 'recorded_only_not_attested',
            'recorded_completed' => $completed,
            'recorded_reserved' => $reserved,
            'recorded_remaining' => $limit - $completed - $reserved,
        ];
    }

    /** @return array{period: string, limit: int, completed: int, reserved: int, remaining: int, state: string} */
    private function summary(string $period, int $limit, int $completed, int $reserved, string $state): array
    {
        return [
            'period' => $period,
            'limit' => $limit,
            'completed' => $completed,
            'reserved' => $reserved,
            'remaining' => max(0, $limit - $completed - $reserved),
            'state' => $state,
        ];
    }

    private function validateIdentity(string $organizationId, string $subjectKey, string $executionId): void
    {
        if (! Str::isUuid($organizationId) || ! Str::isUuid($executionId)
            || preg_match('/\\A[a-zA-Z0-9:_-]{1,64}\\z/D', $subjectKey) !== 1) {
            throw new InvalidArgumentException('CODEBRIDGE_MONTHLY_TRUSTED_IDENTITY_INVALID');
        }
    }
}
