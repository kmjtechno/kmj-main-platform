<?php

declare(strict_types=1);

namespace App\Services\Payments;

use DomainException;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;

/**
 * Durable inbox for events already authenticated by the provider verifier.
 *
 * The inbox deliberately cannot capture payments, confirm commercial orders,
 * grant entitlements, dispatch a checkout or call a live payment API.
 * Merchant identity and environment MUST come from trusted server configuration.
 */
final class VerifiedPaymentWebhookInbox
{
    public function __construct(
        private readonly VerifiedPaymentWebhookEnvelope $envelope,
    ) {}

    /**
     * @param  array<string, string>  $headers  Lowercase HTTP header names.
     * @return array{is_new: bool, state: string, event_key: string}|null
     */
    public function record(
        string $provider,
        string $rawBody,
        array $headers,
        string $webhookSecret,
        string $merchantIdentifier,
        string $environment,
    ): ?array {
        if (! in_array($environment, ['sandbox', 'live'], true)
            || ! preg_match('/\A[A-Za-z0-9_-]{3,128}\z/D', $merchantIdentifier)) {
            throw new InvalidArgumentException('Trusted merchant identity and environment are required.');
        }

        // Inspect signature BEFORE any DB access or JSON field extraction.
        $verified = $this->envelope->inspect($provider, $rawBody, $headers, $webhookSecret);
        if ($verified === null) {
            return null;
        }

        $merchantHash = hash('sha256', $merchantIdentifier);
        $bodyHash = hash('sha256', $rawBody);

        return DB::transaction(function () use ($verified, $environment, $merchantHash, $bodyHash): array {
            $identity = [
                'provider' => $verified['provider'],
                'merchant_identity_hash' => $merchantHash,
                'environment' => $environment,
                'event_key' => $verified['event_id'],
            ];

            // Unique index is the atomic guard against concurrent duplicate delivery.
            $inserted = DB::table('payment_webhook_inbox')->insertOrIgnore([
                ...$identity,
                'body_sha256' => $bodyHash,
                'event_type' => $verified['event_type'],
                'order_reference' => $verified['order_id'],
                'payment_reference' => $verified['payment_id'],
                'state' => 'received_unreconciled',
                'created_at' => now(),
                'updated_at' => now(),
            ]);

            $stored = DB::table('payment_webhook_inbox')
                ->where($identity)
                ->first();

            if ($stored === null
                || $stored->body_sha256 !== $bodyHash
                || $stored->event_type !== $verified['event_type']
                || $stored->order_reference !== $verified['order_id']
                || $stored->payment_reference !== $verified['payment_id']) {
                // A reused provider event ID with altered signed facts must not
                // be silently accepted as an idempotent replay.
                throw new DomainException('Conflicting payment webhook identity replay.');
            }

            return [
                'is_new' => $inserted === 1,
                'state' => (string) $stored->state,
                'event_key' => $verified['event_id'],
            ];
        });
    }
}
