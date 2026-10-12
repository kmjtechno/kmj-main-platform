<?php

declare(strict_types=1);

namespace App\Services\Payments;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;

/**
 * Read-only lookup. Never creates/captures/refunds/charges, marks orders paid,
 * or issues entitlements. Always use server-held sandbox credentials.
 */
final class ReadOnlySandboxPaymentLookup
{
    /**
     * @return array{provider: string, merchant_id: string, gateway_order_id: string, payment_id: string, currency: string, amount_minor: int, status: string}|null
     */
    public function razorpay(
        string $paymentId,
        string $keyId,
        string $keySecret,
        string $merchantId,
    ): ?array {
        if (! preg_match('/\Apay_[A-Za-z0-9]{1,100}\z/D', $paymentId)
            || $keyId === '' || $keySecret === '' || $merchantId === '') {
            return null;
        }

        try {
            // Razorpay test keys use the same REST host; this method never
            // sends a write request. Do not pass live keys into sandbox tests.
            $response = Http::withBasicAuth($keyId, $keySecret)
                ->acceptJson()
                ->connectTimeout(3)
                ->timeout(8)
                ->withOptions(['allow_redirects' => false])
                ->get('https://api.razorpay.com/v1/payments/'.$paymentId);
        } catch (ConnectionException) {
            return null;
        }

        if ($response->status() !== 200) {
            return null;
        }

        $payment = $response->json();
        if (! is_array($payment)
            || ($payment['id'] ?? null) !== $paymentId
            || ($payment['status'] ?? null) !== 'captured'
            || ($payment['captured'] ?? null) !== true
            || ($payment['amount_refunded'] ?? null) !== 0
            || ! is_string($payment['order_id'] ?? null)
            || ! preg_match('/\Aorder_[A-Za-z0-9]{1,100}\z/D', $payment['order_id'])
            || ! is_string($payment['currency'] ?? null)
            || ! preg_match('/\A[A-Z]{3}\z/D', $payment['currency'])
            || ! is_int($payment['amount'] ?? null)
            || $payment['amount'] < 1) {
            return null;
        }

        return [
            'provider' => 'razorpay',
            'merchant_id' => $merchantId,
            'gateway_order_id' => $payment['order_id'],
            'payment_id' => $paymentId,
            'currency' => $payment['currency'],
            'amount_minor' => $payment['amount'],
            'status' => 'captured',
        ];
    }

    /**
     * Cashfree sandbox ONLY. Conversion to minor units is restricted to INR
     * until an audited ISO-4217 exponent policy supports other currencies.
     *
     * @return array{provider: string, merchant_id: string, gateway_order_id: string, payment_id: string, currency: string, amount_minor: int, status: string}|null
     */
    public function cashfree(
        string $orderId,
        string $paymentId,
        string $clientId,
        string $clientSecret,
        string $merchantId,
    ): ?array {
        if (! preg_match('/\A[A-Za-z0-9_-]{1,45}\z/D', $orderId)
            || ! preg_match('/\A[1-9][0-9]{1,24}\z/D', $paymentId)
            || $clientId === '' || $clientSecret === '' || $merchantId === '') {
            return null;
        }

        try {
            $response = Http::withHeaders([
                'x-client-id' => $clientId,
                'x-client-secret' => $clientSecret,
                'x-api-version' => '2025-01-01',
            ])->acceptJson()
                ->connectTimeout(3)
                ->timeout(8)
                ->withOptions(['allow_redirects' => false])
                ->get('https://sandbox.cashfree.com/pg/orders/'.$orderId.'/payments');
        } catch (ConnectionException) {
            return null;
        }

        if ($response->status() !== 200) {
            return null;
        }

        $payments = $response->json();
        if (! is_array($payments) || ! array_is_list($payments)) {
            return null;
        }

        $matches = array_values(array_filter($payments, static fn (mixed $payment): bool => is_array($payment)
            && (string) ($payment['cf_payment_id'] ?? '') === $paymentId));
        if (count($matches) !== 1) {
            return null;
        }

        $payment = $matches[0];
        if (($payment['payment_status'] ?? null) !== 'SUCCESS'
            || ($payment['payment_currency'] ?? null) !== 'INR') {
            return null;
        }

        $minor = $this->inrMinor($payment['payment_amount'] ?? null);
        if ($minor === null || $minor < 1) {
            return null;
        }

        return [
            'provider' => 'cashfree',
            'merchant_id' => $merchantId,
            'gateway_order_id' => $orderId,
            'payment_id' => $paymentId,
            'currency' => 'INR',
            'amount_minor' => $minor,
            'status' => 'SUCCESS',
        ];
    }

    private function inrMinor(mixed $amount): ?int
    {
        // The Cashfree JSON response has a major-unit amount. We deliberately
        // reject sci-notation, sub-paisa fractions and large imprecise values.
        if (! is_int($amount) && ! is_float($amount) && ! is_string($amount)) {
            return null;
        }

        $decimal = (string) $amount;
        if (! preg_match('/\A(0|[1-9][0-9]{0,9})(?:\.([0-9]{1,2}))?\z/D', $decimal, $match)) {
            return null;
        }

        return ((int) $match[1] * 100) + (int) str_pad($match[2] ?? '0', 2, '0');
    }
}
