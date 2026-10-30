import { Head, Link, router } from '@inertiajs/react';
import {
    AlertTriangle,
    Ban,
    Bot,
    Brain,
    CheckCircle2,
    ChevronDown,
    FolderGit2,
    KeyRound,
    Laptop2,
    Loader2,
    Lock,
    MessageSquare,
    MessageSquarePlus,
    PanelLeft,
    PanelRight,
    Play,
    RotateCw,
    SendHorizontal,
    ShieldCheck,
    Wrench,
    X,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import {
    TOOL_ERROR_TEXT,
    ToolJobsPanel,
} from '@/components/codebridge/tool-jobs-panel';
import type {
    Job,
    JobEvent,
    ToolDef,
} from '@/components/codebridge/tool-jobs-panel';

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
type Message = {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    status: 'complete' | 'running' | 'failed' | 'cancelled';
    provider_id: string | null;
    model: string | null;
    error_code: string | null;
    retry_of: string | null;
    started_at: string | null;
    finished_at: string | null;
    elapsed_seconds: number | null;
};
type WorkflowEvent = {
    id: number;
    message_id: string | null;
    kind: string;
    status: string;
    detail: string | null;
    at: string;
};
type Props = {
    canManage: boolean;
    devices: Device[];
    providers: Provider[];
    selected: { device_id: string; project_id: string } | null;
    conversations: { id: string; title: string; updated_at: string }[];
    activeConversation: { id: string; title: string } | null;
    transcript: { messages: Message[]; events: WorkflowEvent[] };
    chatError?: string | null;
    jobs: Job[];
    jobEvents: JobEvent[];
    activeJobId: string | null;
    tools: ToolDef[];
    capabilities: {
        conversations: Capability;
        chat_executor: Capability;
        job_events: Capability;
        device_pairing: Capability;
    };
    links: { control_center: string; ai_providers: string };
};

const BASE = '/services/kmj-codebridge/workspace';
const PAIRING_TEXT: Record<Device['pairing_state'], string> = {
    approved_unredeemed: 'Approved — waiting for the device to redeem it',
    redeemed: 'Pairing redeemed by the device',
    unknown: 'Pairing state unknown',
};
// Plain-language text for the short codes the server records. Unknown codes are shown verbatim.
const ERROR_TEXT: Record<string, string> = {
    rate_limited:
        'The free provider is rate limiting requests. Try again later.',
    auth_failed:
        'The provider rejected the API key. Re-test it in AI providers.',
    connection_failed: 'The provider could not be reached.',
    provider_unavailable: 'The provider reported an outage.',
    unexpected_status: 'The provider returned an unexpected response.',
    response_too_large:
        'The provider response was too large and was discarded.',
    empty_response: 'The provider returned no text.',
    abandoned:
        'The request did not finish in time and was marked failed. Nothing was recorded after that point.',
    cancelled_by_user:
        'Cancelled by you. Any late provider output was discarded.',
    provider_disabled: 'This provider is disabled.',
    provider_unhealthy: 'This provider is not healthy. Re-test it.',
    model_discovery_stale: 'Model discovery is stale. Re-test the provider.',
    model_not_discovered: 'That model was not found in the latest discovery.',
    zero_spend_blocked:
        'Blocked by the zero-spend rule: this model is not verified free.',
    internal_error: 'An internal error stopped this request.',
};
const CHAT_ERROR_TEXT: Record<string, string> = {
    conversation_busy: 'A request is already running in this conversation.',
    provider_not_found: 'That provider is not available to your organization.',
    retry_not_allowed:
        'Only the newest failed or cancelled reply can be retried.',
    not_running: 'That request is no longer running.',
};
const EVENT_LABEL: Record<string, string> = {
    inference_started: 'Request sent to free model',
    inference_completed: 'Reply received',
    inference_failed: 'Request failed',
    cancelled: 'Cancelled',
};

function clock(iso: string): string {
    const date = new Date(iso);

    return Number.isNaN(date.getTime())
        ? ''
        : date.toLocaleTimeString([], { hour12: false });
}

export default function CodeBridgeWorkspace(props: Props) {
    const {
        canManage,
        devices,
        providers,
        selected,
        conversations,
        activeConversation,
        transcript,
        chatError,
        jobs,
        jobEvents,
        activeJobId,
        tools,
        capabilities,
        links,
    } = props;
    const projects = devices.flatMap((device) =>
        device.projects.map((project) => ({ device, project })),
    );
    const active = projects.find(
        ({ device, project }) =>
            device.id === selected?.device_id &&
            project.id === selected?.project_id,
    );
    const admitted = providers.flatMap((provider) =>
        provider.free_admitted_models.map((model) => ({
            providerId: provider.id,
            provider: provider.name,
            model,
        })),
    );
    const running = transcript.messages.find((m) => m.status === 'running');
    const lastMessage = transcript.messages[transcript.messages.length - 1];
    const retryable =
        lastMessage &&
        lastMessage.role === 'assistant' &&
        (lastMessage.status === 'failed' || lastMessage.status === 'cancelled')
            ? lastMessage
            : null;

    const [leftOpen, setLeftOpen] = useState(false);
    const [rightOpen, setRightOpen] = useState(false);
    const [draft, setDraft] = useState('');
    const [choice, setChoice] = useState(
        admitted[0] ? `${admitted[0].providerId}|${admitted[0].model}` : '',
    );
    const [sending, setSending] = useState(false);
    const endRef = useRef<HTMLDivElement>(null);
    const busy = sending || running !== undefined;
    const choiceValid = admitted.some(
        (item) => `${item.providerId}|${item.model}` === choice,
    );

    // Real status only: while a request is genuinely running (this tab or another),
    // re-read the stored transcript. Nothing is animated or estimated.
    useEffect(() => {
        if (!busy || !activeConversation) {
            return;
        }
        const timer = setInterval(() => {
            router.reload({
                only: ['transcript'],
                async: true,
                preserveScroll: true,
            } as Parameters<typeof router.reload>[0]);
        }, 2000);

        return () => clearInterval(timer);
    }, [busy, activeConversation]);

    useEffect(() => {
        endRef.current?.scrollIntoView?.({ block: 'end' });
    }, [transcript.messages.length, running?.status]);

    const selection = () => {
        const [provider_id, model] = choice.split('|');

        return { provider_id, model };
    };
    const conversationUrl = (id: string) => `${BASE}/conversations/${id}`;
    const go = (query: Record<string, string>) =>
        router.get(BASE, query, { preserveScroll: true });

    const send = () => {
        if (
            !activeConversation ||
            !choiceValid ||
            draft.trim() === '' ||
            busy
        ) {
            return;
        }
        const submittedDraft = draft;
        setSending(true);
        router.post(
            `${conversationUrl(activeConversation.id)}/messages`,
            { content: draft, ...selection() },
            {
                preserveScroll: true,
                onSuccess: (page) => {
                    if (!page.props.chatError) {
                        setDraft((current) =>
                            current === submittedDraft ? '' : current,
                        );
                    }
                },
                onFinish: () => setSending(false),
            },
        );
    };

    const blocked = !selected
        ? 'Select a paired project to start a conversation.'
        : !activeConversation
          ? 'Start a new chat for this project.'
          : !capabilities.chat_executor.available || !choiceValid
            ? capabilities.chat_executor.reason
            : null;

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
                        data-testid="new-chat"
                        disabled={!selected}
                        title={
                            selected
                                ? 'Start a new conversation'
                                : 'Select a paired project first'
                        }
                        onClick={() => {
                            if (!selected) {
                                return;
                            }
                            router.post(`${BASE}/conversations`, {
                                device_id: selected.device_id,
                                project_id: selected.project_id,
                            });
                            setLeftOpen(false);
                        }}
                        className="flex h-10 items-center gap-2 rounded-xl border border-cyan-500/30 px-3 text-xs font-bold enabled:hover:border-violet-400/60 disabled:opacity-60"
                    >
                        <MessageSquarePlus className="h-4 w-4" />
                        New chat
                        {!selected && <Lock className="ml-auto h-3.5 w-3.5" />}
                    </button>

                    <h2 className="mt-1 text-[11px] font-black tracking-wider text-cyan-300 uppercase">
                        Projects
                    </h2>
                    <nav
                        aria-label="Authorized projects"
                        className="flex max-h-[40%] flex-col gap-1 overflow-y-auto"
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
                            const isActive =
                                device.id === selected?.device_id &&
                                project.id === selected?.project_id;

                            return (
                                <button
                                    key={`${device.id}/${project.id}`}
                                    type="button"
                                    aria-current={isActive ? 'true' : undefined}
                                    onClick={() => {
                                        go({
                                            device: device.id,
                                            project: project.id,
                                        });
                                        setLeftOpen(false);
                                    }}
                                    className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-left text-xs ${isActive ? 'border-violet-400/60 bg-violet-500/10' : 'border-transparent hover:border-cyan-500/30'}`}
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

                    <h2 className="mt-1 text-[11px] font-black tracking-wider text-cyan-300 uppercase">
                        Conversations
                    </h2>
                    <nav
                        aria-label="Conversations"
                        data-testid="conversation-list"
                        className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto"
                    >
                        {selected && conversations.length === 0 && (
                            <p className="text-xs text-slate-400">
                                No conversations for this project yet.
                            </p>
                        )}
                        {!selected && (
                            <p className="text-xs text-slate-400">
                                {capabilities.conversations.reason}
                            </p>
                        )}
                        {conversations.map((conversation) => (
                            <button
                                key={conversation.id}
                                type="button"
                                aria-current={
                                    conversation.id === activeConversation?.id
                                        ? 'true'
                                        : undefined
                                }
                                onClick={() => {
                                    if (selected) {
                                        go({
                                            device: selected.device_id,
                                            project: selected.project_id,
                                            c: conversation.id,
                                        });
                                    }
                                    setLeftOpen(false);
                                }}
                                className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-left text-xs ${conversation.id === activeConversation?.id ? 'border-violet-400/60 bg-violet-500/10' : 'border-transparent hover:border-cyan-500/30'}`}
                            >
                                <MessageSquare className="h-4 w-4 shrink-0 text-slate-400" />
                                <span className="truncate">
                                    {conversation.title}
                                </span>
                            </button>
                        ))}
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
                                {activeConversation
                                    ? activeConversation.title
                                    : active
                                      ? active.project.name
                                      : 'KMJ CodeBridge Workspace'}
                            </h1>
                            <p className="truncate text-[11px] text-slate-400">
                                {active
                                    ? `${active.project.name} · device ${active.device.name} · connection ${active.device.connection_status.replace('_', ' ')}`
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

                    <div className="flex-1 space-y-4 overflow-y-auto p-4">
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
                            {(active ? [active.device] : devices).map(
                                (device) => (
                                    <StatusCard
                                        key={device.id}
                                        title={device.name}
                                        state={device.registration}
                                        tone="ok"
                                    >
                                        {PAIRING_TEXT[device.pairing_state]}.
                                        Live agent status is{' '}
                                        <strong>not verified</strong> by the
                                        Main Platform (registration is not a
                                        heartbeat).
                                        {device.pending_projects.map(
                                            (pending) => (
                                                <span
                                                    key={pending.id}
                                                    className="mt-2 block text-amber-300"
                                                >
                                                    Project “{pending.name}”
                                                    requested — local setup
                                                    pending.
                                                </span>
                                            ),
                                        )}
                                    </StatusCard>
                                ),
                            )}
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
                                    ? 'Providers are healthy and models pass the zero-spend rule. No paid fallback exists.'
                                    : 'Add and test a free provider to admit models. No paid fallback exists.'}
                            </StatusCard>
                        </section>

                        {chatError && (
                            <p
                                role="alert"
                                data-testid="chat-error"
                                className="flex items-center gap-2 rounded-xl border border-amber-400/40 bg-amber-500/10 p-3 text-xs text-amber-200"
                            >
                                <AlertTriangle className="h-4 w-4 shrink-0" />
                                {CHAT_ERROR_TEXT[chatError] ??
                                    TOOL_ERROR_TEXT[chatError] ??
                                    chatError}
                            </p>
                        )}

                        <section
                            aria-label="Conversation"
                            aria-live="polite"
                            data-testid="conversation"
                            className="space-y-3"
                        >
                            {!activeConversation && (
                                <p
                                    data-testid="conversation-empty"
                                    className="rounded-2xl border border-cyan-500/20 p-4 text-xs text-slate-400"
                                >
                                    <Bot className="mb-2 h-5 w-5 text-cyan-300" />
                                    {selected
                                        ? 'Start a new chat or open a conversation from the left.'
                                        : 'Select an authorized project to see its conversations.'}
                                </p>
                            )}
                            {transcript.messages.map((message) => (
                                <MessageBubble
                                    key={message.id}
                                    message={message}
                                    onCancel={() =>
                                        activeConversation &&
                                        router.post(
                                            `${conversationUrl(activeConversation.id)}/messages/${message.id}/cancel`,
                                            {},
                                            { preserveScroll: true },
                                        )
                                    }
                                />
                            ))}
                            {retryable && activeConversation && (
                                <button
                                    type="button"
                                    data-testid="retry"
                                    disabled={busy || !choiceValid}
                                    onClick={() =>
                                        router.post(
                                            `${conversationUrl(activeConversation.id)}/messages/${retryable.id}/retry`,
                                            selection(),
                                            { preserveScroll: true },
                                        )
                                    }
                                    className="inline-flex items-center gap-2 rounded-xl border border-cyan-500/40 px-3 py-2 text-xs font-bold disabled:opacity-60"
                                >
                                    <RotateCw className="h-3.5 w-3.5" />
                                    Retry with selected model
                                </button>
                            )}
                            <div ref={endRef} />
                        </section>

                        <section
                            aria-label="Workflow events"
                            data-testid="job-events"
                        >
                            <details
                                className="rounded-2xl border border-violet-400/30 bg-violet-500/5 p-3"
                                open={running !== undefined}
                            >
                                <summary className="flex cursor-pointer items-center gap-2 text-xs font-bold">
                                    <Wrench className="h-4 w-4 text-violet-300" />
                                    Workflow events
                                    <span className="ml-auto rounded-full border border-slate-500/40 px-2 py-0.5 text-[10px] text-slate-300">
                                        {transcript.events.length} recorded
                                    </span>
                                    <ChevronDown className="h-4 w-4" />
                                </summary>
                                <ol
                                    data-testid="event-list"
                                    className="mt-3 space-y-2"
                                >
                                    {transcript.events.length === 0 && (
                                        <li className="text-xs text-slate-400">
                                            No events recorded for this
                                            conversation.
                                        </li>
                                    )}
                                    {transcript.events.map((event) => (
                                        <li
                                            key={event.id}
                                            className="flex items-start gap-2 text-xs"
                                        >
                                            <EventIcon status={event.status} />
                                            <span className="min-w-0 flex-1">
                                                <span className="font-bold">
                                                    {EVENT_LABEL[event.kind] ??
                                                        event.kind}
                                                </span>
                                                {event.detail && (
                                                    <span className="block truncate text-slate-400">
                                                        {ERROR_TEXT[
                                                            event.detail
                                                        ] ?? event.detail}
                                                    </span>
                                                )}
                                            </span>
                                            <time className="shrink-0 text-slate-500">
                                                {clock(event.at)}
                                            </time>
                                        </li>
                                    ))}
                                </ol>
                                <p className="mt-3 border-t border-slate-700/50 pt-2 text-[11px] text-slate-400">
                                    Chat events only. Device tool requests have
                                    their own timeline in the right pane.
                                </p>
                            </details>
                        </section>
                    </div>

                    <form
                        onSubmit={(event) => {
                            event.preventDefault();
                            send();
                        }}
                        className="border-t border-cyan-500/20 p-3"
                    >
                        <div className="flex items-end gap-2 rounded-2xl border border-cyan-500/30 bg-[#0a1020] p-2">
                            <label htmlFor="ws-composer" className="sr-only">
                                Message
                            </label>
                            <textarea
                                id="ws-composer"
                                data-testid="composer"
                                disabled={blocked !== null || busy}
                                value={draft}
                                maxLength={4000}
                                rows={2}
                                onChange={(event) =>
                                    setDraft(event.target.value)
                                }
                                onKeyDown={(event) => {
                                    if (
                                        event.key === 'Enter' &&
                                        !event.shiftKey
                                    ) {
                                        event.preventDefault();
                                        send();
                                    }
                                }}
                                placeholder={
                                    blocked ?? 'Message the free model…'
                                }
                                className="min-h-10 flex-1 resize-none bg-transparent px-2 py-1 text-sm outline-none disabled:opacity-60"
                            />
                            <button
                                type="submit"
                                data-testid="send"
                                disabled={
                                    blocked !== null ||
                                    busy ||
                                    draft.trim() === ''
                                }
                                aria-label="Send"
                                className="rounded-xl bg-violet-600 p-2 disabled:opacity-40"
                            >
                                {busy ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <SendHorizontal className="h-4 w-4" />
                                )}
                            </button>
                        </div>
                        {blocked !== null && (
                            <p
                                data-testid="composer-blocked"
                                className="mt-1 text-[11px] text-amber-300"
                            >
                                Blocked: {blocked}
                            </p>
                        )}
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
                        icon={<Play className="h-4 w-4" />}
                        title="Device tool requests"
                    >
                        <ToolJobsPanel
                            available={capabilities.job_events.available}
                            reason={capabilities.job_events.reason}
                            selected={selected}
                            tools={tools}
                            jobs={jobs}
                            jobEvents={jobEvents}
                            activeJobId={activeJobId}
                        />
                    </PaneSection>

                    <PaneSection
                        icon={<Bot className="h-4 w-4" />}
                        title="Model"
                    >
                        {admitted.length === 0 ? (
                            <p
                                data-testid="admitted-models"
                                className="text-xs text-slate-400"
                            >
                                No free model admitted.
                            </p>
                        ) : (
                            <>
                                <label htmlFor="ws-model" className="sr-only">
                                    Free model
                                </label>
                                <select
                                    id="ws-model"
                                    data-testid="model-select"
                                    value={choice}
                                    disabled={busy}
                                    onChange={(event) =>
                                        setChoice(event.target.value)
                                    }
                                    className="w-full rounded-lg border border-cyan-500/30 bg-[#0a1020] px-2 py-2 text-xs"
                                >
                                    {admitted.map((item) => (
                                        <option
                                            key={`${item.providerId}|${item.model}`}
                                            value={`${item.providerId}|${item.model}`}
                                        >
                                            {item.model} · {item.provider}
                                        </option>
                                    ))}
                                </select>
                                <ul
                                    data-testid="admitted-models"
                                    className="sr-only"
                                >
                                    {admitted.map((item) => (
                                        <li
                                            key={`${item.providerId}|${item.model}`}
                                        >
                                            {item.model}
                                        </li>
                                    ))}
                                </ul>
                            </>
                        )}
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
                                <dt>Messages</dt>
                                <dd>{transcript.messages.length}</dd>
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
                            Conversation history is stored for this project.
                            Long-term memory is not stored here; continuity is
                            saved on your device through CodeBridge in your AI
                            client.
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

function EventIcon({ status }: { status: string }) {
    if (status === 'complete') {
        return (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
        );
    }
    if (status === 'running') {
        return (
            <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-violet-300" />
        );
    }
    if (status === 'cancelled') {
        return <Ban className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />;
    }

    return <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />;
}

function MessageBubble({
    message,
    onCancel,
}: {
    message: Message;
    onCancel: () => void;
}) {
    const mine = message.role === 'user';

    return (
        <article
            data-testid={`message-${message.role}`}
            data-status={message.status}
            className={`max-w-[92%] rounded-2xl border p-3 text-sm ${mine ? 'ml-auto border-violet-400/40 bg-violet-500/10' : 'border-cyan-500/25 bg-[#0a1020]'}`}
        >
            {message.status === 'running' && (
                <div className="flex flex-wrap items-center gap-2 text-xs text-violet-200">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span data-testid="running-status">
                        Waiting for {message.model} ·{' '}
                        {message.elapsed_seconds ?? 0}s elapsed
                    </span>
                    <button
                        type="button"
                        data-testid="cancel"
                        onClick={onCancel}
                        className="ml-auto rounded-lg border border-violet-400/50 px-2 py-1 font-bold"
                    >
                        Cancel
                    </button>
                </div>
            )}
            {message.status === 'complete' && (
                <p className="break-words whitespace-pre-wrap">
                    {message.content}
                </p>
            )}
            {(message.status === 'failed' ||
                message.status === 'cancelled') && (
                <p
                    data-testid="message-problem"
                    className="flex items-start gap-2 text-xs text-amber-200"
                >
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>
                        {message.status === 'cancelled'
                            ? 'Cancelled. '
                            : 'Failed. '}
                        {message.error_code
                            ? (ERROR_TEXT[message.error_code] ??
                              message.error_code)
                            : ''}
                    </span>
                </p>
            )}
            {!mine && message.status === 'complete' && message.model && (
                <p className="mt-2 text-[10px] text-slate-500">
                    {message.model}
                    {message.elapsed_seconds !== null
                        ? ` · ${message.elapsed_seconds}s`
                        : ''}
                </p>
            )}
        </article>
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
