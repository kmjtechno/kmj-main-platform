import { Head, router } from '@inertiajs/react';
import OperatorModuleNavigation from '@/components/operator-module-navigation';
import {
    Activity,
    ArchiveRestore,
    Bot,
    CloudCog,
    Database,
    HardDrive,
    MemoryStick,
    RefreshCw,
    RotateCw,
    Server,
    ShieldCheck,
    ShieldEllipsis,
    TriangleAlert,
} from 'lucide-react';
import { useEffect, useState } from 'react';

type OpsSnapshot = {
    captured_at: string;
    environment: string;
    deployed_sha: string | null;
    cpu: {
        cores: number;
        load_1m: number;
        load_5m: number;
        load_15m: number;
        load_percent_estimate: number;
    };
    memory: {
        total_bytes: number;
        used_bytes: number;
        available_bytes: number;
        used_percent: number;
    };
    disk: {
        total_bytes: number;
        used_bytes: number;
        free_bytes: number;
        used_percent: number;
    };
    uptime_seconds: number | null;
    php: {
        memory_usage_bytes: number;
        memory_peak_bytes: number;
        memory_limit: string;
    };
    database: { status: string };
    failed_jobs: number;
    queue_restart_at: number | null;
};

type BackupStatus = {
    status: string;
    completed_at: string | null;
    age_hours: number | null;
    max_age_hours: number;
    git_sha: string | null;
};

type ComplianceSignal = {
    code: string;
    status: string;
    value: number | null;
    unit: string;
    warning_threshold?: number;
    critical_threshold?: number;
};

type OperationalReadiness = {
    deployment: {
        status: string;
        deployed_sha: string | null;
        database_status: string;
        evidence: string;
    };
    backups: Record<'daily' | 'weekly' | 'monthly', BackupStatus>;
    autonomous_worker: {
        status: string;
        source: string;
        execution_gate: string;
        write_gate: string;
        live_run_observed: boolean;
    };
    free_ai_router: {
        status: string;
        policy: string;
        configured_provider_count: number;
        configured_providers: string[];
        live_route_observed: boolean;
        paid_fallback: boolean;
    };
    compliance_guard: {
        status: string;
        mode: string;
        provider_policy_enforcement: string;
        legal_interpretation: boolean;
        signals: ComplianceSignal[];
    };
};

type ActionAudit = {
    id: number;
    actor_user_id: number;
    action: string;
    outcome: string;
    created_at: string | null;
};

type OutboxHealth = {
    status: string;
    max_attempts: number;
    pending: number;
    due: number;
    retrying: number;
    exhausted: number;
    published: number;
    recent_exhausted: Array<{
        id: string;
        event_type: string;
        aggregate_type: string;
        aggregate_id: string;
        organization_id: string | null;
        attempts: number;
        last_error: string | null;
        occurred_at: string | null;
        updated_at: string | null;
    }>;
};

type Props = {
    snapshot: OpsSnapshot;
    readiness: OperationalReadiness;
    outbox: OutboxHealth;
    recentActions: ActionAudit[];
};

function bytes(value: number): string {
    if (value <= 0) {
        return '0 B';
    }

    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const index = Math.min(
        Math.floor(Math.log(value) / Math.log(1024)),
        units.length - 1,
    );

    return `${(value / 1024 ** index).toFixed(index >= 3 ? 1 : 0)} ${units[index]}`;
}

function uptime(seconds: number | null): string {
    if (seconds === null) {
        return 'Unavailable';
    }

    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    return `${days}d ${hours}h ${minutes}m`;
}

function statusTone(status: string): string {
    if (['healthy', 'fresh', 'enabled'].includes(status)) {
        return 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300';
    }

    if (['critical', 'degraded', 'invalid'].includes(status)) {
        return 'border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-300';
    }

    return 'border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300';
}

function StatusPill({ status }: { status: string }) {
    return (
        <span
            className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-black tracking-wide uppercase ${statusTone(status)}`}
        >
            {status.replaceAll('_', ' ')}
        </span>
    );
}

function Gauge({ value }: { value: number }) {
    const width = Math.min(100, Math.max(0, value));

    return (
        <div className="bg-muted mt-4 h-2 overflow-hidden rounded-full">
            <div
                className="h-full rounded-full bg-red-500 transition-[width] duration-500"
                style={{ width: `${width}%` }}
            />
        </div>
    );
}

function MetricCard({
    icon: Icon,
    label,
    value,
    detail,
    gauge,
}: {
    icon: typeof Activity;
    label: string;
    value: string;
    detail: string;
    gauge?: number;
}) {
    return (
        <div className="bg-card rounded-2xl border p-5">
            <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground text-xs font-bold tracking-wide uppercase">
                    {label}
                </span>
                <Icon className="h-4 w-4 text-red-500" />
            </div>
            <div className="mt-3 text-3xl font-black tracking-tight">
                {value}
            </div>
            <div className="text-muted-foreground mt-1 text-xs">{detail}</div>
            {gauge !== undefined ? <Gauge value={gauge} /> : null}
        </div>
    );
}

function ReadinessCard({
    icon: Icon,
    label,
    status,
    detail,
    children,
}: {
    icon: typeof Activity;
    label: string;
    status: string;
    detail: string;
    children?: React.ReactNode;
}) {
    return (
        <div className="bg-card rounded-2xl border p-5">
            <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-red-500" />
                    <span className="text-xs font-black tracking-wide uppercase">
                        {label}
                    </span>
                </div>
                <StatusPill status={status} />
            </div>
            <p className="text-muted-foreground mt-3 text-xs leading-5">
                {detail}
            </p>
            {children}
        </div>
    );
}

function backupDetail(backup: BackupStatus): string {
    if (backup.age_hours === null) {
        return 'No verified success marker yet';
    }

    return `${backup.age_hours.toFixed(1)}h old · freshness window ${backup.max_age_hours}h`;
}

export default function OperatorOps({
    snapshot,
    readiness,
    recentActions,
    outbox,
}: Props) {
    const [refreshing, setRefreshing] = useState(false);
    const [restarting, setRestarting] = useState(false);

    const refresh = () => {
        setRefreshing(true);
        router.reload({
            only: ['snapshot', 'readiness', 'outbox', 'recentActions'],
            onFinish: () => setRefreshing(false),
        });
    };

    useEffect(() => {
        const timer = window.setInterval(() => {
            router.reload({
                only: ['snapshot', 'readiness', 'outbox', 'recentActions'],
            });
        }, 15_000);

        return () => window.clearInterval(timer);
    }, []);

    const restartQueue = () => {
        if (
            !window.confirm(
                'Restart queue workers? Running jobs are allowed to finish before workers restart.',
            )
        ) {
            return;
        }

        setRestarting(true);
        router.post(
            '/operator/ops/actions/queue-restart',
            {},
            {
                preserveScroll: true,
                onFinish: () => setRestarting(false),
            },
        );
    };

    const databaseHealthy = snapshot.database.status === 'healthy';
    const providers = readiness.free_ai_router.configured_providers;

    return (
        <>
            <Head title="Ops Command Center" />
            <div className="flex h-full flex-1 flex-col gap-6 overflow-x-auto p-4 sm:p-6">
                <section className="from-background via-background overflow-hidden rounded-2xl border bg-gradient-to-br to-red-950/10 p-6 sm:p-8">
                    <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
                        <div className="max-w-3xl">
                            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/5 px-3 py-1 text-xs font-bold text-emerald-600 dark:text-emerald-400">
                                <ShieldCheck className="h-3.5 w-3.5" />
                                Platform Owner · passkey gated · safe actions
                                only
                            </div>
                            <h1 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl">
                                KMJ Ops Command Center
                            </h1>
                            <p className="text-muted-foreground mt-3 max-w-2xl text-sm leading-6">
                                Real server telemetry, evidence-based readiness
                                and audited recovery controls. Unknown external
                                state stays explicitly unobserved instead of
                                being guessed.
                            </p>
                        </div>
                        <button
                            type="button"
                            onClick={refresh}
                            disabled={refreshing}
                            className="hover:bg-muted inline-flex items-center justify-center gap-2 rounded-xl border px-4 py-3 text-xs font-bold transition disabled:opacity-50"
                        >
                            <RefreshCw
                                className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`}
                            />
                            Refresh now
                        </button>
                    </div>
                </section>

                <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <MetricCard
                        icon={Activity}
                        label="CPU load estimate"
                        value={`${snapshot.cpu.load_percent_estimate.toFixed(1)}%`}
                        detail={`${snapshot.cpu.cores} cores · load ${snapshot.cpu.load_1m} / ${snapshot.cpu.load_5m} / ${snapshot.cpu.load_15m}`}
                        gauge={snapshot.cpu.load_percent_estimate}
                    />
                    <MetricCard
                        icon={MemoryStick}
                        label="RAM allocation"
                        value={`${snapshot.memory.used_percent.toFixed(1)}%`}
                        detail={`${bytes(snapshot.memory.used_bytes)} / ${bytes(snapshot.memory.total_bytes)}`}
                        gauge={snapshot.memory.used_percent}
                    />
                    <MetricCard
                        icon={HardDrive}
                        label="Disk capacity"
                        value={`${snapshot.disk.used_percent.toFixed(1)}%`}
                        detail={`${bytes(snapshot.disk.used_bytes)} used · ${bytes(snapshot.disk.free_bytes)} free`}
                        gauge={snapshot.disk.used_percent}
                    />
                    <MetricCard
                        icon={Database}
                        label="Database"
                        value={databaseHealthy ? 'Healthy' : 'Degraded'}
                        detail={`${snapshot.failed_jobs} failed queue job${snapshot.failed_jobs === 1 ? '' : 's'}`}
                    />
                </section>

                <section>
                    <div className="mb-3 flex items-end justify-between gap-3">
                        <div>
                            <h2 className="font-black">
                                Readiness & guardrails
                            </h2>
                            <p className="text-muted-foreground mt-1 text-xs">
                                Evidence only. External systems are never marked
                                healthy unless this runtime can actually observe
                                them.
                            </p>
                        </div>
                        <StatusPill
                            status={readiness.compliance_guard.status}
                        />
                    </div>
                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <ReadinessCard
                            icon={Server}
                            label="Deployment"
                            status={readiness.deployment.status}
                            detail="Local deployed SHA plus database health. GitHub workflow state is validated by the deployment pipeline, not fabricated here."
                        >
                            <div className="text-muted-foreground mt-3 font-mono text-[10px] break-all">
                                {readiness.deployment.deployed_sha ??
                                    'SHA unavailable'}
                            </div>
                        </ReadinessCard>
                        <ReadinessCard
                            icon={Bot}
                            label="Autonomous worker"
                            status={readiness.autonomous_worker.status}
                            detail="Execution lives in GitHub Actions. This VPS reports only gates available to its own runtime."
                        >
                            <div className="text-muted-foreground mt-3 text-[11px]">
                                execution{' '}
                                {readiness.autonomous_worker.execution_gate} ·
                                write {readiness.autonomous_worker.write_gate}
                            </div>
                        </ReadinessCard>
                        <ReadinessCard
                            icon={CloudCog}
                            label="Free AI router"
                            status={readiness.free_ai_router.status}
                            detail="Strict verified-zero policy remains enforced. Credential presence is shown without revealing any credential value."
                        >
                            <div className="text-muted-foreground mt-3 text-[11px]">
                                {providers.length > 0
                                    ? `${providers.length} configured: ${providers.join(', ')}`
                                    : 'No provider credential observed by this app'}
                            </div>
                        </ReadinessCard>
                        <ReadinessCard
                            icon={ShieldEllipsis}
                            label="Compliance guard"
                            status={readiness.compliance_guard.status}
                            detail="Internal operational thresholds only. Provider legal-policy enforcement stays off until approved policy rules exist."
                        >
                            <div className="text-muted-foreground mt-3 text-[11px]">
                                provider rules:{' '}
                                {
                                    readiness.compliance_guard
                                        .provider_policy_enforcement
                                }
                            </div>
                        </ReadinessCard>
                    </div>
                </section>

                <section className="bg-card rounded-2xl border p-5 sm:p-6">
                    <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
                        <div>
                            <div className="flex items-center gap-2">
                                <RotateCw className="h-4 w-4 text-red-500" />
                                <h2 className="font-bold">
                                    Transactional outbox
                                </h2>
                            </div>
                            <p className="text-muted-foreground mt-1 text-xs leading-5">
                                Pending delivery, scheduled retry and
                                exhausted-message state from the durable event
                                outbox.
                            </p>
                        </div>
                        <StatusPill status={outbox.status} />
                    </div>

                    <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                        {[
                            ['Pending', outbox.pending],
                            ['Due now', outbox.due],
                            ['Retrying', outbox.retrying],
                            ['Exhausted', outbox.exhausted],
                            ['Published', outbox.published],
                        ].map(([label, value]) => (
                            <div
                                key={String(label)}
                                className="rounded-xl border p-4"
                            >
                                <div className="text-muted-foreground text-[10px] font-black tracking-wide uppercase">
                                    {label}
                                </div>
                                <div className="mt-2 text-2xl font-black">
                                    {value}
                                </div>
                            </div>
                        ))}
                    </div>

                    {outbox.recent_exhausted.length > 0 ? (
                        <div className="mt-5 overflow-hidden rounded-xl border">
                            <div className="border-b px-4 py-3 text-xs font-black">
                                Recent exhausted messages
                            </div>
                            <div className="divide-y">
                                {outbox.recent_exhausted.map((message) => (
                                    <div
                                        key={message.id}
                                        className="grid gap-1 px-4 py-3 text-xs md:grid-cols-[1fr_1fr_auto]"
                                    >
                                        <div>
                                            <div className="font-black">
                                                {message.event_type}
                                            </div>
                                            <div className="text-muted-foreground mt-1 font-mono text-[10px]">
                                                {message.aggregate_type}:
                                                {message.aggregate_id}
                                            </div>
                                        </div>
                                        <div className="text-muted-foreground">
                                            {message.last_error ??
                                                'No failure detail recorded'}
                                        </div>
                                        <div className="font-black">
                                            {message.attempts}/
                                            {outbox.max_attempts}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : null}
                </section>

                <section className="bg-card rounded-2xl border p-5 sm:p-6">
                    <div className="flex items-center gap-2">
                        <ArchiveRestore className="h-4 w-4 text-red-500" />
                        <h2 className="font-bold">Backup freshness evidence</h2>
                    </div>
                    <p className="text-muted-foreground mt-1 text-xs leading-5">
                        A marker is written only after encrypted remote upload
                        succeeds. Missing markers are shown as unknown/missing,
                        never assumed healthy.
                    </p>
                    <div className="mt-5 grid gap-3 md:grid-cols-3">
                        {(['daily', 'weekly', 'monthly'] as const).map(
                            (tier) => {
                                const backup = readiness.backups[tier];

                                return (
                                    <div
                                        key={tier}
                                        className="rounded-xl border p-4"
                                    >
                                        <div className="flex items-center justify-between gap-3">
                                            <span className="text-xs font-black tracking-wide uppercase">
                                                {tier}
                                            </span>
                                            <StatusPill
                                                status={backup.status}
                                            />
                                        </div>
                                        <p className="text-muted-foreground mt-3 text-[11px]">
                                            {backupDetail(backup)}
                                        </p>
                                        {backup.completed_at ? (
                                            <p className="text-muted-foreground mt-1 text-[10px]">
                                                {new Date(
                                                    backup.completed_at,
                                                ).toLocaleString()}
                                            </p>
                                        ) : null}
                                    </div>
                                );
                            },
                        )}
                    </div>
                </section>

                <section className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
                    <div className="bg-card rounded-2xl border p-5 sm:p-6">
                        <div className="flex items-center gap-2">
                            <Server className="h-4 w-4 text-red-500" />
                            <h2 className="font-bold">Runtime evidence</h2>
                        </div>
                        <div className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
                            <div className="rounded-xl border p-4">
                                <div className="text-muted-foreground text-xs">
                                    Environment
                                </div>
                                <div className="mt-1 font-bold">
                                    {snapshot.environment}
                                </div>
                            </div>
                            <div className="rounded-xl border p-4">
                                <div className="text-muted-foreground text-xs">
                                    Server uptime
                                </div>
                                <div className="mt-1 font-bold">
                                    {uptime(snapshot.uptime_seconds)}
                                </div>
                            </div>
                            <div className="rounded-xl border p-4">
                                <div className="text-muted-foreground text-xs">
                                    PHP memory
                                </div>
                                <div className="mt-1 font-bold">
                                    {bytes(snapshot.php.memory_usage_bytes)} ·
                                    limit {snapshot.php.memory_limit}
                                </div>
                            </div>
                            <div className="rounded-xl border p-4">
                                <div className="text-muted-foreground text-xs">
                                    Deployed SHA
                                </div>
                                <div className="mt-1 font-mono text-xs font-bold break-all">
                                    {snapshot.deployed_sha ?? 'Unavailable'}
                                </div>
                            </div>
                        </div>
                        <div className="text-muted-foreground mt-4 text-[11px]">
                            Snapshot{' '}
                            {new Date(snapshot.captured_at).toLocaleString()} ·
                            auto-refresh every 15 seconds
                        </div>
                    </div>

                    <div className="bg-card rounded-2xl border p-5 sm:p-6">
                        <div className="flex items-center gap-2">
                            <RotateCw className="h-4 w-4 text-red-500" />
                            <h2 className="font-bold">Safe recovery actions</h2>
                        </div>
                        <p className="text-muted-foreground mt-2 text-xs leading-5">
                            Only allow-listed, reversible or low-risk actions
                            belong here. Every action is audited.
                        </p>
                        <button
                            type="button"
                            onClick={restartQueue}
                            disabled={restarting}
                            className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-4 py-3 text-sm font-bold text-white transition hover:bg-red-500 disabled:opacity-50"
                        >
                            <RotateCw
                                className={`h-4 w-4 ${restarting ? 'animate-spin' : ''}`}
                            />
                            Restart queue workers
                        </button>
                        <div className="mt-3 flex items-start gap-2 rounded-xl border border-amber-500/15 bg-amber-500/5 p-3 text-xs text-amber-700 dark:text-amber-300">
                            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                            Production deploy, DNS, billing, destructive DB and
                            raw shell remain owner-approved outside this
                            console.
                        </div>
                    </div>
                </section>

                <section className="bg-card rounded-2xl border p-5 sm:p-6">
                    <h2 className="font-bold">Operational guardrail signals</h2>
                    <p className="text-muted-foreground mt-1 text-xs">
                        These are KMJ internal warning thresholds, not claims
                        about a hosting provider&apos;s legal or contractual
                        limits.
                    </p>
                    <div className="mt-5 grid gap-2 lg:grid-cols-2">
                        {readiness.compliance_guard.signals.map((signal) => (
                            <div
                                key={signal.code}
                                className="flex items-center justify-between gap-4 rounded-xl border px-4 py-3"
                            >
                                <div>
                                    <div className="text-xs font-bold">
                                        {signal.code}
                                    </div>
                                    <div className="text-muted-foreground mt-1 text-[10px]">
                                        value{' '}
                                        {signal.value === null
                                            ? 'unavailable'
                                            : `${signal.value} ${signal.unit}`}
                                    </div>
                                </div>
                                <StatusPill status={signal.status} />
                            </div>
                        ))}
                    </div>
                </section>

                <section className="bg-card rounded-2xl border p-5 sm:p-6">
                    <h2 className="font-bold">Operator action audit</h2>
                    <p className="text-muted-foreground mt-1 text-xs">
                        Latest privileged actions recorded by the control plane.
                    </p>
                    {recentActions.length === 0 ? (
                        <div className="text-muted-foreground mt-5 rounded-xl border border-dashed p-8 text-center text-sm">
                            No operator actions recorded yet.
                        </div>
                    ) : (
                        <div className="mt-5 divide-y overflow-hidden rounded-xl border">
                            {recentActions.map((event) => (
                                <div
                                    key={event.id}
                                    className="grid gap-2 px-4 py-3 text-xs sm:grid-cols-[1fr_auto_auto] sm:items-center"
                                >
                                    <div className="font-semibold">
                                        {event.action}
                                    </div>
                                    <div
                                        className={
                                            event.outcome === 'success'
                                                ? 'font-bold text-emerald-600 dark:text-emerald-400'
                                                : 'font-bold text-red-500'
                                        }
                                    >
                                        {event.outcome}
                                    </div>
                                    <div className="text-muted-foreground">
                                        {event.created_at
                                            ? new Date(
                                                  event.created_at,
                                              ).toLocaleString()
                                            : 'Unknown time'}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </section>
            </div>
        </>
    );
}
