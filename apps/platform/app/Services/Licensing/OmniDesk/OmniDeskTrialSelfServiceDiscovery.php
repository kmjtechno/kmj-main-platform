<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use App\Models\User;
use App\Services\Licensing\OmniDeskLicenseContract;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

/**
 * Read-only first-party trial action availability for the existing customer Hub.
 * Never infer authorization from an item rendered in the browser: the POST
 * separately rechecks all facts inside OmniDeskAutomaticTrialProvisioner.
 */
final class OmniDeskTrialSelfServiceDiscovery
{
    public function __construct(
        private readonly OrganizationDirectory $directory,
        private readonly OrganizationCapabilityContext $capabilities,
    ) {}

    /** @return list<array{organization_id:string,organization_name:string,trial_days:int}> */
    public function forUser(User $user): array
    {
        if (config('omnidesk-licensing.trial_self_service_enabled', false) !== true
            || ! $user->exists || ! $user->hasVerifiedEmail()) {
            return [];
        }

        $product = Product::query()
            ->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)
            ->where('status', 'active')
            ->where('licensing_enabled', true)
            ->where('is_public', true)
            ->whereIn('lifecycle', ['available', 'public-beta'])
            ->first();
        if (! $product instanceof Product) {
            return [];
        }
        $plan = Plan::query()
            ->where('product_id', $product->getKey())
            ->where('code', OmniDeskAutomaticTrialProvisioner::TRIAL_PLAN)
            ->where('status', 'active')
            ->where('pricing_model', 'trial')
            ->whereNull('amount_minor')
            ->first();
        $days = $plan instanceof Plan ? (int) $plan->getAttribute('trial_days') : 0;
        if ($days < 1 || $days > 30
            || ! EntitlementPolicy::query()
                ->where('product_id', $product->getKey())
                ->where('code', OmniDeskAutomaticTrialProvisioner::TRIAL_POLICY)
                ->where('capability', OmniDeskLicenseContract::CAPABILITY)
                ->where('status', 'active')
                ->exists()) {
            return [];
        }

        $userId = (int) $user->getKey();
        $eligibleMemberships = OrganizationMembership::query()
            ->where('user_id', $userId)
            ->whereIn('role', ['owner', 'admin'])
            ->limit(50)
            ->pluck('organization_id')
            ->map(static fn (mixed $id): string => (string) $id)
            ->all();

        $items = [];
        foreach ($this->directory->forUser($userId) as $organization) {
            $organizationId = (string) $organization['id'];
            if (! in_array($organizationId, $eligibleMemberships, true)
                || ! $this->capabilities->allows($userId, $organizationId, 'license.manage')
                || DB::table('kslp_licenses')->where(
                    'trial_subject_hash',
                    hash('sha256', 'KMJ_OMNIDESK|'.strtolower($organizationId)),
                )->exists()) {
                continue;
            }

            $items[] = [
                'organization_id' => $organizationId,
                'organization_name' => (string) $organization['name'],
                'trial_days' => $days,
            ];
        }

        return $items;
    }
}
