<?php

declare(strict_types=1);

namespace App\Services\Payments;

use DomainException;
use Illuminate\Support\Facades\Http;

final class CashfreeSandboxOrderClient
{
    private const ENDPOINT = 'https://sandbox.cashfree.com/pg/orders';

    /**
     * Creates a Cashfree test order only. The ID, currency, amount and customer
     * MUST originate from an authorized server-side commercial order.
     *
     * @return array{order_id: string, payment_session_id: string}
     */
    public function create(
        string $serverOrderId,
        int $amountMinor,
        string $currency,
        string $customerId,
        string $customerPhone,
        string $clientId,
        string $clientSecret,
    ): array {
        if (! preg_match('/\\A[A-Za-z0-9_-]{1,45}\\z/D', $serverOrderId)
            || $amountMinor < 100 || $amountMinor > 100000000
            || $currency !== 'INR'
            || ! preg_match('/\\A[A-Za-z0-9_-]{1,40}\\z/D', $customerId)
            || ! preg_match('/\\A[6-9][0-9]{9}\\z/D', $customerPhone)
            || $clientId === '' || $clientSecret === '') {
            throw new DomainException('CASHFREE_SANDBOX_INVALID_ORDER');
        }

        $response = Http::acceptJson()
            ->timeout(10)
            ->connectTimeout(5)
            ->withHeaders([
                'x-client-id' => $clientId,
                'x-client-secret' => $clientSecret,
                'x-api-version' => '2025-01-01',
                'x-idempotency-key' => hash('sha256', 'kmj-cashfree-sandbox:'.$serverOrderId),
            ])
            ->post(self::ENDPOINT, [
                'order_id' => $serverOrderId,
                'order_amount' => round($amountMinor / 100, 2),
                'order_currency' => $currency,
                'customer_details' => [
                    'customer_id' => $customerId,
                    'customer_phone' => $customerPhone,
                ],
            ]);

        if (! $response->successful()) {
            throw new DomainException('CASHFREE_SANDBOX_PROVIDER_UNAVAILABLE');
        }

        $body = $response->json();
        if (! is_array($body)
            || ($body['order_id'] ?? null) !== $serverOrderId
            || ($body['order_currency'] ?? null) !== $currency
            || ! is_numeric($body['order_amount'] ?? null)
            || (int) round(((float) $body['order_amount']) * 100) !== $amountMinor
            || ! is_string($body['payment_session_id'] ?? null)
            || strlen($body['payment_session_id']) < 16
            || strlen($body['payment_session_id']) > 4096) {
            throw new DomainException('CASHFREE_SANDBOX_ORDER_MISMATCH');
        }

        return [
            'order_id' => $serverOrderId,
            'payment_session_id' => $body['payment_session_id'],
        ];
    }
}
