<?php

namespace KMJ\MainPlatform\Entitlements\Services;

use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;

final class EntitlementReader
{
    /**
     * @return list<array{id: string, product_id: string, product_name: string, product_slug: string, capability: string, status: string, starts_at: string, ends_at: string|null}>
     */
    public function forOrganization(string $organizationId): array
    {
        $entitlements = Entitlement::query()
            ->where('organization_id', $organizationId)
            ->orderByDesc('created_at')
            ->get();

        $products = Product::query()
            ->whereIn('id', $entitlements->pluck('product_id')->filter()->unique())
            ->get(['id', 'name', 'slug'])
            ->keyBy(fn (Product $product): string => (string) $product->getKey());

        return $entitlements
            ->map(function (Entitlement $entitlement) use ($products): array {
                $productId = (string) $entitlement->product_id;
                $product = $products->get($productId);

                return [
                    'id' => (string) $entitlement->getKey(),
                    'product_id' => $productId,
                    'product_name' => $product instanceof Product ? (string) $product->name : 'Unknown product',
                    'product_slug' => $product instanceof Product ? (string) $product->slug : $productId,
                    'capability' => (string) $entitlement->capability,
                    // A time-limited grant stops counting once it ends.
                    'status' => $entitlement->status === 'active' && $entitlement->ends_at?->isPast() === true
                        ? 'expired'
                        : (string) $entitlement->status,
                    'starts_at' => $entitlement->starts_at->toIso8601String(),
                    'ends_at' => $entitlement->ends_at?->toIso8601String(),
                ];
            })
            ->values()
            ->all();
    }
}
