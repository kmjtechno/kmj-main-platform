<?php

use App\Http\Middleware\HandleAppearance;
use App\Http\Middleware\HandleInertiaRequests;
use App\Http\Middleware\SetPreferredLocale;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Middleware\AddLinkHeadersForPreloadedAssets;
use Illuminate\Http\Request;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: [
            __DIR__.'/../routes/web.php',
            __DIR__.'/../routes/commerce-sales.php',
            __DIR__.'/../routes/product-manager.php',
            __DIR__.'/../routes/operator-ops.php',
            __DIR__.'/../routes/kslp-public.php',
            __DIR__.'/../routes/codebridge-oauth.php',
        ],
        api: __DIR__.'/../routes/codebridge-api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        $middleware->encryptCookies(except: ['appearance', 'sidebar_state']);
        // OAuth machine endpoints authenticate by PKCE/refresh token, not cookies.
        $middleware->validateCsrfTokens(except: ['oauth/token', 'oauth/register']);

        $middleware->web(append: [
            HandleAppearance::class,
            SetPreferredLocale::class,
            HandleInertiaRequests::class,
            AddLinkHeadersForPreloadedAssets::class,
        ]);
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->shouldRenderJsonWhen(
            fn (Request $request) => $request->is('api/*') || $request->expectsJson(),
        );
    })->create();
