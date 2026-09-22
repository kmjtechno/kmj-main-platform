<?php

namespace App\Services\Licensing;

use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;

final class SandboxProductAuthorityValidator
{
    public function __construct(
        private readonly ProductLicenseProfileRegistry $profiles,
    ) {}

    /**
     * @param  array<string, mixed>  $claims
     */
    public function failureReason(array $claims): ?string
    {
        $organizationId = $claims['organization_id'] ?? null;
        $productId = $claims['product_id'] ?? null;
        $entitlementId = $claims['entitlement_id'] ?? null;

        if (! is_string($organizationId) || ! is_string($productId) || ! is_string($entitlementId)) {
            return 'missing_claims';
        }

        $product = Product::query()->find($productId);

        if ($product === null) {
            return 'product_unavailable';
        }

        $profile = $this->profiles->forSlug((string) $product->getAttribute('slug'));

        if ($profile === null) {
            return 'unsupported_product';
        }

        if (! $profile->allowsStatus((string) $product->getAttribute('status'))) {
            return 'product_unavailable';
        }

        $now = now();
        $entitlement = Entitlement::query()
            ->whereKey($entitlementId)
            ->where('organization_id', $organizationId)
            ->where('product_id', $productId)
            ->where('status', 'active')
            ->where(function ($query) use ($now): void {
                $query->whereNull('starts_at')->orWhere('starts_at', '<=', $now);
            })
            ->where(function ($query) use ($now): void {
                $query->whereNull('ends_at')->orWhere('ends_at', '>', $now);
            })
            ->first();

        if ($entitlement === null) {
            return 'entitlement_unavailable';
        }

        if ((string) $entitlement->getAttribute('capability') !== $profile->capability) {
            return 'capability_mismatch';
        }

        return null;
    }
}
