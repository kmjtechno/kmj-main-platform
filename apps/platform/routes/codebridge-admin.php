<?php

use App\Models\User;
use App\Services\Licensing\CodeBridge\CodeBridgeDeviceCredentialService;
use App\Services\Licensing\CodeBridge\CodeBridgeDeviceEnrollmentService;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;

Route::middleware(['auth', 'verified', 'password.confirm'])
    ->prefix('operator/codebridge')
    ->name('operator.codebridge.')
    ->group(function (): void {
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
