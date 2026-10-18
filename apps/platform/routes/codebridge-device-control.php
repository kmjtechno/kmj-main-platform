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
        $credentials->revoke((string) $device->license_id, $tenantId, $deviceId, time(), 'platform-user:'.$user->getKey());
    } catch (DomainException) {
        abort(409, 'CodeBridge device credential could not be disconnected.');
    }

    return back()
        ->with('status', 'Device authorization disconnected. Reconnect with a new pairing code. Gateway status may update after its next credential revalidation.')
        ->header('Cache-Control', 'no-store, private');
})->middleware(['password.confirm', 'throttle:10,1'])
    ->name('services.codebridge.devices.disconnect');

/**
 * Stage a project assignment on an already-registered CodeBridge device.
 *
 * This is a durable request, not an agent filesystem grant. Only a separately
 * authorized local project setup plus a verified agent connection may activate
 * access. In particular, never add this ID to device introspection here.
 */
Route::post('services/kmj-codebridge/organizations/{tenantId}/devices/{deviceId}/projects/assign', function (
    Request $request,
    string $tenantId,
    string $deviceId,
    OrganizationDirectory $organizations,
) {
    $user = $request->user();
    abort_unless($user instanceof User, 401);
    abort_unless((bool) preg_match('/\A[A-Za-z0-9_-]{1,64}\z/D', $tenantId), 404);
    abort_unless((bool) preg_match('/\A[A-Za-z0-9_-]{1,64}\z/D', $deviceId), 404);
    abort_unless($organizations->userCanManage((int) $user->id, $tenantId), 403);

    $input = $request->validate([
        'project_id' => ['required', 'string', 'regex:/\A[a-z0-9][a-z0-9_-]{0,63}\z/D'],
        'project_name' => ['required', 'string', 'min:2', 'max:100'],
        'repository_url' => [
            'required', 'string', 'max:255',
            'regex:/\Ahttps:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\z/D',
        ],
    ]);
    $projectId = $input['project_id'];

    // Bind to this tenant's active credential and live CodeBridge license.
    $device = DB::table('codebridge_device_credentials as c')
        ->join('kslp_licenses as l', 'l.id', '=', 'c.license_id')
        ->where('c.tenant_id', $tenantId)
        ->where('c.device_id', $deviceId)
        ->whereNull('c.revoked_at')
        ->where('c.expires_at_epoch', '>', time())
        ->where('l.customer_id', $tenantId)
        ->where('l.product', 'KMJ_CODEBRIDGE')
        ->where('l.status', 'active')
        ->whereNull('l.revoked_at')
        ->where('l.starts_at', '<=', now())
        ->where('l.expires_at', '>', now())
        ->first(['c.activation_id']);
    abort_unless($device !== null, 404);

    $paired = DB::table('codebridge_device_pairings')
        ->where('tenant_id', $tenantId)
        ->where('activation_id', $device->activation_id)
        ->where('project_id', $projectId)
        ->exists();
    if ($paired) {
        return back()->withErrors(['project_id' => 'Project already assigned during device pairing.']);
    }

    DB::transaction(function () use ($tenantId, $deviceId, $projectId, $input, $user): void {
        $existing = DB::table('codebridge_project_assignments')
            ->where('tenant_id', $tenantId)
            ->where('device_id', $deviceId)
            ->where('project_id', $projectId)
            ->lockForUpdate()
            ->first();
        if ($existing !== null) {
            // Idempotent exact retries; do not silently change an existing request.
            if ($existing->project_name !== $input['project_name']
                || $existing->repository_url !== $input['repository_url']) {
                abort(409, 'Project ID already assigned with different details.');
            }

            return;
        }
        DB::table('codebridge_project_assignments')->insert([
            'id' => (string) \Illuminate\Support\Str::uuid(),
            'tenant_id' => $tenantId,
            'device_id' => $deviceId,
            'project_id' => $projectId,
            'project_name' => $input['project_name'],
            'repository_url' => $input['repository_url'],
            'status' => 'pending_local_setup',
            'requested_by' => (int) $user->getKey(),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    });

    return back()
        ->with('status', 'Project assignment saved. Local agent authorization and heartbeat verification still required.')
        ->header('Cache-Control', 'no-store, private');
})->middleware('throttle:10,1')
    ->name('services.codebridge.devices.projects.assign');
