import { Head, Link } from '@inertiajs/react';
import {
    Activity,
    ArrowUpRight,
    Bot,
    CheckCircle2,
    CircleAlert,
    Clock3,
    Cpu,
    Database,
    HardDrive,
    MemoryStick,
    Radio,
    RefreshCw,
    Server,
    ShieldCheck,
    Workflow,
    XCircle,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

type ProcessState = 'online' | 'attention' | 'idle' | 'blocked';

type ProcessSnapshot = {
    key: string;
    label: string;
    status: ProcessState;
    detail: string;
};

type MonitorStatus = {
    status: 'healthy' | 'degraded';
    timestamp: string;
    runtime: {
        application: boolean;
        database: boolean;
        database_latency_ms: number | null;
        response_latency_ms: number;
        system_load_percent: number | null;
        memory_used_percent: number | null;
        disk_used_percent: number | null;
        server_uptime_seconds: number | null;
        pending_jobs: number;
        failed_jobs: number;
        runner_count: number;
        queue_worker_count: number;
        ai_router_online: boolean;
        ai_router_model_count: number;
        ai_router_latency_ms: number | null;
    };
    deployment: {
        source: string;
        approved_sha: string | null;
        deployed_sha: string | null;
        deployed_at: string | null;
        http_health: string;
        rendered_ui: string;
    };
    processes: ProcessSnapshot[];
    safety: {
        environment: string;
        production_untouched: boolean;
        paid_ai_fallback: string;
        local_llm_inference: string;
    };
};

type Sample = {
    time: string;
    load: number;
    memory: number;
    database: number;
    response: number;
};

const statusClass: Record<ProcessState, string> = {
    online: 'border-emerald-400/20 bg-emerald-400/[0.07] text-emerald-300',
    attention: 'border-amber-300/20 bg-amber-300/[0.07] text-amber-200',
    idle: 'border-sky-300/20 bg-sky-300/[0.06] text-sky-200',
    blocked: 'border-red-400/20 bg-red-400/[0.07] text-red-300',
};

function MiniChart({
    title,
    value,
    values,
    suffix = '',
    fixedMax,
}: {
    title: string;
    value: number;
    values: number[];
    suffix?: string;
    fixedMax?: number;
}) {
    const width = 360;
    const height = 108;
    const safeValues = values.length > 0 ? values : [0];
    const maxValue = Math.max(fixedMax ?? 0, ...safeValues, 1);
    const minValue = fixedMax ? 0 : Math.min(...safeValues, maxValue);
    const span = Math.max(maxValue - minValue, 1);
    const points = safeValues
        .map((item, index) => {
            const x =
                safeValues.length === 1
                    ? width / 2
                    : (index / (safeValues.length - 1)) * width;
            const y = height - ((item - minValue) / span) * (height - 12) - 6;

            return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(' ');

    return (
        <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.025] p-4">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <div className="text-[10px] font-bold tracking-[0.16em] text-white/35 uppercase">
                        {title}
                    </div>
                    <div className="mt-1 text-2xl font-black tracking-tight text-white">
                        {value.toFixed(value < 10 ? 1 : 0)}
                        {suffix}
                    </div>
                </div>
                <Activity className="h-4 w-4 text-[#ff4b53]" />
            </div>
            <div className="mt-3 h-24 w-full">
                <svg
                    viewBox={`0 0 ${width} ${height}`}
                    className="h-full w-full"
                    preserveAspectRatio="none"
                    aria-label={`${title} live graph`}
                >
                    <defs>
                        <linearGradient id={`fill-${title}`} x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="rgba(226,27,35,0.24)" />
                            <stop offset="100%" stopColor="rgba(226,27,35,0)" />
                        </linearGradient>
                    </defs>
                    <line x1="0" y1="27" x2={width} y2="27" stroke="rgba(255,255,255,0.05)" />
                    <line x1="0" y1="54" x2={width} y2="54" stroke="rgba(255,255,255,0.05)" />
                    <line x1="0" y1="81" x2={width} y2="81" stroke="rgba(255,255,255,0.05)" />
                    <polyline
                        points={points}
                        fill="none"
                        stroke="#ef3340"
                        strokeWidth="3"
                        strokeLinejoin="round"
                        strokeLinecap="round"
                    />
                </svg>
            </div>
            <div className="mt-1 text-[10px] text-white/25">
                Last {safeValues.length} sample{safeValues.length === 1 ? '' : 's'} · updates automatically
            </div>
        </div>
    );
}

function formatUptime(seconds: number | null) {
    if (seconds === null) {
        return 'Unknown';
    }

    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) {
        return `${days}d ${hours}h`;
    }

    return `${hours}h ${minutes}m`;
}

export default function Info({ pollIntervalMs }: { pollIntervalMs: number }) {
    const [status, setStatus] = useState<MonitorStatus | null>(null);
    const [samples, setSamples] = useState<Sample[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [refreshing, setRefreshing] = useState(false);

    const refresh = async () => {
        setRefreshing(true);

        try {
            const response = await fetch('/info/status', {
                headers: { Accept: 'application/json' },
                cache: 'no-store',
            });

            if (!response.ok) {
                throw new Error(`Monitor endpoint returned ${response.status}`);
            }

            const payload = (await response.json()) as MonitorStatus;
            setStatus(payload);
            setError(null);
            setSamples((current) => [
                ...current.slice(-59),
                {
                    time: payload.timestamp,
                    load: payload.runtime.system_load_percent ?? 0,
                    memory: payload.runtime.memory_used_percent ?? 0,
                    database: payload.runtime.database_latency_ms ?? 0,
                    response: payload.runtime.response_latency_ms,
                },
            ]);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Monitor refresh failed');
        } finally {
            setRefreshing(false);
        }
    };

    useEffect(() => {
        void refresh();
        const timer = window.setInterval(() => void refresh(), pollIntervalMs);

        return () => window.clearInterval(timer);
    }, [pollIntervalMs]);

    const processSummary = useMemo(() => {
        if (!status) {
            return { online: 0, attention: 0, blocked: 0 };
        }

        return status.processes.reduce(
            (result, process) => {
                if (process.status === 'online') result.online += 1;
                if (process.status === 'attention' || process.status === 'idle') result.attention += 1;
                if (process.status === 'blocked') result.blocked += 1;
                return result;
            },
            { online: 0, attention: 0, blocked: 0 },
        );
    }, [status]);

    const loadValues = samples.map((sample) => sample.load);
    const memoryValues = samples.map((sample) => sample.memory);
    const databaseValues = samples.map((sample) => sample.database);
    const responseValues = samples.map((sample) => sample.response);

    return (
        <>
            <Head title="Live Operations Monitor — KMJ TECHNO">
                <meta name="robots" content="noindex,nofollow,noarchive" />
            </Head>

            <div className="min-h-screen bg-[#07090c] text-white selection:bg-[#e21b23] selection:text-white">
                <div className="pointer-events-none fixed inset-0 overflow-hidden">
                    <div className="absolute -top-56 left-1/2 h-[34rem] w-[52rem] -translate-x-1/2 rounded-full bg-[#e21b23]/10 blur-[130px]" />
                    <div className="absolute top-[44rem] -right-48 h-80 w-80 rounded-full bg-[#9e1118]/10 blur-[120px]" />
                </div>

                <header className="relative z-20 border-b border-white/[0.07] bg-[#07090c]/88 backdrop-blur-xl">
                    <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-5 px-5 py-4 sm:px-8">
                        <div className="flex items-center gap-3">
                            <div className="grid h-10 w-10 place-items-center rounded-xl border border-[#e21b23]/35 bg-[#e21b23]/10 text-[#ff4b53]">
                                <Radio className="h-5 w-5" />
                            </div>
                            <div>
                                <div className="flex items-center gap-2 text-sm font-black tracking-[0.12em]">
                                    KMJ TECHNO
                                    <span className="rounded-full border border-amber-300/20 bg-amber-300/[0.06] px-2 py-0.5 text-[8px] font-black tracking-[0.12em] text-amber-200 uppercase">
                                        Temporary
                                    </span>
                                </div>
                                <div className="mt-0.5 text-[10px] tracking-[0.2em] text-white/30 uppercase">
                                    Staging live operations monitor
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() => void refresh()}
                                className="inline-flex h-10 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.035] px-3 text-xs font-bold text-white/70 transition hover:bg-white/[0.07] hover:text-white"
                            >
                                <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                                Refresh
                            </button>
                            <Link
                                href="/"
                                className="inline-flex h-10 items-center gap-2 rounded-xl bg-[#e21b23] px-4 text-xs font-bold text-white shadow-[0_10px_32px_rgba(226,27,35,0.2)] transition hover:bg-[#f1252e]"
                            >
                                Live product
                                <ArrowUpRight className="h-3.5 w-3.5" />
                            </Link>
                        </div>
                    </div>
                </header>

                <main className="relative z-10 mx-auto max-w-[1500px] px-5 py-7 sm:px-8 sm:py-9">
                    <section className="grid gap-5 xl:grid-cols-[1.35fr_.65fr]">
                        <div className="rounded-[1.6rem] border border-white/[0.08] bg-white/[0.025] p-5 sm:p-7">
                            <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
                                <div>
                                    <div className="flex items-center gap-2 text-[10px] font-bold tracking-[0.16em] text-[#ff555d] uppercase">
                                        <span className="h-2 w-2 animate-pulse rounded-full bg-[#ef3340] shadow-[0_0_14px_#ef3340]" />
                                        Live staging telemetry
                                    </div>
                                    <h1 className="mt-3 text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                                        One page for the whole delivery system.
                                    </h1>
                                    <p className="mt-3 max-w-3xl text-sm leading-6 text-white/45 sm:text-base">
                                        Runtime health, VPS load, database latency, queue state, self-hosted runners,
                                        verified-free AI routing and exact deployment evidence — refreshed continuously without exposing secrets.
                                    </p>
                                </div>

                                <div
                                    className={`shrink-0 rounded-2xl border px-4 py-3 ${
                                        status?.status === 'healthy'
                                            ? 'border-emerald-400/20 bg-emerald-400/[0.07]'
                                            : 'border-amber-300/20 bg-amber-300/[0.07]'
                                    }`}
                                >
                                    <div className="text-[9px] font-black tracking-[0.14em] text-white/35 uppercase">
                                        Overall status
                                    </div>
                                    <div className="mt-1 flex items-center gap-2 text-sm font-black">
                                        {status?.status === 'healthy' ? (
                                            <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                                        ) : (
                                            <CircleAlert className="h-4 w-4 text-amber-200" />
                                        )}
                                        {status?.status ?? 'Connecting'}
                                    </div>
                                </div>
                            </div>

                            {error && (
                                <div className="mt-5 flex items-center gap-3 rounded-xl border border-red-400/20 bg-red-400/[0.06] px-4 py-3 text-sm text-red-200">
                                    <XCircle className="h-4 w-4 shrink-0" />
                                    {error}
                                </div>
                            )}

                            <div className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                                {[
                                    {
                                        icon: Cpu,
                                        label: 'VPS load',
                                        value: `${status?.runtime.system_load_percent ?? 0}%`,
                                        note: '1-minute normalized load',
                                    },
                                    {
                                        icon: MemoryStick,
                                        label: 'Memory used',
                                        value: `${status?.runtime.memory_used_percent ?? 0}%`,
                                        note: 'Available system memory',
                                    },
                                    {
                                        icon: Database,
                                        label: 'DB latency',
                                        value: `${status?.runtime.database_latency_ms ?? 0} ms`,
                                        note: status?.runtime.database ? 'Database online' : 'Database probe failed',
                                    },
                                    {
                                        icon: Clock3,
                                        label: 'Server uptime',
                                        value: formatUptime(status?.runtime.server_uptime_seconds ?? null),
                                        note: 'Kernel uptime',
                                    },
                                ].map(({ icon: Icon, label, value, note }) => (
                                    <div key={label} className="rounded-2xl border border-white/[0.07] bg-black/15 p-4">
                                        <div className="flex items-center justify-between">
                                            <span className="text-[10px] font-bold tracking-[0.12em] text-white/35 uppercase">
                                                {label}
                                            </span>
                                            <Icon className="h-4 w-4 text-white/35" />
                                        </div>
                                        <div className="mt-3 text-xl font-black tracking-tight text-white">{value}</div>
                                        <div className="mt-1 text-[10px] text-white/30">{note}</div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="rounded-[1.6rem] border border-white/[0.08] bg-white/[0.025] p-5 sm:p-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <div className="text-[10px] font-bold tracking-[0.14em] text-white/35 uppercase">Process state</div>
                                    <div className="mt-1 text-lg font-black">Live summary</div>
                                </div>
                                <Workflow className="h-5 w-5 text-[#ff4b53]" />
                            </div>
                            <div className="mt-5 grid grid-cols-3 gap-2">
                                {[
                                    ['Online', processSummary.online, 'text-emerald-300'],
                                    ['Watch', processSummary.attention, 'text-amber-200'],
                                    ['Blocked', processSummary.blocked, 'text-red-300'],
                                ].map(([label, value, className]) => (
                                    <div key={label} className="rounded-xl border border-white/[0.07] bg-black/15 p-3 text-center">
                                        <div className={`text-xl font-black ${className}`}>{value}</div>
                                        <div className="mt-1 text-[9px] font-bold tracking-[0.12em] text-white/30 uppercase">{label}</div>
                                    </div>
                                ))}
                            </div>
                            <div className="mt-5 space-y-3 text-xs">
                                <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
                                    <span className="text-white/40">Queue</span>
                                    <span className="font-bold text-white/75">
                                        {status?.runtime.pending_jobs ?? 0} pending · {status?.runtime.failed_jobs ?? 0} failed
                                    </span>
                                </div>
                                <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
                                    <span className="text-white/40">CI runners</span>
                                    <span className="font-bold text-white/75">{status?.runtime.runner_count ?? 0} visible</span>
                                </div>
                                <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
                                    <span className="text-white/40">AI route</span>
                                    <span className={status?.runtime.ai_router_online ? 'font-bold text-emerald-300' : 'font-bold text-red-300'}>
                                        {status?.runtime.ai_router_online ? 'Reachable' : 'Fail-closed'}
                                    </span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span className="text-white/40">Last sample</span>
                                    <span className="font-bold text-white/75">
                                        {status?.timestamp
                                            ? new Intl.DateTimeFormat(undefined, {
                                                  hour: '2-digit',
                                                  minute: '2-digit',
                                                  second: '2-digit',
                                              }).format(new Date(status.timestamp))
                                            : 'Connecting'}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </section>

                    <section className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <MiniChart
                            title="VPS load"
                            value={status?.runtime.system_load_percent ?? 0}
                            values={loadValues}
                            suffix="%"
                            fixedMax={100}
                        />
                        <MiniChart
                            title="Memory"
                            value={status?.runtime.memory_used_percent ?? 0}
                            values={memoryValues}
                            suffix="%"
                            fixedMax={100}
                        />
                        <MiniChart
                            title="Database latency"
                            value={status?.runtime.database_latency_ms ?? 0}
                            values={databaseValues}
                            suffix=" ms"
                        />
                        <MiniChart
                            title="Monitor response"
                            value={status?.runtime.response_latency_ms ?? 0}
                            values={responseValues}
                            suffix=" ms"
                        />
                    </section>

                    <section className="mt-5 grid gap-5 xl:grid-cols-[1fr_.72fr]">
                        <div className="rounded-[1.6rem] border border-white/[0.08] bg-white/[0.025] p-5 sm:p-6">
                            <div className="flex items-center justify-between gap-4">
                                <div>
                                    <div className="text-[10px] font-bold tracking-[0.14em] text-white/35 uppercase">End-to-end process</div>
                                    <h2 className="mt-1 text-xl font-black">What is actually running</h2>
                                </div>
                                <Server className="h-5 w-5 text-[#ff4b53]" />
                            </div>

                            <div className="mt-5 grid gap-3 lg:grid-cols-2">
                                {(status?.processes ?? []).map((process) => (
                                    <div key={process.key} className="rounded-2xl border border-white/[0.07] bg-black/15 p-4">
                                        <div className="flex items-start justify-between gap-3">
                                            <div className="min-w-0">
                                                <div className="text-sm font-bold text-white/85">{process.label}</div>
                                                <p className="mt-2 text-[11px] leading-5 text-white/35">{process.detail}</p>
                                            </div>
                                            <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[8px] font-black tracking-[0.1em] uppercase ${statusClass[process.status]}`}>
                                                {process.status}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="space-y-5">
                            <div className="rounded-[1.6rem] border border-white/[0.08] bg-white/[0.025] p-5 sm:p-6">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <div className="text-[10px] font-bold tracking-[0.14em] text-white/35 uppercase">Deployment evidence</div>
                                        <h2 className="mt-1 text-lg font-black">Current staging release</h2>
                                    </div>
                                    <HardDrive className="h-5 w-5 text-white/35" />
                                </div>
                                <div className="mt-5 space-y-3 text-xs">
                                    <div className="rounded-xl border border-white/[0.07] bg-black/15 p-3">
                                        <div className="text-[9px] font-bold tracking-[0.12em] text-white/30 uppercase">Deployed SHA</div>
                                        <div className="mt-1 break-all font-mono text-[11px] text-white/70">
                                            {status?.deployment.deployed_sha ?? 'Evidence pending'}
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-2 gap-2">
                                        <div className="rounded-xl border border-white/[0.07] bg-black/15 p-3">
                                            <div className="text-[9px] text-white/30 uppercase">HTTP health</div>
                                            <div className="mt-1 font-bold text-white/70">{status?.deployment.http_health ?? 'unknown'}</div>
                                        </div>
                                        <div className="rounded-xl border border-white/[0.07] bg-black/15 p-3">
                                            <div className="text-[9px] text-white/30 uppercase">Rendered UI</div>
                                            <div className="mt-1 font-bold text-white/70">{status?.deployment.rendered_ui ?? 'unknown'}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="rounded-[1.6rem] border border-emerald-400/10 bg-emerald-400/[0.035] p-5 sm:p-6">
                                <div className="flex items-start gap-3">
                                    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-emerald-400/15 bg-emerald-400/[0.06] text-emerald-300">
                                        <ShieldCheck className="h-4 w-4" />
                                    </div>
                                    <div>
                                        <div className="text-sm font-black">Safety boundary</div>
                                        <p className="mt-2 text-[11px] leading-5 text-white/40">
                                            This page is staging-only. Production remains untouched. No secrets, signing keys or provider credentials are returned by the monitor.
                                        </p>
                                    </div>
                                </div>
                                <div className="mt-4 grid gap-2 text-[10px] sm:grid-cols-2">
                                    <div className="rounded-lg border border-white/[0.06] bg-black/15 px-3 py-2 text-white/45">
                                        Paid AI fallback: <span className="font-bold text-white/70">prohibited</span>
                                    </div>
                                    <div className="rounded-lg border border-white/[0.06] bg-black/15 px-3 py-2 text-white/45">
                                        Local LLM: <span className="font-bold text-white/70">prohibited</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>

                    <section className="mt-5 rounded-[1.6rem] border border-white/[0.08] bg-white/[0.025] p-5 sm:p-6">
                        <div className="grid gap-4 sm:grid-cols-3">
                            <div className="flex items-center gap-3">
                                <div className="grid h-9 w-9 place-items-center rounded-xl border border-white/[0.08] bg-black/15 text-white/45">
                                    <Bot className="h-4 w-4" />
                                </div>
                                <div>
                                    <div className="text-xs font-bold">Autonomous execution</div>
                                    <div className="mt-1 text-[10px] text-white/30">Runners + verified-free AI dependency visible</div>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="grid h-9 w-9 place-items-center rounded-xl border border-white/[0.08] bg-black/15 text-white/45">
                                    <Database className="h-4 w-4" />
                                </div>
                                <div>
                                    <div className="text-xs font-bold">Authority runtime</div>
                                    <div className="mt-1 text-[10px] text-white/30">Database + queue health sampled continuously</div>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="grid h-9 w-9 place-items-center rounded-xl border border-white/[0.08] bg-black/15 text-white/45">
                                    <RefreshCw className="h-4 w-4" />
                                </div>
                                <div>
                                    <div className="text-xs font-bold">Automatic refresh</div>
                                    <div className="mt-1 text-[10px] text-white/30">Every {Math.round(pollIntervalMs / 1000)} seconds · last 60 samples</div>
                                </div>
                            </div>
                        </div>
                    </section>
                </main>
            </div>
        </>
    );
}
