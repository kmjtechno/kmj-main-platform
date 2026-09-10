<?php

namespace KMJ\MainPlatform\Organizations\Services;

use InvalidArgumentException;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Organizations\Models\Organization;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;

final class OrganizationCreator
{
    public function create(string $name, int $ownerUserId): Organization
    {
        $name = trim($name);

        if ($name === '') {
            throw new InvalidArgumentException('Organization name is required.');
        }

        return DB::transaction(function () use ($name, $ownerUserId): Organization {
            $organization = Organization::query()->create([
                'name' => $name,
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
