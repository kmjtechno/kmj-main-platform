<?php

namespace App\Providers;

use App\Contracts\Events\OutboxPublisher;
use App\Services\AiProviders\DashboardAiProviderScope;
use App\Services\AiProviders\ResolvesAiProviderScope;
use App\Services\Events\LaravelEventOutboxPublisher;
use App\Services\Events\TransactionalOutbox;
use App\Services\Licensing\LicenseRevoker;
use App\Services\Licensing\LicenseValidator;
use App\Services\Licensing\RustSandboxLicenseVerifier;
use App\Services\Licensing\SandboxLicenseIssuer;
use App\Services\Licensing\SandboxLicenseLifecycle;
use App\Services\Licensing\SandboxLicenseValidationEngine;
use App\Services\Mail\BrandedAuthNotifications;
use Carbon\CarbonImmutable;
use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Contracts\Foundation\Application;
use Illuminate\Support\Facades\Date;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\ServiceProvider;
use Illuminate\Validation\Rules\Password;
use Illuminate\Http\Request;
use KMJ\MainPlatform\Commerce\Contracts\DomainEventRecorder as CommerceDomainEventRecorder;
use KMJ\MainPlatform\Entitlements\Contracts\DomainEventRecorder as EntitlementDomainEventRecorder;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        $this->app->singleton(TransactionalOutbox::class);
        $this->app->bind(ResolvesAiProviderScope::class, DashboardAiProviderScope::class);
        $this->app->bind(OutboxPublisher::class, LaravelEventOutboxPublisher::class);
        $this->app->bind(CommerceDomainEventRecorder::class, fn (Application $app): TransactionalOutbox => $app->make(TransactionalOutbox::class));
        $this->app->bind(EntitlementDomainEventRecorder::class, fn (Application $app): TransactionalOutbox => $app->make(TransactionalOutbox::class));

        $this->app->singleton(SandboxLicenseIssuer::class, function (): SandboxLicenseIssuer {
            return new SandboxLicenseIssuer($this->sandboxLicenseSecret());
        });

        $this->app->singleton(LicenseValidator::class, function (): LicenseValidator {
            return new LicenseValidator($this->sandboxLicenseSecret());
        });

        $this->app->singleton(RustSandboxLicenseVerifier::class, function (): RustSandboxLicenseVerifier {
            return new RustSandboxLicenseVerifier(
                (string) config('services.kmj_sandbox_licensing.rust_verifier_binary', ''),
                $this->sandboxLicenseSecret(),
                (float) config('services.kmj_sandbox_licensing.rust_verifier_timeout', 5),
            );
        });

        $this->app->singleton(SandboxLicenseValidationEngine::class, function (Application $app): SandboxLicenseValidationEngine {
            return new SandboxLicenseValidationEngine(
                $app->make(LicenseValidator::class),
                $app->make(RustSandboxLicenseVerifier::class),
                (string) config('services.kmj_sandbox_licensing.validation_engine', 'php'),
            );
        });

        $this->app->singleton(LicenseRevoker::class);
        $this->app->singleton(SandboxLicenseLifecycle::class);
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        $this->configureDefaults();
        $this->configureCodeBridgeEnrollmentLimiter();
        BrandedAuthNotifications::register();
    }

    /**
     * Configure default behaviors for production-ready applications.
     */
    protected function configureDefaults(): void
    {
        Date::use(CarbonImmutable::class);

        DB::prohibitDestructiveCommands(
            app()->isProduction(),
        );

        Password::defaults(fn (): ?Password => app()->isProduction()
            ? Password::min(12)
                ->mixedCase()
                ->letters()
                ->numbers()
                ->symbols()
                ->uncompromised()
            : null,
        );
    }

    /**
     * Rate-limit anonymous first-party device enrollment by BOTH remote source
     * and the requested device ID. IP-only 10/min conflates independent P520
     * projects behind the same office or reverse-proxy address. Retain an
     * independent IP-wide abuse ceiling; malformed IDs stay in a strict shared
     * per-IP bucket and never bypass rate-limiting.
     */
    private function configureCodeBridgeEnrollmentLimiter(): void
    {
        RateLimiter::for('codebridge-device-enrollment', function (Request $request): array {
            // Never use untrusted Forwarded headers directly as a limiter key:
            // rely on Laravel's configured and verified proxy trust boundary.
            $ipHash = hash('sha256', (string) ($request->ip() ?? 'unknown'));
            $rawId = $request->input('device.id');
            $id = is_string($rawId) && preg_match('/\\A[A-Za-z0-9_-]{1,64}\\z/D', $rawId) === 1
                ? $rawId
                : null;

            return [
                Limit::perMinute(120)->by('cb-enroll:ip:'.$ipHash),
                Limit::perMinute(10)->by($id !== null
                    ? 'cb-enroll:device:'.$ipHash.':'.hash('sha256', $id)
                    : 'cb-enroll:invalid:'.$ipHash),
            ];
        });
    }

    private function sandboxLicenseSecret(): string
    {
        $configured = trim((string) config('services.kmj_sandbox_licensing.secret', ''));

        if ($configured !== '') {
            return $configured;
        }

        $appKey = (string) config('app.key');

        return hash('sha256', 'kmj-main-platform:sandbox-license:'.$appKey);
    }
}
