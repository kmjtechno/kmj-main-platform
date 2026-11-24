<?php

declare(strict_types=1);

namespace App\Services\Payments;

use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Receives provider webhooks: verify the exact raw bytes, then record the event once.
 *
 * Receipt is NOT settlement. This class never marks an order paid, never touches
 * entitlements and never issues a license. It only keeps an idempotent, minimal
 * inbox row for a later reconciliation step.
 */
final class PaymentWebhookReceiver
{
    public const ACCEPTED = 'accepted';

    public const DUPLICATE = 'duplicate';

    public const INVALID_SIGNATURE = 'invalid_signature';

    public const INVALID_PAYLOAD = 'invalid_payload';

    public const CONFLICT = 'conflict';

    public const UNAVAILABLE = 'unavailable';

    public function __construct(
        private readonly PaymentWebhookSignatureRouter $router,
        private readonly OwnerPaymentGatewaySettings $settings,
    ) {}

    /**
     * @param  array<string, string>  $headers  lowercase header name => value
     */
    public function receive(string $provider, string $rawBody, array $headers): string
    {
        if (! in_array($provider, ['razorpay', 'cashfree'], true)) {
            return self::INVALID_SIGNATURE;
        }

        if (! Schema::hasTable('payment_webhook_events')) {
            return self::UNAVAILABLE;
        }

        $secret = $this->settings->webhookSecret($provider);
        if ($secret === null) {
            return self::UNAVAILABLE;
        }

        if (! $this->router->verify($provider, $rawBody, $headers, $secret)) {
            return self::INVALID_SIGNATURE;
        }

        $payload = json_decode($rawBody, true);
        // Signed does not mean well-formed: require a JSON object with the provider's envelope.
        if (! is_array($payload) || $payload === [] || array_is_list($payload)) {
            return self::INVALID_PAYLOAD;
        }
        $envelope = $provider === 'razorpay' ? 'payload' : 'data';
        if ($this->safe($payload[$provider === 'razorpay' ? 'event' : 'type'] ?? null, 96) === null
            || ! is_array($payload[$envelope] ?? null)) {
            return self::INVALID_PAYLOAD;
        }

        $hash = hash('sha256', $rawBody);
        $eventId = $this->eventId($provider, $headers, $hash);
        [$type, $orderId, $paymentId] = $this->references($provider, $payload);

        $row = [
            'provider' => $provider,
            'event_type' => $type,
            'provider_order_id' => $orderId,
            'provider_payment_id' => $paymentId,
            'payload_sha256' => $hash,
            'received_at' => now(),
            'created_at' => now(),
            'updated_at' => now(),
        ];

        // Atomic on the unique (provider, event_id) index, so concurrent retries cannot double-insert.
        if (DB::table('payment_webhook_events')->insertOrIgnore($row + [
            'event_id' => $eventId,
            'processing_status' => 'received',
        ]) === 1) {
            return self::ACCEPTED;
        }

        $existing = DB::table('payment_webhook_events')
            ->where('provider', $provider)->where('event_id', $eventId)->value('payload_sha256');
        if ($existing === $hash) {
            return self::DUPLICATE;
        }

        // Same event id, different validly signed bytes: never collapse silently.
        // Keep the original untouched, record a sanitized conflict (deduped by hash), fail closed.
        DB::table('payment_webhook_events')->insertOrIgnore($row + [
            'event_id' => 'conflict:'.substr($hash, 0, 32),
            'processing_status' => 'conflict',
        ]);

        return self::CONFLICT;
    }

    /** @param array<string, string> $headers */
    private function eventId(string $provider, array $headers, string $hash): string
    {
        $header = $headers['x-razorpay-event-id'] ?? '';
        if ($provider === 'razorpay' && preg_match('/\\A[A-Za-z0-9_\\-]{1,128}\\z/D', $header)) {
            return $header;
        }

        // No provider event id: identical retries carry identical bytes.
        return 'sha256:'.$hash;
    }

    /**
     * @param  array<mixed>  $payload
     * @return array{0: ?string, 1: ?string, 2: ?string}
     */
    private function references(string $provider, array $payload): array
    {
        if ($provider === 'razorpay') {
            $type = $this->safe($payload['event'] ?? null, 96);
            $payment = data_get($payload, 'payload.payment.entity.id');
            // Refund-only and dispute-only envelopes may carry a payment
            // reference without an order. Never use these as capture proof.
            if ($payment === null && is_string($type)) {
                if (str_starts_with($type, 'refund.')) {
                    $payment = data_get($payload, 'payload.refund.entity.payment_id');
                } elseif (str_starts_with($type, 'payment.dispute.')) {
                    $payment = data_get($payload, 'payload.dispute.entity.payment_id');
                }
            }

            return [
                $type,
                $this->safe(data_get($payload, 'payload.payment.entity.order_id')
                    ?? data_get($payload, 'payload.order.entity.id'), 64),
                $this->safe($payment, 64),
            ];
        }

        return [
            $this->safe($payload['type'] ?? null, 96),
            $this->safe(data_get($payload, 'data.order.order_id'), 64),
            $this->safe(data_get($payload, 'data.payment.cf_payment_id'), 64),
        ];
    }

    private function safe(mixed $value, int $max): ?string
    {
        if (is_int($value)) {
            $value = (string) $value;
        }

        return is_string($value) && preg_match('/\\A[A-Za-z0-9_.\\-]{1,'.$max.'}\\z/D', $value) ? $value : null;
    }
}
