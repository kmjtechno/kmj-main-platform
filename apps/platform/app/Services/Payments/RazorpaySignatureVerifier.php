<?php

declare(strict_types=1);

namespace App\Services\Payments;

/**
 * Verify Razorpay authenticity without granting a license or modifying commerce state.
 *
 * The checkout order ID MUST come from the server's trusted local order record.
 * Webhook verification MUST use the exact raw HTTP request bytes, not parsed JSON.
 */
final class RazorpaySignatureVerifier
{
    public function verifyCheckout(
        string $expectedOrderId,
        string $callbackOrderId,
        string $paymentId,
        string $signature,
        string $apiSecret,
    ): bool {
        if (! $this->validProviderId($expectedOrderId, 'order_')
            || ! $this->validProviderId($callbackOrderId, 'order_')
            || ! $this->validProviderId($paymentId, 'pay_')
            || ! $this->validSignature($signature)
            || $apiSecret === ''
            || ! hash_equals($expectedOrderId, $callbackOrderId)) {
            return false;
        }

        $expected = hash_hmac('sha256', $expectedOrderId.'|'.$paymentId, $apiSecret);

        return hash_equals($expected, $signature);
    }

    public function verifyWebhook(
        string $rawBody,
        string $signature,
        string $webhookSecret,
    ): bool {
        if ($rawBody === '' || strlen($rawBody) > 262144
            || ! $this->validSignature($signature)
            || $webhookSecret === '') {
            return false;
        }

        $expected = hash_hmac('sha256', $rawBody, $webhookSecret);

        return hash_equals($expected, $signature);
    }

    private function validProviderId(string $id, string $prefix): bool
    {
        return strlen($id) <= 128
            && (bool) preg_match('/\\A'.preg_quote($prefix, '/').'[A-Za-z0-9]+\\z/D', $id);
    }

    private function validSignature(string $signature): bool
    {
        return (bool) preg_match('/\\A[a-f0-9]{64}\\z/D', $signature);
    }
}
