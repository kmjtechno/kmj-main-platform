<?php

namespace App\Services\Releases;

use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;
use KMJ\MainPlatform\Releases\Models\ProductRelease;
use KMJ\MainPlatform\Releases\Services\PromotedReleaseReader;

final class CustomerReleaseAccess
{
    public function __construct(
        private readonly PromotedReleaseReader $releases,
    ) {}

    public function latestForOrganizationProduct(
        int $userId,
        string $organizationId,
        string $productId,
    ): ?ProductRelease {
        if (! $this->hasEffectiveEntitlement($userId, $organizationId, $productId)) {
            return null;
        }

        return $this->releases->latestForProduct($productId);
    }

    public function downloadableForUser(int $userId, string $releaseId): ?ProductRelease
    {
        $release = ProductRelease::query()
            ->with('artifact')
            ->whereKey($releaseId)
            ->where('status', 'promoted')
            ->whereNull('revoked_at')
            ->whereHas('artifact')
            ->first();

        if (! $release instanceof ProductRelease) {
            return null;
        }

        $organizationIds = OrganizationMembership::query()
            ->where('user_id', $userId)
            ->pluck('organization_id')
            ->filter()
            ->all();

        if ($organizationIds === []) {
            return null;
        }

        $now = now();

        $entitled = Entitlement::query()
            ->whereIn('organization_id', $organizationIds)
            ->where('product_id', $release->product_id)
            ->where('status', 'active')
            ->where(function ($query) use ($now): void {
                $query->whereNull('starts_at')->orWhere('starts_at', '<=', $now);
            })
            ->where(function ($query) use ($now): void {
                $query->whereNull('ends_at')->orWhere('ends_at', '>', $now);
            })
            ->exists();

        return $entitled ? $release : null;
    }

    private function hasEffectiveEntitlement(
        int $userId,
        string $organizationId,
        string $productId,
    ): bool {
        $member = OrganizationMembership::query()
            ->where('organization_id', $organizationId)
            ->where('user_id', $userId)
            ->exists();

        if (! $member) {
            return false;
        }

        $now = now();

        return Entitlement::query()
            ->where('organization_id', $organizationId)
            ->where('product_id', $productId)
            ->where('status', 'active')
            ->where(function ($query) use ($now): void {
                $query->whereNull('starts_at')->orWhere('starts_at', '<=', $now);
            })
            ->where(function ($query) use ($now): void {
                $query->whereNull('ends_at')->orWhere('ends_at', '>', $now);
            })
            ->exists();
    }
}
