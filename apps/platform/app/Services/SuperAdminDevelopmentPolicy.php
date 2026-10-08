<?php

declare(strict_types=1);

namespace App\Services;

use App\Models\User;
use Illuminate\Support\Facades\DB;

/**
 * First-party product-control profile, not a fabricated license or quota.
 *
 * Only a previously provisioned, email-verified Platform Owner with a
 * registered passkey may inspect this cross-product development profile.
 * Read/execute permissions, real signed licensing, costs and per-device
 * worker ceilings are always enforced by their respective services.
 */
final class SuperAdminDevelopmentPolicy
{
    public function __construct(
        private readonly PlatformOwnerAccess $ownerAccess,
    ) {}

    /** @return array<string,mixed> */
    public function describe(User $user): array
    {
        $this->ownerAccess->require($user);

        $products = DB::table('products')
            ->where('slug', 'like', 'kmj-%')
            ->orderBy('slug')
            ->pluck('slug')
            ->filter(fn (mixed $slug): bool => is_string($slug)
                && preg_match('/^kmj-[a-z0-9-]+$/D', $slug) === 1)
            ->values()
            ->all();

        return [
            'profile' => 'kmj.super-admin.hyperspeed',
            'status' => 'management-profile-only',
            'subject' => [
                'user_id' => (string) $user->getKey(),
                'email' => (string) $user->email,
                'email_verified' => true,
                'platform_owner_verified' => true,
                'passkey_required' => true,
            ],
            'scope' => [
                'kind' => 'kmj-first-party-products',
                'registered_product_slugs' => $products,
                'logical_task_backlog' => 'unmetered',
                'operator_management' => true,
            ],
            'execution' => [
                'max_parallel_jobs' => 'signed-entitlement-and-current-resources',
                'cross_device_scaling' => 'each-device-authorized-separately',
                'agent_workers' => 'bounded-by-licensed-capacity-and-provider-quota',
                'production_signing_required' => true,
                'audit_required' => true,
            ],
            'cost' => [
                'automatic_paid_fallback_enabled' => false,
                'unapproved_spend_inr_minor' => 0,
                'requires_separate_budget_approval' => true,
            ],
            'grants_product_license' => false,
            'changes_entitlements' => false,
            'changes_user_role' => false,
        ];
    }
}
