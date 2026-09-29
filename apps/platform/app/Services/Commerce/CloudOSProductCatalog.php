<?php

namespace App\Services\Commerce;

use DomainException;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Catalog\Services\PlanCatalog;
use KMJ\MainPlatform\Catalog\Services\ProductCatalog;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Entitlements\Services\EntitlementPolicyRegistry;

final class CloudOSProductCatalog
{
    public const SLUG = 'kmj-cloudos';

    public const NAME = 'KMJ CloudOS';

    public const POLICY_CODE = 'cloudos.platform.default';

    public const CAPABILITY = 'cloudos.platform.access';

    public function __construct(
        private readonly ProductCatalog $products,
        private readonly PlanCatalog $plans,
        private readonly EntitlementPolicyRegistry $policies,
    ) {}

    public function sync(): Product
    {
        return DB::transaction(function (): Product {
            $product = $this->products->ensureCommercialProduct(self::SLUG, self::NAME);
            $this->plans->ensureCloudOSPlans((string) $product->getKey());
            $policy = $this->policies->ensure(
                (string) $product->getKey(),
                self::POLICY_CODE,
                self::CAPABILITY,
            );

            if (! $this->matchesCanonicalPolicy($policy, $product)) {
                throw new DomainException('CloudOS entitlement policy conflicts with canonical catalog facts.');
            }

            return $product;
        });
    }

    private function matchesCanonicalPolicy(EntitlementPolicy $policy, Product $product): bool
    {
        return (string) $policy->getAttribute('product_id') === (string) $product->getKey()
            && (string) $policy->getAttribute('capability') === self::CAPABILITY
            && (string) $policy->getAttribute('status') === 'active';
    }
}
