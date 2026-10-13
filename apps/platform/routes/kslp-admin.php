<?php

use App\Models\User;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Carbon;
use Illuminate\Support\Str;
use Illuminate\Support\Facades\DB;
use Inertia\Inertia;

Route::get('operator/kslp', function (Request $request, PlatformOwnerAccess $access, KslpLicenseControlPlane $control) {
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

    return Inertia::render('operator-kslp', [
        'metrics' => [
            'licenses' => DB::table('kslp_licenses')->count(),
            'active' => DB::table('kslp_licenses')->where('status', 'active')->count(),
            'trials' => DB::table('kslp_licenses')->where('plan', 'trial')->count(),
            'activations' => DB::table('kslp_activations')->whereNull('deactivated_at')->count(),
            'revoked' => DB::table('kslp_licenses')->whereNotNull('revoked_at')->count(),
            'issuerSubscriptions' => DB::table('kslp_issuer_subscriptions')->where('status', 'active')->count(),
        ],
        'licenses' => $licenses,
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
