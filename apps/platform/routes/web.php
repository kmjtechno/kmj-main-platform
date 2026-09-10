<?php

use App\Services\AuthorityBootstrapper;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;
use KMJ\MainPlatform\Entitlements\Services\EntitlementReader;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

Route::inertia('/', 'welcome')->name('home');

Route::middleware(['auth', 'verified'])->group(function () {
    Route::get('dashboard', function (
        Request $request,
        OrganizationDirectory $organizations,
        EntitlementReader $entitlements,
    ) {
        $items = collect($organizations->forUser($request->user()->id))
            ->map(function (array $organization) use ($entitlements): array {
                $organization['entitlements'] = $entitlements->forOrganization($organization['id']);

                return $organization;
            })
            ->values()
            ->all();

        return Inertia::render('dashboard', [
            'organizations' => $items,
        ]);
    })->name('dashboard');

    Route::post('organizations', function (Request $request, AuthorityBootstrapper $bootstrapper) {
        $validated = $request->validate([
            'name' => ['required', 'string', 'min:2', 'max:160'],
        ]);

        $bootstrapper->createOrganizationWithSandboxAccess(
            $validated['name'],
            $request->user()->id,
        );

        return redirect()->route('dashboard');
    })->name('organizations.store');
});

require __DIR__.'/settings.php';
