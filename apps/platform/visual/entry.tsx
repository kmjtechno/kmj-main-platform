// Development-only renderer. Never registered as a Laravel route or authentication bypass.
import { createInertiaApp } from '@inertiajs/react';
import Welcome from '../resources/js/pages/welcome';
import OperatorCommandOs from '../resources/js/components/operator-command-os';
import OwnerModuleShell from '../resources/js/layouts/owner-module-shell';
import OperatorOps from '../resources/js/pages/operator-ops';
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
const ownerOps = location.pathname === '/operator/ops';

const owner = ['/operator', '/super-admin'].includes(location.pathname);
void createInertiaApp({
    page: {
        component: ownerOps ? 'operator-ops' : owner ? 'operator' : 'welcome',
        props: {
            errors: {},
            // Landing is a signed-out customer preview; owner routes use
            // synthetic session data. Never authenticate or persist a user.
            auth: {
                user:
                    owner || ownerOps
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
            operator: { enabled: owner || ownerOps },
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
        url: location.pathname,
        version: 'locked-ui-visual-fixture',
        clearHistory: false,
        encryptHistory: false,
    },
    resolve: () =>
        ownerOps ? OwnerOpsPreview : owner ? OperatorCommandOs : Welcome,
});
