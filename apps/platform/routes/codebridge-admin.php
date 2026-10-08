<?php

use App\Models\User;
use App\Services\Licensing\CodeBridge\CodeBridgeDeviceCredentialService;
use App\Services\Licensing\CodeBridge\CodeBridgeDeviceEnrollmentService;
use App\Services\Licensing\CodeBridge\CodeBridgeOwnerTierService;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;
use KMJ\MainPlatform\Catalog\Services\PlanCatalog;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

Route::middleware(['auth', 'verified', 'password.confirm'])
    ->prefix('operator/codebridge')
    ->name('operator.codebridge.')
    ->group(function (): void {
        Route::get('owner-plan', function (Request $request, PlatformOwnerAccess $access, OrganizationDirectory $organizations) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);

            $ownedTenants = collect($organizations->forUser((int) $user->id))
                ->filter(fn (array $org): bool => $organizations->userCanManage((int) $user->id, $org['id']))
                ->pluck('id')
                ->all();

            $licenses = $ownedTenants === [] ? collect() : DB::table('kslp_licenses')
                ->whereIn('customer_id', $ownedTenants)
                ->where('product', 'KMJ_CODEBRIDGE')
                ->orderByDesc('created_at')
                ->get(['id', 'customer_id', 'plan', 'status', 'expires_at', 'revoked_at']);

            return Inertia::render('operator-codebridge-owner', [
                'licenses' => $licenses,
                'limits' => ['devices' => PlanCatalog::CODEBRIDGE_OWNER_DEVICES, 'concurrent_jobs' => PlanCatalog::CODEBRIDGE_OWNER_CONCURRENCY],
            ]);
        })->name('owner-plan');

        Route::post('licenses/owner-tier', function (Request $request, PlatformOwnerAccess $access, OrganizationDirectory $organizations, CodeBridgeOwnerTierService $service) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);
            $v = $request->validate([
                'license_id' => ['required', 'uuid'],
                'tenant_id' => ['required', 'string', 'regex:/\\A[A-Za-z0-9_-]{1,64}\\z/'],
                'confirm' => ['required', 'in:UPGRADE_CODEBRIDGE_OWNER'],
            ]);
            // A platform owner may upgrade only a CodeBridge license owned by their
            // own organization; knowing another tenant's license ID is insufficient.
            abort_unless($organizations->userCanManage((int) $user->id, $v['tenant_id']), 403);

            try {
                $result = $service->upgrade(
                    $v['license_id'],
                    $v['tenant_id'],
                    'platform-owner:'.$user->getKey(),
                );
                if ($request->header('X-Inertia')) {
                    return redirect()->route('operator.codebridge.owner-plan');
                }

                return response()->json($result)->header('Cache-Control', 'no-store');
            } catch (DomainException $e) {
                if ($request->header('X-Inertia')) {
                    return back()->withErrors(['license_id' => $e->getMessage()]);
                }

                return response()->json(['error' => $e->getMessage()], 409)->header('Cache-Control', 'no-store');
            }
        })->name('licenses.owner-tier');

        Route::post('devices/enroll', function (Request $request, PlatformOwnerAccess $access, CodeBridgeDeviceEnrollmentService $service) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);
            $v = $request->validate([
                'license_id' => ['required', 'uuid'],
                'activation_id' => ['required', 'uuid'],
                'tenant_id' => ['required', 'string', 'regex:/\\A[A-Za-z0-9_-]{1,64}\\z/'],
                'device_id' => ['required', 'string', 'regex:/\\A[A-Za-z0-9_-]{1,64}\\z/'],
            ]);
            abort_unless(DB::table('kslp_licenses')->where('id', $v['license_id'])->where('customer_id', $v['tenant_id'])->where('product', 'KMJ_CODEBRIDGE')->exists(), 404);

            try {
                $result = $service->enroll($v['license_id'], $v['activation_id'], $v['tenant_id'], $v['device_id'], time());

                return response()->json($result, 201)->header('Cache-Control', 'no-store');
            } catch (DomainException $e) {
                return response()->json(['error' => $e->getMessage()], 409)->header('Cache-Control', 'no-store');
            }
        })->name('devices.enroll');

        Route::post('devices/rotate', function (Request $request, PlatformOwnerAccess $access, CodeBridgeDeviceCredentialService $service) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);
            $v = $request->validate([
                'license_id' => ['required', 'uuid'],
                'tenant_id' => ['required', 'string', 'regex:/\\A[A-Za-z0-9_-]{1,64}\\z/'],
                'device_id' => ['required', 'string', 'regex:/\\A[A-Za-z0-9_-]{1,64}\\z/'],
            ]);
            abort_unless(DB::table('kslp_licenses')->where('id', $v['license_id'])->where('customer_id', $v['tenant_id'])->where('product', 'KMJ_CODEBRIDGE')->exists(), 404);

            try {
                return response()->json($service->rotate($v['license_id'], $v['tenant_id'], $v['device_id'], time()))
                    ->header('Cache-Control', 'no-store');
            } catch (DomainException $e) {
                return response()->json(['error' => $e->getMessage()], 409)->header('Cache-Control', 'no-store');
            }
        })->name('devices.rotate');

        Route::post('devices/revoke', function (Request $request, PlatformOwnerAccess $access, CodeBridgeDeviceCredentialService $service) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);
            $v = $request->validate([
                'license_id' => ['required', 'uuid'],
                'tenant_id' => ['required', 'string', 'regex:/\\A[A-Za-z0-9_-]{1,64}\\z/'],
                'device_id' => ['required', 'string', 'regex:/\\A[A-Za-z0-9_-]{1,64}\\z/'],
            ]);
            abort_unless(DB::table('kslp_licenses')->where('id', $v['license_id'])->where('customer_id', $v['tenant_id'])->where('product', 'KMJ_CODEBRIDGE')->exists(), 404);

            try {
                $service->revoke($v['license_id'], $v['tenant_id'], $v['device_id'], time());

                return response()->json(['revoked' => true])->header('Cache-Control', 'no-store');
            } catch (DomainException $e) {
                return response()->json(['error' => $e->getMessage()], 409)->header('Cache-Control', 'no-store');
            }
        })->name('devices.revoke');
    });
