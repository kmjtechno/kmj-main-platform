import AppLayout from '../resources/js/layouts/app-layout';
import DeveloperApps from '../resources/js/pages/developer-apps';
// Development-only renderer. Never registered as a Laravel route or authentication bypass.
import { createInertiaApp, usePage } from '@inertiajs/react';
import type { ManagedProduct } from '../resources/js/components/operator-product-manager';
import Welcome from '../resources/js/pages/welcome';
import Operator from '../resources/js/pages/operator';
import OperatorProducts from '../resources/js/pages/operator-products';
import OwnerModuleShell from '../resources/js/layouts/owner-module-shell';
import OperatorOps from '../resources/js/pages/operator-ops';
import CodeBridgeService from '../resources/js/pages/services/codebridge';
import { workspaceProps } from './workspace-fixture';
import CodeBridgeWorkspace from '../resources/js/pages/services/codebridge-workspace';
import OperatorCodeBridgeOwner from '../resources/js/pages/operator-codebridge-owner';
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

/**
 * Local browser fixture for the real guarded Operations page and its shared
 * owner shell. All telemetry is explicitly synthetic/unverified; no Laravel,
 * credentials, remote health checks, API calls, or commercial actions.
 */
function OwnerOpsPreview() {
    const unknownBackup = {
        status: 'unknown',
        completed_at: null,
        age_hours: null,
        max_age_hours: 24,
        git_sha: null,
    };
    return (
        <OwnerModuleShell>
            <OperatorOps
                snapshot={{
                    captured_at: '2026-01-01T00:00:00Z',
                    environment: 'synthetic-preview',
                    deployed_sha: null,
                    cpu: {
                        cores: 0,
                        load_1m: 0,
                        load_5m: 0,
                        load_15m: 0,
                        load_percent_estimate: 0,
                    },
                    memory: {
                        total_bytes: 0,
                        used_bytes: 0,
                        available_bytes: 0,
                        used_percent: 0,
                    },
                    disk: {
                        total_bytes: 0,
                        used_bytes: 0,
                        free_bytes: 0,
                        used_percent: 0,
                    },
                    uptime_seconds: null,
                    php: {
                        memory_usage_bytes: 0,
                        memory_peak_bytes: 0,
                        memory_limit: 'unknown',
                    },
                    database: { status: 'unknown' },
                    failed_jobs: 0,
                    queue_restart_at: null,
                }}
                readiness={{
                    deployment: {
                        status: 'unknown',
                        deployed_sha: null,
                        database_status: 'unknown',
                        evidence: 'synthetic-preview',
                    },
                    backups: {
                        daily: unknownBackup,
                        weekly: unknownBackup,
                        monthly: unknownBackup,
                    },
                    autonomous_worker: {
                        status: 'unknown',
                        source: 'synthetic-preview',
                        execution_gate: 'unknown',
                        write_gate: 'unknown',
                        live_run_observed: false,
                    },
                    free_ai_router: {
                        status: 'unknown',
                        policy: 'no credential',
                        configured_provider_count: 0,
                        configured_providers: [],
                        live_route_observed: false,
                        paid_fallback: false,
                    },
                    compliance_guard: {
                        status: 'unknown',
                        mode: 'synthetic-preview',
                        provider_policy_enforcement: 'off',
                        legal_interpretation: false,
                        signals: [],
                    },
                }}
                outbox={{
                    status: 'unknown',
                    max_attempts: 0,
                    pending: 0,
                    due: 0,
                    retrying: 0,
                    exhausted: 0,
                    published: 0,
                    recent_exhausted: [],
                }}
                recentActions={[]}
            />
        </OwnerModuleShell>
    );
}
function OwnerDevicesPreview() {
    return (
        <OwnerModuleShell>
            <OperatorCodeBridgeOwner
                endpoint="http://127.0.0.1:4173/mcp"
                licenses={[]}
                limits={{ devices: 2147483647, concurrent_jobs: 16 }}
                organizations={[
                    {
                        id: 'qa-preview-organization',
                        name: 'Synthetic preview organization',
                        plan: null,
                        deviceLimit: null,
                        managedCount: 1,
                        canManage: false,
                        devices: [
                            {
                                id: 'qa-preview-desktop',
                                name: 'Synthetic preview desktop',
                                platform: 'windows',
                                arch: 'x64',
                                projects: [
                                    {
                                        id: 'qa-preview-project',
                                        name: 'Synthetic preview project',
                                    },
                                ],
                                registration: 'registered',
                                connection_status: 'not_verified',
                            },
                        ],
                    },
                ]}
            />
        </OwnerModuleShell>
    );
}
function WorkspacePreview() {
    // Synthetic props only (visual/workspace-fixture.ts); they follow Inertia page updates.
    return (
        <CodeBridgeWorkspace
            {...(usePage().props as unknown as React.ComponentProps<
                typeof CodeBridgeWorkspace
            >)}
        />
    );
}
function CanonicalDevicesPreview() {
    return (
        <CodeBridgeService
            organization={{
                id: 'qa-preview-organization',
                name: 'Synthetic preview organization',
                role: 'owner',
            }}
            entitlement={{
                id: 'qa-preview-entitlement',
                capability: 'codebridge',
                status: 'active',
                starts_at: '2026-01-01',
            }}
            canManageOwnerPlan={true}
            canManageDevices={false}
            service={{
                endpoint: 'http://127.0.0.1:4173/mcp',
                oauth_ready: false,
                plan: null,
                license_status: 'unverified',
                license_starts_at: null,
                license_expires_at: null,
                permissions: [],
                device_limit: null,
                managed_devices: 1,
                pending_pairings: 0,
                connected_clients: [],
                access_token_ttl_seconds: 0,
                devices: [
                    {
                        id: 'qa-preview-desktop',
                        name: 'Synthetic preview desktop',
                        platform: 'windows',
                        arch: 'x64',
                        projects: [
                            {
                                id: 'qa-preview-project',
                                name: 'Synthetic preview project',
                            },
                        ],
                        registration: 'registered',
                        connection_status: 'not_verified',
                    },
                ],
            }}
        />
    );
}

function OwnerDashboardPreview() {
    return (
        <Operator
            ownerView={
                location.pathname === '/super-admin'
                    ? 'dashboard'
                    : 'command-center'
            }
            metrics={{
                users: 0,
                organizations: 0,
                entitlements: 0,
                orders: 0,
                confirmed_orders: 0,
                confirmed_inr_revenue_minor: 0,
            }}
            catalogProducts={catalog.map((product) => ({
                ...product,
                active_policy_count: 0,
                active_entitlement_count: 0,
            }))}
            canonicalProductCount={catalog.length}
            missingCanonicalSlugs={[]}
            recentOrders={[]}
        />
    );
}
function OwnerDeveloperPreview() {
    return (
        <AppLayout>
            <DeveloperApps
                organizations={[]}
                applications={[]}
                keys={[]}
                canIssueKeys={false}
                newKey={null}
            />
        </AppLayout>
    );
}
function OwnerProductsPreview() {
    const previewProducts = usePage().props.previewProducts as
        | ManagedProduct[]
        | undefined;
    return (
        <OwnerModuleShell>
            <OperatorProducts
                products={
                    previewProducts ??
                    catalog.map((product, index) => ({
                        ...product,
                        id:
                            '00000000-0000-4000-8000-' +
                            String(index + 1).padStart(12, '0'),
                        category: 'developer',
                        lifecycle: 'planned',
                        sort_order: (index + 1) * 10,
                        image_path: '/assets/locked/landing-hero.webp',
                        content: null,
                    }))
                }
                generation={{
                    text_configured:
                        new URLSearchParams(location.search).get(
                            'syntheticCloud',
                        ) === '1',
                    image_configured: true,
                }}
            />
        </OwnerModuleShell>
    );
}
const workspace = location.pathname === '/services/kmj-codebridge/workspace';
const canonicalDevices = location.pathname === '/services/kmj-codebridge';
const ownerProducts = location.pathname === '/operator/products';
const ownerDeveloper = location.pathname === '/developer/apps';
const ownerDevices = location.pathname === '/operator/codebridge/owner-plan';
const ownerOps = location.pathname === '/operator/ops';

const owner = ['/operator', '/super-admin'].includes(location.pathname);
void createInertiaApp({
    page: {
        component: workspace
            ? 'services/codebridge-workspace'
            : canonicalDevices
              ? 'services/codebridge'
              : ownerProducts
                ? 'operator-products'
                : ownerOps
                  ? 'operator-ops'
                  : ownerDevices
                    ? 'operator-codebridge-owner'
                    : ownerDeveloper
                      ? 'developer-apps'
                      : owner
                        ? 'operator'
                        : 'welcome',
        props: {
            errors: {},
            ...(workspace ? workspaceProps() : {}),
            // Landing is a signed-out customer preview; owner routes use
            // synthetic session data. Never authenticate or persist a user.
            auth: {
                user:
                    workspace ||
                    canonicalDevices ||
                    owner ||
                    ownerOps ||
                    ownerDevices ||
                    ownerDeveloper ||
                    ownerProducts
                        ? {
                              id: 1,
                              name: 'KMJ QA Owner',
                              email: 'owner@example.invalid',
                              email_verified_at: null,
                              created_at: '2026-01-01',
                              updated_at: '2026-01-01',
                          }
                        : null,
            },
            operator: {
                enabled:
                    owner ||
                    ownerOps ||
                    ownerDevices ||
                    ownerDeveloper ||
                    ownerProducts,
            },
            localization: {
                locale: 'en',
                switch_url: '/?lang=hi',
                switch_label: 'हिंदी',
            },
            publicSite: {
                base_url: 'http://127.0.0.1:4173',
                indexable: false,
                registration_available: false,
            },
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
        url: location.pathname + location.search,
        version: 'locked-ui-visual-fixture',
        clearHistory: false,
        encryptHistory: false,
    },
    resolve: () =>
        workspace
            ? WorkspacePreview
            : canonicalDevices
              ? CanonicalDevicesPreview
              : ownerProducts
                ? OwnerProductsPreview
                : ownerDeveloper
                  ? OwnerDeveloperPreview
                  : ownerOps
                    ? OwnerOpsPreview
                    : ownerDevices
                      ? OwnerDevicesPreview
                      : owner
                        ? OwnerDashboardPreview
                        : Welcome,
});
