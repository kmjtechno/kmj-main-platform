<?php

use App\Services\Licensing\CodeBridge\CodeBridgeDevicePairingService;
use App\Services\Licensing\CodeBridge\CodeBridgeRenewalService;
use App\Services\Licensing\Kslp\KslpSigner;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;

Route::post('v1/codebridge/renew', function (Request $request) {
    if (!config('codebridge.enabled', false)) {
        abort(503);
    }
    if (strlen($request->getContent()) > 4096) {
        abort(413);
    }
    $credential = $request->bearerToken();
    if (!is_string($credential) || strlen($credential) < 32 || strlen($credential) > 4096) {
        abort(401);
    }
    try {
        if (!app()->bound(KslpSigner::class)) {
            abort(503);
        }
        $service = new CodeBridgeRenewalService(DB::connection()->getPdo(), app(KslpSigner::class));
        $token = $service->renew($credential, $request->json()->all(), time());

        return response()->json(['token' => $token])->header('Cache-Control', 'no-store');
    } catch (DomainException) {
        return response()->json(['error' => 'CODEBRIDGE_RENEWAL_DENIED'], 403)->header('Cache-Control', 'no-store');
    } catch (Throwable) {
        return response()->json(['error' => 'CODEBRIDGE_RENEWAL_UNAVAILABLE'], 503)->header('Cache-Control', 'no-store');
    }
})->middleware('throttle:30,1');


Route::post('codebridge/v1/device-enrollments', function (Request $request, CodeBridgeDevicePairingService $pairings) {
    if (!config('codebridge.enabled', false)) {
        abort(503);
    }
    if (strlen($request->getContent()) > 16384) {
        abort(413);
    }
    $v = $request->validate([
        'product' => ['required', 'in:KMJ_CODEBRIDGE'],
        'device.id' => ['required', 'string', 'regex:/\A[A-Za-z0-9_-]{1,64}\z/'],
        'device.name' => ['required', 'string', 'min:1', 'max:128'],
        'device.platform' => ['required', 'string', 'max:32'],
        'device.arch' => ['required', 'string', 'max:32'],
        'project.id' => ['required', 'string', 'regex:/\A[A-Za-z0-9_-]{1,64}\z/'],
        'project.name' => ['required', 'string', 'min:1', 'max:128'],
        'requested_permissions' => ['required', 'array', 'min:1', 'max:3'],
        'requested_permissions.*' => ['required', 'in:read,write,execute'],
        'code_challenge' => ['required', 'string', 'regex:/\A[A-Za-z0-9_-]{43,128}\z/'],
        'code_challenge_method' => ['required', 'in:S256'],
    ]);

    return response()->json($pairings->create($v, time()), 201)->header('Cache-Control', 'no-store');
})->middleware('throttle:10,1');

Route::post('codebridge/v1/device-enrollments/token', function (Request $request, CodeBridgeDevicePairingService $pairings) {
    if (!config('codebridge.enabled', false)) {
        abort(503);
    }
    if (strlen($request->getContent()) > 8192) {
        abort(413);
    }
    $v = $request->validate([
        'product' => ['required', 'in:KMJ_CODEBRIDGE'],
        'device_code' => ['required', 'string', 'min:32', 'max:4096'],
        'code_verifier' => ['required', 'string', 'min:43', 'max:128'],
        'device_id' => ['required', 'string', 'regex:/\A[A-Za-z0-9_-]{1,64}\z/'],
    ]);

    try {
        return response()->json(
            $pairings->redeem($v['device_code'], $v['code_verifier'], $v['device_id'], time())
        )->header('Cache-Control', 'no-store');
    } catch (DomainException $e) {
        $status = match ($e->getMessage()) {
            'CODEBRIDGE_PAIRING_PENDING' => 428,
            'CODEBRIDGE_PAIRING_DENIED' => 403,
            'CODEBRIDGE_PAIRING_EXPIRED', 'CODEBRIDGE_PAIRING_CONSUMED' => 410,
            default => 400,
        };

        return response()->json(['error' => $e->getMessage()], $status)->header('Cache-Control', 'no-store');
    }
})->middleware('throttle:60,1');
