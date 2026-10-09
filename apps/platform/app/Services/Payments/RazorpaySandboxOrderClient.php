<?php

declare(strict_types=1);

namespace App\Services\Payments;

use DomainException;
use Illuminate\Support\Facades\Http;

/**
 * A test-key-only Razorpay Orders API adapter. The amount and receipt must
 * originate in the server-owned commercial order; no capture or license grant.
 */
final class RazorpaySandboxOrderClient
{
    private const ENDPOINT = 'https://api.razorpay.com/v1/orders';

    /**
     * @return array{order_id: string, amount_minor: int, currency: string}
     */
    public function create(
        string $serverReceipt,
        int $amountMinor,
        string $currency,
        string $testKeyId,
        string $testKeySecret,
    ): array {
        if (! preg_match('/\A[A-Za-z0-9_-]{1,40}\z/D', $serverReceipt)
            || $amountMinor < 100 || $amountMinor > 100000000
            || $currency !== 'INR'
            || ! preg_match('/\Arzp_test_[A-Za-z0-9]+\z/D', $testKeyId)
            || strlen($testKeySecret) < 8 || strlen($testKeySecret) > 256
            || str_contains($testKeySecret, "\r") || str_contains($testKeySecret, "\n")) {
            throw new DomainException('RAZORPAY_SANDBOX_INVALID_ORDER');
        }

        $response = Http::withBasicAuth($testKeyId, $testKeySecret)
            ->acceptJson()
            ->timeout(10)
            ->connectTimeout(5)
            ->post(self::ENDPOINT, [
                'amount' => $amountMinor,
                'currency' => $currency,
                'receipt' => $serverReceipt,
                'partial_payment' => false,
            ]);

        if (! $response->successful()) {
            throw new DomainException('RAZORPAY_SANDBOX_PROVIDER_UNAVAILABLE');
        }

        $body = $response->json();
        if (! is_array($body)
            || ! is_string($body['id'] ?? null)
            || ! preg_match('/\Aorder_[A-Za-z0-9]+\z/D', $body['id'])
            || ($body['receipt'] ?? null) !== $serverReceipt
            || ($body['currency'] ?? null) !== $currency
            || ($body['amount'] ?? null) !== $amountMinor
            || ($body['status'] ?? null) !== 'created'
            || ($body['amount_paid'] ?? null) !== 0
            || ($body['amount_due'] ?? null) !== $amountMinor) {
            throw new DomainException('RAZORPAY_SANDBOX_ORDER_MISMATCH');
        }

        return [
            'order_id' => $body['id'],
            'amount_minor' => $amountMinor,
            'currency' => $currency,
        ];
    }
}
