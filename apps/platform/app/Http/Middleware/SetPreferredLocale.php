<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\App;
use Symfony\Component\HttpFoundation\Response;

class SetPreferredLocale
{
    /**
     * @var array<int, string>
     */
    private const SUPPORTED_LOCALES = ['en', 'hi'];

    public function handle(Request $request, Closure $next): Response
    {
        $requestedLocale = $request->query('lang');
        $cookieLocale = $request->cookie('kmj_locale');

        $locale = $this->resolveLocale(
            is_string($requestedLocale) ? $requestedLocale : null,
            is_string($cookieLocale) ? $cookieLocale : null,
        );

        App::setLocale($locale);

        $response = $next($request);

        if (
            is_string($requestedLocale)
            && in_array($requestedLocale, self::SUPPORTED_LOCALES, true)
            && $requestedLocale !== $cookieLocale
        ) {
            $response->headers->setCookie(cookie(
                'kmj_locale',
                $locale,
                525600,
                '/',
                null,
                $request->isSecure(),
                true,
                false,
                'lax',
            ));
        }

        return $response;
    }

    private function resolveLocale(?string $requestedLocale, ?string $cookieLocale): string
    {
        if (in_array($requestedLocale, self::SUPPORTED_LOCALES, true)) {
            return $requestedLocale;
        }

        if (in_array($cookieLocale, self::SUPPORTED_LOCALES, true)) {
            return $cookieLocale;
        }

        $configuredLocale = (string) config('app.locale', 'en');

        return in_array($configuredLocale, self::SUPPORTED_LOCALES, true)
            ? $configuredLocale
            : 'en';
    }
}
