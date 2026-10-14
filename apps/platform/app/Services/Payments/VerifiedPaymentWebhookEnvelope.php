<?php

declare(strict_types=1);

namespace App\Services\Payments;

use JsonException;

/**
 * Provider-authenticated, read-only webhook classification.
 *
 * This class intentionally performs NO database write, payment capture or
 * license/entitlement fulfillment. Consumers MUST atomically deduplicate the
 * returned event ID and reconcile the payment with the provider server API,
 * the server-owned order, exact amount and currency before changing state.
 */
final class VerifiedPaymentWebhookEnvelope
{
    public function __construct(
        private readonly PaymentWebhookSignatureRouter $signatures,
    ) {}

    /**
     * @param  array<string, string>  $headers  Lowercase HTTP header names.
     * @return array{provider: string, event_id: string, event_type: string, order_id: string, payment_id: string, requires_reconciliation: true}|null
     */
    public function inspect(string $provider, string $rawBody, array $headers, string $secret): ?array
    {
        if (! in_array($provider, ['razorpay', 'cashfree'], true)
            || ! $this->signatures->verify($provider, $rawBody, $headers, $secret)) {
            return null;
        }

        try {
            $payload = json_decode($rawBody, true, 16, JSON_THROW_ON_ERROR);
        } catch (JsonException) {
            return null;
        }

        if (! is_array($payload)) {
            return null;
        }

        if ($provider === 'razorpay') {
            return $this->razorpay($payload, $headers);
        }

        return $this->cashfree($payload);
    }

    /**
     * @param  array<string, mixed>  $event
     * @param  array<string, string>  $headers
     * @return array{provider: string, event_id: string, event_type: string, order_id: string, payment_id: string, requires_reconciliation: true}|null
     */
    private function razorpay(array $event, array $headers): ?array
    {
        $type = $event['event'] ?? null;
        $eventId = $headers['x-razorpay-event-id'] ?? null;
        $entity = $event['payload']['payment']['entity'] ?? null;
        if (! in_array($type, ['payment.captured', 'payment.failed'], true)
            || ! is_string($eventId)
            || ! preg_match('/\A[A-Za-z0-9_-]{8,128}\z/D', $eventId)
            || ! is_array($entity)) {
            return null;
        }

        $orderId = $entity['order_id'] ?? null;
        $paymentId = $entity['id'] ?? null;
        if (! $this->validId($orderId, 'order_') || ! $this->validId($paymentId, 'pay_')) {
            return null;
        }

        return [
            'provider' => 'razorpay',
            'event_id' => hash('sha256', 'razorpay:'.$eventId),
            'event_type' => $type,
            'order_id' => $orderId,
            'payment_id' => $paymentId,
            'requires_reconciliation' => true,
        ];
    }

    /**
     * @param  array<string, mixed>  $event
     * @return array{provider: string, event_id: string, event_type: string, order_id: string, payment_id: string, requires_reconciliation: true}|null
     */
    private function cashfree(array $event): ?array
    {
        $type = $event['type'] ?? null;
        $orderId = $event['data']['order']['order_id'] ?? null;
        $paymentId = $event['data']['payment']['cf_payment_id'] ?? null;
        $status = $event['data']['payment']['payment_status'] ?? null;
        $statuses = [
            'PAYMENT_SUCCESS_WEBHOOK' => 'SUCCESS',
            'PAYMENT_FAILED_WEBHOOK' => 'FAILED',
            'PAYMENT_USER_DROPPED_WEBHOOK' => 'USER_DROPPED',
        ];

        if (! is_string($type)
            || ! isset($statuses[$type])
            || $status !== $statuses[$type]
            || ! is_string($orderId)
            || ! preg_match('/\A[A-Za-z0-9_-]{1,45}\z/D', $orderId)
            || (! is_string($paymentId) && ! is_int($paymentId))) {
            return null;
        }

        $paymentId = (string) $paymentId;
        if (! preg_match('/\A[1-9][0-9]{1,24}\z/D', $paymentId)) {
            return null;
        }

        return [
            'provider' => 'cashfree',
            'event_id' => hash('sha256', 'cashfree:'.$type.':'.$orderId.':'.$paymentId),
            'event_type' => $type,
            'order_id' => $orderId,
            'payment_id' => $paymentId,
            'requires_reconciliation' => true,
        ];
    }

    private function validId(mixed $value, string $prefix): bool
    {
        return is_string($value)
            && strlen($value) <= 128
            && (bool) preg_match('/\A'.preg_quote($prefix, '/').'[A-Za-z0-9]+\z/D', $value);
    }
}
