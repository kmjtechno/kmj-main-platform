import { Head, Link } from '@inertiajs/react';
import {
    Bot,
    Brain,
    ChevronDown,
    FolderGit2,
    KeyRound,
    Laptop2,
    Lock,
    MessageSquarePlus,
    PanelLeft,
    PanelRight,
    SendHorizontal,
    ShieldCheck,
    Wrench,
    X,
} from 'lucide-react';
import { useState } from 'react';

type DeviceProject = { id: string; name: string };
type PendingProject = {
    id: string;
    name: string;
    repository: string;
    status: string;
};
type Device = {
    id: string;
    name: string;
    platform: string | null;
    arch: string | null;
    projects: DeviceProject[];
    pending_projects: PendingProject[];
    registered_at: string | null;
    registration: string;
    pairing_state: 'approved_unredeemed' | 'redeemed' | 'unknown';
    connection_status: string;
};
type Provider = {
    id: string;
    name: string;
    host: string;
    enabled: boolean;
    health: string;
    free_tier: string;
    default_model: string | null;
    free_admitted_models: string[];
};
type Capability = { available: boolean; reason: string };
type Props = {
    canManage: boolean;
    devices: Device[];
    providers: Provider[];
    capabilities: {
        conversations: Capability;
        chat_executor: Capability;
        job_events: Capability;
        device_pairing: Capability;
    };
    links: { control_center: string; ai_providers: string };
};

const PAIRING_TEXT: Record<Device['pairing_state'], string> = {
    approved_unredeemed: 'Approved — waiting for the device to redeem it',
    redeemed: 'Pairing redeemed by the device',
    unknown: 'Pairing state unknown',
};

export default function CodeBridgeWorkspace({
    canManage,
    devices,
    providers,
    capabilities,
    links,
}: Props) {
    const projects = devices.flatMap((device) =>
        device.projects.map((project) => ({ device, project })),
    );
    const [selected, setSelected] = useState<string | null>(
        projects[0]
            ? `${projects[0].device.id}/${projects[0].project.id}`
            : null,
    );
    const [leftOpen, setLeftOpen] = useState(false);
    const [rightOpen, setRightOpen] = useState(false);

    const active = projects.find(
        ({ device, project }) => `${device.id}/${project.id}` === selected,
    );
    const admitted = providers.flatMap((provider) =>
        provider.free_admitted_models.map((model) => ({
            provider: provider.name,
            model,
        })),
    );

    return (
        <>
            <Head title="AI Workspace" />
            <div
                data-testid="ai-workspace"
                className="relative flex h-[calc(100dvh-4rem)] min-h-[32rem] overflow-hidden bg-[#05070d] text-slate-200"
            >
                {/* LEFT: projects & conversations */}
                <aside
                    aria-label="Projects and conversations"
                    data-testid="pane-left"
                    className={`absolute inset-y-0 left-0 z-30 flex w-72 shrink-0 flex-col gap-3 border-r border-cyan-500/20 bg-[#080c16]/95 p-3 backdrop-blur transition-transform lg:static lg:w-[20%] lg:min-w-60 lg:translate-x-0 ${leftOpen ? 'translate-x-0' : '-translate-x-full'}`}
                >
                    <div className="flex items-center justify-between lg:hidden">
                        <span className="text-xs font-bold">Projects</span>
                        <button
                            type="button"
                            aria-label="Close projects"
                            onClick={() => setLeftOpen(false)}
                            className="rounded-lg p-2"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </div>
                    <button
                        type="button"
                        disabled
                        aria-disabled="true"
                        title={capabilities.conversations.reason}
                        className="flex h-10 items-center gap-2 rounded-xl border border-cyan-500/30 px-3 text-xs font-bold opacity-60"
                    >
                        <MessageSquarePlus className="h-4 w-4" />
                        New chat
                        <Lock className="ml-auto h-3.5 w-3.5" />
                    </button>
                    <p
                        data-testid="conversations-blocked"
                        className="text-[11px] leading-relaxed text-slate-400"
                    >
                        {capabilities.conversations.reason}
                    </p>

                    <h2 className="mt-2 text-[11px] font-black tracking-wider text-cyan-300 uppercase">
                        Projects
                    </h2>
                    <nav
                        aria-label="Authorized projects"
                        className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto"
                    >
                        {projects.length === 0 && (
                            <p
                                data-testid="no-projects"
                                className="text-xs text-slate-400"
                            >
                                No authorized project is paired yet. Pair a
                                device in the Control Center.
                            </p>
                        )}
                        {projects.map(({ device, project }) => {
                            const key = `${device.id}/${project.id}`;

                            return (
                                <button
                                    key={key}
                                    type="button"
                                    aria-current={
                                        key === selected ? 'true' : undefined
                                    }
                                    onClick={() => {
                                        setSelected(key);
                                        setLeftOpen(false);
                                    }}
                                    className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-left text-xs ${key === selected ? 'border-violet-400/60 bg-violet-500/10' : 'border-transparent hover:border-cyan-500/30'}`}
                                >
                                    <FolderGit2 className="h-4 w-4 shrink-0 text-cyan-300" />
                                    <span className="min-w-0">
                                        <span className="block truncate font-bold">
                                            {project.name}
                                        </span>
                                        <span className="block truncate text-[11px] text-slate-400">
                                            {device.name}
                                        </span>
                                    </span>
                                </button>
                            );
                        })}
                    </nav>
                </aside>
                {leftOpen && (
                    <button
                        type="button"
                        aria-label="Close projects overlay"
                        onClick={() => setLeftOpen(false)}
                        className="absolute inset-0 z-20 bg-black/60 lg:hidden"
                    />
                )}

                {/* CENTER: workflow */}
                <main
                    data-testid="pane-center"
                    className="flex min-w-0 flex-1 flex-col lg:w-[59%]"
                >
                    <header className="flex items-center gap-2 border-b border-cyan-500/20 px-3 py-2">
                        <button
                            type="button"
                            aria-label="Open projects"
                            onClick={() => setLeftOpen(true)}
                            className="rounded-lg p-2 lg:hidden"
                        >
                            <PanelLeft className="h-4 w-4" />
                        </button>
                        <div className="min-w-0 flex-1">
                            <h1 className="truncate text-sm font-black">
                                {active
                                    ? active.project.name
                                    : 'KMJ CodeBridge Workspace'}
                            </h1>
                            <p className="truncate text-[11px] text-slate-400">
                                {active
                                    ? `Device ${active.device.name} · connection ${active.device.connection_status.replace('_', ' ')}`
                                    : 'Select an authorized project'}
                            </p>
                        </div>
                        <button
                            type="button"
                            aria-label="Open tools and context"
                            onClick={() => setRightOpen(true)}
                            className="rounded-lg p-2 lg:hidden"
                        >
                            <PanelRight className="h-4 w-4" />
                        </button>
                    </header>

                    <div
                        className="flex-1 space-y-4 overflow-y-auto p-4"
                        aria-live="polite"
                    >
                        <section
                            aria-label="Workflow status"
                            className="grid gap-3 md:grid-cols-2"
                        >
                            {devices.length === 0 && (
                                <StatusCard
                                    title="No device registered"
                                    state="setup required"
                                    tone="warn"
                                >
                                    Open the Control Center to pair a device.
                                    Pairing stays in the Main Platform.
                                </StatusCard>
                            )}
                            {devices.map((device) => (
                                <StatusCard
                                    key={device.id}
                                    title={device.name}
                                    state={device.registration}
                                    tone="ok"
                                >
                                    {PAIRING_TEXT[device.pairing_state]}. Live
                                    agent status is{' '}
                                    <strong>not verified</strong> by the Main
                                    Platform (registration is not a heartbeat).
                                    {device.pending_projects.map((pending) => (
                                        <span
                                            key={pending.id}
                                            className="mt-2 block text-amber-300"
                                        >
                                            Project “{pending.name}” requested —
                                            local setup pending.
                                        </span>
                                    ))}
                                </StatusCard>
                            ))}
                            <StatusCard
                                title="Free AI models"
                                state={
                                    admitted.length > 0
                                        ? `${admitted.length} admitted`
                                        : 'none admitted'
                                }
                                tone={admitted.length > 0 ? 'ok' : 'warn'}
                            >
                                {admitted.length > 0
                                    ? 'Providers are healthy and models pass the zero-spend rule. Readiness only: chat execution is not available here.'
                                    : 'Add and test a free provider to admit models. No paid fallback exists.'}
                            </StatusCard>
                        </section>

                        <section
                            aria-label="Tool and job events"
                            data-testid="job-events"
                        >
                            <details className="rounded-2xl border border-violet-400/30 bg-violet-500/5 p-3">
                                <summary className="flex cursor-pointer items-center gap-2 text-xs font-bold">
                                    <Wrench className="h-4 w-4 text-violet-300" />
                                    Tool &amp; job timeline
                                    <span className="ml-auto rounded-full border border-amber-400/40 px-2 py-0.5 text-[10px] text-amber-300">
                                        unavailable
                                    </span>
                                    <ChevronDown className="h-4 w-4" />
                                </summary>
                                <p className="mt-2 text-xs text-slate-400">
                                    {capabilities.job_events.reason} No elapsed
                                    times, percentages or step counts are shown
                                    because none are recorded here.
                                </p>
                            </details>
                        </section>

                        <section
                            aria-label="Conversation"
                            data-testid="conversation-empty"
                            className="rounded-2xl border border-cyan-500/20 p-4 text-xs text-slate-400"
                        >
                            <Bot className="mb-2 h-5 w-5 text-cyan-300" />
                            No messages. {capabilities.chat_executor.reason}
                        </section>
                    </div>

                    <form
                        onSubmit={(event) => event.preventDefault()}
                        className="border-t border-cyan-500/20 p-3"
                    >
                        <div className="flex items-end gap-2 rounded-2xl border border-cyan-500/30 bg-[#0a1020] p-2">
                            <label htmlFor="ws-composer" className="sr-only">
                                Message composer (unavailable)
                            </label>
                            <textarea
                                id="ws-composer"
                                data-testid="composer"
                                disabled
                                rows={2}
                                placeholder="Chat execution is not connected"
                                className="min-h-10 flex-1 resize-none bg-transparent px-2 py-1 text-sm outline-none disabled:opacity-60"
                            />
                            <button
                                type="submit"
                                disabled
                                aria-label="Send (unavailable)"
                                className="rounded-xl bg-violet-600/40 p-2 opacity-60"
                            >
                                <SendHorizontal className="h-4 w-4" />
                            </button>
                        </div>
                        <p
                            data-testid="composer-blocked"
                            className="mt-1 text-[11px] text-amber-300"
                        >
                            Blocked: {capabilities.chat_executor.reason}
                        </p>
                    </form>
                </main>

                {/* RIGHT: context */}
                <aside
                    aria-label="Tools and context"
                    data-testid="pane-right"
                    className={`absolute inset-y-0 right-0 z-30 flex w-80 max-w-[90vw] shrink-0 flex-col gap-4 overflow-y-auto border-l border-cyan-500/20 bg-[#080c16]/95 p-3 backdrop-blur transition-transform lg:static lg:w-[21%] lg:min-w-64 lg:translate-x-0 ${rightOpen ? 'translate-x-0' : 'translate-x-full'}`}
                >
                    <div className="flex items-center justify-between lg:hidden">
                        <span className="text-xs font-bold">Context</span>
                        <button
                            type="button"
                            aria-label="Close tools and context"
                            onClick={() => setRightOpen(false)}
                            className="rounded-lg p-2"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </div>

                    <PaneSection
                        icon={<Wrench className="h-4 w-4" />}
                        title="Tools"
                    >
                        <Link
                            href={`${links.control_center}#devices`}
                            className="block rounded-lg border border-cyan-500/30 px-3 py-2 text-xs font-bold"
                        >
                            <Laptop2 className="mr-2 inline h-3.5 w-3.5" />
                            Devices &amp; pairing
                        </Link>
                        <Link
                            href={links.ai_providers}
                            className="block rounded-lg border border-cyan-500/30 px-3 py-2 text-xs font-bold"
                        >
                            <KeyRound className="mr-2 inline h-3.5 w-3.5" />
                            AI providers
                        </Link>
                        <Link
                            href={links.control_center}
                            className="block rounded-lg border border-cyan-500/30 px-3 py-2 text-xs font-bold"
                        >
                            <ShieldCheck className="mr-2 inline h-3.5 w-3.5" />
                            Control Center
                        </Link>
                    </PaneSection>

                    <PaneSection
                        icon={<Bot className="h-4 w-4" />}
                        title="Model"
                    >
                        <ul data-testid="admitted-models" className="space-y-1">
                            {admitted.length === 0 && (
                                <li className="text-xs text-slate-400">
                                    No free model admitted.
                                </li>
                            )}
                            {admitted.slice(0, 20).map((item) => (
                                <li
                                    key={`${item.provider}/${item.model}`}
                                    className="truncate text-xs"
                                    title={`${item.provider} · ${item.model}`}
                                >
                                    {item.model}
                                    <span className="text-slate-500">
                                        {' '}
                                        · {item.provider}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    </PaneSection>

                    <PaneSection
                        icon={<ShieldCheck className="h-4 w-4" />}
                        title="Session"
                    >
                        <dl className="space-y-1 text-xs text-slate-300">
                            <div className="flex justify-between gap-2">
                                <dt>Devices</dt>
                                <dd>{devices.length}</dd>
                            </div>
                            <div className="flex justify-between gap-2">
                                <dt>Projects</dt>
                                <dd>{projects.length}</dd>
                            </div>
                            <div className="flex justify-between gap-2">
                                <dt>Role</dt>
                                <dd>{canManage ? 'Manager' : 'Member'}</dd>
                            </div>
                        </dl>
                    </PaneSection>

                    <PaneSection
                        icon={<Brain className="h-4 w-4" />}
                        title="Memory"
                    >
                        <p className="text-xs text-slate-400">
                            Not stored here. Continuity is saved on your device
                            through CodeBridge in your AI client.
                        </p>
                    </PaneSection>
                </aside>
                {rightOpen && (
                    <button
                        type="button"
                        aria-label="Close context overlay"
                        onClick={() => setRightOpen(false)}
                        className="absolute inset-0 z-20 bg-black/60 lg:hidden"
                    />
                )}
            </div>
        </>
    );
}

function StatusCard({
    title,
    state,
    tone,
    children,
}: {
    title: string;
    state: string;
    tone: 'ok' | 'warn';
    children: React.ReactNode;
}) {
    return (
        <article className="rounded-2xl border border-cyan-500/25 bg-[#0a1020] p-3 text-xs">
            <header className="mb-1 flex items-center justify-between gap-2">
                <h3 className="truncate font-black">{title}</h3>
                <span
                    className={`rounded-full border px-2 py-0.5 text-[10px] ${tone === 'ok' ? 'border-emerald-400/40 text-emerald-300' : 'border-amber-400/40 text-amber-300'}`}
                >
                    {state}
                </span>
            </header>
            <p className="text-slate-400">{children}</p>
        </article>
    );
}

function PaneSection({
    icon,
    title,
    children,
}: {
    icon: React.ReactNode;
    title: string;
    children: React.ReactNode;
}) {
    return (
        <section className="space-y-2">
            <h2 className="flex items-center gap-2 text-[11px] font-black tracking-wider text-cyan-300 uppercase">
                {icon}
                {title}
            </h2>
            {children}
        </section>
    );
}
