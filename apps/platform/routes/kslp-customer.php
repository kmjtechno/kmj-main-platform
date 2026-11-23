<?php

declare(strict_types=1);

use App\Models\User;
use App\Services\Licensing\Kslp\KslpCustomerWorkspaceQuery;
use App\Services\Licensing\OmniDesk\OmniDeskAutomaticTrialProvisioner;
use App\Services\Licensing\OmniDesk\OmniDeskTrialSelfServiceDiscovery;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;

// Already inside the existing auth + verified web route group.
// No independent AuthSP login, backend, signer or licensing database.
Route::get('licensing', function (
    Request $request,
    KslpCustomerWorkspaceQuery $workspace,
    OmniDeskTrialSelfServiceDiscovery $trials,
    PlatformOwnerAccess $ownerAccess,
) {
    $user = $request->user();
    abort_unless($user instanceof User && $user->hasVerifiedEmail(), 403);

    // The owner still has ONE canonical global Licensing Hub and owner step-up.
    if ($ownerAccess->allows($user)) {
        return redirect()->route('operator.kslp');
    }

    $response = Inertia::render('licensing-hub', [
        ...$workspace->forUser($user),
        'omnidesk_trial_organizations' => $trials->forUser($user),
    ])
        ->toResponse($request);
    $response->headers->set('Cache-Control', 'private, no-store');

    return $response;
})->name('licensing.hub');

// Mutating only the one canonical first-party KSLP trial ledger. This route is
// required from web.php inside auth+verified WEB middleware, so Laravel's
// session and CSRF guard apply. No stateless device API bearer is involved.
Route::post('licensing/omnidesk/trial', function (
    Request $request,
    OmniDeskAutomaticTrialProvisioner $provisioner,
    OrganizationCapabilityContext $capabilities,
) {
    $actor = $request->user();
    abort_unless($actor instanceof User && $actor->hasVerifiedEmail(), 403);
    abort_unless(config('omnidesk-licensing.trial_self_service_enabled', false) === true, 503);

    $validated = $request->validate([
        'organization_id' => ['required', 'uuid'],
    ]);
    $organizationId = $validated['organization_id'];
    abort_unless(
        $capabilities->allows((int) $actor->getKey(), $organizationId, 'license.manage'),
        403,
    );

    try {
        $result = $provisioner->provision($actor, $organizationId);
    } catch (DomainException $exception) {
        if ($exception->getMessage() === 'OMNIDESK_TRIAL_FORBIDDEN') {
            abort(403);
        }

        // The UI must not infer a license from an error or from HTTP 200.
        // A policy-disabled or corrupted trial never becomes signed rights.
        return back()->withErrors([
            'trial' => 'OmniDesk trial is unavailable for this organization.',
        ]);
    }

    return redirect()->route('licensing.hub')->with(
        'success',
        $result['already_exists']
            ? 'Existing trial recorded. No new license or device activation was issued.'
            : 'Trial ledger created. Device activation still requires a signed lease.',
    );
})->middleware('throttle:3,1')->name('licensing.omnidesk.trial');
