<?php

declare(strict_types=1);

use App\Models\User;
use App\Services\CodeBridge\HostedSignedSettlement;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

Route::post('services/kmj-codebridge/organizations/{tenantId}/devices/{deviceId}/receipt-signer/challenge', function (Request $request, string $tenantId, string $deviceId, HostedSignedSettlement $settlement) {
    abort_unless(config('codebridge.enabled') && config('codebridge.hosted_metering_pilot_enabled'), 503);
    abort_unless(config('codebridge.hosted_metering_pilot_tenant') === $tenantId, 404);
    $actor = $request->user();
    abort_unless($actor instanceof User, 401);
    try {
        $challenge = $settlement->issueSignerChallenge($actor, $tenantId, $deviceId);
    } catch (DomainException) {
        abort(403);
    }
    $request->session()->put('codebridge.receipt_signer_challenge', $challenge);

    return response()->json($challenge)->header('Cache-Control', 'no-store, private');
})->middleware(['password.confirm', 'throttle:10,1'])->name('services.codebridge.signers.challenge');

Route::post('services/kmj-codebridge/organizations/{tenantId}/devices/{deviceId}/receipt-signer/confirm', function (Request $request, string $tenantId, string $deviceId, HostedSignedSettlement $settlement) {
    abort_unless(config('codebridge.enabled') && config('codebridge.hosted_metering_pilot_enabled'), 503);
    abort_unless(config('codebridge.hosted_metering_pilot_tenant') === $tenantId, 404);
    $actor = $request->user();
    abort_unless($actor instanceof User, 401);
    $input = $request->validate([
        'public_key' => ['required', 'string', 'size:44'],
        'signature' => ['required', 'string', 'size:88'],
        'confirm' => ['required', 'in:APPROVE_DEVICE_RECEIPT_SIGNER'],
    ]);
    $challenge = $request->session()->pull('codebridge.receipt_signer_challenge');
    abort_unless(is_array($challenge), 409);
    try {
        $settlement->confirmSignerChallenge($actor, $tenantId, $deviceId, $challenge, $input['public_key'], $input['signature']);
    } catch (DomainException) {
        abort(409, 'Receipt signer proof rejected.');
    }

    return response()->json(['enrollment' => 'PINNED'])->header('Cache-Control', 'no-store, private');
})->middleware(['password.confirm', 'throttle:10,1'])->name('services.codebridge.signers.confirm');
