<?php

declare(strict_types=1);

namespace App\Services\CodeBridge;

use App\Models\User;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

/**
 * A bounded, read-only reconciliation of the non-commercial git_status pilot.
 * Never represents all remote tools, tokens, paid seats or billing.
 */
final class HostedPilotUsageSnapshot
{
    public function __construct(private readonly OrganizationDirectory $organizations) {}

    /** @return array<string, mixed>|null */
    public function forOwner(User $actor, string $organization, ?CarbonImmutable $at = null): ?array
    {
        if (! config('codebridge.enabled') || ! config('codebridge.hosted_metering_pilot_enabled')
            || config('codebridge.hosted_metering_pilot_tenant') !== $organization
            || ! $actor->exists || $actor->email_verified_at === null
            || ! $this->organizations->userCanManage((int) $actor->getKey(), $organization)) {
            return null;
        }

        $month = ($at ?? CarbonImmutable::now('UTC'))->utc()->startOfMonth();

        return DB::transaction(function () use ($organization, $month): ?array {
            $period = DB::table('codebridge_usage_periods')
                ->where('organization_id', $organization)->where('subject_key', 'account')
                ->where('period_start_utc', $month->toDateString())->lockForUpdate()->first();
            if ($period === null) {
                return null;
            }
            $limit = match ($period->plan_code) {
                'community' => 10000,
                'pro' => 100000,
                default => null,
            };
            $completed = (int) $period->completed_calls;
            $reserved = (int) $period->reserved_calls;
            if ($limit === null || (int) $period->monthly_limit !== $limit || $completed < 0
                || $reserved < 0 || $completed > $limit || $reserved > $limit - $completed) {
                return null;
            }

            $activeLicense = DB::table('kslp_licenses')->where('customer_id', $organization)
                ->where('product', 'KMJ_CODEBRIDGE')->where('plan', $period->plan_code)
                ->where('status', 'active')->whereNull('revoked_at')
                ->where('starts_at', '<=', now())->where('expires_at', '>', now())->exists();
            if (! $activeLicense) {
                return null;
            }

            $executions = DB::table('codebridge_usage_executions as e')
                ->where('e.organization_id', $organization)->where('e.subject_key', 'account')
                ->where('e.period_start_utc', $month->toDateString());
            if ((clone $executions)->count() !== $completed + $reserved) {
                return null;
            }
            $bound = $executions->join('codebridge_receipt_bindings as b', 'b.execution_id', '=', 'e.execution_id')
                ->whereColumn('b.organization_id', 'e.organization_id')
                ->whereColumn('b.subject_key', 'e.subject_key')
                ->where('b.plan_code', $period->plan_code)->where('b.pilot_only', true);
            $verified = (clone $bound)->where('e.state', 'completed')->where('b.outcome', 'succeeded')
                ->whereNotNull('b.verified_signature')->count();
            $pending = (clone $bound)->where('e.state', 'reserved')->whereNull('b.outcome')->count();
            if ($verified !== $completed || $pending !== $reserved) {
                return null;
            }

            return [
                'status' => 'pilot_only',
                'billable' => false,
                'tool' => 'git_status',
                'limit' => $limit,
                'completed' => $verified,
                'reserved' => $pending,
                'remaining' => $limit - $verified - $pending,
                'reset_at' => $month->addMonth()->toIso8601String(),
            ];
        });
    }
}
