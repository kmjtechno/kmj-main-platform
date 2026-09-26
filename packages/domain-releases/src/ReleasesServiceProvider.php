<?php

namespace KMJ\MainPlatform\Releases;

use Illuminate\Support\ServiceProvider;

final class ReleasesServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        $this->loadMigrationsFrom(__DIR__.'/../database/migrations');
    }
}
