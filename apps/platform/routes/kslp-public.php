<?php

use App\Services\Licensing\Kslp\KslpKeyRegistry;
use App\Services\Licensing\OmniDeskLicenseContract;
use Illuminate\Support\Facades\Route;

Route::prefix('api/v1/kslp')->group(function (): void {
    Route::get('contract', function () {
        $digest = file_get_contents(base_path('../../contracts/kslp-v1/CONTRACT.sha256'));
        abort_if($digest === false, 503);

        return response()->json([
            'protocol_version' => 'KSLP-v1',
            'contract_sha256' => trim($digest),
            'algorithms' => ['Ed25519'],
        ])->header('Cache-Control', 'public, max-age=300')
            ->header('Access-Control-Allow-Origin', '*');
    });

    Route::get('keys/{purpose}', function (string $purpose, KslpKeyRegistry $keys) {
        abort_unless(in_array($purpose, KslpKeyRegistry::PURPOSES, true), 404);

        return response()->json([
            'protocol_version' => 'KSLP-v1',
            'purpose' => $purpose,
            'keys' => $keys->discovery($purpose),
        ])->header('Cache-Control', 'public, max-age=300')
            ->header('Access-Control-Allow-Origin', '*');
    });
});

Route::get(OmniDeskLicenseContract::KEYS_ENDPOINT, function (KslpKeyRegistry $keys) {
    return response()->json([
        'protocol_version' => OmniDeskLicenseContract::PROTOCOL_VERSION,
        'contract_version' => OmniDeskLicenseContract::CONTRACT_VERSION,
        'product_id' => OmniDeskLicenseContract::PRODUCT_ID,
        'product_slug' => OmniDeskLicenseContract::PRODUCT_SLUG,
        'keys' => $keys->omniDeskDiscovery(),
    ])->header('Cache-Control', 'public, max-age=300')
        ->header('Access-Control-Allow-Origin', '*')
        ->header('X-Content-Type-Options', 'nosniff');
})->name('omnidesk.licensing.keys');
