<?php

use App\Models\User;
use App\Services\AuthorityBootstrapper;
use App\Services\Licensing\SandboxLicenseLifecycle;
use DateTimeImmutable as ImmutableDateTime;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Services\EntitlementReader;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

Route::inertia('/', 'welcome')->name('home');

Route::middleware(['auth', 'verified'])->group(function () {
    Route::get('dashboard', function (
        Request $request,
        OrganizationDirectory $organizations,
        EntitlementReader $entitlements,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $items = collect($organizations->forUser($user->id))
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

    Route::get('sandbox-licenses', function (
        Request $request,
        OrganizationDirectory $organizations,
        EntitlementReader $entitlements,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $items = collect($organizations->forUser($user->id))
            ->map(function (array $organization) use ($entitlements): array {
                $organization['entitlements'] = $entitlements->forOrganization($organization['id']);

                return $organization;
            })
            ->values()
            ->all();

        return Inertia::render('sandbox-licenses', [
            'organizations' => $items,
            'licenseResult' => $request->session()->get('sandbox_license'),
            'validationResult' => $request->session()->get('sandbox_license_validation'),
        ]);
    })->name('sandbox-licenses.index');

    Route::post('organizations', function (Request $request, AuthorityBootstrapper $bootstrapper) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'name' => ['required', 'string', 'min:2', 'max:160'],
        ]);

        $bootstrapper->createOrganizationWithSandboxAccess(
            $validated['name'],
            $user->id,
        );

        return redirect()->route('dashboard');
    })->name('organizations.store');

    Route::post('sandbox-licenses', function (
        Request $request,
        OrganizationDirectory $organizations,
        SandboxLicenseLifecycle $licenses,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'organization_id' => ['required', 'uuid'],
            'entitlement_id' => ['required', 'uuid'],
        ]);

        abort_unless($organizations->userCanManage($user->id, $validated['organization_id']), 403);

        $entitlement = Entitlement::query()
            ->whereKey($validated['entitlement_id'])
            ->where('organization_id', $validated['organization_id'])
            ->where('status', 'active')
            ->firstOrFail();

        $license = $licenses->issue(
            (string) $entitlement->getAttribute('organization_id'),
            (string) $entitlement->getAttribute('product_id'),
            $entitlement->getKey(),
            new ImmutableDateTime('+30 minutes'),
        );

        return redirect()
            ->route('sandbox-licenses.index')
            ->with('sandbox_license', [
                'token' => $license,
                'validation' => $licenses->validate($license),
            ]);
    })->name('sandbox-licenses.store');

    Route::post('sandbox-licenses/validate', function (
        Request $request,
        OrganizationDirectory $organizations,
        SandboxLicenseLifecycle $licenses,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'license' => ['required', 'string', 'max:8192'],
        ]);

        $result = $licenses->validate($validated['license']);
        $organizationId = $result['claims']['organization_id'] ?? null;

        if (is_string($organizationId)) {
            abort_unless($organizations->userCanManage($user->id, $organizationId), 403);
        }

        return redirect()
            ->route('sandbox-licenses.index')
            ->with('sandbox_license_validation', $result);
    })->name('sandbox-licenses.validate');

    Route::post('sandbox-licenses/revoke', function (
        Request $request,
        OrganizationDirectory $organizations,
        SandboxLicenseLifecycle $licenses,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'license' => ['required', 'string', 'max:8192'],
            'reason' => ['nullable', 'string', 'max:255'],
        ]);

        $result = $licenses->validate($validated['license']);
        $claims = $result['claims'];
        $organizationId = is_array($claims) ? ($claims['organization_id'] ?? null) : null;
        $jti = is_array($claims) ? ($claims['jti'] ?? null) : null;

        abort_unless(is_string($organizationId) && is_string($jti), 422);
        abort_unless($organizations->userCanManage($user->id, $organizationId), 403);

        $licenses->revoke($jti, $validated['reason'] ?? null);

        return redirect()
            ->route('sandbox-licenses.index')
            ->with('sandbox_license_validation', $licenses->validate($validated['license']));
    })->name('sandbox-licenses.revoke');
});

require __DIR__.'/settings.php';
