<?php

namespace KMJ\MainPlatform\Organizations;

use Illuminate\Support\ServiceProvider;

final class OrganizationsServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        $this->loadMigrationsFrom(__DIR__.'/../database/migrations');
    }
}
