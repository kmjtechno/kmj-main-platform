<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Routing\Middleware\ThrottleRequests;
use Symfony\Component\HttpFoundation\Response;

/**
 * Protect only the built-in Fortify signup endpoint, including direct HTTP posts.
 *
 * No change to customer login, webhook callbacks, passkeys or OAuth flows.
 */
final class ThrottlePublicRegistration
{
    public function handle(Request $request, Closure $next): Response
    {
        if (! $request->isMethod('POST') || ! $request->is('register')) {
            return $next($request);
        }

        return app(ThrottleRequests::class)->handle(
            $request,
            $next,
            'public-registration',
        );
    }
}
