<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Tests\TestCase;

final class StagingAuthenticatedSmokeCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_authenticated_surface_smoke_runs_without_persisting_synthetic_user(): void
    {
        $originalEnvironment = app()->environment();
        $usersBefore = User::query()->count();

        app()->detectEnvironment(static fn (): string => 'staging');

        try {
            $exitCode = Artisan::call('staging:smoke-authenticated-surfaces');
        } finally {
            app()->detectEnvironment(static fn (): string => $originalEnvironment);
        }

        $this->assertSame(0, $exitCode, Artisan::output());
        $this->assertSame($usersBefore, User::query()->count());
    }
}
