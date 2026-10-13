<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use App\Models\User;
use KMJ\MainPlatform\Entitlements\Services\EntitlementReader;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

/** Same access rule as the CodeBridge dashboard: an active kmj-codebridge entitlement. */
final class DashboardAiProviderScope implements ResolvesAiProviderScope
{
    public function __construct(
        private readonly OrganizationDirectory $organizations,
        private readonly EntitlementReader $entitlements,
    ) {}

    public function for(User $user): array
    {
        foreach ($this->organizations->forUser((int) $user->id) as $organization) {
            foreach ($this->entitlements->forOrganization($organization['id']) as $entitlement) {
                if ($entitlement['product_slug'] === 'kmj-codebridge' && $entitlement['status'] === 'active') {
                    return [
                        'organization_id' => $organization['id'],
                        'can_manage' => $this->organizations->userCanManage((int) $user->id, $organization['id']),
                    ];
                }
            }
        }

        abort(404);
    }
}
