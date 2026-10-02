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
            );
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

        {{-- Approved transparent high-visibility KMJ TECHNO favicon. --}}
        <link rel="icon" type="image/png" sizes="64x64" href="/kmj-favicon-v2-20261002.png">
        <link rel="shortcut icon" type="image/png" href="/kmj-favicon-v2-20261002.png">
        <link rel="apple-touch-icon" href="/assets/brand/kmj-app-icon.png">

        @fonts

        @viteReactRefresh
        @vite(['resources/css/app.css', 'resources/js/app.tsx', "resources/js/pages/{$page['component']}.tsx"])
        <x-inertia::head>
            <title>{{ config('app.name', 'Laravel') }}</title>
        </x-inertia::head>
    </head>
    <body class="font-sans antialiased">
        <x-inertia::app />
    </body>
</html>
