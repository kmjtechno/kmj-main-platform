<?php

declare(strict_types=1);

namespace App\Services\Payments;

/**
 * Cashfree PG signs the exact x-webhook-timestamp + raw request body using
 * HMAC-SHA256 and base64. Verification is not payment reconciliation or
 * permission to grant entitlements.
 */
final class CashfreeSignatureVerifier
{
    public function verifyWebhook(
        string $rawBody,
        string $timestamp,
        string $signature,
        string $clientSecret,
    ): bool {
        if ($rawBody === '' || strlen($rawBody) > 262144
            || ! preg_match('/\\A[1-9][0-9]{9,15}\\z/D', $timestamp)
            || $clientSecret === ''
            || strlen($signature) !== 44) {
            return false;
        }

        $provided = base64_decode($signature, true);
        if ($provided === false || strlen($provided) !== 32
            || ! hash_equals(base64_encode($provided), $signature)) {
            return false;
        }

        $expected = hash_hmac('sha256', $timestamp.$rawBody, $clientSecret, true);

        return hash_equals($expected, $provided);
    }
}
