<?php

declare(strict_types=1);

use App\Models\User;
use App\Services\AuthorityBootstrapper;
use App\Services\Licensing\Kslp\KslpDeveloperKeys;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\Schema;
use Inertia\Inertia;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

// Separate from sandbox licensing. No customer licence or private key is
// created merely by viewing the developer portal.
Route::middleware(['auth', 'verified'])->prefix('developer')->name('developer.')->group(function (): void {
    Route::get('apps', function (
        Request $request,
        OrganizationDirectory $directory,
        OrganizationCapabilityContext $capabilities,
    ) {
        $actor = $request->user();
        abort_unless($actor instanceof User, 401);

        $organizations = collect($directory->forUser($actor->id))
            ->filter(fn (array $org): bool => $capabilities->allows($actor->id, $org['id'], 'license.manage'))
            ->map(function (array $org): array {
                $subscription = DB::table('kslp_issuer_subscriptions')
                    ->where('organization_id', $org['id'])->first();
                $org['issuer_status'] = $subscription?->status ?? 'not_subscribed';
                $org['product_limit'] = (int) ($subscription?->product_limit ?? 0);
                $org['current_period_end'] = $subscription?->current_period_end ?? null;

                return $org;
            })->values()->all();

        $tenantIds = array_column($organizations, 'id');
        $products = $tenantIds === [] ? [] : DB::table('kslp_licensed_products')
            ->whereIn('organization_id', $tenantIds)
            ->orderBy('created_at', 'desc')
            ->limit(100)
            ->get(['id', 'organization_id', 'product_code', 'name', 'status', 'created_at'])
            ->all();

        $storageReady = Schema::hasTable('kslp_license_keys');
        $keys = ($storageReady && $tenantIds !== [])
            ? DB::table('kslp_license_keys as k')
                ->join('kslp_licenses as l', 'l.id', '=', 'k.license_id')
                ->whereIn('k.organization_id', $tenantIds)
                ->orderBy('k.created_at', 'desc')
                ->limit(100)
                ->get([
                    'k.id', 'k.organization_id', 'k.licensed_product_id',
                    'k.license_id', 'k.display_prefix', 'k.first_activated_at',
                    'k.revoked_at', 'l.plan', 'l.customer_id', 'l.expires_at',
                ])->all() : [];

        return Inertia::render('developer-apps', [
            'organizations' => $organizations,
            'applications' => $products,
            'keys' => $keys,
            'canIssueKeys' => $storageReady && (bool) config('services.kmj_developer_licensing.enabled', false),
            'newKey' => $request->session()->get('developer_license_key'),
        ]);
    })->name('apps.index');

    Route::post('organizations', function (
        Request $request,
        AuthorityBootstrapper $bootstrapper,
    ) {
        $actor = $request->user();
        abort_unless($actor instanceof User, 401);
        $data = $request->validate(['name' => ['required', 'string', 'min:2', 'max:160']]);
        $bootstrapper->createOrganizationWithSandboxAccess($data['name'], $actor->id);

        return redirect()->route('developer.apps.index');
    })->middleware('throttle:3,1')->name('organizations.store');

    Route::post('apps', function (
        Request $request,
        OrganizationCapabilityContext $capabilities,
        KslpIssuerSubscriptionAuthority $authority,
    ) {
        $actor = $request->user();
        abort_unless($actor instanceof User, 401);
        abort_unless((bool) config('services.kmj_developer_licensing.enabled', false), 503);
        $data = $request->validate([
            'organization_id' => ['required', 'uuid'],
            'product_code' => ['required', 'string', 'regex:/^[A-Z0-9][A-Z0-9_.:-]{2,95}$/'],
            'name' => ['required', 'string', 'min:2', 'max:160'],
        ]);
        abort_unless($capabilities->allows($actor->id, $data['organization_id'], 'license.manage'), 403);

        try {
            $authority->registerProduct($data['organization_id'], $data['product_code'], $data['name']);
        } catch (DomainException $exception) {
            return back()->withErrors(['product_code' => $exception->getMessage()]);
        }

        return redirect()->route('developer.apps.index')->with('success', 'Application registered.');
    })->middleware(['password.confirm', 'throttle:10,1'])->name('apps.store');

    Route::post('keys/{key}/revoke', function (
        Request $request,
        string $key,
        OrganizationCapabilityContext $capabilities,
        KslpLicenseControlPlane $control,
    ) {
        $actor = $request->user();
        abort_unless($actor instanceof User, 401);
        abort_unless((bool) config('services.kmj_developer_licensing.enabled', false), 503);
        abort_unless(Schema::hasTable('kslp_license_keys'), 503);
        $data = $request->validate(['reason' => ['required', 'string', 'min:3', 'max:500']]);

        DB::transaction(function () use ($key, $capabilities, $control, $actor, $data): void {
            $record = DB::table('kslp_license_keys')->where('id', $key)->lockForUpdate()->first();
            abort_unless($record !== null, 404);
            abort_unless($capabilities->allows($actor->id, $record->organization_id, 'license.manage'), 403);
            if ($record->revoked_at !== null) {
                return;
            }

            $control->revoke($record->license_id, (string) $actor->id, $data['reason']);
            DB::table('kslp_license_keys')->where('id', $key)->update([
                'revoked_at' => now(),
                'updated_at' => now(),
            ]);
        }, 3);

        return redirect()->route('developer.apps.index');
    })->middleware(['password.confirm', 'throttle:5,1'])->name('keys.revoke');

    Route::post('keys', function (
        Request $request,
        OrganizationCapabilityContext $capabilities,
        KslpDeveloperKeys $developerKeys,
    ) {
        $actor = $request->user();
        abort_unless($actor instanceof User, 401);
        abort_unless((bool) config('services.kmj_developer_licensing.enabled', false), 503);
        abort_unless(Schema::hasTable('kslp_license_keys'), 503);

        $data = $request->validate([
            'organization_id' => ['required', 'uuid'],
            'product_code' => ['required', 'string', 'max:96'],
            'customer_id' => ['required', 'string', 'min:3', 'max:128'],
            'plan' => ['required', 'in:trial'],
        ]);
        abort_unless($capabilities->allows($actor->id, $data['organization_id'], 'license.manage'), 403);

        try {
            $issued = $developerKeys->issue(
                $data['organization_id'], $data['product_code'],
                $data['customer_id'], $data['plan'], (string) $actor->id,
            );
        } catch (DomainException $exception) {
            return back()->withErrors(['customer_id' => $exception->getMessage()]);
        }

        // Flash exactly once to the authorized issuer; never persist a
        // recoverable plaintext key or include it in the audit log.
        return redirect()->route('developer.apps.index')
            ->with('developer_license_key', $issued);
    })->middleware(['password.confirm', 'throttle:10,1'])->name('keys.store');
});
