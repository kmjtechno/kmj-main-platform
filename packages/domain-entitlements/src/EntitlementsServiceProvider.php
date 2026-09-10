<?php

namespace KMJ\MainPlatform\Entitlements;

use Illuminate\Support\ServiceProvider;

final class EntitlementsServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        $this->loadMigrationsFrom(__DIR__.'/../database/migrations');
    }
}
