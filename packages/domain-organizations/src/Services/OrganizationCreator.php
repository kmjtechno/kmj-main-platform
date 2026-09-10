<?php

namespace KMJ\MainPlatform\Organizations\Services;

use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Organizations\Models\Organization;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;

final class OrganizationCreator
{
    public function create(string $name, int $ownerUserId): Organization
    {
        return DB::transaction(function () use ($name, $ownerUserId): Organization {
            $organization = Organization::query()->create([
                'name' => trim($name),
            ]);

            OrganizationMembership::query()->create([
                'organization_id' => $organization->getKey(),
                'user_id' => $ownerUserId,
                'role' => 'owner',
            ]);

            return $organization;
        });
    }
}
