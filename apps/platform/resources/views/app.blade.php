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

        {{-- Locked KMJ TECHNO favicon generated from the approved KMJ app icon. --}}
        <link rel="icon" type="image/png" sizes="512x512" href="/favicon.png?v=kmj-brand-20261002">
        <link rel="shortcut icon" type="image/png" href="/favicon.png?v=kmj-brand-20261002">
        <link rel="apple-touch-icon" href="/favicon.png?v=kmj-brand-20261002">

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
