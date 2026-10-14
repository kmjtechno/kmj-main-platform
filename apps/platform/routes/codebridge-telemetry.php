<?php

declare(strict_types=1);

use App\Models\User;
use App\Services\Licensing\CodeBridge\CodeBridgeLocalTelemetry;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;
use KMJ\MainPlatform\Entitlements\Services\EntitlementReader;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

// Included only inside the existing auth+verified session route group.
// Read-only, small cache-backed snapshots; no Ollama or job execution on VPS.
Route::get('services/kmj-codebridge/telemetry', function (
    Request $request,
    OrganizationDirectory $organizations,
    EntitlementReader $entitlements,
    CodeBridgeLocalTelemetry $telemetry,
) {
    $user = $request->user();
    abort_unless($user instanceof User, 401);
    $tenant = $request->query('tenant_id');
    abort_unless(is_string($tenant) && (bool) preg_match('/\A[A-Za-z0-9_-]{1,64}\z/D', $tenant), 404);

    abort_unless(
        collect($organizations->forUser((int) $user->id))
            ->contains(fn (array $org): bool => $org['id'] === $tenant),
        404
    );
    abort_unless(
        collect($entitlements->forOrganization($tenant))
            ->contains(fn (array $item): bool => $item['product_slug'] === 'kmj-codebridge'
                && $item['status'] === 'active'),
        404
    );
    abort_unless(
        DB::table('kslp_licenses')
            ->where('customer_id', $tenant)
            ->where('product', 'KMJ_CODEBRIDGE')
            ->where('status', 'active')
            ->whereNull('revoked_at')
            ->where('starts_at', '<=', now())
            ->where('expires_at', '>', now())
            ->exists(),
        404
    );

    // Credentials are the access boundary. Expired/revoked devices cannot
    // contribute telemetry even when a cached report remains fresh.
    $devices = DB::table('codebridge_device_credentials')
        ->where('tenant_id', $tenant)
        ->whereNull('revoked_at')
        ->where('expires_at_epoch', '>', time())
        ->limit(100)
        ->pluck('device_id')
        ->all();

    return response()->json($telemetry->snapshot($tenant, $devices))
        ->header('Cache-Control', 'no-store, private')
        ->header('X-Content-Type-Options', 'nosniff');
})->name('services.codebridge.telemetry')->middleware('throttle:30,1');
