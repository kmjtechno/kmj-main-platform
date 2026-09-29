<?php

use App\Services\Licensing\CodeBridge\CodeBridgeRenewalService;
use App\Services\Licensing\Kslp\KslpSigner;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;

Route::post('v1/codebridge/renew', function (Request $request) {
    if (!config('codebridge.enabled', false)) { abort(503); }
    if (strlen($request->getContent()) > 4096) { abort(413); }
    $credential = $request->bearerToken();
    if (!is_string($credential) || strlen($credential) < 32 || strlen($credential) > 4096) { abort(401); }
    try {
        if (!app()->bound(KslpSigner::class)) { abort(503); }
        $service = new CodeBridgeRenewalService(DB::connection()->getPdo(), app(KslpSigner::class));
        $token = $service->renew($credential, $request->json()->all(), time());
        return response()->json(['token' => $token])->header('Cache-Control', 'no-store');
    } catch (DomainException) {
        return response()->json(['error' => 'CODEBRIDGE_RENEWAL_DENIED'], 403)->header('Cache-Control', 'no-store');
    } catch (Throwable) {
        return response()->json(['error' => 'CODEBRIDGE_RENEWAL_UNAVAILABLE'], 503)->header('Cache-Control', 'no-store');
    }
})->middleware('throttle:30,1');
