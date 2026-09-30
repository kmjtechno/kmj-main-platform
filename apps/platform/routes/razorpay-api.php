<?php

use App\Services\Commerce\RazorpayWebhookProcessor;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

Route::post('razorpay/webhook', function (Request $request, RazorpayWebhookProcessor $processor) {
    $result = $processor->process(
        $request->getContent(),
        (string) $request->header('X-Razorpay-Signature', ''),
        (string) $request->header('X-Razorpay-Event-Id', ''),
    );

    return response()->json($result);
})->name('razorpay.webhook');
