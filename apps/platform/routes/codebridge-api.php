<?php

use App\Services\CodeBridge\OAuth\OAuthServer;
use App\Services\Licensing\CodeBridge\CodeBridgeDevicePairingService;
use App\Services\Licensing\CodeBridge\CodeBridgeRenewalService;
use App\Services\Licensing\Kslp\KslpSigner;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

Route::post('v1/codebridge/renew', function (Request $request) {
    if (! config('codebridge.enabled', false)) {
        abort(503);
    }
    if (strlen($request->getContent()) > 4096) {
        abort(413);
    }
    $credential = $request->bearerToken();
    if (! is_string($credential) || strlen($credential) < 32 || strlen($credential) > 4096) {
        abort(401);
    }
    try {
        if (! app()->bound(KslpSigner::class)) {
            abort(503);
        }
        $service = new CodeBridgeRenewalService(DB::connection()->getPdo(), app(KslpSigner::class));
        $token = $service->renew($credential, $request->json()->all(), time());

        return response()->json(['token' => $token])->header('Cache-Control', 'no-store');
    } catch (DomainException) {
        return response()->json(['error' => 'CODEBRIDGE_RENEWAL_DENIED'], 403)->header('Cache-Control', 'no-store');
    } catch (Throwable) {
        return response()->json(['error' => 'CODEBRIDGE_RENEWAL_UNAVAILABLE'], 503)->header('Cache-Control', 'no-store');
    }
})->middleware('throttle:30,1');

Route::post('codebridge/v1/device-enrollments', function (Request $request, CodeBridgeDevicePairingService $pairings) {
    if (! config('codebridge.enabled', false)) {
        abort(503);
    }
    if (strlen($request->getContent()) > 16384) {
        abort(413);
    }
    $v = $request->validate([
        'product' => ['required', 'in:KMJ_CODEBRIDGE'],
        'device.id' => ['required', 'string', 'regex:/\A[A-Za-z0-9_-]{1,64}\z/'],
        'device.name' => ['required', 'string', 'min:1', 'max:128'],
        'device.platform' => ['required', 'string', 'max:32'],
        'device.arch' => ['required', 'string', 'max:32'],
        'project.id' => ['required', 'string', 'regex:/\A[A-Za-z0-9_-]{1,64}\z/'],
        'project.name' => ['required', 'string', 'min:1', 'max:128'],
        'requested_permissions' => ['required', 'array', 'min:1', 'max:3'],
        'requested_permissions.*' => ['required', 'in:read,write,execute'],
        'code_challenge' => ['required', 'string', 'regex:/\A[A-Za-z0-9_-]{43,128}\z/'],
        'code_challenge_method' => ['required', 'in:S256'],
    ]);

    return response()->json($pairings->create($v, time()), 201)->header('Cache-Control', 'no-store');
})->middleware('throttle:10,1');

Route::post('codebridge/v1/device-enrollments/token', function (Request $request, CodeBridgeDevicePairingService $pairings) {
    if (! config('codebridge.enabled', false)) {
        abort(503);
    }
    if (strlen($request->getContent()) > 8192) {
        abort(413);
    }
    $v = $request->validate([
        'product' => ['required', 'in:KMJ_CODEBRIDGE'],
        'device_code' => ['required', 'string', 'min:32', 'max:4096'],
        'code_verifier' => ['required', 'string', 'min:43', 'max:128'],
        'device_id' => ['required', 'string', 'regex:/\A[A-Za-z0-9_-]{1,64}\z/'],
    ]);

    try {
        return response()->json(
            $pairings->redeem($v['device_code'], $v['code_verifier'], $v['device_id'], time())
        )->header('Cache-Control', 'no-store');
    } catch (DomainException $e) {
        $status = match ($e->getMessage()) {
            'CODEBRIDGE_PAIRING_PENDING' => 428,
            'CODEBRIDGE_PAIRING_DENIED' => 403,
            'CODEBRIDGE_PAIRING_EXPIRED', 'CODEBRIDGE_PAIRING_CONSUMED' => 410,
            default => 400,
        };

        return response()->json(['error' => $e->getMessage()], $status)->header('Cache-Control', 'no-store');
    }
})->middleware('throttle:60,1');

Route::post('codebridge/v1/device-credentials/introspect', function (Request $request) {
    if (! config('codebridge.enabled', false)) {
        abort(503);
    }
    $credential = $request->bearerToken();
    if (! is_string($credential) || strlen($credential) < 32 || strlen($credential) > 4096) {
        abort(401);
    }

    $row = DB::table('codebridge_device_credentials as c')
        ->join('kslp_licenses as l', 'l.id', '=', 'c.license_id')
        ->leftJoin('codebridge_device_pairings as p', 'p.activation_id', '=', 'c.activation_id')
        ->where('c.token_hash', hash('sha256', $credential))
        ->whereNull('c.revoked_at')
        ->where('c.expires_at_epoch', '>', time())
        ->where('l.product', 'KMJ_CODEBRIDGE')
        ->where('l.status', 'active')
        ->whereNull('l.revoked_at')
        ->where('l.starts_at', '<=', now())
        ->where('l.expires_at', '>', now())
        ->select(['c.device_id', 'c.tenant_id', 'p.project_id', 'p.requested_permissions'])
        ->first();

    if (! $row) {
        return response()->json(['active' => false], 401)->header('Cache-Control', 'no-store');
    }

    $permissions = [];
    if (is_string($row->requested_permissions) && $row->requested_permissions !== '') {
        try {
            $decoded = json_decode($row->requested_permissions, true, 8, JSON_THROW_ON_ERROR);
            if (is_array($decoded)) {
                $permissions = array_values(array_unique(array_values(array_intersect(
                    ['read', 'write', 'execute'],
                    array_filter($decoded, 'is_string'),
                ))));
            }
        } catch (Throwable) {
            $permissions = [];
        }
    }
    if ($permissions === []) {
        return response()->json(['active' => false], 401)->header('Cache-Control', 'no-store');
    }

    return response()->json([
        'active' => true,
        'device_id' => $row->device_id,
        'tenant_id' => $row->tenant_id,
        'projects' => is_string($row->project_id) && $row->project_id !== '' ? [$row->project_id] : [],
        'permissions' => $permissions,
    ])->header('Cache-Control', 'no-store');
})->middleware('throttle:120,1');

Route::post('codebridge/v1/user-access/introspect', function (
    Request $request,
    OAuthServer $oauth,
    OrganizationDirectory $organizations,
) {
    if (! config('codebridge.enabled', false) || ! $oauth->enabled()) {
        abort(503);
    }
    $token = $request->bearerToken();
    $claims = is_string($token) ? $oauth->verifyAccessToken($token) : null;
    if (! is_array($claims) || ! preg_match('/\Akmj-user:([1-9][0-9]*)\z/D', (string) ($claims['sub'] ?? ''), $match)) {
        return response()->json(['active' => false], 401)->header('Cache-Control', 'no-store');
    }

    $scopePermissions = [];
    foreach (($claims['scopes'] ?? []) as $scope) {
        if (is_string($scope) && str_starts_with($scope, 'codebridge:')) {
            $permission = substr($scope, strlen('codebridge:'));
            if (in_array($permission, ['read', 'write', 'execute'], true)) {
                $scopePermissions[] = $permission;
            }
        }
    }
    $scopePermissions = array_values(array_unique($scopePermissions));
    if ($scopePermissions === []) {
        return response()->json(['active' => false], 403)->header('Cache-Control', 'no-store');
    }

    $userId = (int) $match[1];
    $memberships = collect($organizations->forUser($userId))
        ->filter(fn (array $org): bool => isset($org['id']) && is_string($org['id'])
            && $organizations->userCanManage($userId, $org['id']))
        ->filter(fn (array $org): bool => DB::table('kslp_licenses')
            ->where('customer_id', $org['id'])
            ->where('product', 'KMJ_CODEBRIDGE')
            ->where('status', 'active')
            ->whereNull('revoked_at')
            ->where('starts_at', '<=', now())
            ->where('expires_at', '>', now())
            ->exists())
        ->map(fn (array $org): array => [
            'tenant_id' => $org['id'],
            'permissions' => $scopePermissions,
        ])
        ->values()
        ->all();

    if ($memberships === []) {
        return response()->json(['active' => false], 403)->header('Cache-Control', 'no-store');
    }

    return response()->json([
        'active' => true,
        'user_id' => $claims['sub'],
        'memberships' => $memberships,
    ])->header('Cache-Control', 'no-store');
})->middleware('throttle:120,1');
