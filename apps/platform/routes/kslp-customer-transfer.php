<?php

declare(strict_types=1);

use App\Models\User;
use App\Services\Licensing\Kslp\KslpCustomerDeviceTransfer;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

// Included ONLY inside the existing auth + verified web group (CSRF enabled).
// No public challenge endpoint, no bearer auth shortcut, no legacy AuthSP API.
Route::middleware(['password.confirm', 'throttle:3,1'])
    ->prefix('licensing/devices/transfer')
    ->name('licensing.device.transfer.')
    ->group(function (): void {
        Route::post('{license}/challenge', function (
            Request $request,
            string $license,
            KslpCustomerDeviceTransfer $transfer,
        ) {
            abort_unless((bool) config('services.kmj_customer_device_transfer.enabled', false), 503);
            abort_if(strlen($request->getContent()) > 1024, 413);
            $actor = $request->user();
            abort_unless($actor instanceof User && $actor->hasVerifiedEmail(), 403);
            $data = $request->validate([
                'server_identity' => ['required', 'string', 'starts_with:ed25519:', 'max:160'],
            ]);
            try {
                $receipt = $transfer->challenge($actor, $license, $data['server_identity']);
            } catch (DomainException) {
                return response()->json(['error' => 'KSLP_DEVICE_TRANSFER_DENIED'], 409)
                    ->header('Cache-Control', 'no-store, private');
            }

            return response()->json($receipt)->header('Cache-Control', 'no-store, private');
        })->name('challenge');

        Route::post('{license}/complete', function (
            Request $request,
            string $license,
            KslpCustomerDeviceTransfer $transfer,
        ) {
            abort_unless((bool) config('services.kmj_customer_device_transfer.enabled', false), 503);
            abort_if(strlen($request->getContent()) > 4096, 413);
            $actor = $request->user();
            abort_unless($actor instanceof User && $actor->hasVerifiedEmail(), 403);
            $data = $request->validate([
                'server_identity' => ['required', 'string', 'starts_with:ed25519:', 'max:160'],
                'machine_hash' => ['required', 'regex:/^[a-f0-9]{64}$/'],
                'request_id' => ['required', 'uuid'],
                'challenge_id' => ['required', 'uuid'],
                'nonce' => ['required', 'string', 'min:32', 'max:128'],
                'signature' => ['required', 'string', 'min:64', 'max:128'],
                'reason' => ['required', 'string', 'min:8', 'max:240'],
            ]);

            try {
                $receipt = $transfer->transfer(
                    $actor, $license,
                    $data['server_identity'], $data['machine_hash'],
                    $data['request_id'], $data['challenge_id'],
                    $data['nonce'], $data['signature'], $data['reason'],
                );
            } catch (DomainException) {
                return response()->json(['error' => 'KSLP_DEVICE_TRANSFER_DENIED'], 409)
                    ->header('Cache-Control', 'no-store, private');
            }

            return response()->json($receipt)->header('Cache-Control', 'no-store, private');
        })->name('complete');
    });
