<?php

declare(strict_types=1);

use App\Models\User;
use App\Services\AuthorityBootstrapper;
use App\Services\Licensing\Kslp\KslpDeveloperKeys;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use Illuminate\Http\Request;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
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
                if ($subscription === null) {
                    $org['issuer_status'] = 'not_subscribed';
                    $org['product_limit'] = 0;
                    $org['current_period_end'] = null;
                } else {
                    $org['issuer_status'] = (string) $subscription->status;
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
                    'l.status', 'l.grace_until',
                    'l.revoked_at as license_revoked_at',
                ])->map(static function ($key) {
                    // The displayed state is evaluated by the server from
                    // real timestamps: no client-clock guessing or N+1 calls.
                    $now = now();
                    $expiry = Carbon::parse($key->expires_at);
                    if ($key->revoked_at !== null || $key->license_revoked_at !== null || $key->status !== 'active') {
                        $key->display_state = 'REVOKED_OR_SUSPENDED';
                    } elseif ($now->lte($expiry)) {
                        $key->display_state = $now->gte($expiry->copy()->subDays(7))
                            ? 'RENEWAL_DUE' : 'ACTIVE';
                    } elseif ($key->grace_until !== null && $now->lte(Carbon::parse($key->grace_until))) {
                        $key->display_state = 'GRACE';
                    } else {
                        $key->display_state = 'RESTRICTED';
                    }

                    unset($key->license_revoked_at);

                    return $key;
                })->all() : [];

        // Scoped to the visible 100 license keys: never load devices across
        // tenants, expose raw fingerprints/public identities, or query an
        // unbounded global activation directory.
        $licenseIds = array_values(array_map(
            static fn ($key): string => (string) $key->license_id,
            $keys,
        ));
        $activeDevices = $licenseIds === [] ? [] : DB::table('kslp_activations')
            ->whereIn('license_id', $licenseIds)
            ->whereNull('deactivated_at')
            ->orderByDesc('activated_at')
            ->limit(100)
            ->get(['id', 'license_id', 'activated_at'])
            ->all();
        $activeSeatCounts = $licenseIds === [] ? [] : DB::table('kslp_activations')
            ->whereIn('license_id', $licenseIds)
            ->whereNull('deactivated_at')
            ->selectRaw('license_id, count(*) as seats')
            ->groupBy('license_id')
            ->pluck('seats', 'license_id')
            ->map(static fn ($n): int => (int) $n)
            ->all();
        $recentEvents = $licenseIds === [] ? [] : DB::table('kslp_license_events')
            ->whereIn('license_id', $licenseIds)
            ->orderByDesc('created_at')
            ->limit(100)
            ->get(['license_id', 'action', 'created_at'])
            ->all();

        // One-time plaintext bootstrap keys also appear in Inertia props.
        // HTTP no-store alone does not protect client-side navigation history.
        Inertia::encryptHistory();

        $response = Inertia::render('developer-apps', [
            'organizations' => $organizations,
            'applications' => $products,
            'keys' => $keys,
            'activeDevices' => $activeDevices,
            'activeSeatCounts' => $activeSeatCounts,
            'recentEvents' => $recentEvents,
            'canIssueKeys' => $storageReady && (bool) config('services.kmj_developer_licensing.enabled', false),
            'newKey' => $request->session()->get('developer_license_key'),
        ])->toResponse($request);
        // The first-use plaintext bootstrap key is displayed only once.
        // Forbid browser/shared-proxy caching of this sensitive console.
        $response->headers->set('Cache-Control', 'private, no-store, max-age=0');

        return $response;
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
            'product_code' => ['required', 'string', 'regex:/^[A-Z0-9][A-Z0-9_.:-]{2,63}$/D'],
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

    // Device seat recovery is deliberately distinct from license revocation.
    // It never issues/reissues a license, alters payment state or treats a
    // registered device as a signed commercial entitlement.
    Route::post('keys/{key}/devices/{activation}/release', function (
        Request $request,
        string $key,
        string $activation,
        OrganizationCapabilityContext $capabilities,
    ) {
        $actor = $request->user();
        abort_unless($actor instanceof User, 401);
        abort_unless(Str::isUuid($key) && Str::isUuid($activation), 404);
        abort_unless((bool) config('services.kmj_developer_licensing.enabled', false), 503);
        abort_unless(Schema::hasTable('kslp_license_keys'), 503);
        $data = $request->validate([
            'reason' => ['required', 'string', 'min:3', 'max:500', 'regex:/\\S/'],
        ]);

        DB::transaction(function () use ($key, $activation, $capabilities, $actor, $data): void {
            // Lock order is key -> license -> activation, matching issuer
            // actions and preventing seat release racing with activation.
            $record = DB::table('kslp_license_keys')
                ->where('id', $key)->lockForUpdate()->first();
            abort_unless($record !== null, 404);
            abort_unless($capabilities->allows($actor->id, $record->organization_id, 'license.manage'), 403);
            abort_if($record->revoked_at !== null, 409);

            $license = DB::table('kslp_licenses')
                ->where('id', $record->license_id)
                ->lockForUpdate()->first(['id', 'issuer_organization_id', 'revoked_at', 'status']);
            abort_unless($license !== null, 404);
            abort_unless($license->issuer_organization_id === $record->organization_id, 404);
            abort_if($license->revoked_at !== null || $license->status !== 'active', 409);

            $device = DB::table('kslp_activations')
                ->where('id', $activation)
                ->where('license_id', $record->license_id)
                ->lockForUpdate()
                ->first(['id', 'deactivated_at']);
            abort_unless($device !== null, 404);
            if ($device->deactivated_at !== null) {
                return; // Repeat request: no new sequence or audit event.
            }

            $now = now();
            DB::table('kslp_activations')
                ->where('id', $activation)
                ->whereNull('deactivated_at')
                ->update(['deactivated_at' => $now, 'updated_at' => $now]);
            // Bump the server sequence for subsequent verified lease checks.
            // Already-issued offline leases cannot be recalled instantly.
            DB::table('kslp_licenses')->where('id', $record->license_id)
                ->update(['sequence' => DB::raw('sequence + 1'), 'updated_at' => $now]);
            DB::table('kslp_license_events')->insert([
                'license_id' => $record->license_id,
                'actor_id' => (string) $actor->id,
                'action' => 'developer_device_released',
                'reason' => $data['reason'],
                'correlation_id' => (string) Str::uuid(),
                'metadata' => json_encode(['activation_id' => $activation], JSON_THROW_ON_ERROR),
                'created_at' => $now,
            ]);
        }, 3);

        return redirect()->route('developer.apps.index')
            ->with('success', 'Device seat released. Re-activation requires new device proof.');
    })->middleware(['password.confirm', 'throttle:5,1'])->name('keys.devices.release');

    Route::post('keys/{key}/revoke', function (
        Request $request,
        string $key,
        OrganizationCapabilityContext $capabilities,
        KslpLicenseControlPlane $control,
    ) {
        $actor = $request->user();
        abort_unless($actor instanceof User, 401);
        abort_unless(Str::isUuid($key), 404);
        abort_unless((bool) config('services.kmj_developer_licensing.enabled', false), 503);
        abort_unless(Schema::hasTable('kslp_license_keys'), 503);
        $data = $request->validate(['reason' => ['required', 'string', 'min:3', 'max:500', 'regex:/\\S/']]);

        DB::transaction(function () use ($key, $capabilities, $control, $actor, $data): void {
            $record = DB::table('kslp_license_keys')->where('id', $key)->lockForUpdate()->first();
            abort_unless($record !== null, 404);
            abort_unless($capabilities->allows($actor->id, $record->organization_id, 'license.manage'), 403);
            // Verify issuer/tenant linkage under the same lock boundary;
            // a customer-supplied key ID never confers access to a license.
            $license = DB::table('kslp_licenses')
                ->where('id', $record->license_id)
                ->lockForUpdate()
                ->first(['issuer_organization_id']);
            abort_unless($license !== null && $license->issuer_organization_id === $record->organization_id, 404);
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
            'product_code' => ['required', 'string', 'max:64'],
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
