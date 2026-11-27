<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\User;
use App\Services\Commerce\RefundEntitlementRevoker;
use App\Services\Staff\PlatformStaffAuthority;
use DomainException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;

final class OrderRefundRevokeAccessController extends Controller
{
    public function __invoke(
        Request $request,
        string $order,
        PlatformStaffAuthority $authority,
        RefundEntitlementRevoker $revoker,
    ): JsonResponse|RedirectResponse {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        abort_unless($authority->allows($user, PlatformStaffAuthority::ENTITLEMENT_REVOKE_AFTER_REFUND), 403);

        try {
            $result = $revoker->revoke((int) $user->getKey(), $order);
        } catch (DomainException $e) {
            if ($request->expectsJson()) {
                return response()->json(['code' => $e->getMessage()], 422);
            }

            return back()->withErrors(['refund' => $e->getMessage()]);
        }

        if ($request->expectsJson()) {
            return response()->json($result);
        }

        return back()->with('status', 'refund-access-revoked');
    }
}
