<?php

namespace App\Services\Staging;

use Illuminate\Http\Client\PendingRequest;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use RuntimeException;
use Throwable;

final class ProductionHomeMirror
{
    public const FRESH_CACHE_KEY = 'kmj.staging.production-home.fresh';

    private const LAST_GOOD_CACHE_KEY = 'kmj.staging.production-home.last-good';

    private const STAGING_HOST = 'staging.kmjtechno.com';

    public function shouldMirror(Request $request): bool
    {
        return (bool) config('services.kmj_staging_home_mirror.enabled', false)
            && strtolower($request->getHost()) === self::STAGING_HOST;
    }

    public function render(): string
    {
        return $this->renderPath('/');
    }

    public function renderPath(string $path): string
    {
        $path = $this->normalizePath($path);
        [$freshKey, $lastGoodKey] = $this->cacheKeys($path);
        $fresh = Cache::get($freshKey);

        if (is_string($fresh) && $fresh !== '') {
            return $this->decorate($fresh);
        }

        try {
            $origin = rtrim((string) config('services.kmj_staging_home_mirror.origin'), '/');
            $response = $this->request()->get($origin.$path);

            if (! $response->successful()) {
                throw new RuntimeException('Production site origin returned a non-success response.');
            }

            $html = $response->body();
            if (! str_contains(strtolower($html), '<html') || trim($html) === '') {
                throw new RuntimeException('Production site origin returned invalid HTML.');
            }

            $seconds = max(5, (int) config('services.kmj_staging_home_mirror.cache_seconds', 30));
            Cache::put($freshKey, $html, now()->addSeconds($seconds));
            Cache::forever($lastGoodKey, $html);

            return $this->decorate($html);
        } catch (Throwable $exception) {
            $lastGood = Cache::get($lastGoodKey);
            if (is_string($lastGood) && $lastGood !== '') {
                return $this->decorate($lastGood);
            }

            throw new RuntimeException('Production site mirror is unavailable.', previous: $exception);
        }
    }

    private function request(): PendingRequest
    {
        $request = Http::accept('text/html')
            ->connectTimeout(4)
            ->timeout(10)
            ->retry(2, 250, throw: false)
            ->withHeaders([
                'User-Agent' => 'KMJ Main Platform staging production mirror/1.0',
            ]);

        $originIp = trim((string) config('services.kmj_staging_home_mirror.origin_ip', ''));
        if ($originIp !== '' && defined('CURLOPT_RESOLVE')) {
            $request = $request->withOptions([
                'curl' => [CURLOPT_RESOLVE => ["kmjtechno.com:443:{$originIp}"]],
            ]);
        }

        return $request;
    }

    private function normalizePath(string $path): string
    {
        $path = trim($path);
        if ($path === '') {
            return '/';
        }

        if (! str_starts_with($path, '/') || str_starts_with($path, '//')) {
            throw new RuntimeException('Invalid production mirror path.');
        }

        return $path;
    }

    /** @return array{0: string, 1: string} */
    private function cacheKeys(string $path): array
    {
        if ($path === '/') {
            return [self::FRESH_CACHE_KEY, self::LAST_GOOD_CACHE_KEY];
        }

        $suffix = hash('sha256', $path);

        return [self::FRESH_CACHE_KEY.'.'.$suffix, self::LAST_GOOD_CACHE_KEY.'.'.$suffix];
    }

    private function decorate(string $html): string
    {
        if (! str_contains($html, 'name="kmj-staging-mirror"')) {
            $injection = '<base href="https://staging.kmjtechno.com/">'
                .'<meta name="kmj-staging-mirror" content="production-home">'
                .'<meta name="robots" content="noindex,nofollow">';
            $html = preg_replace('/<head(\s[^>]*)?>/i', '$0'.$injection, $html, 1) ?? $html;
        }

        $html = preg_replace(
            '/(<a\b[^>]*\bhref=["\'])https:\/\/(?:www\.)?kmjtechno\.com(?=\/|["\'])/i',
            '$1https://staging.kmjtechno.com',
            $html,
        ) ?? $html;
        $html = preg_replace(
            '/(<form\b[^>]*\baction=["\'])https:\/\/(?:www\.)?kmjtechno\.com(?=\/|["\'])/i',
            '$1https://staging.kmjtechno.com',
            $html,
        ) ?? $html;

        return $html;
    }
}
