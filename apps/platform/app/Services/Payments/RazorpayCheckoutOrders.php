<?php

declare(strict_types=1);

namespace App\Services\Payments;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use InvalidArgumentException;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;

/**
 * Opens one SANDBOX provider order for a requested commercial order.
 *
 * Reserve the intent in a committed transaction BEFORE outbound HTTP, so a
 * provider-success/DB-failure cannot silently issue a second order on retry.
 * An incomplete intent is fail-closed and requires operator reconciliation.
 * No charge, entitlement or license is created by this service.
 */
final class RazorpayCheckoutOrders
{
    public function __construct(
        private readonly OwnerPaymentGatewaySettings $settings,
        private readonly RazorpaySandboxOrderClient $client,
    ) {}

    /**
     * @return array{provider_order_id: string, amount_minor: int, currency: string}
     */
    public function open(string $commercialOrderId, int $expectedAmountMinor): array
    {
        return $this->openInternal($commercialOrderId, $expectedAmountMinor, null);
    }

    /**
     * Internal KSLP sandbox checkout entry point. The caller supplies the
     * licensed product scope, never a merchant-approved settlement claim.
     *
     * @return array{provider_order_id: string, amount_minor: int, currency: string}
     */
    public function openReviewed(string $commercialOrderId, string $licensedProductId, int $expectedAmountMinor): array
    {
        if ($licensedProductId === '') {
            throw new DomainException('RAZORPAY_REVIEWED_TERMS_REQUIRED');
        }

        return $this->openInternal($commercialOrderId, $expectedAmountMinor, $licensedProductId);
    }

    /** @return array{provider_order_id: string, amount_minor: int, currency: string} */
    private function openInternal(string $commercialOrderId, int $expectedAmountMinor, ?string $licensedProductId): array
    {
        if ($expectedAmountMinor < 100 || $expectedAmountMinor > 100000000) {
            throw new InvalidArgumentException('RAZORPAY_EXPECTED_AMOUNT_INVALID');
        }

        // Only the reservation needs a DB lock. Never hold it while waiting
        // on an external payment provider's network response.
        $decision = DB::transaction(function () use ($commercialOrderId, $expectedAmountMinor, $licensedProductId): array {
            $order = CommercialOrder::query()->whereKey($commercialOrderId)->lockForUpdate()->firstOrFail();
            if ((string) $order->getAttribute('status') !== 'requested') {
                throw new DomainException('RAZORPAY_ORDER_NOT_OPENABLE');
            }

            $this->assertReviewedTerms($order, $expectedAmountMinor, $licensedProductId);

            $existing = DB::table('commerce_provider_orders')
                ->where('commercial_order_id', $commercialOrderId)->where('provider', 'razorpay')->first();
            if ($existing !== null) {
                if ((int) $existing->amount_minor !== $expectedAmountMinor) {
                    throw new DomainException('RAZORPAY_ORDER_AMOUNT_CONFLICT');
                }

                // This is a sandbox-only entry point. An old or manually
                // reconciled LIVE/foreign-currency link must never be handed
                // back to a sandbox checkout as an apparently valid order.
                if ((string) $existing->environment !== 'sandbox') {
                    throw new DomainException('RAZORPAY_ORDER_ENVIRONMENT_CONFLICT');
                }
                if ((string) $existing->currency !== 'INR') {
                    throw new DomainException('RAZORPAY_ORDER_CURRENCY_CONFLICT');
                }

                return ['linked' => $this->shape((string) $existing->provider_order_id, (int) $existing->amount_minor, (string) $existing->currency), 'credentials' => null];
            }

            $intent = DB::table('commerce_provider_order_intents')
                ->where('commercial_order_id', $commercialOrderId)->where('provider', 'razorpay')->first();
            if ($intent !== null) {
                if ((int) $intent->amount_minor !== $expectedAmountMinor) {
                    throw new DomainException('RAZORPAY_ORDER_AMOUNT_CONFLICT');
                }

                // A previous external call may have succeeded even if PHP
                // timed out or the subsequent DB link insert failed. Do not
                // call create again without provider-side reconciliation.
                throw new DomainException('RAZORPAY_ORDER_CREATION_PENDING_REVIEW');
            }

            try {
                $credentials = $this->settings->sandboxCredentials('razorpay');
            } catch (InvalidArgumentException) {
                throw new DomainException('RAZORPAY_SANDBOX_CREDENTIALS_NOT_READY');
            }

            DB::table('commerce_provider_order_intents')->insert([
                'commercial_order_id' => $order->getKey(),
                'provider' => 'razorpay',
                'amount_minor' => $expectedAmountMinor,
                'currency' => 'INR',
                'creation_status' => 'creating',
                'created_at' => now(),
                'updated_at' => now(),
            ]);

            return ['linked' => null, 'credentials' => $credentials];
        });

        if ($decision['linked'] !== null) {
            return $decision['linked'];
        }

        $credentials = $decision['credentials'];

        // The reservation has committed and is now durable. On network
        // timeout or DB failure, leave it unresolved; retry must NOT create
        // another provider order from an uncertain remote outcome.
        $created = $this->client->create(
            $commercialOrderId,
            $expectedAmountMinor,
            'INR',
            $credentials['client_id'],
            $credentials['client_secret'],
        );

        return DB::transaction(function () use ($commercialOrderId, $expectedAmountMinor, $created, $licensedProductId): array {
            $order = CommercialOrder::query()->whereKey($commercialOrderId)->lockForUpdate()->firstOrFail();
            if ((string) $order->getAttribute('status') !== 'requested') {
                throw new DomainException('RAZORPAY_ORDER_NOT_OPENABLE');
            }

            $this->assertReviewedTerms($order, $expectedAmountMinor, $licensedProductId);

            $intent = DB::table('commerce_provider_order_intents')
                ->where('commercial_order_id', $commercialOrderId)->where('provider', 'razorpay')->first();
            if ($intent === null || $intent->creation_status !== 'creating'
                || (int) $intent->amount_minor !== $expectedAmountMinor || $intent->currency !== 'INR') {
                throw new DomainException('RAZORPAY_ORDER_INTENT_MISMATCH');
            }

            DB::table('commerce_provider_orders')->insert([
                'commercial_order_id' => $order->getKey(),
                'provider' => 'razorpay',
                'provider_order_id' => $created['order_id'],
                'amount_minor' => $created['amount_minor'],
                'currency' => $created['currency'],
                'environment' => 'sandbox',
                'created_at' => now(),
                'updated_at' => now(),
            ]);

            DB::table('commerce_provider_order_intents')
                ->where('commercial_order_id', $commercialOrderId)->where('provider', 'razorpay')
                ->where('creation_status', 'creating')
                ->update(['creation_status' => 'linked', 'updated_at' => now()]);

            return $this->shape($created['order_id'], $created['amount_minor'], $created['currency']);
        });
    }

    /**
     * Called only while holding the commercial-order lock, before reserving
     * provider creation and again before linking the response. Legacy
     * unbound sandbox orders retain their existing test-only path, but an
     * existing reviewed binding cannot be bypassed by using open().
     */
    private function assertReviewedTerms(CommercialOrder $order, int $amountMinor, ?string $licensedProductId): void
    {
        $terms = Schema::hasTable('kslp_commercial_order_terms')
            ? DB::table('kslp_commercial_order_terms')->where('commercial_order_id', $order->getKey())->first()
            : null;

        if ($terms === null) {
            if ($licensedProductId !== null) {
                throw new DomainException('RAZORPAY_REVIEWED_TERMS_REQUIRED');
            }

            return;
        }

        $organizationId = (string) $order->getAttribute('organization_id');
        $catalogId = (string) $order->getAttribute('product_id');
        $product = DB::table('kslp_licensed_products')
            ->where('id', $terms->licensed_product_id)
            ->where('organization_id', $organizationId)
            ->where('status', 'active')->lockForUpdate()->first(['product_code']);
        $catalog = DB::table('products')->where('id', $catalogId)
            ->lockForUpdate()->first(['slug']);

        if ($terms->issuer_organization_id !== $organizationId
            || $terms->catalog_product_id !== $catalogId
            || ($licensedProductId !== null && $terms->licensed_product_id !== $licensedProductId)
            || $product === null
            || $terms->licensed_product_code !== $product->product_code
            || $catalog === null
            || $terms->catalog_slug !== $catalog->slug
            || $terms->currency !== 'INR'
            || (int) $terms->amount_minor !== $amountMinor) {
            throw new DomainException('RAZORPAY_REVIEWED_TERMS_MISMATCH');
        }
    }

    /** @return array{provider_order_id: string, amount_minor: int, currency: string} */
    private function shape(string $providerOrderId, int $amountMinor, string $currency): array
    {
        return ['provider_order_id' => $providerOrderId, 'amount_minor' => $amountMinor, 'currency' => $currency];
    }
}
