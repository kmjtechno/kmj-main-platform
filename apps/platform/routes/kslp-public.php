<?php

use App\Services\Licensing\Kslp\KslpKeyRegistry;
use Illuminate\Support\Facades\Route;

Route::prefix('api/v1/kslp')->group(function (): void {
    Route::get('contract', function () {
        $digest = file_get_contents(base_path('../../contracts/kslp-v1/CONTRACT.sha256'));
        abort_if($digest === false, 503);

        return response()->json(['protocol_version' => 'KSLP-v1', 'contract_sha256' => trim($digest), 'algorithms' => ['Ed25519']])->header('Cache-Control', 'public, max-age=300')
            ->header('Access-Control-Allow-Origin', '*');
    });
    Route::get('keys/{purpose}', function (string $purpose, KslpKeyRegistry $keys) {
        abort_unless(in_array($purpose, KslpKeyRegistry::PURPOSES, true), 404);

        return response()->json(['protocol_version' => 'KSLP-v1', 'purpose' => $purpose, 'keys' => $keys->discovery($purpose)])->header('Cache-Control', 'public, max-age=300')
            ->header('Access-Control-Allow-Origin', '*');
    });
});
