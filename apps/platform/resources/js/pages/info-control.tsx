import { Activity, AlertTriangle, Bot, GitPullRequest, ServerCog } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
    deliveryMilestones,
    deliveryProgress,
    deliveryProgressMeta,
} from '@/data/delivery-progress';
import Info from './info';

type DeliveryStage = {
    key?: string;
    label?: string;
    status?: string;
};

type DeliverySnapshot = {
    status: string;
    captured_at?: string | null;
    current_worker?: {
        status?: string;
        run_number?: number;
        phase?: string;
        retry_count?: number;
    };
    current_task?: {
        issue_number?: number;
        title?: string;
        state?: string;
    } | null;
    runners?: Array<{ name?: string; status?: string; busy?: boolean }>;
    pull_request?: { number?: number; title?: string; state?: string } | null;
    ci?: { status?: string; failed_checks?: number };
    staging?: { status?: string; deployed_sha?: string | null };
    pipeline?: DeliveryStage[];
    blocker?: { code?: string | null; message?: string | null; recoverable?: boolean };
};

type StatusPayload = {
    delivery?: DeliverySnapshot;
};

const stageClass: Record<string, string> = {
    complete: 'border-emerald-400/25 bg-emerald-400/10 text-emerald-200',
    active: 'border-sky-400/25 bg-sky-400/10 text-sky-200',
    waiting: 'border-white/10 bg-white/[0.04] text-white/55',
    blocked: 'border-red-400/25 bg-red-400/10 text-red-200',
    failed: 'border-red-400/25 bg-red-400/10 text-red-200',
};

export default function InfoControl({ pollIntervalMs }: { pollIntervalMs: number }) {
    const [delivery, setDelivery] = useState<DeliverySnapshot | null>(null);

    useEffect(() => {
        let active = true;
        let timer: number | undefined;

        const refresh = async () => {
            try {
                const response = await fetch('/info/status', {
                    headers: { Accept: 'application/json' },
                    cache: 'no-store',
                });
                if (!response.ok) {
                    return;
                }
                const payload = (await response.json()) as StatusPayload;
                if (active) {
                    setDelivery(payload.delivery ?? null);
                }
            } catch {
                // The underlying monitor already reports network health; keep the
                // last known delivery snapshot instead of inventing a healthy state.
            }
        };

        void refresh();
        timer = window.setInterval(() => void refresh(), pollIntervalMs);

        return () => {
            active = false;
            if (timer !== undefined) {
                window.clearInterval(timer);
            }
        };
    }, [pollIntervalMs]);

    const milestoneCounts = useMemo(() => {
        const verified = deliveryMilestones.filter((item) => item.state === 'verified').length;
        const active = deliveryMilestones.filter((item) => item.state === 'active').length;
        return { verified, active, remaining: deliveryMilestones.length - verified };
    }, []);

    const workerState = delivery?.current_worker?.status ?? 'unknown';
    const task = delivery?.current_task;
    const blocker = delivery?.blocker;
    const onlineRunners = (delivery?.runners ?? []).filter((runner) => runner.status === 'online').length;

    return (
        <div className="min-h-screen bg-[#08090b] text-white">
            <section className="border-b border-white/[0.08] bg-[#0b0c0f] px-4 py-5 sm:px-6 lg:px-8">
                <div className="mx-auto max-w-[1400px] rounded-3xl border border-white/[0.08] bg-white/[0.025] p-5 shadow-2xl shadow-black/30 sm:p-6">
                    <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
                        <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2 text-[11px] font-bold tracking-[0.15em] text-white/45 uppercase">
                                <Activity className="h-4 w-4 text-[#ef3340]" />
                                Delivery progress
                                <span className="rounded-full border border-white/10 px-2 py-1 text-white/35">
                                    evidence-based
                                </span>
                            </div>
                            <div className="mt-3 flex flex-wrap items-end gap-x-4 gap-y-2">
                                <div className="text-4xl font-black tracking-tight sm:text-5xl">
                                    {deliveryProgress}%
                                </div>
                                <div className="pb-1 text-sm text-white/45">
                                    {milestoneCounts.verified}/{deliveryMilestones.length} verified ·{' '}
                                    {milestoneCounts.active} active · {milestoneCounts.remaining} remaining
                                </div>
                            </div>
                            <div className="mt-4 h-3 overflow-hidden rounded-full border border-white/[0.08] bg-black/40">
                                <div
                                    className="h-full rounded-full bg-gradient-to-r from-[#b91720] via-[#ef3340] to-[#ff6870] transition-[width] duration-700"
                                    style={{ width: `${deliveryProgress}%` }}
                                    role="progressbar"
                                    aria-label="KMJ Main Platform delivery progress"
                                    aria-valuemin={0}
                                    aria-valuemax={100}
                                    aria-valuenow={deliveryProgress}
                                />
                            </div>
                            <div className="mt-2 text-xs text-white/35">{deliveryProgressMeta}</div>
                        </div>

                        <div className="grid gap-3 sm:grid-cols-2 xl:w-[560px]">
                            <div className="rounded-2xl border border-white/[0.08] bg-black/25 p-4">
                                <div className="flex items-center gap-2 text-xs font-bold text-white/45 uppercase">
                                    <Bot className="h-4 w-4 text-[#ef3340]" /> Current worker
                                </div>
                                <div className="mt-2 text-lg font-bold">{workerState}</div>
                                <div className="mt-1 truncate text-xs text-white/45">
                                    {delivery?.current_worker?.run_number
                                        ? `Run #${delivery.current_worker.run_number}`
                                        : 'No live run evidence'}
                                    {delivery?.current_worker?.phase
                                        ? ` · ${delivery.current_worker.phase}`
                                        : ''}
                                </div>
                            </div>
                            <div className="rounded-2xl border border-white/[0.08] bg-black/25 p-4">
                                <div className="flex items-center gap-2 text-xs font-bold text-white/45 uppercase">
                                    <ServerCog className="h-4 w-4 text-[#ef3340]" /> Runners
                                </div>
                                <div className="mt-2 text-lg font-bold">
                                    {onlineRunners}/{delivery?.runners?.length ?? 0} online
                                </div>
                                <div className="mt-1 text-xs text-white/45">
                                    {(delivery?.runners ?? []).filter((runner) => runner.busy).length} busy
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="mt-5 grid gap-4 lg:grid-cols-[1.15fr_1.85fr]">
                        <div className="rounded-2xl border border-white/[0.08] bg-black/20 p-4">
                            <div className="text-[10px] font-bold tracking-[0.14em] text-white/35 uppercase">
                                Current task
                            </div>
                            <div className="mt-2 font-bold text-white/90">
                                {task?.issue_number ? `#${task.issue_number} · ` : ''}
                                {task?.title ?? 'Waiting for live task evidence'}
                            </div>
                            <div className="mt-2 flex flex-wrap gap-3 text-xs text-white/45">
                                <span>state: {task?.state ?? 'unknown'}</span>
                                <span>CI: {delivery?.ci?.status ?? 'unknown'}</span>
                                <span>
                                    staging: {delivery?.staging?.status ?? 'unknown'}
                                </span>
                                {delivery?.pull_request?.number ? (
                                    <span className="inline-flex items-center gap-1">
                                        <GitPullRequest className="h-3.5 w-3.5" /> PR #{delivery.pull_request.number}
                                    </span>
                                ) : null}
                            </div>
                            {blocker?.code || blocker?.message ? (
                                <div className="mt-3 rounded-xl border border-red-400/20 bg-red-400/[0.06] p-3 text-xs text-red-200">
                                    <div className="flex items-center gap-2 font-bold">
                                        <AlertTriangle className="h-4 w-4" />
                                        {blocker.code ?? 'Blocked'}
                                    </div>
                                    {blocker.message ? <div className="mt-1 text-red-100/70">{blocker.message}</div> : null}
                                </div>
                            ) : null}
                        </div>

                        <div className="rounded-2xl border border-white/[0.08] bg-black/20 p-4">
                            <div className="text-[10px] font-bold tracking-[0.14em] text-white/35 uppercase">
                                Delivery pipeline
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2">
                                {(delivery?.pipeline ?? []).length > 0 ? (
                                    delivery?.pipeline?.map((stage) => (
                                        <div
                                            key={stage.key ?? stage.label}
                                            className={`rounded-xl border px-3 py-2 text-xs font-bold ${stageClass[stage.status ?? 'waiting'] ?? stageClass.waiting}`}
                                        >
                                            {stage.label ?? stage.key ?? 'Stage'} · {stage.status ?? 'waiting'}
                                        </div>
                                    ))
                                ) : (
                                    <div className="text-sm text-white/35">
                                        Live pipeline evidence is unavailable or stale.
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <Info pollIntervalMs={pollIntervalMs} />
        </div>
    );
}
