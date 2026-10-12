<?php

declare(strict_types=1);

use App\Services\Licensing\Kslp\KslpActivationProof;
use App\Services\Licensing\Kslp\KslpDeveloperKeys;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use DomainException;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\Schema;

/*
 * Staging-only first-use device registration. An activation record is NOT a
 * product lease. Production signing requires separate KSLP release gates.
 * No session cookies or CSRF: these routes are registered in API middleware.
 */
Route::prefix('v1/kslp/developer')->middleware('throttle:5,1')->group(function (): void {
    Route::post('activation/challenge', function (
        Request $request,
        KslpDeveloperKeys $keys,
        KslpActivationProof $proof,
    ) {
        abort_unless((bool) config('services.kmj_developer_licensing.enabled', false), 503);
        abort_unless(Schema::hasTable('kslp_license_keys'), 503);
        abort_if(strlen($request->getContent()) > 2048, 413);
        $data = $request->validate([
            'license_key' => ['required', 'string', 'min:48', 'max:48'],
            'server_identity' => ['required', 'string', 'starts_with:ed25519:', 'max:160'],
        ]);
        try {
            $license = $keys->resolve($data['license_key']);
            $challenge = $proof->challenge($license['license_id'], $data['server_identity']);
        } catch (DomainException) {
            return response()->json(['error' => 'KSLP_ACTIVATION_DENIED'], 422)
                ->header('Cache-Control', 'no-store');
        }

        // The customer SDK needs the authoritative license ID to sign the
        // exact KSLP-ACTIVATE-v1|license|nonce challenge string.
        return response()->json([
            ...$challenge,
            'license_id' => $license['license_id'],
            'product' => $license['product_code'],
        ])->header('Cache-Control', 'no-store');
    });

    Route::post('activation/complete', function (
        Request $request,
        KslpDeveloperKeys $keys,
        KslpLicenseControlPlane $licenses,
    ) {
        abort_unless((bool) config('services.kmj_developer_licensing.enabled', false), 503);
        abort_unless(Schema::hasTable('kslp_license_keys'), 503);
        abort_if(strlen($request->getContent()) > 4096, 413);
        $data = $request->validate([
            'license_key' => ['required', 'string', 'min:48', 'max:48'],
            'server_identity' => ['required', 'string', 'starts_with:ed25519:', 'max:160'],
            'machine_hash' => ['required', 'regex:/^[a-f0-9]{64}$/'],
            'request_id' => ['required', 'string', 'min:8', 'max:128'],
            'challenge_id' => ['required', 'uuid'],
            'nonce' => ['required', 'string', 'min:32', 'max:128'],
            'signature' => ['required', 'string', 'min:64', 'max:128'],
            'metadata_consent' => ['required', 'boolean'],
            'platform' => ['nullable', 'in:windows,linux,macos,android,ios,other'],
            'app_version' => ['nullable', 'string', 'max:64'],
        ]);
        try {
            // The application/device activation and consented first-login
            // metadata must either both commit or both roll back.
            [$license, $activation] = DB::transaction(function () use ($keys, $licenses, $data): array {
                $license = $keys->resolve($data['license_key']);
                $activation = $licenses->activate(
                    $license['license_id'],
                    $data['server_identity'],
                    $data['machine_hash'],
                    $data['request_id'],
                    'developer-key-activation',
                    $data['challenge_id'],
                    $data['nonce'],
                    $data['signature'],
                );

                DB::table('kslp_license_keys')
                    ->where('license_id', $license['license_id'])
                    ->whereNull('first_activated_at')
                    ->update(['first_activated_at' => now(), 'updated_at' => now()]);

                // Explicit consent can be withdrawn on any future retry.
                // The bootstrap endpoint does not gather hardware serials.
                DB::table('kslp_license_keys')
                    ->where('license_id', $license['license_id'])
                    ->update([
                        'client_platform' => $data['metadata_consent'] ? ($data['platform'] ?? null) : null,
                        'client_app_version' => $data['metadata_consent'] ? ($data['app_version'] ?? null) : null,
                        'metadata_consented_at' => $data['metadata_consent'] ? now() : null,
                        'updated_at' => now(),
                    ]);

                return [$license, $activation];
            }, 3);
        } catch (DomainException) {
            return response()->json(['error' => 'KSLP_ACTIVATION_DENIED'], 422)
                ->header('Cache-Control', 'no-store');
        }

        return response()->json([
            'activation_id' => $activation['id'],
            'product' => $license['product_code'],
            'device_registered' => true,
            'signed_lease_issued' => false,
            'status' => 'activation_recorded_pending_signed_lease',
        ])->header('Cache-Control', 'no-store');
    });
});
