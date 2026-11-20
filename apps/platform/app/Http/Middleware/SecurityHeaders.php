<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Conservative, response-only security headers for every web response.
 *
 * Deliberately NOT a full script/style CSP: Inertia/Vite and the payment-provider checkouts need
 * inline and third-party scripts, so a strict script policy would break the site. This only adds
 * headers that cannot change what a page renders:
 *  - X-Content-Type-Options: nosniff
 *  - Referrer-Policy: strict-origin-when-cross-origin
 *  - Content-Security-Policy: frame-ancestors 'self'; base-uri 'self'; object-src 'none'
 *    (clickjacking / base-tag injection / plugin protection) plus the legacy X-Frame-Options
 *  - Strict-Transport-Security on HTTPS only (180 days, no includeSubDomains, no preload)
 *
 * A header a controller already set is never overridden (the product-media endpoint sets its own
 * sandboxed CSP). Set SECURITY_HEADERS_ENABLED=false to switch the whole middleware off.
 */
final class SecurityHeaders
{
    public const CSP = "frame-ancestors 'self'; base-uri 'self'; object-src 'none'";

    public const HSTS = 'max-age=15552000';

    public function handle(Request $request, Closure $next): Response
    {
        $response = $next($request);

        if (! config('security-headers.enabled', true)) {
            return $response;
        }

        $headers = [
            'X-Content-Type-Options' => 'nosniff',
            'Referrer-Policy' => 'strict-origin-when-cross-origin',
            'X-Frame-Options' => 'SAMEORIGIN',
            'Content-Security-Policy' => self::CSP,
        ];

        if ($request->isSecure()) {
            $headers['Strict-Transport-Security'] = self::HSTS;
        }

        foreach ($headers as $name => $value) {
            if (! $response->headers->has($name)) {
                $response->headers->set($name, $value);
            }
        }

        return $response;
    }
}
