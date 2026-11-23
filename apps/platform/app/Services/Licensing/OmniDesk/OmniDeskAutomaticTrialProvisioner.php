<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use App\Models\User;
use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Entitlements\Services\EntitlementIssuer;
use KMJ\MainPlatform\Organizations\Models\Organization;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;

/**
 * One-Hub, self-service first-party OmniDesk trial ledger provisioning.
 *
 * No signed device lease is produced: an independently authorized device
 * activation and real protected OmniDeskSigner are still mandatory.
 * Only an already APPROVED, enabled product, trial plan and entitlement policy
 * can become a trial; unconfigured pre-alpha catalog never grants rights.
 */
final class OmniDeskAutomaticTrialProvisioner
{
    public const TRIAL_PLAN = 'omnidesk.trial';

    public const TRIAL_POLICY = 'omnidesk.trial.remote_access';

    public function __construct(private readonly EntitlementIssuer $entitlements) {}

    /**
     * Provision at most one organization trial, idempotent across client retry,
     * job retry, process crashes and concurrent same-organization requests.
     *
     * @return array{license_id:string,entitlement_id:string,expires_at:string,status:string,already_exists:bool}
     */
    public function provision(User $actor, string $organizationId): array
    {
        if (! Str::isUuid($organizationId) || ! $actor->exists || $actor->getKey() === null) {
            throw new DomainException('OMNIDESK_TRIAL_FORBIDDEN');
        }

        return DB::transaction(function () use ($actor, $organizationId): array {
            $account = User::query()->whereKey($actor->getKey())->first();
            if (! $account instanceof User || ! $account->hasVerifiedEmail()) {
                throw new DomainException('OMNIDESK_TRIAL_FORBIDDEN');
            }

            // Serialize all trial requests per organization before touching
            // the entitlement or unique trial-subject ledger.
            $organization = Organization::query()->whereKey($organizationId)->lockForUpdate()->first();
            if ($organization === null) {
                throw new DomainException('OMNIDESK_TRIAL_FORBIDDEN');
            }
            $membership = OrganizationMembership::query()
                ->where('organization_id', $organizationId)
                ->where('user_id', $account->getKey())
                ->lockForUpdate()
                ->first();
            if ($membership === null || ! in_array($membership->getAttribute('role'), ['owner', 'admin'], true)) {
                throw new DomainException('OMNIDESK_TRIAL_FORBIDDEN');
            }

            $fingerprint = hash('sha256', 'KMJ_OMNIDESK|'.strtolower($organizationId));
            $previous = DB::table('kslp_licenses')
                ->where('trial_subject_hash', $fingerprint)
                ->lockForUpdate()
                ->first();
            $idempotencyKey = 'omnidesk:first-trial:'.$organizationId;

            if ($previous !== null) {
                if ((string) $previous->customer_id !== $organizationId
                    || (string) $previous->product !== OmniDeskLicenseContract::PRODUCT_ID
                    || (string) $previous->plan !== 'trial') {
                    throw new DomainException('OMNIDESK_TRIAL_CONFLICT');
                }
                $entitlement = DB::table('entitlements')
                    ->where('idempotency_key', $idempotencyKey)
                    ->where('organization_id', $organizationId)
                    ->first();
                if ($entitlement === null) {
                    throw new DomainException('OMNIDESK_TRIAL_CONFLICT');
                }

                return [
                    'license_id' => (string) $previous->id,
                    'entitlement_id' => (string) $entitlement->id,
                    'expires_at' => (string) $previous->expires_at,
                    // A revoked/expired trial cannot be refreshed or
                    // reissued merely by calling this endpoint again.
                    'status' => $this->isActive($previous, $entitlement) ? 'active' : 'restricted',
                    'already_exists' => true,
                ];
            }

            $product = Product::query()
                ->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)
                ->lockForUpdate()
                ->first();
            if ($product === null || $product->getAttribute('status') !== 'active'
                || ! $product->getAttribute('licensing_enabled')
                || ! $product->getAttribute('is_public')
                || ! in_array($product->getAttribute('lifecycle'), ['available', 'public-beta'], true)) {
                throw new DomainException('OMNIDESK_TRIAL_NOT_ENABLED');
            }

            $plan = Plan::query()
                ->where('product_id', $product->getKey())
                ->where('code', self::TRIAL_PLAN)
                ->lockForUpdate()
                ->first();
            if ($plan === null || $plan->getAttribute('status') !== 'active'
                || $plan->getAttribute('pricing_model') !== 'trial'
                || $plan->getAttribute('amount_minor') !== null
                || (int) $plan->getAttribute('trial_days') < 1 || (int) $plan->getAttribute('trial_days') > 30) {
                throw new DomainException('OMNIDESK_TRIAL_NOT_ENABLED');
            }

            $policy = EntitlementPolicy::query()
                ->where('code', self::TRIAL_POLICY)
                ->where('product_id', $product->getKey())
                ->where('capability', OmniDeskLicenseContract::CAPABILITY)
                ->where('status', 'active')
                ->lockForUpdate()
                ->first();
            if ($policy === null) {
                throw new DomainException('OMNIDESK_TRIAL_NOT_ENABLED');
            }

            $now = now();
            $endsAt = $now->copy()->addDays((int) $plan->getAttribute('trial_days'));
            $entitlement = $this->entitlements->issue($organizationId, $policy, $idempotencyKey);
            if ($entitlement->getAttribute('status') !== 'active'
                || $entitlement->getAttribute('ends_at') !== null
                || $entitlement->getAttribute('organization_id') !== $organizationId) {
                throw new DomainException('OMNIDESK_TRIAL_CONFLICT');
            }
            $entitlement->forceFill(['starts_at' => $now, 'ends_at' => $endsAt])->save();

            $licenseId = (string) Str::uuid();
            DB::table('kslp_licenses')->insert([
                'id' => $licenseId,
                'customer_id' => $organizationId,
                'product' => OmniDeskLicenseContract::PRODUCT_ID,
                'plan' => 'trial',
                'status' => 'active',
                'trial_subject_hash' => $fingerprint,
                'sequence' => 1,
                'starts_at' => $now,
                'expires_at' => $endsAt,
                'grace_until' => null,
                'revoked_at' => null,
                'created_at' => $now,
                'updated_at' => $now,
            ]);
            DB::table('kslp_license_events')->insert([
                'license_id' => $licenseId,
                'actor_id' => (string) $account->getKey(),
                'action' => 'omnidesk_trial_auto_provisioned',
                'reason' => 'Verified first-party self-service one-time trial',
                'correlation_id' => (string) Str::uuid(),
                'metadata' => json_encode([
                    'entitlement_id' => (string) $entitlement->getKey(),
                    'trial_days' => (int) $plan->getAttribute('trial_days'),
                ], JSON_THROW_ON_ERROR),
                'created_at' => $now,
            ]);

            return [
                'license_id' => $licenseId,
                'entitlement_id' => (string) $entitlement->getKey(),
                'expires_at' => $endsAt->toDateTimeString(),
                'status' => 'active',
                'already_exists' => false,
            ];
        }, 3);
    }

    private function isActive(object $license, object $entitlement): bool
    {
        /** @var array{status:string,revoked_at:mixed,starts_at:string,expires_at:string} $licenseFields */
        $licenseFields = (array) $license;
        /** @var array{status:string,starts_at:string,ends_at:?string} $entitlementFields */
        $entitlementFields = (array) $entitlement;

        return $licenseFields['status'] === 'active'
            && $licenseFields['revoked_at'] === null
            && now()->gte($licenseFields['starts_at'])
            && now()->lt($licenseFields['expires_at'])
            && $entitlementFields['status'] === 'active'
            && now()->gte($entitlementFields['starts_at'])
            && ($entitlementFields['ends_at'] === null
                || now()->lt($entitlementFields['ends_at']));
    }
}
