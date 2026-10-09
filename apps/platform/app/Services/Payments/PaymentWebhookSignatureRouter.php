<?php

declare(strict_types=1);

namespace App\Services\Payments;

/**
 * Provider-bound verification. An authenticated signature does not settle an
 * order, capture a payment, or grant any license.
 */
final class PaymentWebhookSignatureRouter
{
    public function __construct(
        private readonly RazorpaySignatureVerifier $razorpay,
        private readonly CashfreeSignatureVerifier $cashfree,
    ) {}

    /**
     * Header names are normalized by the framework to lowercase before use.
     *
     * @param  array<string, string>  $headers
     */
    public function verify(
        string $provider,
        string $rawBody,
        array $headers,
        string $providerSecret,
    ): bool {
        if ($providerSecret === '' || $rawBody === '' || strlen($rawBody) > 262144) {
            return false;
        }

        return match ($provider) {
            'razorpay' => $this->razorpay->verifyWebhook(
                $rawBody,
                $headers['x-razorpay-signature'] ?? '',
                $providerSecret,
            ),
            'cashfree' => $this->cashfree->verifyWebhook(
                $rawBody,
                $headers['x-webhook-timestamp'] ?? '',
                $headers['x-webhook-signature'] ?? '',
                $providerSecret,
            ),
            default => false,
        };
    }
}
