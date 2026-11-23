<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use InvalidArgumentException;
use KMJ\MainPlatform\Entitlements\Models\EntitlementLedgerEntry;

/**
 * Single-Hub, narrowly-scoped automatic expiry for first-party OmniDesk trials.
 *
 * A timer is NOT an authorization oracle: signed leases and the private API
 * already refuse expired rights by their authoritative timestamps. This job
 * makes the immutable license/entitlement audit ledgers catch up, without
 * touching paid plans, renewals, signing, devices or customer payment records.
 */
final class OmniDeskAutomaticTrialExpiry
{
    /** @return array{expired:int,blocked:int,skipped:int} */
    public function expireDue(int $limit = 50): array
    {
        if ($limit < 1 || $limit > 100) {
            throw new InvalidArgumentException('OMNIDESK_EXPIRY_INVALID_LIMIT');
        }

        $ids = DB::table('kslp_licenses')
            ->where('product', OmniDeskLicenseContract::PRODUCT_ID)
            ->where('plan', 'trial')
            ->where('status', 'active')
            ->whereNotNull('trial_subject_hash')
            ->where('expires_at', '<=', now())
            ->orderBy('expires_at')
            ->limit($limit)
            ->pluck('id');

        $counts = ['expired' => 0, 'blocked' => 0, 'skipped' => 0];
        foreach ($ids as $id) {
            $result = $this->expireOne((string) $id);
            $counts[$result]++;
        }

        return $counts;
    }

    /** @return 'expired'|'blocked'|'skipped' */
    private function expireOne(string $licenseId): string
    {
        return DB::transaction(function () use ($licenseId): string {
            // Match activation, deactivation and renewal lock order: license
            // FIRST, then entitlement. Never lock an activation/binding here.
            $row = DB::table('kslp_licenses')
                ->where('id', $licenseId)
                ->lockForUpdate()
                ->first();

            if ($row === null) {
                return 'skipped';
            }

            /** @var array{status:string,product:string,plan:string,customer_id:string,expires_at:string,revoked_at:mixed,trial_subject_hash:?string,grace_until:mixed} $license */
            $license = (array) $row;
            if ($license['status'] !== 'active'
                || $license['revoked_at'] !== null
                || Carbon::parse($license['expires_at'])->isFuture()) {
                return 'skipped';
            }

            $orgId = $license['customer_id'];
            $expectedSubject = hash('sha256', 'KMJ_OMNIDESK|'.strtolower($orgId));

            // Never sweep generic KSLP trials, delegated trials or records
            // with unrecognized original issuance/expiry policy.
            if ($license['product'] !== OmniDeskLicenseContract::PRODUCT_ID
                || $license['plan'] !== 'trial'
                || ! Str::isUuid($orgId)
                || ! is_string($license['trial_subject_hash'])
                || ! hash_equals($expectedSubject, $license['trial_subject_hash'])
                || $license['grace_until'] !== null
                || ! DB::table('kslp_license_events')
                    ->where('license_id', $licenseId)
                    ->where('action', 'omnidesk_trial_auto_provisioned')
                    ->exists()) {
                return 'blocked';
            }

            $productId = DB::table('products')
                ->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)
                ->value('id');

            $entitlementRow = DB::table('entitlements')
                ->where('idempotency_key', 'omnidesk:first-trial:'.$orgId)
                ->where('organization_id', $orgId)
                ->lockForUpdate()
                ->first();

            if ($productId === null || $entitlementRow === null) {
                return 'blocked';
            }

            /** @var array{id:string,organization_id:string,product_id:string,policy_id:string,capability:string,status:string,starts_at:string,ends_at:?string} $entitlement */
            $entitlement = (array) $entitlementRow;
            $policyMatches = DB::table('entitlement_policies')
                ->where('id', $entitlement['policy_id'])
                ->where('product_id', $productId)
                ->where('code', OmniDeskAutomaticTrialProvisioner::TRIAL_POLICY)
                ->where('capability', OmniDeskLicenseContract::CAPABILITY)
                ->exists();

            if ($entitlement['organization_id'] !== $orgId
                || $entitlement['product_id'] !== (string) $productId
                || $entitlement['capability'] !== OmniDeskLicenseContract::CAPABILITY
                || $entitlement['status'] !== 'active'
                || $entitlement['ends_at'] === null
                || Carbon::parse($entitlement['ends_at'])->getTimestamp()
                    !== Carbon::parse($license['expires_at'])->getTimestamp()
                || ! $policyMatches) {
                return 'blocked';
            }

            $now = now();
            // Keep both rows and their evidence atomic. If a conflicting
            // write changes either state, rollback instead of partial expiry.
            $licenseUpdated = DB::table('kslp_licenses')
                ->where('id', $licenseId)->where('status', 'active')
                ->update([
                    'status' => 'expired',
                    'sequence' => DB::raw('sequence + 1'),
                    'updated_at' => $now,
                ]);
            $entitlementUpdated = DB::table('entitlements')
                ->where('id', $entitlement['id'])->where('status', 'active')
                ->update(['status' => 'expired', 'updated_at' => $now]);

            if ($licenseUpdated !== 1 || $entitlementUpdated !== 1) {
                throw new DomainException('OMNIDESK_TRIAL_EXPIRY_CONFLICT');
            }

            DB::table('kslp_license_events')->insert([
                'license_id' => $licenseId,
                'actor_id' => 'kmj-licensing-hub-scheduler',
                'action' => 'omnidesk_trial_auto_expired',
                'reason' => 'Trial and entitlement reached their original approved expiry',
                'correlation_id' => (string) Str::uuid(),
                'metadata' => json_encode([
                    'entitlement_id' => $entitlement['id'],
                    'original_expires_at' => $license['expires_at'],
                ], JSON_THROW_ON_ERROR),
                'created_at' => $now,
            ]);

            EntitlementLedgerEntry::query()->create([
                'entitlement_id' => $entitlement['id'],
                'organization_id' => $orgId,
                'event_type' => 'entitlement.expired',
                'payload' => [
                    'product_id' => (string) $productId,
                    'policy_id' => $entitlement['policy_id'],
                    'capability' => OmniDeskLicenseContract::CAPABILITY,
                    'status' => 'expired',
                    'license_id' => $licenseId,
                ],
                'occurred_at' => $now,
            ]);

            return 'expired';
        }, 3);
    }
}
