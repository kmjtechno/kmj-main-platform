import { Activity, BrainCircuit, RefreshCw, Workflow } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

type Telemetry = {
    source: 'authenticated_agent_reports';
    observed_at: string;
    authorized_devices: number;
    active_devices: number | null;
    ollama: {
        reachable: boolean | null;
        sampled_devices: number;
        models: string[];
    };
    autopilot: {
        queued: number | null;
        running: number | null;
        waiting: number | null;
        sampled_devices: number;
        partial: boolean;
    };
};

const value = (count: number | null): string =>
    count === null ? 'Not reported' : String(count);

export default function CodeBridgeLiveTelemetryCard({
    tenantId,
    active,
}: {
    tenantId: string;
    active: boolean;
}) {
    const [data, setData] = useState<Telemetry | null>(null);
    const [status, setStatus] = useState<'loading' | 'available' | 'unavailable'>(
        'loading',
    );
    const [refreshing, setRefreshing] = useState(false);
    const request = useRef<AbortController | null>(null);
    const refresh = useCallback(async () => {
        if (request.current || document.visibilityState === 'hidden') return;
        const controller = new AbortController();
        request.current = controller;
        setRefreshing(true);
        try {
            const response = await fetch(
                `/services/kmj-codebridge/telemetry?tenant_id=${encodeURIComponent(tenantId)}`,
                {
                    credentials: 'same-origin',
                    cache: 'no-store',
                    headers: { Accept: 'application/json' },
                    signal: controller.signal,
                },
            );
            if (!response.ok) throw new Error('TELEMETRY_UNAVAILABLE');
            const result = (await response.json()) as Telemetry;
            if (result.source !== 'authenticated_agent_reports')
                throw new Error('TELEMETRY_SOURCE_UNVERIFIED');
            setData(result);
            setStatus('available');
        } catch {
            if (!controller.signal.aborted) {
                setData(null);
                setStatus('unavailable');
            }
        } finally {
            if (request.current === controller) request.current = null;
            if (!controller.signal.aborted) setRefreshing(false);
        }
    }, [tenantId]);

    useEffect(() => {
        if (!active) {
            request.current?.abort();
            request.current = null;
            return;
        }
        void refresh();
        // Passive 45-second polling only while visible; the browser performs
        // no inference and the platform reads a tiny tenant-scoped cache.
        const id = window.setInterval(() => void refresh(), 45_000);
        const visible = () => {
            if (document.visibilityState === 'visible') void refresh();
        };
        document.addEventListener('visibilitychange', visible);
        return () => {
            window.clearInterval(id);
            document.removeEventListener('visibilitychange', visible);
            request.current?.abort();
            request.current = null;
        };
    }, [active, refresh]);

    const fresh = data?.active_devices ?? null;
    const ollama =
        data?.ollama.reachable === true
            ? 'Reachable'
            : data?.ollama.reachable === false
              ? 'Not reachable'
              : 'Not reported';
    const queue = data?.autopilot.queued ?? null;

    return (
        <section
            aria-label="CodeBridge agent telemetry"
            className="mt-5 rounded-2xl border border-slate-700/70 bg-slate-950 p-4 text-slate-100 sm:p-5"
        >
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                    <Activity aria-hidden="true" className="h-5 w-5 text-red-500" />
                    <h3 className="text-sm font-black">
                        Live agent telemetry
                    </h3>
                </div>
                <button
                    type="button"
                    onClick={() => void refresh()}
                    disabled={refreshing}
                    className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-700 px-3 text-xs font-semibold hover:border-red-500 focus-visible:ring-2 focus-visible:ring-red-500 disabled:opacity-50"
                >
                    <RefreshCw aria-hidden="true" className="h-4 w-4 text-red-500" />
                    Refresh
                </button>
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-400">
                Fresh observations from authenticated local CodeBridge agents.
                Registration alone never counts as online. No inference is
                executed by this dashboard.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
                    <p className="text-xs text-slate-400">Active reporting devices</p>
                    <p className="mt-2 text-xl font-black text-white">{value(fresh)}</p>
                    <p className="mt-1 text-xs text-slate-400">
                        {data ? `${data.authorized_devices} authorized` : 'Awaiting verified feed'}
                    </p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
                    <p className="flex items-center gap-2 text-xs text-slate-400">
                        <BrainCircuit aria-hidden="true" className="h-4 w-4 text-red-400" />
                        Local Ollama
                    </p>
                    <p className="mt-2 text-lg font-bold text-white">{ollama}</p>
                    <p className="mt-1 break-words text-xs text-slate-400">
                        {data?.ollama.models.length
                            ? data.ollama.models.join(', ')
                            : 'No verified model list'}
                    </p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
                    <p className="flex items-center gap-2 text-xs text-slate-400">
                        <Workflow aria-hidden="true" className="h-4 w-4 text-red-400" />
                        Autopilot queued tasks
                    </p>
                    <p className="mt-2 text-xl font-black text-white">{value(queue)}</p>
                    <p className="mt-1 text-xs text-slate-400">
                        {data?.autopilot.queued === null || !data
                            ? 'Journal not reported'
                            : `Running ${data.autopilot.running}, waiting ${data.autopilot.waiting}${data.autopilot.partial ? ' · Partial coverage' : ''}`}
                    </p>
                </div>
            </div>
            <p className="mt-3 text-xs text-slate-400" aria-live="polite">
                {status === 'loading'
                    ? 'Checking for an authenticated local feed…'
                    : status === 'unavailable'
                      ? 'Telemetry request unavailable; no status is inferred.'
                      : data?.active_devices === null
                        ? 'No recent authenticated heartbeat. Values are not reported.'
                        : 'Agent reports received; counts represent fresh reporters and journal snapshots, not independent process attestation.'}
            </p>
        </section>
    );
}
