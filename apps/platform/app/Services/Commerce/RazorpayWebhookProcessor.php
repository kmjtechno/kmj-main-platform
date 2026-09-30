<?php

namespace App\Services\Commerce;

use App\Models\RazorpayPaymentAttempt;
use App\Models\RazorpayWebhookEvent;
use DomainException;
use Illuminate\Support\Facades\DB;
use JsonException;

final class RazorpayWebhookProcessor
{
    /**
     * @return array{status: 'processed'|'replayed'|'ignored', event: string}
     */
    public function process(string $rawBody, string $signature, string $eventId): array
    {
        $secret = trim((string) config('services.razorpay.webhook_secret'));
        $signature = trim($signature);
        $eventId = trim($eventId);

        if (! (bool) config('services.razorpay.enabled', false) || $secret === '') {
            throw new DomainException('Razorpay webhook processing is disabled.');
        }

        if ($rawBody === '' || ! preg_match('/^[A-Za-z0-9_-]{6,128}$/', $eventId)) {
            throw new DomainException('Razorpay webhook envelope is invalid.');
        }

        $expected = hash_hmac('sha256', $rawBody, $secret);

        if (! preg_match('/^[a-f0-9]{64}$/i', $signature) || ! hash_equals($expected, strtolower($signature))) {
            throw new DomainException('Razorpay webhook signature verification failed.');
        }

        $hash = hash('sha256', $rawBody);
        $existing = RazorpayWebhookEvent::query()->find($eventId);

        if ($existing !== null) {
            if ($existing->payload_sha256 !== $hash) {
                throw new DomainException('Razorpay webhook event id was replayed with different payload.');
            }

            return ['status' => 'replayed', 'event' => $existing->event_type];
        }

        try {
            $payload = json_decode($rawBody, true, flags: JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new DomainException('Razorpay webhook JSON is invalid.', previous: $exception);
        }

        if (! is_array($payload) || ! is_string($payload['event'] ?? null)) {
            throw new DomainException('Razorpay webhook event type is missing.');
        }

        $eventType = $payload['event'];

        return DB::transaction(function () use ($eventId, $eventType, $hash, $payload): array {
            $attempt = match ($eventType) {
                'payment.captured' => $this->applyCapturedPayment($payload),
                'payment.failed' => $this->applyFailedPayment($payload),
                'refund.processed' => $this->applyProcessedRefund($payload),
                default => null,
            };

            RazorpayWebhookEvent::query()->create([
                'event_id' => $eventId,
                'event_type' => $eventType,
                'payload_sha256' => $hash,
                'payment_attempt_id' => $attempt?->getKey(),
                'processed_at' => now(),
            ]);

            return [
                'status' => $attempt === null ? 'ignored' : 'processed',
                'event' => $eventType,
            ];
        });
    }

    /** @param array<string, mixed> $payload */
    private function applyCapturedPayment(array $payload): RazorpayPaymentAttempt
    {
        $payment = $payload['payload']['payment']['entity'] ?? null;

        if (! is_array($payment)) {
            throw new DomainException('Razorpay captured-payment payload is missing.');
        }

        $attempt = $this->attemptForOrder($payment['order_id'] ?? null);

        if (
            ! is_string($payment['id'] ?? null)
            || ! preg_match('/^pay_[A-Za-z0-9]+$/', $payment['id'])
            || ($payment['status'] ?? null) !== 'captured'
            || ($payment['captured'] ?? null) !== true
            || ($payment['amount'] ?? null) !== $attempt->amount_minor
            || ($payment['currency'] ?? null) !== $attempt->currency
        ) {
            throw new DomainException('Razorpay captured payment does not match stored commercial facts.');
        }

        if ($attempt->provider_payment_id !== null && $attempt->provider_payment_id !== $payment['id']) {
            throw new DomainException('Razorpay order is already bound to a different payment id.');
        }

        $attempt->forceFill([
            'provider_payment_id' => $payment['id'],
            'status' => 'captured',
            'captured_at' => $attempt->captured_at ?? now(),
            'failure_code' => null,
        ])->save();

        return $attempt;
    }

    /** @param array<string, mixed> $payload */
    private function applyFailedPayment(array $payload): ?RazorpayPaymentAttempt
    {
        $payment = $payload['payload']['payment']['entity'] ?? null;

        if (! is_array($payment) || ! is_string($payment['order_id'] ?? null)) {
            return null;
        }

        $attempt = RazorpayPaymentAttempt::query()
            ->where('provider_order_id', $payment['order_id'])
            ->lockForUpdate()
            ->first();

        if ($attempt === null || $attempt->status === 'captured') {
            return $attempt;
        }

        $attempt->forceFill([
            'status' => 'failed',
            'failure_code' => 'provider_payment_failed',
        ])->save();

        return $attempt;
    }

    /** @param array<string, mixed> $payload */
    private function applyProcessedRefund(array $payload): RazorpayPaymentAttempt
    {
        $refund = $payload['payload']['refund']['entity'] ?? null;

        if (! is_array($refund) || ! is_string($refund['payment_id'] ?? null)) {
            throw new DomainException('Razorpay refund payload is missing.');
        }

        $attempt = RazorpayPaymentAttempt::query()
            ->where('provider_payment_id', $refund['payment_id'])
            ->lockForUpdate()
            ->first();

        $amount = $refund['amount'] ?? null;

        if (
            $attempt === null
            || ! is_int($amount)
            || $amount < 1
            || $amount > $attempt->amount_minor
            || ($refund['currency'] ?? null) !== $attempt->currency
        ) {
            throw new DomainException('Razorpay refund does not match stored commercial facts.');
        }

        $refunded = min($attempt->amount_minor, $attempt->refunded_amount_minor + $amount);
        $attempt->forceFill([
            'refunded_amount_minor' => $refunded,
            'status' => $refunded === $attempt->amount_minor ? 'refunded' : 'partially_refunded',
            'refunded_at' => $refunded === $attempt->amount_minor ? now() : null,
        ])->save();

        return $attempt;
    }

    private function attemptForOrder(mixed $providerOrderId): RazorpayPaymentAttempt
    {
        if (! is_string($providerOrderId)) {
            throw new DomainException('Razorpay payment order id is missing.');
        }

        $attempt = RazorpayPaymentAttempt::query()
            ->where('provider_order_id', $providerOrderId)
            ->lockForUpdate()
            ->first();

        if ($attempt === null) {
            throw new DomainException('Razorpay payment is not associated with a KMJ checkout.');
        }

        return $attempt;
    }
}
