<?php

declare(strict_types=1);

namespace App\Services\Payments;

/**
 * Pure, fail-closed comparison of a verified webhook, a server-owned checkout
 * quote, and a NEW server-to-provider payment lookup.
 *
 * No payments, entitlement issuance, or database writes occur here.
 * The caller must verify the webhook through VerifiedPaymentWebhookInbox, load
 * the immutable checkout quote from its own database, then query the payment
 * provider with server-side credentials. Never trust browser-supplied facts.
 */
final class PaymentCapturedEvidenceGuard
{
    /**
     * @param  array{provider: string, event_id: string, event_type: string, order_id: string, payment_id: string, requires_reconciliation: true}  $event
     * @param  array{provider: string, merchant_id: string, gateway_order_id: string, currency: string, amount_minor: int, internal_order_id: string}  $quote
     * @param  array{provider: string, merchant_id: string, gateway_order_id: string, payment_id: string, currency: string, amount_minor: int, status: string}  $fetched
     */
    public function matches(array $event, array $quote, array $fetched): bool
    {
        $provider = $quote['provider'];
        if (! in_array($provider, ['razorpay', 'cashfree'], true)
            || $event['provider'] !== $provider
            || $fetched['provider'] !== $provider
            || $event['requires_reconciliation'] !== true) {
            return false;
        }

        // Success status must be confirmed independently by the provider API.
        if (($provider === 'razorpay'
                && ($event['event_type'] !== 'payment.captured' || $fetched['status'] !== 'captured'))
            || ($provider === 'cashfree'
                && ($event['event_type'] !== 'PAYMENT_SUCCESS_WEBHOOK' || $fetched['status'] !== 'SUCCESS'))) {
            return false;
        }

        if ($quote['internal_order_id'] === ''
            || $quote['merchant_id'] === ''
            || $quote['gateway_order_id'] === ''
            || $quote['amount_minor'] < 1
            || ! preg_match('/\A[A-Z]{3}\z/D', $quote['currency'])
            || $fetched['amount_minor'] < 1) {
            return false;
        }

        return hash_equals($quote['merchant_id'], $fetched['merchant_id'])
            && hash_equals($quote['gateway_order_id'], $event['order_id'])
            && hash_equals($quote['gateway_order_id'], $fetched['gateway_order_id'])
            && hash_equals($event['payment_id'], $fetched['payment_id'])
            && $quote['currency'] === $fetched['currency']
            && $quote['amount_minor'] === $fetched['amount_minor'];
    }
}
