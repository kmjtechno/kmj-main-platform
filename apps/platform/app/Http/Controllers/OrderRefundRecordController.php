<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\User;
use App\Services\Commerce\OrderRefundRecorder;
use App\Services\Staff\PlatformStaffAuthority;
use DomainException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;

final class OrderRefundRecordController extends Controller
{
    public function __invoke(
        Request $request,
        string $order,
        PlatformStaffAuthority $authority,
        OrderRefundRecorder $recorder,
    ): JsonResponse|RedirectResponse {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        abort_unless($authority->allows($user, PlatformStaffAuthority::BILLING_REFUND_RECORD), 403);

        $data = $request->validate([
            'amount_minor' => ['required', 'integer', 'min:1'],
            'reason' => ['required', 'string', 'max:240'],
            'request_key' => ['required', 'string', 'min:8', 'max:120'],
            'provider_refund_reference' => ['nullable', 'string', 'max:120'],
        ]);

        try {
            $result = $recorder->record(
                (int) $user->getKey(),
                $order,
                (int) $data['amount_minor'],
                (string) $data['reason'],
                (string) $data['request_key'],
                $data['provider_refund_reference'] ?? null,
            );
        } catch (DomainException $e) {
            if ($request->expectsJson()) {
                return response()->json(['code' => $e->getMessage()], 422);
            }

            return back()->withErrors(['refund' => $e->getMessage()]);
        }

        if ($request->expectsJson()) {
            return response()->json($result, $result['reused'] ? 200 : 201);
        }

        return back()->with('status', 'refund-recorded');
    }
}
