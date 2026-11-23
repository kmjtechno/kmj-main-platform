<?php

use App\Models\User;
use App\Services\Licensing\Kslp\KslpDeveloperWorkspaceQuery;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use App\Services\Licensing\OmniDesk\OmniDeskOfferCatalog;
use App\Services\Licensing\UnverifiedAccountCleanup;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use Inertia\Inertia;

Route::get('operator/kslp', function (Request $request, PlatformOwnerAccess $access, KslpLicenseControlPlane $control, KslpDeveloperWorkspaceQuery $developerWorkspace, UnverifiedAccountCleanup $cleanup, OmniDeskOfferCatalog $omniOffers) {
    $user = $request->user();
    abort_unless($user instanceof User, 401);
    $access->require($user);

    $filters = $request->validate([
        'customer_q' => ['sometimes', 'nullable', 'string', 'max:96'],
        'plan' => ['sometimes', 'nullable', 'in:trial,professional,business,enterprise,custom_oem'],
    ]);
    $search = trim((string) ($filters['customer_q'] ?? ''));
    $plan = (string) ($filters['plan'] ?? '');

    // Owner-only name/email lookup. Bound the intermediate account set and
    // never expose account credentials or unrestricted directory results.
    $matchingUserIds = $search !== ''
        ? User::query()
            ->where(function ($query) use ($search) {
                $escaped = addcslashes($search, '%_\\');
                $query->where('name', 'like', '%'.$escaped.'%')
                    ->orWhere('email', 'like', '%'.$escaped.'%');
            })
            ->limit(40)
            ->pluck('id')
            ->all()
        : [];

    $query = DB::table('kslp_licenses')
        ->when($plan !== '', fn ($query) => $query->where('plan', $plan))
        ->when($search !== '', function ($query) use ($search, $matchingUserIds) {
            $escaped = addcslashes($search, '%_\\');
            $query->where(function ($query) use ($search, $escaped, $matchingUserIds) {
                $query->where('customer_id', 'like', '%'.$escaped.'%')
                    ->orWhere('product', 'like', '%'.$escaped.'%')
                    ->orWhereIn('customer_id', $matchingUserIds);
                if (Str::isUuid($search)) {
                    $query->orWhere('id', $search);
                }
            });
        });
    $matchingCount = (clone $query)->count();
    $activationCounts = DB::table('kslp_activations')
        ->whereNull('deactivated_at')
        ->selectRaw('license_id, count(*) as aggregate')
        ->groupBy('license_id')
        ->pluck('aggregate', 'license_id');
    $licenses = $query->latest('created_at')->limit(100)->get()->map(function ($row) use ($control, $activationCounts) {
        $license = (array) $row;
        $license['state'] = $control->state((string) $row->id);
        $license['active_activations'] = (int) $activationCounts->get((string) $row->id, 0);

        return $license;
    })->all();

    // Catalog entitlements and KSLP signed licenses remain distinct records
    // behind the same owner-only administrative view. Never infer a paid plan
    // or grant a signed product license from an entitlement lookup.
    $entitlements = DB::table('entitlements as entitlement')
        ->join('organizations as organization', 'organization.id', '=', 'entitlement.organization_id')
        ->join('products as product', 'product.id', '=', 'entitlement.product_id')
        ->when($search !== '', function ($query) use ($search) {
            $escaped = addcslashes($search, '%_\\');
            $query->where(function ($query) use ($escaped) {
                $query->where('organization.name', 'like', '%'.$escaped.'%')
                    ->orWhere('product.name', 'like', '%'.$escaped.'%')
                    ->orWhere('product.slug', 'like', '%'.$escaped.'%');
            });
        })
        ->orderByDesc('entitlement.created_at')
        ->limit(60)
        ->get([
            'entitlement.id',
            'organization.id as organization_id',
            'organization.name as organization_name',
            'product.slug as product_slug',
            'product.name as product_name',
            'entitlement.capability',
            'entitlement.status',
            'entitlement.starts_at',
            'entitlement.ends_at',
        ]);

    // One commercial KSLP authority, with separate bounded role views.
    // A KSLP license count is NOT a developer issuer subscription count.
    // Owner may inspect issuer organization readiness but this read-only view
    // does not grant a tier, create an app, enable a flag or issue a key.
    $issuerOrganizations = DB::table('organizations as organization')
        ->leftJoin('kslp_issuer_subscriptions as issuer', 'issuer.organization_id', '=', 'organization.id')
        ->orderBy('organization.name')
        ->limit(60)
        ->get([
            'organization.id',
            'organization.name',
            'issuer.tier',
            'issuer.status as issuer_status',
            'issuer.product_limit',
            'issuer.monthly_issue_limit',
            'issuer.current_period_end',
        ]);
    $issuerOrganizationIds = $issuerOrganizations->pluck('id')->all();
    $issuerAppCounts = $issuerOrganizationIds === []
        ? collect()
        : DB::table('kslp_licensed_products')
            ->whereIn('organization_id', $issuerOrganizationIds)
            ->selectRaw('organization_id, count(*) as aggregate')
            ->groupBy('organization_id')
            ->pluck('aggregate', 'organization_id');
    $issuerWorkspaces = $issuerOrganizations->map(function ($organization) use ($issuerAppCounts): array {
        $status = (string) ($organization->issuer_status ?? 'not_subscribed');
        if ($status === 'active' && $organization->current_period_end
            && Carbon::parse($organization->current_period_end)->isPast()) {
            $status = 'expired';
        }

        return [
            'id' => (string) $organization->id,
            'name' => (string) $organization->name,
            'issuer_status' => $status,
            'tier' => $organization->tier === null ? null : (string) $organization->tier,
            'registered_apps' => (int) $issuerAppCounts->get((string) $organization->id, 0),
            'product_limit' => (int) ($organization->product_limit ?? 0),
            'monthly_issue_limit' => (int) ($organization->monthly_issue_limit ?? 0),
            'current_period_end' => $organization->current_period_end,
        ];
    })->all();

    // Non-mutating preview only; a schema/introspection anomaly blocks cleanup,
    // but cannot break the owner license directory.
    $unverified = ['unverified' => User::query()->whereNull('email_verified_at')->count(),
        'eligible' => 0, 'protected' => 0, 'sha256' => '', 'status' => 'ROLLOUT_BLOCKED'];
    // Full schema/FK scans are deliberately NOT run on every owner page
    // while the protected cleanup flag is OFF. Only a bounded count is shown.
    if ((bool) config('services.kmj_unverified_account_cleanup.enabled', false)) {
        try {
            $proof = $cleanup->preview();
            $unverified = [...$proof, 'status' => 'PREVIEW_ONLY'];
            unset($unverified['candidateIds']);
        } catch (Throwable) {
            $unverified['status'] = 'PREVIEW_BLOCKED';
            // Unknown table/FK state can never authorize deletion.
        }
    }

    return Inertia::render('operator-kslp', [
        'metrics' => [
            'licenses' => DB::table('kslp_licenses')->count(),
            'active' => DB::table('kslp_licenses')->where('status', 'active')->count(),
            'trials' => DB::table('kslp_licenses')->where('plan', 'trial')->count(),
            'activations' => DB::table('kslp_activations')->whereNull('deactivated_at')->count(),
            'revoked' => DB::table('kslp_licenses')->whereNotNull('revoked_at')->count(),
            // Effective active issuers: expired subscriptions are not eligible
            // even if the historical status column is still "active".
            'issuerSubscriptions' => DB::table('kslp_issuer_subscriptions')
                ->where('status', 'active')
                ->where(fn ($query) => $query->whereNull('current_period_end')
                    ->orWhere('current_period_end', '>', now()))
                ->count(),
        ],
        'licenses' => $licenses,
        'omnideskOffers' => $omniOffers->preview(),
        'omnideskOfferVersion' => OmniDeskOfferCatalog::VERSION,
        'omnideskReleaseFlags' => [
            'trial' => (bool) config('omnidesk-licensing.trial_self_service_enabled', false),
            'paid' => (bool) config('omnidesk-licensing.live_paid_fulfillment_enabled', false),
            'gateway' => (bool) config('payment-providers.live_charging_enabled', false),
        ],
        'issuerWorkspaces' => $issuerWorkspaces,
        'developerIssuanceEnabled' => Schema::hasTable('kslp_license_keys') && (bool) config('services.kmj_developer_licensing.enabled', false),
        // Reuse exactly the tenant-restricted developer workspace query. Global
        // KSLP data stays owner-only; a commercial lease never becomes an issuer.
        'unverifiedEmailCleanup' => [
            ...$unverified,
            'enabled' => (bool) config('services.kmj_unverified_account_cleanup.enabled', false),
        ],
        'developerWorkspace' => [
            ...$developerWorkspace->forUser($user),
            'canAccessOwnerHub' => true,
            'newKey' => $request->session()->get('developer_license_key'),
            'newKeys' => $request->session()->get('developer_license_batch'),
        ],
        'productEntitlements' => $entitlements,
        'filters' => ['customer_q' => $search, 'plan' => $plan],
        'matchingCount' => $matchingCount,
        'customerOptions' => User::query()
            ->select(['id', 'name', 'email'])
            ->orderByDesc('id')
            ->limit(60)
            ->get()
            ->map(fn (User $customer) => [
                'id' => (string) $customer->id,
                'name' => (string) $customer->name,
                'email' => (string) $customer->email,
            ])
            ->all(),
        'events' => DB::table('kslp_license_events')->latest('created_at')->limit(50)->get(),
    ]);
})->name('operator.kslp')->middleware('password.confirm');

// Owner may prepare price options in the EXISTING canonical Licensing Hub.
// This inserts PAUSED plans only; no publish, private-key access or charge.
Route::post('operator/kslp/omnidesk/offers/prepare', function (
    Request $request,
    PlatformOwnerAccess $access,
    OmniDeskOfferCatalog $catalog,
) {
    $actor = $request->user();
    abort_unless($actor instanceof User, 401);
    $access->require($actor);

    try {
        $result = $catalog->prepare();
    } catch (DomainException) {
        return back()->withErrors([
            'omnidesk_offers' => 'Catalog conflict or missing OmniDesk product. Review the authoritative product and plan records; nothing was partially changed.',
        ]);
    }

    Log::notice('KMJ_OWNER_OMNIDESK_OFFERS_PREPARED_PAUSED', [
        'actor_id' => (int) $actor->getKey(),
        'created' => $result['created'],
        'unchanged' => $result['unchanged'],
        'launch_enabled' => false,
    ]);

    return redirect('/operator/kslp#omnidesk-offers')
        ->with('success', 'OmniDesk INR launch offers prepared as PAUSED. No payment, free rights or signed license enabled.');
})->middleware(['password.confirm', 'throttle:3,1'])
    ->name('operator.kslp.omnidesk.offers.prepare');

// One-click owner-initiated deletion of ONLY exact-preview, old, standalone
// email-unverified accounts. Disabled until protected backup/release approval.
// No blanket DELETE where email_verified_at IS NULL is ever allowed.
Route::post('operator/kslp/unverified-accounts/purge', function (
    Request $request,
    PlatformOwnerAccess $access,
    UnverifiedAccountCleanup $cleanup,
) {
    $actor = $request->user();
    abort_unless($actor instanceof User, 401);
    $access->require($actor);
    abort_unless((bool) config('services.kmj_unverified_account_cleanup.enabled', false), 503);

    $values = $request->validate([
        'confirmation' => ['required', 'in:REMOVE_UNVERIFIED_EMAIL_USERS'],
        'expected' => ['required', 'integer', 'min:0', 'max:100'],
        'sha256' => ['required', 'string', 'regex:/\\A[a-f0-9]{64}\\z/D'],
    ]);
    try {
        $removed = $cleanup->purge((int) $values['expected'], $values['sha256']);
    } catch (RuntimeException) {
        return back()->withErrors([
            'cleanup' => 'Cohort changed or protected account linkage detected. Refresh the preview; no partial deletion.',
        ]);
    }

    Log::notice('KMJ_OWNER_UNVERIFIED_EMAIL_CLEANUP', [
        'actor_id' => (int) $actor->id,
        'deleted_count' => $removed,
        'preview_sha256' => $values['sha256'],
        'email_addresses_logged' => false,
    ]);

    return redirect('/operator/kslp#unverified-accounts')
        ->with('success', "Removed {$removed} eligible old unverified accounts.");
})->middleware(['password.confirm', 'throttle:1,1'])
    ->name('operator.kslp.unverified-cleanup');

Route::post('operator/kslp/licenses', function (Request $request, PlatformOwnerAccess $access, KslpLicenseControlPlane $control) {
    $user = $request->user();
    abort_unless($user instanceof User, 401);
    $access->require($user);
    $v = $request->validate(['customer_id' => ['required', 'string', 'max:128'], 'plan' => ['required', 'in:trial,professional,business,enterprise,custom_oem'], 'reason' => ['required', 'string', 'max:500']]);
    $control->issue($v['customer_id'], $v['plan'], (string) $user->id, $v['reason']);

    return redirect()->route('operator.kslp');
})->name('operator.kslp.issue')->middleware('password.confirm');

Route::post('operator/kslp/licenses/{license}/action', function (Request $request, string $license, PlatformOwnerAccess $access, KslpLicenseControlPlane $control) {
    $user = $request->user();
    abort_unless($user instanceof User, 401);
    $access->require($user);
    $v = $request->validate(['action' => ['required', 'in:revoke,reactivate,renew,change_plan'], 'reason' => ['required', 'string', 'max:500'], 'plan' => ['nullable', 'in:professional,business,enterprise,custom_oem'], 'days' => ['nullable', 'integer', 'min:1', 'max:1095']]);
    match ($v['action']) {
        'revoke' => $control->revoke($license, (string) $user->id, $v['reason']),
        'reactivate' => $control->reactivate($license, (string) $user->id, $v['reason']),
        'renew' => $control->renew($license, Carbon::now()->addDays((int) ($v['days'] ?? 365)), (string) $user->id, $v['reason']),
        default => abort(422),
        'change_plan' => $control->changePlan($license, (string) ($v['plan'] ?? ''), (string) $user->id, $v['reason']),
    };

    return redirect()->route('operator.kslp');
})->name('operator.kslp.action')->middleware('password.confirm');
