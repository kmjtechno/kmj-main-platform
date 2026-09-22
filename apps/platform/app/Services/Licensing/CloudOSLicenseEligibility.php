<?php

namespace App\Services\Licensing;

use App\Services\Commerce\CloudOSProductCatalog;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;

final class CloudOSLicenseEligibility
{
    public function eligibleEntitlement(string $organizationId): ?Entitlement
    {
        $organizationId = trim($organizationId);

        if ($organizationId === '') {
            return null;
        }

        $product = Product::query()
            ->where('slug', CloudOSProductCatalog::SLUG)
            ->where('status', 'active')
            ->first();

        if (! $product instanceof Product) {
            return null;
        }

        $now = now();

        return Entitlement::query()
            ->where('organization_id', $organizationId)
            ->where('product_id', $product->getKey())
            ->where('capability', CloudOSProductCatalog::CAPABILITY)
            ->where('status', 'active')
            ->where(function ($query) use ($now): void {
                $query->whereNull('starts_at')->orWhere('starts_at', '<=', $now);
            })
            ->where(function ($query) use ($now): void {
                $query->whereNull('ends_at')->orWhere('ends_at', '>', $now);
            })
            ->oldest('created_at')
            ->oldest('id')
            ->first();
    }
}
