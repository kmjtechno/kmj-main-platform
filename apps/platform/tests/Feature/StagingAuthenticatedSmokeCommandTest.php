<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Request;
use Illuminate\Routing\RouteCollection;
use Illuminate\Routing\Router;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class StagingAuthenticatedSmokeCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_authenticated_surface_smoke_runs_without_persisting_synthetic_user(): void
    {
        $this->assertSmokeLeavesNoSyntheticData();
    }

    public function test_authenticated_surface_smoke_supports_serialized_cached_routes(): void
    {
        $router = app(Router::class);
        $originalRoutes = $router->getRoutes();
        $this->assertInstanceOf(RouteCollection::class, $originalRoutes);
        $cachedRoutes = new RouteCollection;

        foreach ($originalRoutes as $route) {
            $cachedRoute = clone $route;
            $cachedRoute->prepareForSerialization();
            $cachedRoutes->add($cachedRoute);
        }

        $router->setCompiledRoutes($cachedRoutes->compile());

        try {
            $dashboard = $router->getRoutes()->match(Request::create('/dashboard'));
            $this->assertIsString($dashboard->getAction('uses'));
            $this->assertSmokeLeavesNoSyntheticData();
        } finally {
            $router->setRoutes($originalRoutes);
        }
    }

    private function assertSmokeLeavesNoSyntheticData(): void
    {
        $originalEnvironment = app()->environment();
        $usersBefore = User::query()->count();
        $passkeysBefore = DB::table('passkeys')->count();

        app()->detectEnvironment(static fn (): string => 'staging');

        try {
            $this->artisan('staging:smoke-authenticated-surfaces')
                ->expectsOutput('Authenticated staging surfaces PASS: /dashboard, /operator/ops')
                ->assertSuccessful();
        } finally {
            app()->detectEnvironment(static fn (): string => $originalEnvironment);
        }

        $this->assertSame($usersBefore, User::query()->count());
        $this->assertSame($passkeysBefore, DB::table('passkeys')->count());
    }
}
