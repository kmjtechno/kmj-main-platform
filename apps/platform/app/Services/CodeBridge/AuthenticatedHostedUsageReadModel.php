<?php

declare(strict_types=1);

namespace App\Services\CodeBridge;

use App\Models\User;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

/**
 * Internal, read-only foundation for a future authenticated usage meter.
 *
 * These historical ledger counters are NOT cryptographically attested
 * executions. Never use this result for checkout, billing, entitlement
 * issuance, enforcement, or a customer-facing "live usage" claim.
 *
 * A future gateway/seat adapter must independently verify device receipts,
 * KSLP entitlement, purchased plan snapshot and idempotent settlement
 * before a separately reviewed public usage response may be enabled.
 */
final class AuthenticatedHostedUsageReadModel
{
    public function __construct(
        private readonly OrganizationDirectory $directory,
    ) {}

    /**
     * The actor is supplied by trusted server authentication, never an API
     * user id. Tenant and period are derived here, not from request input.
     *
     * @return array<string, mixed>
     */
    public function forUser(User $actor, ?CarbonImmutable $at = null): array
    {
        $now = ($at ?? CarbonImmutable::now('UTC'))->utc();
        $period = $now->startOfMonth()->toDateString();
        $empty = [
            'status' => 'source_only_unverified',
            'period_start_utc' => $period,
            'device_receipts_verified' => false,
            'meter_live' => false,
            'billable' => false,
            'active_plan' => null,
            'remaining_calls' => null,
            'organizations' => [],
        ];

        if (! $actor->exists || $actor->email_verified_at === null) {
            return $empty;
        }

        // Never accept organization_id/subject_key from the request. An actor
        // can have memberships in several organizations; none confer billing
        // authority or ownership of a specific paid seat.
        $organizations = $this->directory->forUser((int) $actor->getKey());
        if ($organizations === []) {
            return $empty;
        }

        $ids = array_values(array_unique(array_column($organizations, 'id')));
        $eligible = DB::table('entitlements as e')
            ->join('products as p', 'p.id', '=', 'e.product_id')
            ->whereIn('e.organization_id', $ids)
            ->where('p.slug', 'kmj-codebridge')
            ->where('e.status', 'active')
            ->where('e.starts_at', '<=', $now->toDateTimeString())
            ->where(function ($query) use ($now): void {
                $query->whereNull('e.ends_at')
                    ->orWhere('e.ends_at', '>', $now->toDateTimeString());
            })
            ->distinct()
            ->pluck('e.organization_id')
            ->map(fn ($id): string => (string) $id)
            ->all();

        if ($eligible === []) {
            return $empty;
        }

        // Aggregate per organization and month only. Never disclose
        // per-seat keys, execution IDs, device IDs, or other tenants' rows.
        // A missing row is UNKNOWN, NOT proof of zero remote calls.
        $rows = DB::table('codebridge_usage_periods')
            ->whereIn('organization_id', $eligible)
            ->where('period_start_utc', $period)
            ->select('organization_id')
            ->selectRaw('SUM(completed_calls) AS recorded_completed')
            ->selectRaw('SUM(reserved_calls) AS recorded_reserved')
            ->groupBy('organization_id')
            ->get()
            ->keyBy('organization_id');

        $visible = [];
        foreach ($organizations as $org) {
            if (! in_array($org['id'], $eligible, true)) {
                continue;
            }
            $row = $rows->get($org['id']);
            $visible[] = [
                'organization_id' => $org['id'],
                'organization_name' => $org['name'],
                'recorded_completed_calls' => $row === null ? null : (int) $row->recorded_completed,
                'recorded_reserved_calls' => $row === null ? null : (int) $row->recorded_reserved,
                'recorded_only_not_verified' => true,
            ];
        }

        return [...$empty, 'organizations' => $visible];
    }
}
