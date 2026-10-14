<?php

declare(strict_types=1);

use App\Services\Payments\VerifiedPaymentWebhookInbox;
use Illuminate\Contracts\Encryption\DecryptException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\Schema;

/**
 * Public machine-to-machine SANDBOX receiver, under /api/payments/webhooks/{provider}.
 * No session, CSRF bypass, browser token, order confirmation or entitlement mutation.
 * A valid signed event is placed into a durable unreconciled inbox only.
 */
Route::post('payments/webhooks/{provider}', function (
    Request $request,
    string $provider,
    VerifiedPaymentWebhookInbox $inbox,
): JsonResponse {
    if (! in_array($provider, ['razorpay', 'cashfree'], true)) {
        return response()->json(['error' => 'NOT_FOUND'], 404)->header('Cache-Control', 'no-store');
    }

    $rawBody = $request->getContent();
    if ($rawBody === '' || strlen($rawBody) > 262144) {
        return response()->json(['error' => 'INVALID_BODY'], 413)->header('Cache-Control', 'no-store');
    }

    if (! Schema::hasTable('payment_gateway_settings') || ! Schema::hasTable('payment_webhook_inbox')) {
        return response()->json(['error' => 'RECEIVER_UNAVAILABLE'], 503)->header('Cache-Control', 'no-store');
    }

    $settings = DB::table('payment_gateway_settings')->where('provider', $provider)->first();
    if ($settings === null || $settings->environment !== 'sandbox'
        || ! is_string($settings->encrypted_client_id) || $settings->encrypted_client_id === '') {
        return response()->json(['error' => 'RECEIVER_UNAVAILABLE'], 503)->header('Cache-Control', 'no-store');
    }

    // Cashfree signs PG webhooks using the API client secret; Razorpay uses a
    // separate owner-defined webhook secret, never the API client secret.
    $secretCiphertext = $provider === 'razorpay'
        ? $settings->encrypted_webhook_secret
        : $settings->encrypted_client_secret;

    if (! is_string($secretCiphertext) || $secretCiphertext === '') {
        return response()->json(['error' => 'RECEIVER_UNAVAILABLE'], 503)->header('Cache-Control', 'no-store');
    }

    try {
        $merchantKeyId = Crypt::decryptString($settings->encrypted_client_id);
        $secret = Crypt::decryptString($secretCiphertext);
    } catch (DecryptException) {
        return response()->json(['error' => 'RECEIVER_UNAVAILABLE'], 503)->header('Cache-Control', 'no-store');
    }
    if ($merchantKeyId === '' || $secret === ''
        || ($provider === 'razorpay' && ! str_starts_with($merchantKeyId, 'rzp_test_'))) {
        return response()->json(['error' => 'RECEIVER_UNAVAILABLE'], 503)->header('Cache-Control', 'no-store');
    }

    $headers = [
        'x-razorpay-signature' => (string) $request->header('X-Razorpay-Signature', ''),
        'x-razorpay-event-id' => (string) $request->header('X-Razorpay-Event-Id', ''),
        'x-webhook-timestamp' => (string) $request->header('X-Webhook-Timestamp', ''),
        'x-webhook-signature' => (string) $request->header('X-Webhook-Signature', ''),
    ];

    // An HMAC-valid envelope cannot produce fulfillment or captured-payment state.
    // Hash the configured server-owned key ID to scope the inbox to this merchant.
    try {
        $accepted = $inbox->record(
            $provider, $rawBody, $headers, $secret,
            'sbx_'.hash('sha256', $merchantKeyId), 'sandbox',
        );
    } catch (\DomainException) {
        return response()->json(['error' => 'CONFLICTING_DELIVERY'], 409)->header('Cache-Control', 'no-store');
    }

    if ($accepted === null) {
        return response()->json(['error' => 'INVALID_SIGNATURE_OR_EVENT'], 401)->header('Cache-Control', 'no-store');
    }

    return response()->json(
        ['received' => true, 'requires_reconciliation' => true],
        $accepted['is_new'] ? 202 : 200,
    )->header('Cache-Control', 'no-store');
})->where('provider', 'razorpay|cashfree')->middleware('throttle:120,1');
