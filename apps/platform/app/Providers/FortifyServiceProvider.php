<?php

namespace App\Providers;

/* @chisel-registration */

use App\Actions\Fortify\CreateNewUser;
/* @end-chisel-registration */
use App\Actions\Fortify\ResetUserPassword;
use App\Http\Responses\ConfirmedPasskeyLoginResponse;
use App\Services\Auth\RegistrationBotGuard;
use App\Services\Commerce\CloudOSProductCatalog;
use App\Services\Commerce\ProductSignupEvents;
use App\Services\Commerce\PublicProductCatalog;
use App\Services\Mail\RegistrationMailReadiness;
use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\ServiceProvider;
use Illuminate\Support\Str;
use Illuminate\Validation\Rules\Password;
use Inertia\Inertia;
use Laravel\Fortify\Features;
use Laravel\Fortify\Fortify;
use Laravel\Passkeys\Contracts\PasskeyLoginResponse;

class FortifyServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        //
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        $this->configureActions();
        $this->configureViews();
        $this->configureRateLimiting();
    }

    /**
     * Configure Fortify actions.
     */
    private function configureActions(): void
    {
        Fortify::resetUserPasswordsUsing(ResetUserPassword::class);
        /* @chisel-registration */
        Fortify::createUsersUsing(CreateNewUser::class);
        /* @end-chisel-registration */
    }

    /**
     * Configure Fortify views.
     */
    private function configureViews(): void
    {
        Fortify::loginView(fn (Request $request) => Inertia::render('auth/login', [
            'canResetPassword' => Features::enabled(Features::resetPasswords()),
            'status' => $request->session()->get('status'),
        ]));

        Fortify::resetPasswordView(fn (Request $request) => Inertia::render('auth/reset-password', [
            'email' => $request->email,
            'token' => $request->route('token'),
            'passwordRules' => Password::defaults()->toPasswordRulesString(),
        ]));

        Fortify::requestPasswordResetLinkView(fn (Request $request) => Inertia::render('auth/forgot-password', [
            'status' => $request->session()->get('status'),
            'mailDeliveryAvailable' => ! app()->isProduction()
                || app(RegistrationMailReadiness::class)->canAttemptDelivery(),
        ]));

        /* @chisel-email-verification */
        Fortify::verifyEmailView(fn (Request $request) => Inertia::render('auth/verify-email', [
            'status' => $request->session()->get('status'),
            'mailDeliveryAvailable' => app(RegistrationMailReadiness::class)->canAttemptDelivery(),
        ]));
        /* @end-chisel-email-verification */

        /* @chisel-registration */
        Fortify::registerView(fn () => Inertia::render('auth/register', [
            'signupProduct' => $this->rememberSignupProduct(),
            'passwordRules' => Password::defaults()->toPasswordRulesString(),
            'registrationAvailable' => ! app()->isProduction()
                || app(RegistrationMailReadiness::class)->canAttemptDelivery(),
            'formToken' => app(RegistrationBotGuard::class)->issueToken(),
        ]));
        /* @end-chisel-registration */

        /* @chisel-2fa */
        Fortify::twoFactorChallengeView(fn () => Inertia::render('auth/two-factor-challenge'));
        /* @end-chisel-2fa */

        $this->app->singleton(
            PasskeyLoginResponse::class,
            ConfirmedPasskeyLoginResponse::class,
        );

        /* @chisel-password-confirmation */
        Fortify::confirmPasswordView(fn () => Inertia::render('auth/confirm-password'));
        /* @end-chisel-password-confirmation */
    }

    /**
     * Configure rate limiting.
     */
    private function configureRateLimiting(): void
    {
        /* @chisel-2fa */
        RateLimiter::for('two-factor', function (Request $request) {
            return Limit::perMinute(5)->by($request->session()->get('login.id'));
        });
        /* @end-chisel-2fa */

        // Independent signup quota; no plaintext IP addresses in cache keys.
        RateLimiter::for('public-registration', static function (Request $request) {
            $ipKey = hash('sha256', (string) $request->ip());

            return [
                Limit::perMinute(6)->by('public-registration-minute:'.$ipKey),
                Limit::perHour(30)->by('public-registration-hour:'.$ipKey),
            ];
        });

        // Own bucket for Google sign-in: numeric `throttle:N,M` shares one per-IP counter with every
        // other numeric throttle, so unrelated traffic from the same IP could 429 the OAuth callback.
        RateLimiter::for('google-signin', static function (Request $request) {
            return Limit::perMinute(20)->by('google-signin:'.hash('sha256', (string) $request->ip()));
        });

        RateLimiter::for('onboarding-profile', static function (Request $request) {
            return Limit::perMinute(20)->by('onboarding-profile:'.hash('sha256', (string) ($request->user()?->getKey() ?? $request->ip())));
        });

        RateLimiter::for('login', function (Request $request) {
            $throttleKey = Str::transliterate(Str::lower($request->input(Fortify::username())).'|'.$request->ip());

            return Limit::perMinute(5)->by($throttleKey);
        });

        /* @chisel-passkeys */
        RateLimiter::for('passkeys', function (Request $request) {
            return Limit::perMinute(10)->by(
                ($request->input('credential.id') ?: $request->session()->getId()).'|'.$request->ip(),
            );
        });
        /* @end-chisel-passkeys */
    }

    /**
     * Keep the product from /register?product=… through password or Google
     * sign-up. Only a public product is remembered.
     *
     * @return array{name: string, kind: string}|null
     */
    private function rememberSignupProduct(): ?array
    {
        $slug = request()->query('product');

        if (! is_string($slug) || strlen($slug) > 96) {
            return null;
        }

        $product = app(PublicProductCatalog::class)->find($slug);

        if ($product === null) {
            return null;
        }

        request()->session()->put(ProductSignupEvents::SESSION_KEY, $slug);

        $purchasable = ($product['purchase_enabled'] ?? false) === true;
        $trial = $slug === CloudOSProductCatalog::SLUG
            && $purchasable
            && config('services.kmj_signup_trial.enabled');

        return [
            'name' => (string) $product['name'],
            'kind' => $trial ? 'trial' : ($purchasable ? 'request' : 'preregister'),
        ];
    }
}
