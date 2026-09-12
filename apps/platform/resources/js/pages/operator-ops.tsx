import { Head, router } from '@inertiajs/react';
import {
    Activity,
    Database,
    HardDrive,
    MemoryStick,
    RefreshCw,
    RotateCw,
    Server,
    ShieldCheck,
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

type ActionAudit = {
    id: number;
    actor_user_id: number;
    action: string;
    outcome: string;
    created_at: string | null;
};

type Props = {
    snapshot: OpsSnapshot;
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

export default function OperatorOps({ snapshot, recentActions }: Props) {
    const [refreshing, setRefreshing] = useState(false);
    const [restarting, setRestarting] = useState(false);

    const refresh = () => {
        setRefreshing(true);
        router.reload({
            only: ['snapshot', 'recentActions'],
            preserveScroll: true,
            onFinish: () => setRefreshing(false),
        });
    };

    useEffect(() => {
        const timer = window.setInterval(() => {
            router.reload({
                only: ['snapshot', 'recentActions'],
                preserveScroll: true,
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
                                Real server telemetry and audited recovery
                                controls. No raw shell, destructive database
                                action, billing mutation, DNS change, or
                                production publish is exposed from this surface.
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
                            raw shell remain owner-approved outside this MVP.
                        </div>
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
