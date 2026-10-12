<?php

use App\Models\User;
use App\Services\Licensing\CodeBridge\CodeBridgeDeviceCredentialService;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

// Deliberately part of the existing auth + verified web route group.
// Every disconnect additionally requires recent password confirmation.
Route::post('services/kmj-codebridge/organizations/{tenantId}/devices/{deviceId}/disconnect', function (
    Request $request,
    string $tenantId,
    string $deviceId,
    OrganizationDirectory $organizations,
    CodeBridgeDeviceCredentialService $credentials,
) {
    $user = $request->user();
    abort_unless($user instanceof User, 401);
    abort_unless((bool) preg_match('/\A[A-Za-z0-9_-]{1,64}\z/D', $tenantId), 404);
    abort_unless((bool) preg_match('/\A[A-Za-z0-9_-]{1,64}\z/D', $deviceId), 404);
    abort_unless($organizations->userCanManage((int) $user->id, $tenantId), 403);

    $validated = $request->validate([
        'confirm_device_id' => ['required', 'string', 'max:64'],
    ]);
    abort_unless(hash_equals($deviceId, $validated['confirm_device_id']), 422);

    // Device ID alone is not an authority. Bind the existing credential to
    // this manager's tenant AND the exact KMJ_CODEBRIDGE license.
    $device = DB::table('codebridge_device_credentials as c')
        ->join('kslp_licenses as l', 'l.id', '=', 'c.license_id')
        ->where('c.tenant_id', $tenantId)
        ->where('c.device_id', $deviceId)
        ->where('l.customer_id', $tenantId)
        ->where('l.product', 'KMJ_CODEBRIDGE')
        ->first(['c.license_id', 'c.revoked_at']);
    abort_unless($device !== null, 404);

    try {
        // Transactional, audited and idempotent; never reveal or rotate tokens.
        $credentials->revoke((string) $device->license_id, $tenantId, $deviceId, time());
    } catch (DomainException) {
        abort(409, 'CodeBridge device credential could not be disconnected.');
    }

    return back()
        ->with('status', 'Device authorization disconnected. Reconnect with a new pairing code. Gateway status may update after its next credential revalidation.')
        ->header('Cache-Control', 'no-store, private');
})->middleware(['password.confirm', 'throttle:10,1'])
    ->name('services.codebridge.devices.disconnect');
