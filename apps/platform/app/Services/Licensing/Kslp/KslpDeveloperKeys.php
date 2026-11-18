<?php

declare(strict_types=1);

namespace App\Services\Licensing\Kslp;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * Opaque bootstrap key, not a signed lease. Only a verified KSLP activation
 * may exchange it for an activation ID; it never authorizes offline use.
 */
final class KslpDeveloperKeys
{
    /**
     * @return array{key: string, license_id: string, product_code: string}
     */
    public function issue(
        string $organizationId,
        string $productCode,
        string $customerId,
        string $plan,
        string $actor,
    ): array {
        // A developer issuer subscription is NOT proof of an end-customer
        // payment. Until verified order/entitlement fulfillment is integrated,
        // this self-service surface must never mint a paid commercial plan.
        if ($plan !== 'trial') {
            throw new DomainException('KSLP_PAID_ENTITLEMENT_REQUIRED');
        }

        return DB::transaction(function () use ($organizationId, $productCode, $customerId, $plan, $actor): array {
            $product = app(KslpIssuerSubscriptionAuthority::class)
                ->authorizeIssue($organizationId, $productCode);

            // Delegated issuer quotas, product limits and plan validation are
            // checked by the existing KSLP commercial control plane.
            $license = app(KslpLicenseControlPlane::class)->issueDelegated(
                $organizationId, $customerId, $productCode, $plan, $actor,
                'Developer application license key issued',
            );

            $plain = 'KMJ1-'.rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '=');
            DB::table('kslp_license_keys')->insert([
                'id' => (string) Str::uuid(),
                'organization_id' => $organizationId,
                'licensed_product_id' => $product['id'],
                'license_id' => $license['id'],
                'key_digest' => hash('sha256', $plain),
                'display_prefix' => substr($plain, 0, 12),
                'created_at' => now(),
                'updated_at' => now(),
            ]);

            return ['key' => $plain, 'license_id' => (string) $license['id'], 'product_code' => $productCode];
        }, 3);
    }

    /**
     * Issue a bounded, all-or-nothing batch of TRIAL bootstrap keys only.
     *
     * One transaction wraps all delegated authority, quota, duplicate-trial
     * checks and insertions. If customer #N is invalid, none of the N keys,
     * licenses or audit events are committed. The returned plaintext secrets
     * are flashed once by the authenticated controller and never stored here.
     *
     * @param list<string> $customerIds
     * @return list<array{customer_id: string, key: string, license_id: string, product_code: string}>
     */
    public function issueTrialBatch(
        string $organizationId,
        string $productCode,
        array $customerIds,
        string $actor,
    ): array {
        if (count($customerIds) < 2 || count($customerIds) > 10) {
            throw new DomainException('KSLP_TRIAL_BATCH_SIZE_INVALID');
        }

        $seen = [];
        foreach ($customerIds as $customerId) {
            if (! is_string($customerId)
                || preg_match('/\A[A-Za-z0-9._:@-]{3,128}\z/D', $customerId) !== 1
                || isset($seen[$customerId])) {
                throw new DomainException('KSLP_TRIAL_BATCH_CUSTOMER_INVALID');
            }
            $seen[$customerId] = true;
        }

        return DB::transaction(function () use (
            $organizationId, $productCode, $customerIds, $actor,
        ): array {
            $results = [];
            foreach ($customerIds as $customerId) {
                $issued = $this->issue(
                    $organizationId, $productCode, $customerId, 'trial', $actor,
                );
                $results[] = [
                    'customer_id' => $customerId,
                    'key' => $issued['key'],
                    'license_id' => $issued['license_id'],
                    'product_code' => $issued['product_code'],
                ];
            }

            // Individual delegated issue events already record license IDs,
            // actor and product. This aggregate audit contains NO keys, raw
            // customer identifiers, device identities or private-key data.
            $now = now();
            DB::table('license_audit_events')->insert([
                'actor_id' => ctype_digit($actor) ? (int) $actor : null,
                'organization_id' => $organizationId,
                'action' => 'kslp_trial_batch_issued',
                'status' => 'success',
                'metadata' => json_encode([
                    'product_code' => $productCode,
                    'count' => count($results),
                ], JSON_THROW_ON_ERROR),
                'created_at' => $now,
                'updated_at' => $now,
            ]);

            return $results;
        }, 3);
    }

    /**
     * Authenticate a random 256-bit bootstrap key, never a client self-issued
     * entitlement. The key is accepted only while issuer/product/license
     * authority is still active. Callers must also prove device key possession.
     *
     * @return array{license_id: string, product_code: string, organization_id: string}
     */
    public function resolve(string $plain): array
    {
        if (! preg_match('/^KMJ1-[A-Za-z0-9_-]{43}$/D', $plain)) {
            throw new DomainException('KSLP_LICENSE_KEY_INVALID');
        }

        $record = DB::table('kslp_license_keys as k')
            ->join('kslp_licenses as l', 'l.id', '=', 'k.license_id')
            ->join('kslp_licensed_products as p', 'p.id', '=', 'k.licensed_product_id')
            ->join('kslp_issuer_subscriptions as s', 's.organization_id', '=', 'k.organization_id')
            ->where('k.key_digest', hash('sha256', $plain))
            ->whereNull('k.revoked_at')
            ->whereNull('l.revoked_at')
            ->where('l.status', 'active')
            ->where('l.starts_at', '<=', now())
            ->where('l.expires_at', '>', now())
            ->whereColumn('p.organization_id', 'k.organization_id')
            ->where('p.status', 'active')
            ->where('s.status', 'active')
            ->where(function ($q): void {
                $q->whereNull('s.current_period_end')->orWhere('s.current_period_end', '>', now());
            })
            ->first([
                'k.license_id', 'k.organization_id', 'p.product_code',
                'l.product as license_product', 'l.issuer_organization_id',
            ]);

        if ($record === null
            || $record->product_code !== $record->license_product
            || $record->organization_id !== $record->issuer_organization_id) {
            throw new DomainException('KSLP_LICENSE_KEY_INVALID');
        }

        return [
            'license_id' => (string) $record->license_id,
            'product_code' => (string) $record->product_code,
            'organization_id' => (string) $record->organization_id,
        ];
    }
}
