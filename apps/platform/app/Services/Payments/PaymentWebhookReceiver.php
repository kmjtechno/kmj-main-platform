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
        if (! is_array($payload)) {
            return self::INVALID_PAYLOAD;
        }

        $hash = hash('sha256', $rawBody);
        $eventId = $this->eventId($provider, $headers, $hash);
        [$type, $orderId, $paymentId] = $this->references($provider, $payload);

        $inserted = DB::table('payment_webhook_events')->insertOrIgnore([
            'provider' => $provider,
            'event_id' => $eventId,
            'event_type' => $type,
            'provider_order_id' => $orderId,
            'provider_payment_id' => $paymentId,
            'payload_sha256' => $hash,
            'processing_status' => 'received',
            'received_at' => now(),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $inserted === 1 ? self::ACCEPTED : self::DUPLICATE;
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
            return [
                $this->safe($payload['event'] ?? null, 96),
                $this->safe(data_get($payload, 'payload.payment.entity.order_id')
                    ?? data_get($payload, 'payload.order.entity.id'), 64),
                $this->safe(data_get($payload, 'payload.payment.entity.id'), 64),
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
