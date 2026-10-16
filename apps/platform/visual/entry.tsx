// Development-only renderer. Never registered as a Laravel route or authentication bypass.
import { createInertiaApp } from '@inertiajs/react';
import Welcome from '../resources/js/pages/welcome';
import OperatorCommandOs from '../resources/js/components/operator-command-os';
import '../resources/css/app.css';
const catalog = [
    [
        'kmj-cloudos',
        'KMJ CloudOS',
        'Cloud Platform',
        'Scalable cloud operating platform with unified access and infrastructure control.',
    ],
    [
        'kmj-codebridge',
        'KMJ CodeBridge',
        'Development',
        'Build, deploy and manage web, mobile and desktop apps with powerful tools.',
    ],
    [
        'kmj-omnidesk',
        'KMJ OmniDesk',
        'Remote Access',
        'Secure remote access, device management and virtual workspaces.',
    ],
    [
        'kmj-calibration-pro',
        'KMJ Calibration Pro',
        'Calibration',
        'Advanced calibration, mapping and precision tools for any surface or system.',
    ],
    [
        'kmj-cinema-platform',
        'KMJ Cinema Platform',
        'Immersive',
        'Next-generation media playback for immersive theaters and attractions.',
    ],
    [
        'kmj-forge',
        'KMJ Forge',
        'Engineering',
        'Engineering and build systems for complex, real-world projects.',
    ],
    [
        'kmj-agent',
        'KMJ Agent',
        'AI Systems',
        'Autonomous AI assistants for business, operations and customer support.',
    ],
    [
        'kmj-cloud-nexus',
        'KMJ Cloud Nexus',
        'Cloud Services',
        'Distributed cloud orchestration and multi-region infrastructure.',
    ],
    [
        'kmj-licensing-hub',
        'KMJ Licensing Hub',
        'Licensing',
        'Product access, licensing and entitlement management for all KMJ products.',
    ],
    [
        'kmj-creative-studio',
        'KMJ Creative Studio',
        'Content & Design',
        'Content creation and immersive media tools for next-generation experiences.',
    ],
].map(([slug, name, eyebrow, summary], i) => ({
    id: String(i),
    slug,
    name,
    eyebrow,
    summary,
    status: 'preview',
    lifecycle: 'Preview',
    lifecycle_label: 'Preview',
    is_public: true,
    purchase_enabled: false,
    licensing_enabled: false,
    headline: name,
    proof: [],
    demo: { kind: 'overview', simulation: true, label: 'Preview' },
}));
const owner = location.pathname === '/operator';
void createInertiaApp({
    page: {
        component: owner ? 'operator' : 'welcome',
        props: {
            errors: {},
            auth: {
                user: {
                    id: 1,
                    name: 'Narendra Singh Kushwah',
                    email: 'owner@example.invalid',
                    email_verified_at: null,
                    created_at: '2026-01-01',
                    updated_at: '2026-01-01',
                },
            },
            publicSite: { base_url: 'http://127.0.0.1:4173', indexable: false },
            products: catalog,
            portfolioCount: catalog.length,
            metrics: {
                users: 0,
                organizations: 0,
                entitlements: 0,
                orders: 0,
                confirmed_orders: 0,
            },
            catalogProducts: catalog,
            recentOrders: [],
            missingCanonicalSlugs: [],
        },
        url: location.pathname,
        version: 'locked-ui-visual-fixture',
        clearHistory: false,
        encryptHistory: false,
    },
    resolve: () => (owner ? OperatorCommandOs : Welcome),
});
