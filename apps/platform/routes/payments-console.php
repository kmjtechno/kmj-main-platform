<?php

use App\Models\User;
use App\Services\Payments\PaymentGatewayReadiness;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;

Route::middleware(['auth', 'verified', 'password.confirm'])
    ->prefix('operator')
    ->name('operator.')
    ->group(function (): void {
        Route::get('payments', function (
            Request $request,
            PlatformOwnerAccess $access,
            PaymentGatewayReadiness $readiness,
        ) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);

            return Inertia::render('operator-payments', [
                'paymentReadiness' => $readiness->snapshot(),
            ]);
        })->name('payments.index');
    });
