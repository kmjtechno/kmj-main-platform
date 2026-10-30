import { router } from '@inertiajs/react';
import { Ban, Loader2, Play } from 'lucide-react';
import { useEffect, useState } from 'react';

export type ToolDef = {
    name: string;
    label: string;
    permission: string;
    description: string;
};
export type Job = {
    id: string;
    tool: string;
    arguments: Record<string, string>;
    status:
        | 'queued'
        | 'claimed'
        | 'running'
        | 'succeeded'
        | 'failed'
        | 'cancelled'
        | 'expired';
    progress: number | null;
    error_code: string | null;
    summary: string | null;
    evidence: Record<string, string | number> | null;
    created_at: string | null;
    claimed_at: string | null;
    started_at: string | null;
    finished_at: string | null;
};
export type JobEvent = {
    seq: number;
    kind: string;
    detail: string | null;
    at: string;
};

const BASE = '/services/kmj-codebridge/workspace';
const ACTIVE = ['queued', 'claimed', 'running'];
const STATUS_TEXT: Record<Job['status'], string> = {
    queued: 'Queued — waiting for the device agent',
    claimed: 'Claimed by the device agent',
    running: 'Running on the device',
    succeeded: 'Device reported success',
    failed: 'Failed',
    cancelled: 'Cancelled',
    expired: 'Expired — no device agent claimed it',
};
const CODE_TEXT: Record<string, string> = {
    not_claimed_by_device:
        'No device agent claimed this request, so nothing ran.',
    lease_expired:
        'The device stopped reporting; it is not known whether the run finished.',
    grant_revoked: 'The device grant no longer allows this tool.',
    cancelled_by_user: 'Cancelled by you.',
    device_reported_failure: 'The device reported a failure.',
};
export const TOOL_ERROR_TEXT: Record<string, string> = {
    jobs_disabled: 'Device tool requests are switched off on this server.',
    unknown_tool: 'That tool is not in the approved list.',
    unexpected_arguments: 'That tool takes no arguments.',
    invalid_gate:
        'Enter a configured gate id (lowercase letters, digits, - or _).',
    idempotency_conflict:
        'That request id was already used for a different request.',
    invalid_idempotency_key: 'Could not create a request id. Reload and retry.',
    too_many_active_jobs:
        'Too many unfinished requests for this project. Cancel or wait.',
};

function newKey(): string {
    const c = globalThis.crypto;
    if (c?.randomUUID) {
        return c.randomUUID().replaceAll('-', '');
    }
    const bytes = new Uint8Array(16);
    c?.getRandomValues?.(bytes);

    return (
        Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('') ||
        Date.now().toString(16).padStart(16, '0')
    );
}

export function ToolJobsPanel({
    available,
    reason,
    selected,
    tools,
    jobs,
    jobEvents,
    activeJobId,
}: {
    available: boolean;
    reason: string;
    selected: { device_id: string; project_id: string } | null;
    tools: ToolDef[];
    jobs: Job[];
    jobEvents: JobEvent[];
    activeJobId: string | null;
}) {
    const [tool, setTool] = useState(tools[0]?.name ?? '');
    const [gate, setGate] = useState('');
    const [busy, setBusy] = useState(false);
    const anyActive = jobs.some((job) => ACTIVE.includes(job.status));

    // Server truth only: re-read stored job state while something is unfinished.
    useEffect(() => {
        if (!available || !anyActive) {
            return;
        }
        const timer = setInterval(() => {
            router.reload({
                only: ['jobs', 'jobEvents'],
                async: true,
                preserveScroll: true,
            } as Parameters<typeof router.reload>[0]);
        }, 3000);

        return () => clearInterval(timer);
    }, [available, anyActive]);

    if (!available) {
        return (
            <p
                data-testid="jobs-unavailable"
                className="text-xs text-slate-400"
            >
                {reason}
            </p>
        );
    }
    const def = tools.find((item) => item.name === tool);
    const needsGate = tool === 'quality_gate';
    const canQueue =
        selected !== null &&
        def !== undefined &&
        !busy &&
        (!needsGate || gate !== '');

    const queue = () => {
        if (!selected || !canQueue) {
            return;
        }
        setBusy(true);
        router.post(
            `${BASE}/tools`,
            {
                device_id: selected.device_id,
                project_id: selected.project_id,
                tool,
                ...(needsGate ? { gate } : {}),
                idempotency_key: newKey(),
            },
            { preserveScroll: true, onFinish: () => setBusy(false) },
        );
    };
    const open = (id: string) =>
        selected &&
        router.get(
            BASE,
            { device: selected.device_id, project: selected.project_id, j: id },
            { preserveScroll: true },
        );

    return (
        <div data-testid="tool-jobs" className="space-y-2 text-xs">
            <p className="text-slate-400">{reason}</p>
            <label htmlFor="ws-tool" className="sr-only">
                Approved tool
            </label>
            <select
                id="ws-tool"
                value={tool}
                onChange={(event) => setTool(event.target.value)}
                className="w-full rounded-lg border border-cyan-500/30 bg-[#0a1020] px-2 py-2"
            >
                {tools.map((item) => (
                    <option key={item.name} value={item.name}>
                        {item.label} ({item.permission})
                    </option>
                ))}
            </select>
            {def && <p className="text-slate-500">{def.description}</p>}
            {needsGate && (
                <>
                    <label htmlFor="ws-gate" className="sr-only">
                        Gate id
                    </label>
                    <input
                        id="ws-gate"
                        value={gate}
                        maxLength={40}
                        placeholder="gate id, e.g. fast"
                        onChange={(event) => setGate(event.target.value)}
                        className="w-full rounded-lg border border-cyan-500/30 bg-[#0a1020] px-2 py-2"
                    />
                </>
            )}
            <button
                type="button"
                data-testid="queue-tool"
                disabled={!canQueue}
                onClick={queue}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-cyan-500/40 px-3 py-2 font-bold disabled:opacity-50"
            >
                {busy ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                    <Play className="h-3.5 w-3.5" />
                )}
                Queue request
            </button>

            {jobs.length === 0 ? (
                <p data-testid="jobs-empty" className="text-slate-500">
                    No tool requests for this project yet.
                </p>
            ) : (
                <ul data-testid="job-list" className="space-y-2">
                    {jobs.map((job) => (
                        <li
                            key={job.id}
                            data-status={job.status}
                            className={`rounded-lg border p-2 ${job.id === activeJobId ? 'border-cyan-400/60' : 'border-slate-700/60'}`}
                        >
                            <button
                                type="button"
                                onClick={() => open(job.id)}
                                className="block w-full text-left"
                            >
                                <span className="font-bold">
                                    {job.tool}
                                    {job.arguments.gate
                                        ? ` · ${job.arguments.gate}`
                                        : ''}
                                </span>
                                <span className="block text-slate-400">
                                    {STATUS_TEXT[job.status]}
                                    {job.progress !== null &&
                                    job.status === 'running'
                                        ? ` · ${job.progress}%`
                                        : ''}
                                </span>
                                {job.error_code && (
                                    <span className="block text-amber-300">
                                        {CODE_TEXT[job.error_code] ??
                                            job.error_code}
                                    </span>
                                )}
                            </button>
                            {job.summary && (
                                <p className="mt-1 text-slate-300">
                                    {job.summary}
                                </p>
                            )}
                            {job.evidence && (
                                <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-2 text-slate-400">
                                    {Object.entries(job.evidence).map(
                                        ([key, value]) => (
                                            <div key={key} className="contents">
                                                <dt>{key}</dt>
                                                <dd className="truncate">
                                                    {String(value)}
                                                </dd>
                                            </div>
                                        ),
                                    )}
                                </dl>
                            )}
                            {ACTIVE.includes(job.status) && (
                                <button
                                    type="button"
                                    onClick={() =>
                                        router.post(
                                            `${BASE}/tools/${job.id}/cancel`,
                                            {},
                                            { preserveScroll: true },
                                        )
                                    }
                                    className="mt-1 inline-flex items-center gap-1 text-amber-300"
                                >
                                    <Ban className="h-3 w-3" /> Cancel
                                </button>
                            )}
                            {job.id === activeJobId && jobEvents.length > 0 && (
                                <ol
                                    data-testid="job-events"
                                    className="mt-2 space-y-1 border-t border-slate-700/50 pt-2"
                                >
                                    {jobEvents.map((event) => (
                                        <li key={event.seq}>
                                            <span className="font-bold">
                                                {event.kind}
                                            </span>{' '}
                                            <time className="text-slate-500">
                                                {new Date(
                                                    event.at,
                                                ).toLocaleTimeString()}
                                            </time>
                                            {event.detail && (
                                                <span className="block text-slate-400">
                                                    {event.detail}
                                                </span>
                                            )}
                                        </li>
                                    ))}
                                </ol>
                            )}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}
