<?php

declare(strict_types=1);

namespace App\Services\Licensing\Kslp;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;

/**
 * Source-only, read-only diagnostics for a FUTURE reseller funding program.
 *
 * No order confirmation, merchant API call, settlement assertion, credit
 * balance, entitlement, license or signer is produced here. Reconciled sandbox
 * webhooks are explicitly not evidence of live merchant settlement.
 */
final class KslpResellerSettlementReadinessInspector
{
    public function __construct(private readonly OrganizationCapabilityContext $capabilities) {}

    /**
     * @return array{
     *     status: string,
     *     blocked_reasons: list<string>,
     *     linked_provider_orders: int,
     *     reconciled_webhook_receipts: int,
     *     reversal_signals: int,
     *     verified_live_settlement: false,
     *     available_credits: null,
     *     paid_issuance_enabled: false
     * }
     */
    public function inspect(
        int $actorId,
        string $issuerOrganizationId,
        string $licensedProductId,
        string $commercialOrderId,
    ): array {
        if ($actorId < 1 || ! $this->capabilities->allows(
            $actorId, $issuerOrganizationId, 'license.manage'
        )) {
            throw new DomainException('KSLP_RESELLER_FUNDING_ACCESS_DENIED');
        }

        $reasons = [
            'RESELLER_DELEGATED_GRANT_MISSING',
            'PRODUCT_ORDER_SKU_MAPPING_UNVERIFIED',
            'LIVE_MERCHANT_SETTLEMENT_UNVERIFIED',
            'REFUND_CHARGEBACK_LIFECYCLE_NOT_READY',
            'PAID_LICENSE_SIGNING_NOT_APPROVED',
        ];
        foreach (['kslp_licensed_products', 'commerce_orders', 'commerce_provider_orders', 'payment_webhook_events'] as $table) {
            if (! Schema::hasTable($table)) {
                $reasons[] = 'SOURCE_SCHEMA_NOT_READY';

                return $this->blocked($reasons, 0, 0, 0);
            }
        }

        $product = DB::table('kslp_licensed_products')
            ->where('organization_id', $issuerOrganizationId)
            ->where('id', $licensedProductId)
            ->first(['id']);

        $order = DB::table('commerce_orders')
            ->where('organization_id', $issuerOrganizationId)
            ->where('id', $commercialOrderId)
            ->first(['status', 'currency', 'amount_minor', 'confirmation_reference']);

        // Do not reveal whether a foreign organization's order or licensed
        // product exists. Never query external events before scope validation.
        if ($product === null || $order === null) {
            throw new DomainException('KSLP_RESELLER_FUNDING_SCOPE_DENIED');
        }

        $commercial = (array) $order;
        if (($commercial['status'] ?? null) !== 'confirmed') {
            $reasons[] = 'COMMERCIAL_ORDER_NOT_CONFIRMED';
        }
        if (! is_int($commercial['amount_minor'] ?? null)
            && ! ctype_digit((string) ($commercial['amount_minor'] ?? ''))) {
            $reasons[] = 'ORDER_PRICE_NOT_RECORDED';
        } elseif ((int) $commercial['amount_minor'] < 1) {
            $reasons[] = 'ORDER_PRICE_NOT_RECORDED';
        }
        if (! preg_match('/\A[A-Z]{3}\z/D', (string) ($commercial['currency'] ?? ''))) {
            $reasons[] = 'ORDER_CURRENCY_NOT_RECORDED';
        }

        // Limit the preview: a large or ambiguous set of links must fail
        // closed, not allow a best-looking provider to be cherry-picked.
        $links = DB::table('commerce_provider_orders')
            ->where('commercial_order_id', $commercialOrderId)
            ->limit(6)
            ->get(['provider', 'provider_order_id', 'amount_minor', 'currency', 'environment']);

        $linkCount = $links->count();
        if ($linkCount === 0) {
            $reasons[] = 'TRUSTED_PROVIDER_ORDER_LINK_MISSING';
        }
        if ($linkCount > 1) {
            $reasons[] = 'MULTIPLE_PROVIDER_LINKS_REQUIRE_REVIEW';
        }
        if ($linkCount > 5) {
            $reasons[] = 'PROVIDER_LINK_PREVIEW_TRUNCATED';
        }

        $reconciled = 0;
        $reversals = 0;
        foreach ($links as $link) {
            $provider = (array) $link;
            if (($provider['environment'] ?? null) !== 'live') {
                $reasons[] = 'PROVIDER_NOT_LIVE';
            }
            if ((int) ($provider['amount_minor'] ?? 0) !== (int) ($commercial['amount_minor'] ?? 0)
                || ($provider['currency'] ?? null) !== ($commercial['currency'] ?? null)) {
                $reasons[] = 'PROVIDER_LINK_FINANCIAL_MISMATCH';
            }
            $providerName = (string) ($provider['provider'] ?? '');
            $providerOrderId = (string) ($provider['provider_order_id'] ?? '');
            if ($providerName === '' || $providerOrderId === '') {
                $reasons[] = 'PROVIDER_REFERENCE_MISSING';

                continue;
            }

            // A webhook inbox records only signed notifications and processor
            // status, not durable independent net settlement or reversal
            // reconciliation. Even a 'reconciled' receipt never funds credits.
            $events = DB::table('payment_webhook_events')
                ->where('provider', $providerName)
                ->where('provider_order_id', $providerOrderId)
                ->limit(101)
                ->get(['processing_status', 'event_type']);
            if ($events->count() > 100) {
                $reasons[] = 'WEBHOOK_PREVIEW_TRUNCATED';
            }
            foreach ($events as $event) {
                $receipt = (array) $event;
                if (($receipt['processing_status'] ?? null) === 'reconciled') {
                    $reconciled++;
                }
                $type = strtolower((string) ($receipt['event_type'] ?? ''));
                if (str_contains($type, 'refund')
                    || str_contains($type, 'dispute')
                    || str_contains($type, 'chargeback')) {
                    $reversals++;
                }
            }
        }
        if ($reconciled === 0) {
            $reasons[] = 'RECONCILED_PROVIDER_RECEIPT_MISSING';
        }
        if ($reversals > 0) {
            $reasons[] = 'PAYMENT_REVERSAL_SIGNAL_PRESENT';
        }

        return $this->blocked($reasons, $linkCount, $reconciled, $reversals);
    }

    /**
     * @param  list<string>  $reasons
     * @return array{status: string, blocked_reasons: list<string>, linked_provider_orders: int, reconciled_webhook_receipts: int, reversal_signals: int, verified_live_settlement: false, available_credits: null, paid_issuance_enabled: false}
     */
    private function blocked(array $reasons, int $linked, int $reconciled, int $reversals): array
    {
        return [
            'status' => 'blocked_source_review_only',
            'blocked_reasons' => array_values(array_unique($reasons)),
            'linked_provider_orders' => $linked,
            'reconciled_webhook_receipts' => $reconciled,
            'reversal_signals' => $reversals,
            'verified_live_settlement' => false,
            'available_credits' => null,
            'paid_issuance_enabled' => false,
        ];
    }
}
