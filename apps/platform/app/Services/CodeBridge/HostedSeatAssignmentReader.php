<?php

declare(strict_types=1);

namespace App\Services\CodeBridge;

use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * Source-only read model for an explicitly recorded assignment.
 * No payment verification, issuance, seat allocation or dispatch happens here.
 * A future settlement authority must write the records and enforce seat capacity.
 */
final class HostedSeatAssignmentReader
{
    /** @return array{organization_id: string, membership_id: string, user_id: string, license_id: string, seat_id: string, assignment_revision: int}|null */
    public function forMember(User $actor, string $organization, string $seat): ?array
    {
        if (! $actor->exists || $actor->email_verified_at === null
            || ! Str::isUuid($organization) || ! Str::isUuid($seat)) {
            return null;
        }

        $now = now();
        $row = DB::table('codebridge_hosted_seat_assignments as s')
            ->join('organization_memberships as m', 'm.id', '=', 's.membership_id')
            ->join('users as u', 'u.id', '=', 'm.user_id')
            ->join('kslp_licenses as l', 'l.id', '=', 's.license_id')
            ->where('s.id', $seat)->where('s.organization_id', $organization)
            ->where('m.organization_id', $organization)->where('m.user_id', $actor->getKey())
            ->whereIn('m.role', ['owner', 'admin', 'member'])->whereNotNull('u.email_verified_at')
            ->where('l.customer_id', $organization)->where('l.product', 'KMJ_CODEBRIDGE')
            ->where('l.plan', 'team')->where('l.status', 'active')->whereNull('l.revoked_at')
            ->where('l.starts_at', '<=', $now)->where('l.expires_at', '>', $now)
            ->where('s.starts_at', '<=', $now)->where('s.ends_at', '>', $now)
            ->whereNull('s.revoked_at')->where('s.assignment_revision', '>', 0)
            ->first(['s.id', 's.organization_id', 's.membership_id', 's.license_id', 's.assignment_revision', 'm.user_id']);

        if ($row === null) {
            return null;
        }

        return [
            'organization_id' => (string) $row->organization_id,
            'membership_id' => (string) $row->membership_id,
            'user_id' => (string) $row->user_id,
            'license_id' => (string) $row->license_id,
            'seat_id' => (string) $row->id,
            'assignment_revision' => (int) $row->assignment_revision,
        ];
    }
}
