<?php

namespace KMJ\MainPlatform\Releases\Services;

use KMJ\MainPlatform\Releases\Models\ProductRelease;

final class PromotedReleaseReader
{
    public function latestForProduct(string $productId): ?ProductRelease
    {
        return ProductRelease::query()
            ->with('artifact')
            ->where('product_id', $productId)
            ->where('status', 'promoted')
            ->whereNull('revoked_at')
            ->whereHas('artifact')
            ->latest('promoted_at')
            ->latest('created_at')
            ->first();
    }
}
