<?php

declare(strict_types=1);

namespace App\Services\Licensing\Kslp;

use App\Models\User;
use App\Services\PlatformOwnerAccess;
use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;

/**
 * Exact owner-reviewed commercial order/product terms. This registry is
 * internal-only and does not publish a price, create checkout, confirm an
 * order, assert settlement, credit an account or issue any license.
 */
final class KslpCommercialOrderTerms
{
    public function __construct(
        private readonly PlatformOwnerAccess $ownerAccess,
        private readonly OrganizationCapabilityContext $capabilities,
    ) {}

    public function record(
        User $owner,
        string $organizationId,
        string $licensedProductId,
        string $orderId,
        string $catalogProductId,
        string $currency,
        int $amountMinor,
        string $reason,
    ): void {
        $this->ownerAccess->require($owner);
        $reason = trim($reason);
        if (! preg_match('/\A[A-Z]{3}\z/D', $currency)
            || $amountMinor < 1 || $amountMinor > 1000000000000
            || mb_strlen($reason) < 8 || mb_strlen($reason) > 240) {
            throw new DomainException('KSLP_ORDER_TERMS_INVALID');
        }
        if (! Schema::hasTable('kslp_commercial_order_terms')) {
            throw new DomainException('KSLP_ORDER_TERMS_SCHEMA_NOT_READY');
        }

        DB::transaction(function () use ($owner, $organizationId, $licensedProductId, $orderId, $catalogProductId, $currency, $amountMinor, $reason): void {
            $this->ownerAccess->require($owner);
            $order = DB::table('commerce_orders')->where('id', $orderId)
                ->where('organization_id', $organizationId)
                ->where('product_id', $catalogProductId)
                ->lockForUpdate()->first(['status']);
            $product = DB::table('kslp_licensed_products')
                ->where('id', $licensedProductId)->where('organization_id', $organizationId)
                ->where('status', 'active')->lockForUpdate()->first(['product_code']);
            $catalog = DB::table('products')->where('id', $catalogProductId)
                ->lockForUpdate()->first(['slug']);

            if ($order === null || $product === null || $catalog === null) {
                throw new DomainException('KSLP_ORDER_TERMS_SCOPE_INVALID');
            }
            if (DB::table('kslp_commercial_order_terms')->where('commercial_order_id', $orderId)->exists()) {
                throw new DomainException('KSLP_ORDER_TERMS_ALREADY_RECORDED');
            }
            // Do not retroactively fit terms to a payment or order already
            // confirmed, cancelled, or linked to a provider checkout.
            if ($order->status !== 'requested'
                || ! Schema::hasTable('commerce_provider_orders')
                || DB::table('commerce_provider_orders')->where('commercial_order_id', $orderId)->exists()) {
                throw new DomainException('KSLP_ORDER_TERMS_ORDER_ALREADY_PROCESSED');
            }

            DB::table('kslp_commercial_order_terms')->insert([
                'commercial_order_id' => $orderId,
                'issuer_organization_id' => $organizationId,
                'licensed_product_id' => $licensedProductId,
                'catalog_product_id' => $catalogProductId,
                'catalog_slug' => (string) $catalog->slug,
                'licensed_product_code' => (string) $product->product_code,
                'currency' => $currency,
                'amount_minor' => $amountMinor,
                'approved_by_user_id' => $owner->id,
                'created_at' => now(),
            ]);
            DB::table('license_audit_events')->insert([
                'actor_id' => $owner->id,
                'organization_id' => $organizationId,
                'action' => 'kslp_commercial_order_terms_recorded',
                'status' => 'success',
                'metadata' => json_encode([
                    'commercial_order_id' => $orderId,
                    'licensed_product_id' => $licensedProductId,
                    'catalog_product_id' => $catalogProductId,
                    'currency' => $currency,
                    'amount_minor' => $amountMinor,
                    'reason' => $reason,
                ], JSON_THROW_ON_ERROR),
                'created_at' => now(),
                'updated_at' => now(),
            ]);
        }, 3);
    }

    /**
     * A matching binding is not verified payment. Only a separate future
     * merchant settlement and signing authority could authorize fulfillment.
     *
     * @return array{status: string, terms_match: bool, verified_live_settlement: false, paid_issuance_enabled: false}
     */
    public function inspect(int $actorId, string $organizationId, string $licensedProductId, string $orderId): array
    {
        if ($actorId < 1 || ! $this->capabilities->allows($actorId, $organizationId, 'license.manage')) {
            throw new DomainException('KSLP_ORDER_TERMS_ACCESS_DENIED');
        }
        if (! Schema::hasTable('kslp_commercial_order_terms')) {
            return $this->result('schema_not_ready', false);
        }

        $order = DB::table('commerce_orders')->where('id', $orderId)
            ->where('organization_id', $organizationId)->first(['status', 'product_id', 'currency', 'amount_minor']);
        $product = DB::table('kslp_licensed_products')->where('id', $licensedProductId)
            ->where('organization_id', $organizationId)->first(['product_code', 'status']);
        if ($order === null || $product === null) {
            throw new DomainException('KSLP_ORDER_TERMS_SCOPE_INVALID');
        }

        $terms = DB::table('kslp_commercial_order_terms')
            ->where('commercial_order_id', $orderId)
            ->where('issuer_organization_id', $organizationId)
            ->where('licensed_product_id', $licensedProductId)
            ->first();

        if ($terms === null) {
            return $this->result('binding_missing', false);
        }

        $catalogSlug = DB::table('products')->where('id', $order->product_id)->value('slug');
        if ($product->status !== 'active'
            || $terms->licensed_product_code !== $product->product_code
            || $terms->catalog_product_id !== $order->product_id
            || $terms->catalog_slug !== $catalogSlug) {
            return $this->result('binding_mismatch', false);
        }
        if ($order->status !== 'confirmed') {
            return $this->result('order_not_confirmed', false);
        }
        if ($order->currency !== $terms->currency
            || $order->amount_minor === null
            || (int) $order->amount_minor !== (int) $terms->amount_minor
            || (int) $terms->amount_minor < 1) {
            return $this->result('amount_or_currency_mismatch', false);
        }

        return $this->result('terms_match_not_settled', true);
    }

    /** @return array{status: string, terms_match: bool, verified_live_settlement: false, paid_issuance_enabled: false} */
    private function result(string $status, bool $matches): array
    {
        return [
            'status' => $status,
            'terms_match' => $matches,
            'verified_live_settlement' => false,
            'paid_issuance_enabled' => false,
        ];
    }
}
