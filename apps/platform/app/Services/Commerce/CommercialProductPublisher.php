<?php

namespace App\Services\Commerce;

use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Catalog\Services\ProductCatalog;
use KMJ\MainPlatform\Entitlements\Services\EntitlementPolicyRegistry;

final class CommercialProductPublisher
{
    public function __construct(
        private readonly ProductCatalog $catalog,
        private readonly EntitlementPolicyRegistry $policies,
    ) {}

    public function publish(string $slug, string $name): Product
    {
        return DB::transaction(function () use ($slug, $name): Product {
            $product = $this->catalog->ensureCommercialProduct($slug, $name);
            $canonicalSlug = (string) $product->getAttribute('slug');

            $this->policies->ensure(
                (string) $product->getKey(),
                'commercial.'.$canonicalSlug.'.default',
                'product.'.$canonicalSlug.'.access',
            );

            return $product;
        });
    }
}
