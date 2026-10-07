<?php

namespace App\Http\Middleware;

use App\Models\User;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Inertia\Middleware;

class HandleInertiaRequests extends Middleware
{
    /**
     * The root template that's loaded on the first page visit.
     *
     * @see https://inertiajs.com/server-side-setup#root-template
     *
     * @var string
     */
    protected $rootView = 'app';

    /**
     * Determines the current asset version.
     *
     * @see https://inertiajs.com/server-side-setup#asset-versioning
     */
    public function version(Request $request): ?string
    {
        return parent::version($request);
    }

    /**
     * Define the props that are shared by default.
     *
     * @see https://inertiajs.com/shared-data
     *
     * @return array<string, mixed>
     */
    public function share(Request $request): array
    {
        $user = $request->user();
        $locale = app()->getLocale();
        $switchLocale = $locale === 'hi' ? 'en' : 'hi';
        $path = $request->getPathInfo();
        $unprefixedPath = preg_replace('#^/(en|hi)(?=/|$)#', '', $path) ?: '/';
        $switchPath = '/'.$switchLocale.($unprefixedPath === '/' ? '/' : $unprefixedPath);
        $switchQuery = $request->query();
        unset($switchQuery['lang']);
        $switchUrl = $switchPath.($switchQuery === [] ? '' : '?'.http_build_query($switchQuery));

        return [
            ...parent::share($request),
            'name' => config('app.name'),
            'publicSite' => [
                'base_url' => rtrim((string) config('app.url'), '/'),
                'indexable' => (bool) config('app.public_indexing', false),
            ],
            'localization' => [
                'locale' => $locale,
                'supported' => ['en', 'hi'],
                'switch_locale' => $switchLocale,
                'switch_label' => $switchLocale === 'hi' ? 'हिंदी' : 'English',
                'switch_url' => $switchUrl,
            ],
            'auth' => [
                'user' => $user,
            ],
            'operator' => [
                'enabled' => $user instanceof User && app(PlatformOwnerAccess::class)->allows($user),
            ],
            'flash' => [
                'sandbox_license' => fn () => $request->session()->get('sandbox_license'),
                'sandbox_license_validation' => fn () => $request->session()->get('sandbox_license_validation'),
            ],
            'sidebarOpen' => ! $request->hasCookie('sidebar_state') || $request->cookie('sidebar_state') === 'true',
        ];
    }
}
