<?php

declare(strict_types=1);

namespace App\Services\Payments;

use DomainException;
use Illuminate\Support\Facades\Http;
use InvalidArgumentException;
use KMJ\MainPlatform\Commerce\Contracts\PaymentProviderAdapter;
use KMJ\MainPlatform\Commerce\ValueObjects\ProviderPaymentConfirmation;

/**
 * Server-to-server evidence for PaymentReconciler: asks Razorpay itself whether a
 * payment is captured. A webhook or browser callback is only a hint; this call is
 * the evidence. SANDBOX test keys from the owner vault only, so it cannot touch real money.
 * Confirming an order never grants an entitlement or license.
 */
final class RazorpayPaymentAdapter implements PaymentProviderAdapter
{
    private const ENDPOINT = 'https://api.razorpay.com/v1/payments/';

    public function __construct(private readonly OwnerPaymentGatewaySettings $settings) {}

    public function provider(): string
    {
        return 'razorpay';
    }

    public function confirmation(string $providerReference): ProviderPaymentConfirmation
    {
        return $this->fetchSettled($providerReference, null);
    }

    /**
     * Same evidence, additionally bound to the Razorpay order we created for the
     * commercial order, so a captured payment for a different order cannot settle it.
     */
    public function confirmationForProviderOrder(string $providerReference, string $providerOrderId): ProviderPaymentConfirmation
    {
        if (! preg_match('/\Aorder_[A-Za-z0-9]{1,64}\z/D', $providerOrderId)) {
            throw new InvalidArgumentException('RAZORPAY_ORDER_REFERENCE_INVALID');
        }

        return $this->fetchSettled($providerReference, $providerOrderId);
    }

    private function fetchSettled(string $providerReference, ?string $expectedOrderId): ProviderPaymentConfirmation
    {
        if (! preg_match('/\Apay_[A-Za-z0-9]{1,64}\z/D', $providerReference)) {
            throw new InvalidArgumentException('RAZORPAY_PAYMENT_REFERENCE_INVALID');
        }

        try {
            $credentials = $this->settings->sandboxCredentials('razorpay');
        } catch (InvalidArgumentException) {
            throw new DomainException('RAZORPAY_SANDBOX_CREDENTIALS_NOT_READY');
        }

        $response = Http::withBasicAuth($credentials['client_id'], $credentials['client_secret'])
            ->acceptJson()
            ->timeout(10)
            ->connectTimeout(5)
            ->get(self::ENDPOINT.$providerReference);

        if (! $response->successful()) {
            throw new DomainException('RAZORPAY_PROVIDER_UNAVAILABLE');
        }

        $body = $response->json();
        // Fail closed unless the provider affirms the exact payment as captured and unrefunded.
        if (! is_array($body)
            || ($body['id'] ?? null) !== $providerReference
            || ($body['status'] ?? null) !== 'captured'
            || ($body['captured'] ?? null) !== true
            || ! is_string($body['currency'] ?? null)
            || ! is_int($body['amount'] ?? null) || $body['amount'] < 1
            // Missing, boolean, string and malformed refund amounts are
            // unknown settlement state, never proof of zero refunds.
            || ! is_int($body['amount_refunded'] ?? null)
            || $body['amount_refunded'] !== 0
            || ($expectedOrderId !== null && ($body['order_id'] ?? null) !== $expectedOrderId)) {
            throw new DomainException('RAZORPAY_PAYMENT_NOT_SETTLED');
        }

        return new ProviderPaymentConfirmation('razorpay', $providerReference, $body['currency'], $body['amount']);
    }
}
