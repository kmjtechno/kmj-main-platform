<?php

declare(strict_types=1);

namespace App\Services\Staff;

use App\Models\User;
use App\Services\PlatformOwnerAccess;

/**
 * Single place that answers "may this KMJ-internal person do this platform action?".
 *
 * KMJ's own staff/billing team is NOT implemented yet (the organization roles owner/admin/member
 * belong to customer organizations, not KMJ staff). Until a real staff model exists, only the
 * Super Admin (platform owner with verified email and a passkey) holds any capability. When the
 * staff team is built, map its billing role to BILLING_REFUND_RECORD here; callers need no change.
 */
final class PlatformStaffAuthority
{
    public const BILLING_REFUND_RECORD = 'billing.refund.record';

    public const ENTITLEMENT_REVOKE_AFTER_REFUND = 'entitlement.revoke.after_refund';

    public function __construct(private readonly PlatformOwnerAccess $owner) {}

    public function allows(User $user, string $capability): bool
    {
        return match ($capability) {
            self::BILLING_REFUND_RECORD,
            self::ENTITLEMENT_REVOKE_AFTER_REFUND => $this->owner->allows($user),
            default => false,
        };
    }
}
