<?php

use App\Services\Payments\PaymentWebhookReceiver;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

// Machine endpoint: authenticated by provider HMAC over the raw bytes, not by session/CSRF.
// Receipt never settles an order or issues a license.
Route::post('webhooks/payments/{provider}', function (
    Request $request,
    string $provider,
    PaymentWebhookReceiver $receiver,
): JsonResponse {
    abort_unless(in_array($provider, ['razorpay', 'cashfree'], true), 404);

    $headers = [];
    foreach (['x-razorpay-signature', 'x-razorpay-event-id', 'x-webhook-timestamp', 'x-webhook-signature'] as $name) {
        $headers[$name] = (string) $request->header($name, '');
    }

    $result = $receiver->receive($provider, $request->getContent(), $headers);

    [$status, $code] = match ($result) {
        PaymentWebhookReceiver::ACCEPTED, PaymentWebhookReceiver::DUPLICATE => ['ok', 200],
        PaymentWebhookReceiver::INVALID_PAYLOAD => ['invalid_payload', 400],
        PaymentWebhookReceiver::CONFLICT => ['event_conflict', 409],
        PaymentWebhookReceiver::UNAVAILABLE => ['unavailable', 503],
        default => ['invalid_signature', 401],
    };

    return response()->json(['status' => $status], $code)->header('Cache-Control', 'no-store');
})->middleware('throttle:120,1')->name('payments.webhook');
