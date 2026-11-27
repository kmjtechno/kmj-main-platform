<?php

declare(strict_types=1);

namespace App\Services\Commerce;

use App\Models\User;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use App\Services\PlatformOwnerAccess;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Entitlements\Services\EntitlementIssuer;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;

/**
 * Records the product a customer signed up for. The owner approved one
 * automatic grant (27 Nov 2026): a CloudOS trial once the email is verified.
 * Every other product stays "waiting" (pre-registered) with no access.
 */
final class ProductSignups
{
    public const WAITING = 'waiting';

    public const TRIAL_STARTED = 'trial_started';

    public const ALREADY_LICENSED = 'already_licensed';

    public function __construct(
        private readonly PublicProductCatalog $products,
        private readonly KslpLicenseControlPlane $licenses,
        private readonly EntitlementIssuer $entitlements,
        private readonly PlatformOwnerAccess $owners,
    ) {}

    /** False until the migration has run, so a release never breaks pages. */
    public function available(): bool
    {
        return Schema::hasTable('product_signups');
    }

    /** @return array<string, string> product slug => state */
    public function forUser(int $userId): array
    {
        if (! $this->available()) {
            return [];
        }

        return DB::table('product_signups')
            ->where('user_id', $userId)
            ->pluck('state', 'product_slug')
            ->all();
    }

    /** Returns false when the product is not a public product. */
    public function record(User $user, string $slug): bool
    {
        if (! $this->available() || $this->products->find($slug) === null) {
            return false;
        }

        DB::table('product_signups')->insertOrIgnore([
            'user_id' => $user->getKey(),
            'product_slug' => $slug,
            'state' => self::WAITING,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $this->fulfil($user);

        return true;
    }

    /** Safe to call repeatedly: starts the CloudOS trial at most once. */
    public function fulfil(User $user): void
    {
        if (! $this->available()
            || ! config('services.kmj_signup_trial.enabled')
            || ! $user->hasVerifiedEmail()
            || $this->owners->allows($user)) {
            return;
        }

        DB::transaction(function () use ($user): void {
            // Serialize double clicks and parallel verification requests.
            User::query()->whereKey($user->getKey())->lockForUpdate()->first();

            $signup = DB::table('product_signups')
                ->where('user_id', $user->getKey())
                ->where('product_slug', CloudOSProductCatalog::SLUG)
                ->where('state', self::WAITING)
                ->first();

            if ($signup === null) {
                return;
            }

            $state = $this->startCloudOsTrial($user);

            if ($state !== null) {
                DB::table('product_signups')
                    ->where('id', $signup->id)
                    ->update(['state' => $state, 'updated_at' => now()]);
            }
        });
    }

    /** Null means "not possible yet": the signup keeps waiting. */
    private function startCloudOsTrial(User $user): ?string
    {
        $product = $this->products->find(CloudOSProductCatalog::SLUG);
        $policy = EntitlementPolicy::query()
            ->where('code', CloudOSProductCatalog::POLICY_CODE)
            ->where('status', 'active')
            ->first();
        $memberships = OrganizationMembership::query()
            ->where('user_id', $user->getKey())
            ->orderBy('created_at')
            ->get();
        $owned = $memberships->firstWhere('role', 'owner');

        if (($product['purchase_enabled'] ?? false) !== true
            || ! $policy instanceof EntitlementPolicy
            || $owned === null) {
            return null;
        }

        $userId = (string) $user->getKey();
        $customerIds = [$userId, ...$memberships->pluck('organization_id')->map(fn ($id): string => (string) $id)->all()];

        if (DB::table('kslp_licenses')
            ->where('product', 'KMJ_CLOUDOS')
            ->whereIn('customer_id', $customerIds)
            ->exists()) {
            return self::ALREADY_LICENSED;
        }

        $license = $this->licenses->issue($userId, 'trial', 'self-service-signup', 'Owner-approved signup trial');
        $organizationId = (string) $owned->getAttribute('organization_id');

        $hasAccess = Entitlement::query()
            ->where('organization_id', $organizationId)
            ->where('product_id', $policy->getAttribute('product_id'))
            ->where('status', 'active')
            ->where(function ($query): void {
                $query->whereNull('ends_at')->orWhere('ends_at', '>', now());
            })
            ->exists();

        if (! $hasAccess) {
            // Product access ends exactly when the trial license expires.
            $this->entitlements->issue(
                $organizationId,
                $policy,
                'cloudos-signup-trial:'.$userId,
                new \DateTimeImmutable((string) $license['expires_at']),
            );
        }

        return self::TRIAL_STARTED;
    }
}
