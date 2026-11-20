<?php

declare(strict_types=1);

namespace App\Services\Payments;

use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

final class PaymentGatewayReadiness
{
    /**
     * Sanitized owner-only status: no API secrets, key IDs, or merchant details.
     *
     * @return array{live_charging_enabled: bool, providers: list<array<string, bool|int|string|null>>}
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
            $lastReceived = $inbox === null ? null : (clone $inbox)->max('received_at');
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
                'webhook_last_received_at' => is_string($lastReceived) ? $lastReceived : null,
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
}
