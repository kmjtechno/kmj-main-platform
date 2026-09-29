<?php

use App\Models\User;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Inertia\Inertia;

Route::get('operator/kslp', function (Request $request, PlatformOwnerAccess $access, KslpLicenseControlPlane $control) {
    $user = $request->user();
    abort_unless($user instanceof User, 401);
    $access->require($user);

    $licenses = DB::table('kslp_licenses')->latest('created_at')->limit(100)->get()->map(function ($row) use ($control) {
        $license = (array) $row;
        $license['state'] = $control->state((string) $row->id);
        $license['active_activations'] = DB::table('kslp_activations')->where('license_id', $row->id)->whereNull('deactivated_at')->count();

        return $license;
    })->all();

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
