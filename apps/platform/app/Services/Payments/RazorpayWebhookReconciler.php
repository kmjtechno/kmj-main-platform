<?php

declare(strict_types=1);

namespace App\Services\Payments;

use DomainException;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;

/**
 * Turns signature-verified inbox rows into confirmed commercial orders, but only on
 * Razorpay's own server-to-server evidence: exact captured payment, bound to the
 * provider order we created, with the amount we expected. A webhook is just a trigger.
 * Never grants an entitlement or license.
 */
final class RazorpayWebhookReconciler
{
    private const TRIGGERS = ['payment.captured', 'order.paid'];

    public function __construct(
        private readonly RazorpayPaymentAdapter $adapter,
        private readonly CommercialOrderService $orders,
    ) {}

    /**
     * @return array{reconciled: int, unmatched: int, rejected: int, retry_later: int}
     */
    public function reconcilePending(int $limit = 50): array
    {
        $reconciled = $unmatched = $rejected = $retryLater = 0;

        $events = DB::table('payment_webhook_events')
            ->where('provider', 'razorpay')
            ->where('processing_status', 'received')
            ->whereIn('event_type', self::TRIGGERS)
            ->orderBy('id')
            ->limit(max(1, min($limit, 500)))
            ->get();

        foreach ($events as $event) {
            $outcome = $this->handle($event);
            match ($outcome['bucket']) {
                'reconciled' => $reconciled++,
                'unmatched' => $unmatched++,
                'rejected' => $rejected++,
                default => $retryLater++,
            };
            if ($outcome['status'] !== null) {
                DB::table('payment_webhook_events')
                    ->where('id', $event->id)->where('processing_status', 'received')
                    ->update([
                        'processing_status' => $outcome['status'],
                        'processing_note' => $outcome['note'],
                        'updated_at' => now(),
                    ]);
            }
        }

        return [
            'reconciled' => $reconciled,
            'unmatched' => $unmatched,
            'rejected' => $rejected,
            'retry_later' => $retryLater,
        ];
    }

    /**
     * @return array{bucket: string, status: ?string, note: string}
     */
    private function handle(object $event): array
    {
        $orderRef = data_get($event, 'provider_order_id');
        $paymentRef = data_get($event, 'provider_payment_id');
        $link = is_string($orderRef)
            ? DB::table('commerce_provider_orders')->where('provider', 'razorpay')->where('provider_order_id', $orderRef)->first()
            : null;

        if ($link === null || ! is_string($paymentRef)) {
            return ['bucket' => 'unmatched', 'status' => 'unmatched', 'note' => 'NO_LINKED_ORDER'];
        }

        // Never let a sandbox provider adapter confirm an imported/live order.
        // A signature-verified inbox row alone is not a paid order.
        if ((string) $link->environment !== 'sandbox') {
            return ['bucket' => 'rejected', 'status' => 'rejected', 'note' => 'PROVIDER_ENVIRONMENT_MISMATCH'];
        }

        try {
            $evidence = $this->adapter->confirmationForProviderOrder($paymentRef, $orderRef);
        } catch (InvalidArgumentException) {
            return ['bucket' => 'rejected', 'status' => 'rejected', 'note' => 'REFERENCE_INVALID'];
        } catch (DomainException $exception) {
            // Provider unreachable or vault not ready is transient: keep the row for the next run.
            if (in_array($exception->getMessage(), ['RAZORPAY_PROVIDER_UNAVAILABLE', 'RAZORPAY_SANDBOX_CREDENTIALS_NOT_READY'], true)) {
                return ['bucket' => 'retry_later', 'status' => null, 'note' => $exception->getMessage()];
            }

            return ['bucket' => 'rejected', 'status' => 'rejected', 'note' => 'NOT_SETTLED'];
        }

        if ($evidence->amountMinor !== (int) $link->amount_minor || $evidence->currency !== (string) $link->currency) {
            return ['bucket' => 'rejected', 'status' => 'rejected', 'note' => 'AMOUNT_MISMATCH'];
        }

        $order = CommercialOrder::query()->whereKey($link->commercial_order_id)->first();
        if ($order === null) {
            return ['bucket' => 'unmatched', 'status' => 'unmatched', 'note' => 'ORDER_MISSING'];
        }

        try {
            // The requester is the ledger actor: the webhook itself has no human operator.
            $this->orders->confirm(
                (string) $order->getKey(),
                (int) $order->getAttribute('requester_user_id'),
                $evidence->currency,
                $evidence->amountMinor,
                'razorpay:'.$evidence->reference,
            );
        } catch (DomainException) {
            return ['bucket' => 'rejected', 'status' => 'rejected', 'note' => 'ORDER_NOT_CONFIRMABLE'];
        }

        return ['bucket' => 'reconciled', 'status' => 'reconciled', 'note' => 'CONFIRMED'];
    }
}
