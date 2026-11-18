<?php

declare(strict_types=1);

use App\Models\User;
use App\Services\AuthorityBootstrapper;
use App\Services\Licensing\Kslp\KslpDeveloperKeys;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use App\Services\PlatformOwnerAccess;
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
        PlatformOwnerAccess $ownerAccess,
    ) {
        $actor = $request->user();
        abort_unless($actor instanceof User, 401);

        $organizations = collect($directory->forUser($actor->id))
            ->filter(fn (array $org): bool => $capabilities->allows($actor->id, $org['id'], 'license.manage'))
            ->map(function (array $org): array {
                $subscription = DB::table('kslp_issuer_subscriptions')
                    ->where('organization_id', $org['id'])->first();
                if ($subscription === null) {
                    $org['issuer_status'] = 'not_subscribed';
                    $org['product_limit'] = 0;
                    $org['current_period_end'] = null;
                } else {
                    $org['issuer_status'] = (string) $subscription->status;
                    if ($org['issuer_status'] === 'active'
                        && $subscription->current_period_end !== null
                        && now()->greaterThan($subscription->current_period_end)) {
                        $org['issuer_status'] = 'expired';
                    }
                    $org['product_limit'] = (int) $subscription->product_limit;
                    $org['current_period_end'] = $subscription->current_period_end;
                }

                return $org;
            })->values()->all();

        $tenantIds = array_column($organizations, 'id');
        $products = $tenantIds === [] ? [] : DB::table('kslp_licensed_products')
            ->whereIn('organization_id', $tenantIds)
            ->orderBy('created_at', 'desc')
            ->limit(100)
            ->get(['id', 'organization_id', 'product_code', 'name', 'status', 'created_at'])
            ->all();

        // Read-only, aggregate-only device evidence. Never expose device
        // public keys, hardware hashes or idempotency tokens through Inertia.
        // A non-deactivated binding is NOT a live connection, entitlement or
        // proof that an expired/revoked license is usable.
        $bindingCounts = DB::table('kslp_activations')
            ->select('license_id')
            ->selectRaw('COUNT(*) AS recorded_binding_count')
            ->selectRaw('SUM(CASE WHEN deactivated_at IS NULL THEN 1 ELSE 0 END) AS non_deactivated_binding_count')
            ->selectRaw('MAX(activated_at) AS last_activation_at')
            ->groupBy('license_id');

        $storageReady = Schema::hasTable('kslp_license_keys');
        $keys = ($storageReady && $tenantIds !== [])
            ? DB::table('kslp_license_keys as k')
                ->join('kslp_licenses as l', 'l.id', '=', 'k.license_id')
                ->leftJoinSub($bindingCounts, 'bindings', fn ($join) => $join->on('bindings.license_id', '=', 'l.id'))
                ->whereIn('k.organization_id', $tenantIds)
                ->orderBy('k.created_at', 'desc')
                ->limit(100)
                ->get([
                    'k.id', 'k.organization_id', 'k.licensed_product_id',
                    'k.license_id', 'k.display_prefix', 'k.first_activated_at',
                    'k.revoked_at', 'l.plan', 'l.customer_id', 'l.expires_at',
                    'bindings.last_activation_at',
                    DB::raw('COALESCE(bindings.recorded_binding_count, 0) AS recorded_binding_count'),
                    DB::raw('COALESCE(bindings.non_deactivated_binding_count, 0) AS non_deactivated_binding_count'),
                ])->all() : [];

        return Inertia::render('developer-apps', [
            'organizations' => $organizations,
            'applications' => $products,
            'keys' => $keys,
            'canIssueKeys' => $storageReady && (bool) config('services.kmj_developer_licensing.enabled', false),
            'canAccessOwnerHub' => $ownerAccess->allows($actor),
            'newKey' => $request->session()->get('developer_license_key'),
            'newKeys' => $request->session()->get('developer_license_batch'),
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

    // Application code is immutable: existing signed licenses bind to it.
    // A pause closes new trial issuance and online bootstrap-key redemption.
    // Existing offline-signed leases remain subject to their own short expiry.
    Route::post('apps/{app}/manage', function (
        Request $request,
        string $app,
        OrganizationCapabilityContext $capabilities,
        KslpIssuerSubscriptionAuthority $authority,
    ) {
        $actor = $request->user();
        abort_unless($actor instanceof User, 401);
        $data = $request->validate([
            'organization_id' => ['required', 'uuid'],
            'action' => ['required', 'in:rename,pause,resume'],
            'name' => ['required_if:action,rename', 'nullable', 'string', 'min:2', 'max:160'],
            'reason' => ['required', 'string', 'min:8', 'max:240'],
        ]);

        abort_unless(
            $capabilities->allows($actor->id, $data['organization_id'], 'license.manage'),
            403,
        );

        // Emergency pause remains possible even when the rollout switch is
        // disabled; rename and resume may NEVER bypass that owner gate.
        abort_unless(
            $data['action'] === 'pause'
                || (bool) config('services.kmj_developer_licensing.enabled', false),
            503,
        );

        try {
            $authority->manageProduct(
                $data['organization_id'],
                $app,
                $data['action'],
                $data['name'] ?? null,
                $data['reason'],
                (int) $actor->id,
            );
        } catch (DomainException $exception) {
            return back()->withErrors(['action' => $exception->getMessage()]);
        }

        return redirect()->route('developer.apps.index')
            ->with('success', 'Application lifecycle updated.');
    })->middleware(['password.confirm', 'throttle:5,1'])->name('apps.manage');

    // Modern AuthSP-equivalent user journey: bounded, trial-only multi-
    // customer issue. Transactionally all-or-none; never a commercial plan.
    Route::post('keys/batch', function (
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
            'customers' => ['required', 'string', 'max:1400'],
            'reason' => ['required', 'string', 'min:8', 'max:240'],
        ]);
        abort_unless(
            $capabilities->allows($actor->id, $data['organization_id'], 'license.manage'),
            403,
        );

        $customerIds = array_values(array_filter(
            array_map('trim', preg_split('/\r\n|\n|\r/', $data['customers'])),
            fn (string $value): bool => $value !== '',
        ));
        try {
            $issued = $developerKeys->issueTrialBatch(
                $data['organization_id'], $data['product_code'],
                $customerIds, (string) $actor->id, $data['reason'],
            );
        } catch (DomainException $exception) {
            return back()->withErrors(['customers' => $exception->getMessage()]);
        }

        // One-time authorized session flash only. On replay, unique trial
        // constraints fail closed rather than generating a second set of keys.
        return redirect()->route('developer.apps.index')
            ->with('developer_license_batch', $issued);
    })->middleware(['password.confirm', 'throttle:2,1'])->name('keys.batch');

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
