<?php

declare(strict_types=1);

use App\Services\Licensing\CodeBridge\CodeBridgeLocalTelemetry;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;

/**
 * One small, credential-bound heartbeat per authorized CodeBridge agent.
 * All resource measurements are generated on the device, never on the VPS.
 */
Route::post('codebridge/v1/telemetry', function (
    Request $request,
    CodeBridgeLocalTelemetry $telemetry,
) {
    abort_unless(config('codebridge.enabled', false), 503);
    abort_if(strlen($request->getContent()) > 4096, 413);
    $token = $request->bearerToken();
    abort_unless(is_string($token) && strlen($token) >= 32 && strlen($token) <= 4096, 401);

    $device = DB::table('codebridge_device_credentials as c')
        ->join('kslp_licenses as l', 'l.id', '=', 'c.license_id')
        ->join('codebridge_device_pairings as p', 'p.activation_id', '=', 'c.activation_id')
        ->where('c.token_hash', hash('sha256', $token))
        ->whereNull('c.revoked_at')
        ->where('c.expires_at_epoch', '>', time())
        ->where('l.product', 'KMJ_CODEBRIDGE')
        ->where('l.customer_id', '=', DB::raw('c.tenant_id'))
        ->where('l.status', 'active')
        ->whereNull('l.revoked_at')
        ->where('l.starts_at', '<=', now())
        ->where('l.expires_at', '>', now())
        ->where('p.tenant_id', '=', DB::raw('c.tenant_id'))
        ->where('p.status', 'consumed')
        ->select(['c.device_id', 'c.tenant_id', 'p.project_id'])
        ->first();
    abort_unless($device !== null, 401);

    $v = $request->validate([
        'project_id' => ['required', 'string', 'regex:/\A[A-Za-z0-9_-]{1,64}\z/D'],
        'ollama' => ['sometimes', 'array'],
        'ollama.reachable' => ['required_with:ollama', 'boolean'],
        'ollama.models' => ['sometimes', 'array', 'max:5'],
        'ollama.models.*' => ['required', 'string', 'regex:/\A[A-Za-z0-9._:\/-]{1,96}\z/D'],
        'queue' => ['sometimes', 'array'],
        'queue.queued' => ['required_with:queue', 'integer', 'between:0,500'],
        'queue.running' => ['required_with:queue', 'integer', 'between:0,500'],
        'queue.waiting' => ['required_with:queue', 'integer', 'between:0,500'],
    ]);
    abort_unless(hash_equals((string) $device->project_id, $v['project_id']), 403);

    $telemetry->record(
        (string) $device->tenant_id,
        (string) $device->device_id,
        (string) $device->project_id,
        [
            'ollama' => $v['ollama'] ?? null,
            'queue' => $v['queue'] ?? null,
        ]
    );
    return response()->json(['accepted' => true], 202)
        ->header('Cache-Control', 'no-store')
        ->header('X-Content-Type-Options', 'nosniff');
})->middleware('throttle:6,1');
