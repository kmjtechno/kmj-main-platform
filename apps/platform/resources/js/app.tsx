import { createInertiaApp } from '@inertiajs/react';
import { Toaster } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { initializeTheme } from '@/hooks/use-appearance';
import AppLayout from '@/layouts/app-layout';
import { isPublicMarketingPage } from '@/lib/public-page-layout';
import AuthLayout from '@/layouts/auth-layout';
import SettingsLayout from '@/layouts/settings/layout';

const appName = import.meta.env.VITE_APP_NAME || 'Laravel';

const buildFingerprint = (doc: Document): string =>
    Array.from(
        doc.querySelectorAll<HTMLElement>(
            'link[href*="/build/assets/"], script[src*="/build/assets/"]',
        ),
    )
        .map(
            (node) =>
                node.getAttribute('href') ?? node.getAttribute('src') ?? '',
        )
        .filter(Boolean)
        .sort()
        .join('|');

const installBuildUpdateWatcher = (): void => {
    if (typeof window === 'undefined') return;

    let currentFingerprint = buildFingerprint(document);
    window.setInterval(async () => {
        if (document.visibilityState !== 'visible') return;

        try {
            const response = await fetch(window.location.href, {
                cache: 'no-store',
            });
            if (!response.ok) return;

            const nextDocument = new DOMParser().parseFromString(
                await response.text(),
                'text/html',
            );
            const nextFingerprint = buildFingerprint(nextDocument);
            if (currentFingerprint && nextFingerprint !== currentFingerprint) {
                window.location.reload();
                return;
            }
            currentFingerprint = nextFingerprint || currentFingerprint;
        } catch {
            // A transient network failure must never interrupt the running app.
        }
    }, 30_000);
};

installBuildUpdateWatcher();

void createInertiaApp({
    title: (title) => (title ? `${title} - ${appName}` : appName),
    layout: (name) => {
        switch (true) {
            case isPublicMarketingPage(name):
                return null;
            case name.startsWith('auth/'):
                return AuthLayout;
            case name.startsWith('settings/'):
                return [AppLayout, SettingsLayout];
            default:
                return AppLayout;
        }
    },
    strictMode: true,
    withApp(app) {
        return (
            <TooltipProvider delayDuration={0}>
                {app}
                <Toaster />
            </TooltipProvider>
        );
    },
    progress: {
        color: '#4B5563',
    },
});

// This will set light / dark mode on load...
initializeTheme();
