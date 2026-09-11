<?php

namespace App\Providers;

use App\Services\Licensing\LicenseRevoker;
use App\Services\Licensing\LicenseValidator;
use App\Services\Licensing\SandboxLicenseIssuer;
use App\Services\Licensing\SandboxLicenseLifecycle;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Date;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\ServiceProvider;
use Illuminate\Validation\Rules\Password;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        $this->app->singleton(SandboxLicenseIssuer::class, function (): SandboxLicenseIssuer {
            return new SandboxLicenseIssuer($this->sandboxLicenseSecret());
        });

        $this->app->singleton(LicenseValidator::class, function (): LicenseValidator {
            return new LicenseValidator($this->sandboxLicenseSecret());
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
