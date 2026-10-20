<?php

use App\Services\Licensing\Kslp\KslpKeyRegistry;
use App\Services\Licensing\OmniDeskLicenseContract;
use Illuminate\Support\Carbon;
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
    $published = collect($keys->discovery('license'))
        ->filter(fn (array $key): bool => $key['not_after'] !== null)
        ->map(function (array $key): array {
            $raw = base64_decode(strtr((string) $key['public_key'], '-_', '+/').'=', true);
            abort_if($raw === false || strlen($raw) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES, 503);

            return [
                'kid' => (string) $key['kid'],
                'algorithm' => OmniDeskLicenseContract::SIGNING_ALGORITHM,
                'public_key_base64' => base64_encode($raw),
                'not_before' => Carbon::parse($key['not_before'])->getTimestamp(),
                'not_after' => Carbon::parse($key['not_after'])->getTimestamp(),
                'status' => $key['status'] === 'retiring' ? 'ROLLOVER' : 'ACTIVE',
            ];
        })
        ->values()
        ->all();

    return response()->json([
        'protocol_version' => OmniDeskLicenseContract::PROTOCOL_VERSION,
        'contract_version' => OmniDeskLicenseContract::CONTRACT_VERSION,
        'product_id' => OmniDeskLicenseContract::PRODUCT_ID,
        'algorithm' => OmniDeskLicenseContract::SIGNING_ALGORITHM,
        'keys' => $published,
    ])->header('Cache-Control', 'public, max-age=300')
        ->header('Access-Control-Allow-Origin', '*');
})->name('licensing.omnidesk.keys');
