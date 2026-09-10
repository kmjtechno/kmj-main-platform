<?php

namespace KMJ\MainPlatform\Organizations\Services;

use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;

final class OrganizationDirectory
{
    /**
     * @return list<array{id: string, name: string, role: string}>
     */
    public function forUser(int $userId): array
    {
        return OrganizationMembership::query()
            ->with('organization')
            ->where('user_id', $userId)
            ->orderBy('created_at')
            ->get()
            ->map(fn (OrganizationMembership $membership): array => [
                'id' => (string) $membership->organization_id,
                'name' => (string) $membership->organization->name,
                'role' => (string) $membership->role,
            ])
            ->values()
            ->all();
    }

    public function userCanManage(int $userId, string $organizationId): bool
    {
        return OrganizationMembership::query()
            ->where('organization_id', $organizationId)
            ->where('user_id', $userId)
            ->where('role', 'owner')
            ->exists();
    }
}
