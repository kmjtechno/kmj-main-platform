<?php

namespace App\Services;

use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Services\ProductCatalog;
use KMJ\MainPlatform\Entitlements\Services\EntitlementIssuer;
use KMJ\MainPlatform\Entitlements\Services\EntitlementPolicyRegistry;
use KMJ\MainPlatform\Organizations\Models\Organization;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;

final class AuthorityBootstrapper
{
    public function __construct(
        private readonly OrganizationCreator $organizations,
        private readonly ProductCatalog $products,
        private readonly EntitlementPolicyRegistry $policies,
        private readonly EntitlementIssuer $entitlements,
    ) {}

    public function createOrganizationWithSandboxAccess(string $name, int $ownerUserId): Organization
    {
        return DB::transaction(function () use ($name, $ownerUserId): Organization {
            $organization = $this->organizations->create($name, $ownerUserId);

            $product = $this->products->ensureSandboxProduct(
                'kmj-main-platform-sandbox',
                'KMJ Main Platform Sandbox',
            );

            $policy = $this->policies->ensure(
                $product->getKey(),
                'main-platform.sandbox.default',
                'sandbox.product.access',
            );

            $this->entitlements->issue(
                $organization->getKey(),
                $policy,
                'organization-bootstrap:'.$organization->getKey(),
            );

            return $organization;
        });
    }
}
