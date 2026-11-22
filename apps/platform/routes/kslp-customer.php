<?php

declare(strict_types=1);

use App\Models\User;
use App\Services\Licensing\Kslp\KslpCustomerWorkspaceQuery;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;

// Already inside the existing auth + verified web route group.
// No independent AuthSP login, backend, signer or licensing database.
Route::get('licensing', function (
    Request $request,
    KslpCustomerWorkspaceQuery $workspace,
    PlatformOwnerAccess $ownerAccess,
) {
    $user = $request->user();
    abort_unless($user instanceof User && $user->hasVerifiedEmail(), 403);

    // The owner still has ONE canonical global Licensing Hub and owner step-up.
    if ($ownerAccess->allows($user)) {
        return redirect()->route('operator.kslp');
    }

    $response = Inertia::render('licensing-hub', $workspace->forUser($user))
        ->toResponse($request);
    $response->headers->set('Cache-Control', 'private, no-store');

    return $response;
})->name('licensing.hub');
