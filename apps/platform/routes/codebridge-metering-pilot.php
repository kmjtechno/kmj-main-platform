<?php

declare(strict_types=1);

use App\Models\User;
use App\Services\CodeBridge\HostedSignedSettlement;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Str;

Route::post('codebridge/v1/hosted-metering-pilot', function (Request $request, HostedSignedSettlement $settlement) {
    abort_unless(config('codebridge.enabled') && config('codebridge.hosted_metering_pilot_enabled'), 503);
    abort_if(strlen($request->getContent()) > 4096, 413);
    $hash = config('codebridge.hosted_metering_pilot_token_hash');
    $tenant = config('codebridge.hosted_metering_pilot_tenant');
    $token = $request->bearerToken();
    abort_unless(is_string($hash) && preg_match('/\\A[a-f0-9]{64}\\z/D', $hash) === 1
        && is_string($token) && preg_match('/\\A[A-Za-z0-9_-]{43,128}\\z/D', $token) === 1
        && hash_equals($hash, hash('sha256', $token))
        && is_string($tenant) && Str::isUuid($tenant), 403);
    $data = $request->json()->all();
    $action = $data['action'] ?? null;
    $execution = $data['execution_id'] ?? null;
    abort_unless(($data['organization_id'] ?? null) === $tenant && is_string($execution) && Str::isUuid($execution), 422);

    try {
        if ($action === 'reserve') {
            abort_unless(count($data) === 7, 422);
            $subject = $data['user_subject'] ?? null;
            $device = $data['device_id'] ?? null;
            $project = $data['project_id'] ?? null;
            abort_unless(is_string($subject) && preg_match('/\\Akmj-user:([1-9][0-9]{0,17})\\z/D', $subject, $match) === 1
                && is_string($device) && preg_match('/\\A[A-Za-z0-9_-]{1,64}\\z/D', $device) === 1
                && is_string($project) && preg_match('/\\A[A-Za-z0-9_-]{1,64}\\z/D', $project) === 1
                && ($data['tool'] ?? null) === 'git_status', 422);
            $actor = User::query()->find((int) $match[1]);
            abort_unless($actor instanceof User, 403);
            $requestHash = hash('sha256', "git_status\n".$device."\n".$project."\n");
            $result = $settlement->reserveForOwner($actor, $tenant, $device, $project, $execution, $requestHash);
            // A replayed completed reservation must not dispatch again.
            abort_unless($result['state'] === 'reserved', 409);

            return response()->json(['reserved' => true, 'request_sha256' => $requestHash], 200)->header('Cache-Control', 'no-store');
        }
        if ($action === 'settle') {
            $signature = $data['signature'] ?? null;
            abort_unless(count($data) === 5 && ($data['outcome'] ?? null) === 'succeeded' && is_string($signature), 422);
            $settlement->settleSigned($tenant, $execution, 'succeeded', $signature);

            return response()->json(['settled' => true])->header('Cache-Control', 'no-store');
        }
    } catch (DomainException) {
        return response()->json(['error' => 'HOSTED_METERING_PILOT_DENIED'], 409)->header('Cache-Control', 'no-store');
    }
    abort(422);
})->middleware('throttle:120,1');
