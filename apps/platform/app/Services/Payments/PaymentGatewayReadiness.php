<?php

declare(strict_types=1);

namespace App\Services\Payments;

final class PaymentGatewayReadiness
{
    /**
     * Sanitized owner-only status: no API secrets, key IDs, or merchant details.
     *
     * @return array{live_charging_enabled: bool, providers: list<array<string, bool|string>>}
     */
    public function snapshot(): array
    {
        $providers = [];
        $ownerSettings = collect(app(OwnerPaymentGatewaySettings::class)->snapshot())->keyBy('provider');

        foreach (['razorpay', 'cashfree'] as $provider) {
            $settings = (array) config('payment-providers.providers.'.$provider, []);
            $record = $ownerSettings->get($provider);
            $keysPresent = ($this->present($settings['client_id'] ?? null)
                && $this->present($settings['client_secret'] ?? null))
                || ((bool) ($record['client_id_stored'] ?? false)
                    && (bool) ($record['client_secret_stored'] ?? false));
            $webhookReady = (bool) ($record['webhook_secret_stored'] ?? false)
                || ($provider === 'cashfree'
                    ? $this->present($settings['client_secret'] ?? null)
                    : $this->present($settings['webhook_secret'] ?? null));

            $providers[] = [
                'id' => $provider,
                'label' => $provider === 'cashfree' ? 'Cashfree Payments' : 'Razorpay',
                'merchant_approval' => ($record['merchant_status'] ?? 'not_verified') === 'owner_reports_approved'
                    ? 'reported_by_owner_not_api_verified' : 'not_verified',
                'sandbox_credentials_present' => $keysPresent,
                'webhook_verification_configured' => $webhookReady,
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

    private function present(mixed $value): bool
    {
        return is_string($value) && trim($value) !== '';
    }
}
