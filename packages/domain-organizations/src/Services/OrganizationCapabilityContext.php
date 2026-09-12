<?php

namespace KMJ\MainPlatform\Organizations\Services;

use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;

final class OrganizationCapabilityContext
{
    private const ROLE_CAPABILITIES = [
        'owner' => [
            'organization.manage',
            'catalog.manage',
            'entitlement.manage',
            'license.manage',
            'security.manage',
        ],
        'admin' => [
            'catalog.manage',
            'entitlement.manage',
            'license.manage',
        ],
        'member' => [],
    ];

    public function membershipFor(int $userId, string $organizationId): ?OrganizationMembership
    {
        return OrganizationMembership::query()
            ->where('user_id', $userId)
            ->where('organization_id', $organizationId)
            ->first();
    }

    /** @return list<string> */
    public function capabilitiesFor(int $userId, string $organizationId): array
    {
        $membership = $this->membershipFor($userId, $organizationId);

        if ($membership === null) {
            return [];
        }

        return self::ROLE_CAPABILITIES[$membership->role] ?? [];
    }

    public function allows(int $userId, string $organizationId, string $capability): bool
    {
        return in_array(
            $capability,
            $this->capabilitiesFor($userId, $organizationId),
            true,
        );
    }
}
