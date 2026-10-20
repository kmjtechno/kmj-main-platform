<?php

declare(strict_types=1);

use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\Schema;
use KMJ\MainPlatform\Entitlements\Services\EntitlementReader;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

/**
 * Project enrollment requests are not live grants. Existing free-mode agents
 * must never be mutated to add a second project automatically.
 */
Route::post('services/kmj-codebridge/projects', function (
    Request $request,
    OrganizationDirectory $organizations,
    EntitlementReader $entitlements,
) {
    $user = $request->user();
    abort_unless($user instanceof User, 401);

    $input = $request->validate([
        'tenant_id' => ['required', 'string', 'max:64'],
        'project_id' => ['required', 'in:kmj-omnidesk'],
    ]);
    $tenantId = $input['tenant_id'];
    $member = collect($organizations->forUser((int) $user->id))
        ->contains(fn (array $organization): bool => $organization['id'] === $tenantId);

    abort_unless($member
        && $organizations->userCanManage((int) $user->id, $tenantId), 403);

    $hasEntitlement = collect($entitlements->forOrganization($tenantId))
        ->contains(fn (array $item): bool => $item['product_slug'] === 'kmj-codebridge'
            && $item['status'] === 'active');
    $hasLicense = DB::table('kslp_licenses')
        ->where('customer_id', $tenantId)
        ->where('product', 'KMJ_CODEBRIDGE')
        ->where('status', 'active')
        ->whereNull('revoked_at')
        ->where('starts_at', '<=', now())
        ->where('expires_at', '>', now())
        ->exists();
    abort_unless($hasEntitlement && $hasLicense, 403);
    abort_unless(Schema::hasTable('codebridge_project_onboarding_requests'), 503);

    $alreadyRegistered = DB::table('codebridge_device_credentials as c')
        ->join('codebridge_device_pairings as p', 'p.activation_id', '=', 'c.activation_id')
        ->where('c.tenant_id', $tenantId)
        ->where('p.tenant_id', $tenantId)
        ->where('p.project_id', $input['project_id'])
        ->whereNull('c.revoked_at')
        ->where('c.expires_at_epoch', '>', time())
        ->exists();
    if ($alreadyRegistered) {
        return redirect()->route('services.codebridge')
            ->with('status', 'OmniDesk already has a registered grant. Verify live gateway connectivity separately.');
    }

    // Only reviewed fixed repository and fixed host preset are accepted.
    // This records a request but never clones, executes, pairs, or grants access.
    // Atomic retry is necessary when a previously redeemed device is later
    // revoked. The fixed provider+host preset cannot be changed by the browser.
    DB::table('codebridge_project_onboarding_requests')->upsert([
        [
            'tenant_id' => $tenantId,
            'project_id' => 'kmj-omnidesk',
            'repository' => 'kmjtechno/kmj-omnidesk',
            'host' => 'lenovo-p720',
            'status' => 'awaiting_agent_pairing',
            'requested_by' => $user->getKey(),
            'created_at' => now(),
            'updated_at' => now(),
        ],
    ], ['tenant_id', 'project_id'], [
        'repository', 'host', 'status', 'requested_by', 'updated_at',
    ]);

    return redirect()->route('services.codebridge')
        ->with('status', 'OmniDesk project setup requested. Run the P720 installer and approve pairing to complete registration.');
})->name('services.codebridge.projects.request')->middleware(['password.confirm', 'throttle:6,1']);
