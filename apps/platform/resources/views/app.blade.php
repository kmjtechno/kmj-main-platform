<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}" @class(['dark' => ($appearance ?? 'system') == 'dark'])>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">

        @php
            $publicIndexableRoute = request()->routeIs(
                'home',
                'company',
                'capabilities',
                'products.*',
                'trust',
                // All legal/policy pages listed in the public sitemap must
                // follow the same explicit production indexing gate.
                'legal.*',
            );
            // Public-only source metadata: used on the initial document response
            // without spinning up a second Node/SSR process or querying secrets.
            $initialSeo = app(\\App\\Services\\Seo\\PublicInitialMetadata::class)
                ->forPage($page, (string) config('app.url'));
        @endphp
        @unless (config('app.public_indexing', false) && $publicIndexableRoute)
            <meta name="robots" content="noindex,nofollow">
        @endunless

        {{-- Inline script to detect system dark mode preference and apply it immediately --}}
        <script>
            (function() {
                const appearance = '{{ $appearance ?? "system" }}';

                if (appearance === 'system') {
                    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

                    if (prefersDark) {
                        document.documentElement.classList.add('dark');
                    }
                }
            })();
        </script>

        {{-- Inline style to set the HTML background color based on our theme in app.css --}}
        <style>
            html {
                background-color: oklch(1 0 0);
            }

            html.dark {
                background-color: oklch(0.145 0 0);
            }
        </style>

        <link rel="icon" href="/favicon-contrast-v1.svg" type="image/svg+xml" sizes="any">
        <link rel="apple-touch-icon" href="/apple-touch-icon.png">

        @fonts

        @viteReactRefresh
        @vite(['resources/css/app.css', 'resources/js/app.tsx', "resources/js/pages/{$page['component']}.tsx"])
        {{-- Fallback metadata is crawlable before React hydrates; PublicSeo owns
             subsequent Inertia navigation using the same canonical facts. --}}
        @if ($initialSeo)
            <meta name="description" content="{{ $initialSeo['description'] }}">
            <link rel="canonical" href="{{ $initialSeo['canonical'] }}">
            <meta property="og:title" content="{{ $initialSeo['title'] }}">
            <meta property="og:description" content="{{ $initialSeo['description'] }}">
            <meta property="og:type" content="{{ $initialSeo['type'] }}">
            <meta property="og:url" content="{{ $initialSeo['canonical'] }}">
            <meta property="og:image" content="{{ $initialSeo['image'] }}">
            <meta name="twitter:card" content="summary_large_image">
            <meta name="twitter:title" content="{{ $initialSeo['title'] }}">
            <meta name="twitter:description" content="{{ $initialSeo['description'] }}">
            <meta name="twitter:image" content="{{ $initialSeo['image'] }}">
        @endif
        <x-inertia::head>
            <title>{{ $initialSeo['title'] ?? config('app.name', 'KMJ TECHNO') }}</title>
        </x-inertia::head>
    </head>
    <body class="font-sans antialiased">
        <x-inertia::app />
    </body>
</html>
