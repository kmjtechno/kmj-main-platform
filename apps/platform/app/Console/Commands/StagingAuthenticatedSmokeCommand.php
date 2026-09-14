<?php

namespace App\Console\Commands;

use App\Models\User;
use Illuminate\Console\Command;
use Illuminate\Http\Request;
use Illuminate\Routing\Router;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Inertia\Response as InertiaResponse;
use RuntimeException;
use Throwable;

final class StagingAuthenticatedSmokeCommand extends Command
{
    protected $signature = 'staging:smoke-authenticated-surfaces';

    protected $description = 'Exercise authenticated staging dashboard and operator surfaces without persisting smoke data';

    public function handle(Router $router): int
    {
        if (! app()->environment('staging')) {
            $this->error('This command is restricted to APP_ENV=staging.');

            return self::FAILURE;
        }

        DB::beginTransaction();

        try {
            $user = User::query()->create([
                'name' => 'KMJ staging smoke owner',
                'email' => 'staging-smoke-'.bin2hex(random_bytes(8)).'@invalid.kmj',
                'password' => Hash::make(bin2hex(random_bytes(24))),
            ]);
            $user->forceFill([
                'email_verified_at' => now(),
                'is_platform_owner' => true,
                'platform_owner_granted_at' => now(),
            ])->save();

            DB::table('passkeys')->insert([
                'user_id' => $user->getKey(),
                'name' => 'Staging smoke passkey',
                'credential_id' => 'staging-smoke-'.bin2hex(random_bytes(16)),
                'credential' => '{}',
                'created_at' => now(),
                'updated_at' => now(),
            ]);

            $this->probe($router, '/dashboard', $user);
            $this->probe($router, '/operator/ops', $user);

            $this->info('Authenticated staging surfaces PASS: /dashboard, /operator/ops');

            return self::SUCCESS;
        } catch (Throwable $exception) {
            report($exception);
            $this->error(sprintf(
                'Authenticated staging surface smoke failed with %s: %s',
                $exception::class,
                $exception->getMessage(),
            ));

            return self::FAILURE;
        } finally {
            DB::rollBack();
        }
    }

    private function probe(Router $router, string $uri, User $user): void
    {
        $request = Request::create($uri, 'GET', server: [
            'HTTP_X_INERTIA' => 'true',
            'HTTP_ACCEPT' => 'text/html,application/xhtml+xml',
        ]);
        $request->setUserResolver(static fn (): User => $user);

        $route = $router->getRoutes()->match($request);
        $request->setRouteResolver(static fn () => $route);

        $action = $route->getAction('uses');
        if (! is_callable($action)) {
            throw new RuntimeException("Smoke route {$uri} does not have a callable action.");
        }

        $previousRequest = app('request');
        $previousTypedRequest = app(Request::class);
        app()->instance('request', $request);
        app()->instance(Request::class, $request);

        try {
            $result = app()->call($action, ['request' => $request]);
        } catch (Throwable $exception) {
            throw new RuntimeException(
                sprintf(
                    'Smoke route %s execution failed with %s: %s',
                    $uri,
                    $exception::class,
                    $exception->getMessage(),
                ),
                previous: $exception,
            );
        } finally {
            app()->instance('request', $previousRequest);
            app()->instance(Request::class, $previousTypedRequest);
        }

        if (! $result instanceof InertiaResponse) {
            throw new RuntimeException("Smoke route {$uri} did not return an Inertia response.");
        }

        $response = $result->toResponse($request);
        if ($response->getStatusCode() >= 400) {
            throw new RuntimeException("Smoke route {$uri} returned HTTP {$response->getStatusCode()}.");
        }
    }
}
