<?php

declare(strict_types=1);

namespace App\Services\Payments;

use Illuminate\Database\Query\Builder;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

final class PaymentGatewayReadiness
{
    /**
     * Sanitized owner-only status: no API secrets, key IDs, or merchant details.
     *
     * @return array{live_charging_enabled: bool, providers: list<array<string, mixed>>}
     */
    public function snapshot(): array
    {
        $providers = [];
        $gatewaySettings = app(OwnerPaymentGatewaySettings::class);
        $ownerSettings = collect($gatewaySettings->snapshot())->keyBy('provider');

        $eventsReady = Schema::hasTable('payment_webhook_events');

        foreach (['razorpay', 'cashfree'] as $provider) {
            $inbox = $eventsReady
                ? DB::table('payment_webhook_events')->where('provider', $provider)
                : null;
            // Count only; payloads and secrets never reach the browser.
            $eventsReceived = $inbox === null ? 0 : (clone $inbox)->where('processing_status', '!=', 'conflict')->count();
            $lastReceived = $inbox === null ? null : (clone $inbox)->where('processing_status', '!=', 'conflict')->max('received_at');
            $recentEvents = $inbox === null ? [] : $this->recentEvents(clone $inbox);
            $settings = (array) config('payment-providers.providers.'.$provider, []);
            $record = $ownerSettings->get($provider);
            // The owner-only sandbox order probe reads its test keys from
            // encrypted owner vault rows, not from environment config. Even
            // rzp_test_* config keys alone cannot make that probe executable.
            // Vault snapshot checks decrypted-key validity fail-closed.
            $keysPresent = (bool) ($record['client_id_stored'] ?? false)
                && (bool) ($record['client_secret_stored'] ?? false);
            // The readiness indicator must use the exact same signing-secret
            // authority as webhook verification (including owner revocation).
            $webhookSecretStored = $gatewaySettings->webhookSecret($provider) !== null;

            $providers[] = [
                'id' => $provider,
                'label' => $provider === 'cashfree' ? 'Cashfree Payments' : 'Razorpay',
                'merchant_approval' => ($record['merchant_status'] ?? 'not_verified') === 'owner_reports_approved'
                    ? 'reported_by_owner_not_api_verified' : 'not_verified',
                'sandbox_credentials_present' => $keysPresent,
                'webhook_secret_stored' => $webhookSecretStored,
                // A stored secret alone proves nothing: this turns true only after the live receiver
                // has accepted at least one provider-signed event for this provider.
                'webhook_verification_configured' => $webhookSecretStored && $eventsReceived > 0,
                'webhook_receiver_url' => url('/webhooks/payments/'.$provider),
                'webhook_events_received' => $eventsReceived,
                'webhook_last_received_at' => $this->iso($lastReceived),
                // Last time the owner-only INR 1 sandbox order was accepted by the provider. This proves
                // the test keys work; it is not a payment, a webhook match or a license.
                'sandbox_order_probe_at' => $this->lastSandboxProbe($provider),
                'recent_events' => $recentEvents,
                'international_approval_recorded' => ($settings['international_approved'] ?? false) === true,
                'live_transaction_verified' => false,
                'status' => $keysPresent ? 'sandbox_validation_required' : 'credentials_required',
            ];
        }

        foreach (['paypal', 'paddle', 'stripe'] as $provider) {
            $providers[] = [
                'id' => $provider,
                'label' => match ($provider) {
                    'paypal' => 'PayPal International',
                    'paddle' => 'Paddle Merchant of Record',
                    default => 'Stripe (invitation required in India)',
                },
                'merchant_approval' => 'not_verified',
                'sandbox_credentials_present' => false,
                'webhook_verification_configured' => false,
                'international_approval_recorded' => false,
                'live_transaction_verified' => false,
                'status' => 'not_integrated',
            ];
        }

        return [
            // No payment collection endpoint is exposed in this release.
            'live_charging_enabled' => false,
            'providers' => $providers,
        ];
    }

    /**
     * Last few received events, sanitized for the owner console. No payload, hash,
     * event id or full provider reference leaves the server.
     *
     * @return list<array{event_type: string, status: string, received_at: string|null, order_ref: string|null, payment_ref: string|null}>
     */
    private function recentEvents(Builder $inbox): array
    {
        $rows = $inbox
            ->where('processing_status', '!=', 'conflict')
            ->orderByDesc('received_at')
            ->orderByDesc('id')
            ->limit(10)
            ->get(['event_type', 'processing_status', 'received_at', 'provider_order_id', 'provider_payment_id'])
            ->map(fn (object $row): array => [
                'event_type' => is_string($row->event_type) && $row->event_type !== '' ? $row->event_type : 'unknown',
                'status' => (string) $row->processing_status,
                'received_at' => $this->iso($row->received_at),
                'order_ref' => $this->tail($row->provider_order_id),
                'payment_ref' => $this->tail($row->provider_payment_id),
            ])
            ->all();

        return array_values($rows);
    }

    private function lastSandboxProbe(string $provider): ?string
    {
        if (! Schema::hasTable('operator_action_audits')) {
            return null;
        }

        $rows = DB::table('operator_action_audits')
            ->where('action', 'payment_gateway.sandbox_order_probe')
            ->where('outcome', 'sandbox_order_created_only')
            ->orderByDesc('id')
            ->limit(50)
            ->get(['metadata', 'created_at']);

        foreach ($rows as $row) {
            $metadata = is_string($row->metadata) ? json_decode($row->metadata, true) : null;
            if (is_array($metadata) && ($metadata['provider'] ?? null) === $provider) {
                return $this->iso($row->created_at);
            }
        }

        return null;
    }

    /** Storage is UTC; send explicit Zulu so the console can show India time. */
    private function iso(mixed $value): ?string
    {
        if (! is_string($value) || $value === '') {
            return null;
        }

        return Carbon::parse($value, 'UTC')->utc()->toIso8601ZuluString();
    }

    private function tail(mixed $id): ?string
    {
        return is_string($id) && $id !== '' ? '…'.substr($id, -8) : null;
    }
}
