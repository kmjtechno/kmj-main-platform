<?php

use App\Models\User;
use App\Services\Payments\OwnerPaymentGatewaySettings;
use App\Services\Payments\PaymentGatewayReadiness;
use App\Services\Payments\PaymentGatewaySandboxProbe;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\Schema;
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
                'gatewaySettings' => app(OwnerPaymentGatewaySettings::class)->snapshot(),
            ]);
        })->name('payments.index');

        Route::put('payments/gateways/{provider}', function (
            Request $request,
            string $provider,
            PlatformOwnerAccess $access,
            OwnerPaymentGatewaySettings $settings,
        ) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);
            abort_unless(in_array($provider, ['cashfree', 'razorpay'], true), 404);
            abort_unless(Schema::hasTable('payment_gateway_settings'), 503, 'Gateway settings storage is not ready.');

            $input = $request->validate([
                'environment' => ['required', 'in:sandbox'],
                'merchant_status' => ['required', 'in:not_verified,verification_pending,owner_reports_approved'],
                'international_requested' => ['required', 'boolean'],
                'client_id' => ['nullable', 'string', 'max:255', 'not_regex:/[\x00-\x1F\x7F]/'],
                'client_secret' => ['nullable', 'string', 'max:1024', 'not_regex:/[\x00-\x1F\x7F]/'],
                'webhook_secret' => ['nullable', 'string', 'max:1024', 'not_regex:/[\x00-\x1F\x7F]/'],
            ]);
            if ($provider === 'razorpay'
                && isset($input['client_id'])
                && $input['client_id'] !== ''
                && ! preg_match('/\\Arzp_test_[A-Za-z0-9]+\\z/D', $input['client_id'])) {
                return back()->withErrors(['client_id' => 'Only Razorpay test keys may be saved here.']);
            }

            $settings->save($user, $provider, $input);

            return redirect()->route('operator.payments.index')
                ->with('success', 'Sandbox settings stored. Provider connection and checkout remain unverified.');
        })->name('payments.settings.update')->middleware('throttle:10,1');

        Route::post('payments/gateways/{provider}/webhook-secret', function (
            Request $request,
            string $provider,
            PlatformOwnerAccess $access,
            OwnerPaymentGatewaySettings $settings,
        ) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);
            abort_unless($provider === 'razorpay', 404);
            abort_unless(Schema::hasTable('payment_gateway_settings'), 503, 'Gateway settings storage is not ready.');

            // Shown once in the console and held only in page memory: JSON, never the session.
            return response()
                ->json(['webhook_secret' => $settings->generateWebhookSecret($user, $provider)])
                ->header('Cache-Control', 'no-store, private');
        })->name('payments.webhook-secret.generate')->middleware('throttle:5,1');

        Route::post('payments/gateways/{provider}/test-connection', function (
            Request $request,
            string $provider,
            PlatformOwnerAccess $access,
            PaymentGatewaySandboxProbe $probe,
        ) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);
            abort_unless(in_array($provider, ['cashfree', 'razorpay'], true), 404);
            abort_unless(Schema::hasTable('payment_gateway_settings'), 503, 'Gateway settings storage is not ready.');

            $input = $request->validate([
                'test_phone' => $provider === 'cashfree'
                    ? ['required', 'regex:/^[6-9][0-9]{9}$/']
                    : ['nullable', 'regex:/^[6-9][0-9]{9}$/'],
            ]);

            try {
                // This is a provider SANDBOX INR 1 order, with NO payment or license.
                $probe->run($user, $provider, $input['test_phone'] ?? null);
            } catch (DomainException|InvalidArgumentException) {
                return back()->withErrors([
                    'sandbox_probe' => 'Sandbox connection could not be verified. Check test keys and provider access.',
                ]);
            }

            return redirect()->route('operator.payments.index')
                ->with('success', 'Sandbox test order created. No payment captured and no license issued.');
        })->name('payments.sandbox.test')->middleware('throttle:3,10');

        Route::delete('payments/gateways/{provider}/credentials', function (
            Request $request,
            string $provider,
            PlatformOwnerAccess $access,
            OwnerPaymentGatewaySettings $settings,
        ) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);
            abort_unless(in_array($provider, ['cashfree', 'razorpay'], true), 404);
            abort_unless(Schema::hasTable('payment_gateway_settings'), 503, 'Gateway settings storage is not ready.');

            $settings->revoke($user, $provider);

            return redirect()->route('operator.payments.index')
                ->with('success', 'Stored sandbox credentials revoked.');
        })->name('payments.settings.revoke')->middleware('throttle:10,1');
    });
