import { Head, router, usePage } from '@inertiajs/react';
import { Activity, AlertTriangle, CheckCircle2, GitBranch, HardDrive, LockKeyhole, Play, RotateCcw, Server, Square, Zap } from 'lucide-react';
import { useEffect, useState } from 'react';

type DevForgeStatus = {
    broker_ready?: boolean;
    state?: string;
    healthy?: boolean;
    busy?: boolean;
    last_action?: string | null;
    last_error?: string | null;
    access?: string;
};
type Props = { devforge: DevForgeStatus };
type Action = 'install' | 'start' | 'stop' | 'restart';

const actions: Array<{ id: Action; title: string; hint: string; icon: typeof Play }> = [
    { id: 'install', title: 'One-click setup', hint: 'Install the isolated, private Git forge', icon: Zap },
    { id: 'start', title: 'Start', hint: 'Start existing forge container', icon: Play },
    { id: 'restart', title: 'Restart', hint: 'Restart forge after verification', icon: RotateCcw },
    { id: 'stop', title: 'Stop', hint: 'Temporarily stop Git hosting', icon: Square },
];

export default function OperatorDevForge({ devforge }: Props) {
    const [pending, setPending] = useState<Action | null>(null);
    const { errors, flash } = usePage<{
        errors?: Record<string, string>;
        flash?: { status?: string };
    }>().props;

    useEffect(() => {
        const handle = window.setInterval(() => router.reload({ only: ['devforge'] }), 10000);
        return () => window.clearInterval(handle);
    }, []);

    const execute = (action: Action) => {
        if (pending || devforge.busy || !devforge.broker_ready) return;
        const question = action === 'stop'
            ? 'Stop KMJ DevForge hosting? Existing repositories remain on disk.'
            : action === 'install'
              ? 'Install private KMJ DevForge on the approved VPS? This does not modify Main Platform.'
              : "Run fixed DevForge action: " + action + "?";
        if (!window.confirm(question)) return;
        setPending(action);
        router.post('/operator/devforge/actions', {
            action, confirm: 'CONTROL_KMJ_DEVFORGE',
        }, { preserveScroll: true, onFinish: () => setPending(null) });
    };

    const label = devforge.busy ? 'Operation running' : (devforge.state ?? 'unknown').replaceAll('_', ' ');
    return (
        <>
            <Head title="KMJ DevForge — Super Admin" />
            <main className="flex flex-1 flex-col gap-6 p-4 sm:p-6">
                <header className="rounded-2xl border bg-card p-6">
                    <div className="flex items-start gap-4">
                        <GitBranch className="h-9 w-9 text-red-500" />
                        <div>
                            <h1 className="text-2xl font-bold">KMJ DevForge Control Center</h1>
                            <p className="mt-1 text-sm text-muted-foreground">
                                KMJ TECHNO · INNOVATE | BUILD | SCALE
                            </p>
                            <p className="mt-3 text-sm text-muted-foreground">
                                Private Git hosting for KMJ projects. Owner/passkey/password-confirmation gated.
                                All host actions use a fixed local broker; no shell or Docker privileges are exposed to the web app.
                            </p>
                        </div>
                    </div>
                </header>

                <div className="grid gap-4 md:grid-cols-3">
                    <section className="rounded-2xl border bg-card p-5">
                        <Activity className="mb-3 h-5 w-5 text-red-500" />
                        <p className="text-xs font-semibold uppercase text-muted-foreground">Live service state</p>
                        <p className="mt-2 text-xl font-bold capitalize">{label}</p>
                        <p className="mt-1 text-sm text-muted-foreground">
                            {devforge.healthy ? 'Loopback health check passed' : 'No healthy Git service verified'}
                        </p>
                    </section>
                    <section className="rounded-2xl border bg-card p-5">
                        <LockKeyhole className="mb-3 h-5 w-5 text-red-500" />
                        <p className="text-xs font-semibold uppercase text-muted-foreground">Security</p>
                        <p className="mt-2 text-xl font-bold">Private by default</p>
                        <p className="mt-1 text-sm text-muted-foreground">Local-only port; no public registration or CI runners</p>
                    </section>
                    <section className="rounded-2xl border bg-card p-5">
                        <Server className="mb-3 h-5 w-5 text-red-500" />
                        <p className="text-xs font-semibold uppercase text-muted-foreground">Host broker</p>
                        <p className="mt-2 text-xl font-bold">{devforge.broker_ready ? 'Connected' : 'Not provisioned'}</p>
                        <p className="mt-1 text-sm text-muted-foreground">One-time secure VPS enrollment required before first click</p>
                    </section>
                </div>

                {flash?.status && <p role="status" className="rounded-xl border p-4 text-sm"><CheckCircle2 className="mr-2 inline h-4 w-4" />{flash.status}</p>}
                {errors?.action && <p role="alert" className="rounded-xl border border-red-500/40 p-4 text-sm text-red-500"><AlertTriangle className="mr-2 inline h-4 w-4" />{errors.action}</p>}

                <section className="rounded-2xl border bg-card p-6">
                    <h2 className="mb-2 text-lg font-semibold">Host controls</h2>
                    <p className="mb-5 text-sm text-muted-foreground">
                        Actions are asynchronous. The live status above is authoritative, not the button confirmation.
                        Running production web, payments and license systems are outside this control surface.
                    </p>
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        {actions.map((action) => {
                            const Icon = action.icon;
                            const disabled = !devforge.broker_ready || !!devforge.busy || pending !== null;
                            return (
                                <button key={action.id} type="button" onClick={() => execute(action.id)}
                                    disabled={disabled}
                                    className="flex min-h-28 flex-col items-start gap-2 rounded-xl border px-4 py-3 text-left transition hover:border-red-500/50 disabled:cursor-not-allowed disabled:opacity-40">
                                    <Icon className="h-5 w-5 text-red-500" />
                                    <strong className="text-sm">{pending === action.id ? 'Submitting...' : action.title}</strong>
                                    <span className="text-xs text-muted-foreground">{action.hint}</span>
                                </button>
                            );
                        })}
                    </div>
                </section>

                <section className="rounded-2xl border bg-card p-6">
                    <h2 className="flex items-center gap-2 text-lg font-semibold"><HardDrive className="h-5 w-5" /> Development acceleration</h2>
                    <p className="mt-3 text-sm text-muted-foreground">
                        Git hosting is separate from CodeBridge execution. Parallel isolated worktrees, signed runners,
                        ModelFabric routing, GitHub mirroring and backup/restore must pass their own gates before activation.
                    </p>
                    {devforge.last_action && <p className="mt-3 text-xs text-muted-foreground">Last host operation: {devforge.last_action}</p>}
                    {devforge.last_error && <p className="mt-2 text-xs text-red-500">Host diagnostic: {devforge.last_error}</p>}
                </section>
            </main>
        </>
    );
}
