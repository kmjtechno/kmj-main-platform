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
        // The existing kslp_licenses.product column is varchar(64), even
        // though the product catalog can hold a longer registered code.
        // Fail before starting a DB transaction, not after issuing a license.
        if (strlen($productCode) > 64) {
            throw new DomainException('KSLP_PRODUCT_CODE_TOO_LONG');
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

            return [
                'key' => $plain,
                'license_id' => (string) $license['id'],
                'product_code' => $productCode,
            ];
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
