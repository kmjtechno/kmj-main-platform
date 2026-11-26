import {
    formatIstClock,
    formatIstDate,
    formatIstStamp,
} from '@/lib/format-ist-date-time';
import { Head, Link, router, usePage } from '@inertiajs/react';
import {
    Activity,
    ArrowRight,
    Boxes,
    ChevronRight,
    Circle,
    Copy,
    ExternalLink,
    KeyRound,
    LockKeyhole,
    Server,
    ShieldCheck,
    Trash2,
    Zap,
} from 'lucide-react';
import { useMemo, useState, type ReactNode } from 'react';
import ModelFabricSafePlayground from '@/components/modelfabric-safe-playground';
import AiProviders, {
    type Preset,
    type Provider as ManagedProvider,
} from '@/pages/services/ai-providers';

type Provider = ManagedProvider & {
    id: string;
    name: string;
    preset: string;
    host: string;
    enabled: boolean;
    free_tier: string;
    health: string;
    models: string[];
    discovered_models: string[];
    discovered_model_count: number;
    error_code: string | null;
    priority: number;
    daily_request_cap: number | null;
    used_today: number;
};

type Evidence = {
    id: string;
    provider_id: string;
    model_id: string;
    price_evidence_url: string;
    price_evidence_note: string;
    verified_at: string;
    expires_at: string;
    data_handling: string;
    capabilities: string[];
    cost_class: string;
    credit_daily_cap: number | null;
    current: boolean;
    revoked: boolean;
};

type Plan = {
    status: string;
    routes: {
        provider: string;
        model: string;
        source: string;
        evidence_expires_at: string | null;
        data_handling: string;
    }[];
    reasons: { provider: string; reason: string }[];
};

type Analytics = {
    provider: string;
    requests: number;
    ok: number;
    p50_ms: number | null;
    p95_ms: number | null;
    last_error: string | null;
    cooling_until: string | null;
};

type Rule = {
    id: string;
    provider_id: string;
    model_pattern: string;
    price_evidence_url: string;
    expires_at: string;
    data_handling: string;
    capabilities: string[];
    active: boolean;
    revoked: boolean;
    matches: number;
};

type Token = {
    id: string;
    name: string;
    prefix: string;
    private_source: boolean;
    expires_at: string;
    last_used_at: string | null;
    active: boolean;
};

type Props = {
    newToken?: string | null;
    tokens: Token[];
    status?: string | null;
    canManage: boolean;
    maxEvidenceDays: number;
    providerPresets: Preset[];
    initialTab: 'start' | 'providers' | 'tokens';
    providers: Provider[];
    evidence: Evidence[];
    rules: Rule[];
    analytics: Analytics[];
    plans: { chat: Plan; privateSource: Plan };
};

const BASE = '/operator/modelfabric';

type Tab =
    | 'providers'
    | 'models'
    | 'tokens'
    | 'playground'
    | 'activity';

// Suggested places to read a provider's own free-tier terms. These are hints only: the owner must
// open the page and confirm it names the exact model before saving evidence.
const PRICING_HINTS: Record<string, string> = {
    gemini: 'https://ai.google.dev/gemini-api/docs/pricing',
    groq: 'https://console.groq.com/docs/rate-limits',
    huggingface: 'https://huggingface.co/docs/inference-providers/pricing',
    cerebras: 'https://inference-docs.cerebras.ai/support/rate-limits',
};

const REASONS: Record<string, string> = {
    no_verified_free_model: 'No model has price evidence yet',
    no_private_source_evidence:
        'Needs proof that the provider does not train on your data',
    no_capable_model: 'No evidenced model has the needed capability',
    model_discovery_stale: 'Model list is stale: run Test connection',
    provider_disabled: 'Provider is disabled',
    auth_failed: 'Provider rejected the key',
};

const reasonText = (reason: string) =>
    REASONS[reason] ?? reason.replaceAll('_', ' ');

/** Plain-language meaning and next step for a provider's last error code. */
const errorHelp = (code: string): string => {
    if (code.startsWith('invalid_catalog')) {
        return 'The provider answered with something that is not a model list. Check token permissions and the provider status page before retrying.';
    }
    switch (code) {
        case 'provider_retired':
            return 'GitHub Models retired on July 30, 2026. No new connection or inference is available. Keep the historical record or remove it in Manage settings.';
        case 'auth_failed':
            return 'The provider rejected the key. Create a new key, reconnect the provider and run Test connection. It is not used until then.';
        case 'rate_limited':
            return 'The provider is rate-limiting. ModelFabric pauses it and retries on its own, so no action is needed.';
        case 'connection_failed':
        case 'provider_unavailable':
            return 'The provider could not be reached or had an outage. ModelFabric retries other routes automatically; run Test connection later.';
        case 'unexpected_status':
        case 'response_too_large':
            return 'The provider returned an unexpected answer. Run Test connection; if it repeats, check the provider status page.';
        default:
            return '';
    }
};

const fieldClass =
    'bg-background/45 border-border focus-visible:ring-ring/60 mt-1 min-h-10 w-full rounded-xl border px-3 text-sm outline-none focus-visible:ring-2';
const primaryButton =
    'inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-bold text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-40';
const ghostButton =
    'hover:bg-muted inline-flex min-h-9 items-center justify-center gap-2 rounded-xl border px-3 text-xs font-bold transition';

function statusTone(tone: 'ok' | 'warn' | 'bad' | 'muted'): string {
    return {
        ok: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
        warn: 'border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300',
        bad: 'border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-300',
        muted: 'border-border bg-muted text-muted-foreground',
    }[tone];
}

function StatusPill({
    tone,
    children,
}: {
    tone: 'ok' | 'warn' | 'bad' | 'muted';
    children: ReactNode;
}) {
    return (
        <span
            className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-black tracking-wide uppercase ${statusTone(tone)}`}
        >
            {children}
        </span>
    );
}

function StatTile({
    icon: Icon,
    label,
    value,
    detail,
    tone,
}: {
    icon: typeof Activity;
    label: string;
    value: string;
    detail: string;
    tone: 'cyan' | 'purple' | 'amber' | 'green';
}) {
    return (
        <article className={`owner-stat ${tone}`}>
            <span>
                <Icon size={22} />
            </span>
            <div>
                <h2>{label}</h2>
                <strong>{value}</strong>
                <p>{detail}</p>
            </div>
        </article>
    );
}

function PanelTitle({
    title,
    href,
    label = 'Open',
}: {
    title: string;
    href?: string;
    label?: string;
}) {
    return (
        <div className="owner-panel-title">
            <h2>
                <Activity size={17} />
                {title}
            </h2>
            {href ? (
                <Link href={href}>
                    {label}
                    <ChevronRight size={13} />
                </Link>
            ) : null}
        </div>
    );
}

function Card({
    title,
    help,
    children,
    id,
    label,
}: {
    title: string;
    help?: string;
    children: ReactNode;
    id?: string;
    label?: string;
}) {
    return (
        <section id={id} aria-label={label ?? title} className="owner-panel">
            <PanelTitle title={title} />
            {help ? (
                <p className="owner-panel-subtitle">{help}</p>
            ) : (
                <div className="h-2" />
            )}
            <div>{children}</div>
        </section>
    );
}

function ProviderLimits({
    provider,
    canManage,
}: {
    provider: Provider;
    canManage: boolean;
}) {
    const [priority, setPriority] = useState(String(provider.priority));
    const [cap, setCap] = useState(
        provider.daily_request_cap === null
            ? ''
            : String(provider.daily_request_cap),
    );
    const percent =
        provider.daily_request_cap && provider.daily_request_cap > 0
            ? Math.min(
                  100,
                  Math.round(
                      (provider.used_today / provider.daily_request_cap) * 100,
                  ),
              )
            : null;

    return (
        <div className="mt-3 border-t pt-3 text-xs">
            <p className="text-muted-foreground">
                Used today: <strong>{provider.used_today}</strong>
                {provider.daily_request_cap
                    ? ` of ${provider.daily_request_cap} (your daily cap)`
                    : ' (no daily cap set)'}
            </p>
            {percent !== null ? (
                <div className="bg-muted mt-1 h-1.5 overflow-hidden rounded-full">
                    <div
                        className={`h-full rounded-full ${percent >= 80 ? 'bg-amber-500' : 'bg-red-500'}`}
                        style={{ width: `${percent}%` }}
                    />
                </div>
            ) : null}
            {canManage ? (
                <form
                    className="mt-2 flex flex-wrap items-end gap-2"
                    onSubmit={(event) => {
                        event.preventDefault();
                        router.patch(
                            `${BASE}/providers/${provider.id}`,
                            {
                                priority: Number(priority),
                                daily_request_cap:
                                    cap === '' ? null : Number(cap),
                            },
                            { preserveScroll: true },
                        );
                    }}
                >
                    <label className="text-[11px] font-medium">
                        Priority (1 = first)
                        <input
                            className={`${fieldClass} w-24`}
                            type="number"
                            min={1}
                            max={999}
                            value={priority}
                            onChange={(e) => setPriority(e.target.value)}
                        />
                    </label>
                    <label className="text-[11px] font-medium">
                        Daily cap (blank = none)
                        <input
                            className={`${fieldClass} w-28`}
                            type="number"
                            min={1}
                            value={cap}
                            onChange={(e) => setCap(e.target.value)}
                        />
                    </label>
                    <button type="submit" className={ghostButton}>
                        Save limits
                    </button>
                </form>
            ) : null}
            <p className="text-muted-foreground mt-2">
                Work moves to another approved provider before the cap is hit
                (at 80% it is deprioritised, at 100% it is skipped).
            </p>
        </div>
    );
}

function PlanCard({
    title,
    note,
    plan,
}: {
    title: string;
    note: string;
    plan: Plan;
}) {
    const none = plan.status === 'NO_FREE_ROUTE_AVAILABLE';
    const [all, setAll] = useState(false);
    const grouped = useMemo(() => {
        const map = new Map<string, string[]>();
        plan.routes.forEach((route) => {
            map.set(route.provider, [
                ...(map.get(route.provider) ?? []),
                route.model,
            ]);
        });

        return [...map.entries()];
    }, [plan.routes]);

    return (
        <div
            className="bg-card rounded-2xl border p-5"
            data-testid="modelfabric-plan"
        >
            <div className="owner-panel-title">
                <h2>
                    <Activity size={17} />
                    {title}
                </h2>
                <StatusPill tone={none ? 'warn' : 'ok'}>
                    {none ? 'Not ready' : 'Ready'}
                </StatusPill>
            </div>
            <p className="mt-3 text-xl font-black">
                {none
                    ? 'No free model is approved yet'
                    : `${plan.routes.length} free model route(s)`}
            </p>
            {none ? (
                <p className="text-muted-foreground mt-1 text-[11px]">
                    System status: NO_FREE_ROUTE_AVAILABLE
                </p>
            ) : null}
            <p className="text-muted-foreground mt-2 text-xs leading-5">
                {note}
            </p>
            <ul className="mt-3 space-y-2 text-xs">
                {grouped.map(([provider, models]) => (
                    <li key={provider}>
                        <strong>{provider}</strong>{' '}
                        <span className="text-muted-foreground">
                            · {models.length} model(s)
                        </span>
                        <span className="text-muted-foreground block break-all">
                            {(all ? models : models.slice(0, 2)).join(', ')}
                            {!all && models.length > 2
                                ? `, +${models.length - 2} more`
                                : ''}
                        </span>
                    </li>
                ))}
                {plan.reasons.map((reason) => (
                    <li
                        key={`${reason.provider}-${reason.reason}`}
                        className="text-muted-foreground flex flex-wrap items-center gap-2"
                    >
                        <StatusPill tone="warn">{reason.provider}</StatusPill>
                        {reasonText(reason.reason)}
                    </li>
                ))}
            </ul>
            {grouped.some(([, models]) => models.length > 2) ? (
                <button
                    type="button"
                    className="mt-3 text-xs font-bold underline"
                    onClick={() => setAll(!all)}
                >
                    {all ? 'Show fewer models' : 'Show all models'}
                </button>
            ) : null}
        </div>
    );
}

function CopyRow({ label, value }: { label: string; value: string }) {
    const [done, setDone] = useState(false);

    return (
        <div className="flex items-center justify-between gap-2 rounded-xl border p-2">
            <span className="min-w-0 text-xs">
                <span className="text-muted-foreground block">{label}</span>
                <span className="font-mono break-all">{value}</span>
            </span>
            <button
                type="button"
                className={ghostButton}
                aria-label={`Copy ${label}`}
                onClick={async () => {
                    try {
                        await navigator.clipboard.writeText(value);
                        setDone(true);
                        window.setTimeout(() => setDone(false), 1500);
                    } catch {
                        setDone(false);
                    }
                }}
            >
                <Copy className="h-3 w-3" /> {done ? 'Copied' : 'Copy'}
            </button>
        </div>
    );
}

/** Copy-ready connection settings. The token is only ever the one-time value already on screen. */
function ConnectGuide({
    origin,
    token,
}: {
    origin: string;
    token: string | null | undefined;
}) {
    const baseUrl = `${origin}/api/modelfabric/v1`;
    const protocolHelp =
        'Custom text chat endpoints only. Streaming replays completed responses; native Responses, tool calling, vision and embeddings are unavailable.';
    const tokenHelp =
        'Set KMJ_MODELFABRIC_TOKEN in a private credential store. Samples never contain your token. Run the read-only model check first. Never paste credentials into source or shell history.';
    // Keep the one-time bearer in the explicit copy row, never in code samples.
    const snippets: { id: string; label: string; code: string }[] = [
        {
            id: 'sdk',
            label: 'Python (OpenAI SDK)',
            code: `import os\nfrom openai import OpenAI\n\nclient = OpenAI(base_url="${baseUrl}", api_key=os.environ["KMJ_MODELFABRIC_TOKEN"])\nreply = client.chat.completions.create(\n    model="modelfabric-auto",\n    messages=[{"role": "user", "content": "ping"}],\n)\nprint(reply.choices[0].message.content)`,
        },
        {
            id: 'curl',
            label: 'curl (read-only model check)',
            code: `curl --fail-with-body "${baseUrl}/models" \\\n  -H "Authorization: Bearer $KMJ_MODELFABRIC_TOKEN"`,
        },
    ];

    return (
        <div className="mt-4 space-y-3" data-testid="modelfabric-connect-guide">
            <p className="text-sm font-black">Connect in 30 seconds</p>
            <p className="text-muted-foreground text-xs">{protocolHelp}</p>
            <div className="grid gap-2 md:grid-cols-3">
                <CopyRow label="Base URL" value={baseUrl} />
                <CopyRow label="Model" value="modelfabric-auto" />
                <CopyRow
                    label="API key"
                    value={
                        token ?? 'Create a token above, then copy it once here'
                    }
                />
            </div>
            <p className="text-muted-foreground text-xs">{tokenHelp}</p>
            {snippets.map((snippet) => (
                <details key={snippet.id} className="rounded-xl border p-2">
                    <summary className="cursor-pointer text-xs font-bold">
                        {snippet.label}
                    </summary>
                    <pre className="bg-muted mt-2 overflow-x-auto rounded-xl p-3 text-xs">
                        {snippet.code}
                    </pre>
                </details>
            ))}
            <p className="text-muted-foreground text-xs">
                Optional: send an X-ModelFabric-Session header (any short id) to
                keep one conversation on the same route.
            </p>
        </div>
    );
}

export default function OperatorModelFabric({
    newToken,
    tokens,
    status,
    canManage,
    maxEvidenceDays,
    providerPresets,
    initialTab,
    providers,
    evidence,
    rules,
    analytics,
    plans,
}: Props) {
    const { errors } = usePage().props as { errors?: Record<string, string> };
    const allowlistProviders = providers.filter(
        (provider) => provider.free_tier === 'allowlist',
    );
    const [tab, setTab] = useState<Tab>(
        newToken ? 'tokens' : initialTab === 'start' ? 'providers' : initialTab,
    );
    const [tokenName, setTokenName] = useState('');
    const [tokenDays, setTokenDays] = useState('30');
    const privateReady =
        plans.privateSource.status !== 'NO_FREE_ROUTE_AVAILABLE';
    const [tokenPrivate, setTokenPrivate] = useState(privateReady);
    const [workflow, setWorkflow] = useState<'chat' | 'coding'>('chat');
    const [copied, setCopied] = useState(false);
    const [providerId, setProviderId] = useState(
        allowlistProviders[0]?.id ?? '',
    );
    const [model, setModel] = useState('');
    const [url, setUrl] = useState('');
    const [note, setNote] = useState('');
    const [days, setDays] = useState(14);
    const [handling, setHandling] = useState('unknown');
    const [caps, setCaps] = useState<string[]>(['chat']);
    const [confirmed, setConfirmed] = useState(false);
    const [costClass, setCostClass] = useState<'free' | 'credit-limited'>(
        'free',
    );
    const [creditCap, setCreditCap] = useState('');
    const [creditAttested, setCreditAttested] = useState(false);
    const [picked, setPicked] = useState<string[]>([]);
    const selected = providers.find((provider) => provider.id === providerId);
    const [rulePattern, setRulePattern] = useState('');
    const [ruleUrl, setRuleUrl] = useState('');
    const [ruleNote, setRuleNote] = useState('');
    const [ruleConfirmed, setRuleConfirmed] = useState(false);
    const ruleMatches = (selected?.discovered_models ?? []).filter((id) => {
        if (!rulePattern.includes('*')) return false;
        const escaped = rulePattern
            .replace(/[.+?^${}()|[\]\\/]/g, '\\$&')
            .replace(/\*/g, '[A-Za-z0-9._/-]*');
        return new RegExp(`^${escaped}$`).test(id);
    });
    const canRule =
        canManage &&
        !!selected &&
        rulePattern.includes('*') &&
        rulePattern.split('*')[0].length >= 10 &&
        ruleUrl.startsWith('https://') &&
        ruleNote.trim().length >= 10 &&
        ruleConfirmed;
    const hint = selected ? PRICING_HINTS[selected.preset] : undefined;
    const modelKnown = !!selected?.discovered_models.includes(model);
    const origin =
        typeof window === 'undefined'
            ? 'https://kmjtechno.com'
            : window.location.origin;

    const healthy = providers.filter(
        (p) => p.enabled && p.health === 'ok',
    ).length;
    const currentEvidence = evidence.filter((row) => row.current).length;
    const activeTokens = tokens.filter((token) => token.active).length;
    const chatTokens = tokens.filter(
        (token) => token.active && !token.private_source,
    ).length;
    const codingTokens = tokens.filter(
        (token) => token.active && token.private_source,
    ).length;
    const requests24h = analytics.reduce((sum, row) => sum + row.requests, 0);
    const okRequests24h = analytics.reduce((sum, row) => sum + row.ok, 0);
    const generalReady = plans.chat.status !== 'NO_FREE_ROUTE_AVAILABLE';
    const canSave =
        canManage &&
        modelKnown &&
        url.startsWith('https://') &&
        note.trim().length >= 10 &&
        confirmed &&
        (costClass === 'free' || (Number(creditCap) >= 1 && creditAttested));

    const listedModels = (selected?.discovered_models ?? []).slice(0, 200);
    const bulkModels = picked
        .filter((id) => listedModels.includes(id))
        .slice(0, 50);
    const canBulk =
        canManage &&
        costClass === 'free' &&
        bulkModels.length > 0 &&
        url.startsWith('https://') &&
        note.trim().length >= 10 &&
        confirmed;

    // A read-only, evidence-backed setup journey. API requests are never
    // started by rendering this page; each stage still requires user action.
    const chatJourney: {
        title: string;
        detail: string;
        complete: boolean;
        tab?: Tab;
        href?: string;
    }[] = [
        {
            title: 'Connect a provider',
            detail: 'Use OAuth where supported, or add an API key securely.',
            complete: providers.some((provider) => provider.enabled),
            href: '/operator/modelfabric?tab=providers',
        },
        {
            title: 'Test and discover models',
            detail: 'Read provider health and catalog; no inference is sent.',
            complete: healthy > 0,
            href: '/operator/modelfabric?tab=providers',
        },
        {
            title: 'Approve verified-free routes',
            detail: 'Review model pricing, expiry, data handling and quotas.',
            complete: generalReady,
            tab: 'models',
        },
        {
            title: 'Create a chat API token',
            detail: 'Copy the hashed-at-rest token once and keep it private.',
            complete: chatTokens > 0,
            tab: 'tokens',
        },
        {
            title: 'Test then monitor',
            detail: 'Check your chat token, then explicitly send a safe prompt. Completion reflects aggregate recent successful usage.',
            complete: okRequests24h > 0,
            tab: 'playground',
        },
    ];

    const codingJourney: typeof chatJourney = [
        ...chatJourney.slice(0, 2),
        {
            title: 'Verify secure coding routes',
            detail: 'Review exact-model zero-cost, coding capability and documented no-training evidence.',
            complete: privateReady,
            tab: 'models',
        },
        {
            title: 'Create a coding token',
            detail: 'Issue a dedicated private-source token. A chat token is not sufficient.',
            complete: codingTokens > 0,
            tab: 'tokens',
        },
        {
            title: 'Connect and verify the worker',
            detail: 'Consent to the exact source scope, configure the enrolled device, and verify a real coding task. Worker evidence is not available on this page.',
            complete: false,
            href: '/services/kmj-codebridge',
        },
    ];
    const setupJourney = workflow === 'coding' ? codingJourney : chatJourney;
    const openWorkflowStep = (destination: Tab) => {
        if (destination === 'tokens') {
            setTokenPrivate(workflow === 'coding');
        }
        if (destination === 'models') {
            // Changing the purpose never carries forward another attestation.
            setConfirmed(false);
            setRuleConfirmed(false);
            setCreditAttested(false);
        }
        setTab(destination);
    };
    const chatNext = (() => {
        if (providers.length === 0) {
            return {
                text: 'Connect your first AI provider (Gemini, Groq or OpenRouter).',
                action: 'Open provider connect page',
                href: '/operator/modelfabric?tab=providers',
            };
        }
        if (healthy === 0) {
            return {
                text: 'No provider is healthy. Run Test connection on the provider page.',
                action: 'Open provider connect page',
                href: '/operator/modelfabric?tab=providers',
            };
        }
        if (!generalReady) {
            return {
                text: 'Approve at least one free model: open its provider page, confirm it is free, then save the evidence.',
                action: 'Verify a free model',
                tab: 'models' as Tab,
            };
        }
        if (chatTokens === 0) {
            return {
                text: 'Create a general chat API token. Secure coding needs its own verified routes and token.',
                action: 'Create API token',
                tab: 'tokens' as Tab,
            };
        }

        if (okRequests24h === 0) {
            return {
                text: 'Your routes and token are ready. Validate the ModelFabric token and run a safe, consented Playground test.',
                action: 'Open Playground',
                tab: 'playground' as Tab,
            };
        }

        return {
            text: 'ModelFabric has recorded a successful request in the last 24 hours. Check Activity; secure coding readiness is separate.',
            action: 'Open Activity',
            tab: 'activity' as Tab,
        };
    })();

    const codingNext = (() => {
        if (healthy === 0) {
            return {
                text: 'Connect and test a free provider before reviewing coding eligibility.',
                action: 'Connect providers',
                href: '/operator/modelfabric?tab=providers',
            };
        }
        if (!privateReady) {
            return {
                text: 'Secure coding is blocked: verify an exact coding model, zero cost and documented no-training handling.',
                action: 'Review coding evidence',
                tab: 'models' as Tab,
            };
        }
        if (codingTokens === 0) {
            return {
                text: 'Eligible coding routes found. Issue a dedicated private-source token.',
                action: 'Create coding token',
                tab: 'tokens' as Tab,
            };
        }
        return {
            text: 'Routes and token available. Source consent and real worker execution still need separate verification.',
            action: 'Open CodeBridge',
            href: '/services/kmj-codebridge',
        };
    })();
    const next = workflow === 'coding' ? codingNext : chatNext;
    const completedSteps = setupJourney.filter((step) => step.complete).length;
    const activeStep = setupJourney.findIndex((step) => !step.complete);

    const DAY = 86_400_000;
    const now = Date.now();
    const daysLeft = (iso: string) =>
        Math.ceil((new Date(iso).getTime() - now) / DAY);
    type Todo = {
        key: string;
        tone: 'bad' | 'warn';
        text: string;
        action: string;
        tab?: Tab;
        href?: string;
    };
    const todos: Todo[] = [];
    const expiredEvidence = evidence.filter(
        (row) => !row.revoked && !row.current,
    ).length;
    const soonEvidence = evidence.filter(
        (row) => row.current && !row.revoked && daysLeft(row.expires_at) <= 7,
    ).length;
    if (expiredEvidence > 0) {
        todos.push({
            key: 'expired',
            tone: 'bad',
            text: `${expiredEvidence} approval(s) expired and are no longer routed. Re-check the pricing page and renew.`,
            action: 'Renew approvals',
            tab: 'models',
        });
    }
    if (soonEvidence > 0) {
        todos.push({
            key: 'soon',
            tone: 'warn',
            text: `${soonEvidence} approval(s) expire within 7 days.`,
            action: 'Renew approvals',
            tab: 'models',
        });
    }
    const unhealthy = providers.filter(
        (p) => p.enabled && p.health !== 'ok',
    ).length;
    if (unhealthy > 0 && providers.length > 0) {
        todos.push({
            key: 'health',
            tone: 'warn',
            text: `${unhealthy} provider(s) are not healthy. Run Test connection.`,
            action: 'Open providers',
            href: '/operator/modelfabric?tab=providers',
        });
    }
    const unapproved = providers.filter(
        (p) =>
            p.enabled &&
            p.health === 'ok' &&
            p.discovered_model_count > 0 &&
            p.models.length === 0,
    ).length;
    if (unapproved > 0) {
        todos.push({
            key: 'unapproved',
            tone: 'warn',
            text: `${unapproved} healthy provider(s) have no approved free model yet, so they are not used.`,
            action: 'Approve models',
            tab: 'models',
        });
    }
    const tokenSoon = tokens.filter(
        (t) => t.active && daysLeft(t.expires_at) <= 7,
    ).length;
    if (tokenSoon > 0) {
        todos.push({
            key: 'tokens',
            tone: 'warn',
            text: `${tokenSoon} API token(s) expire within 7 days.`,
            action: 'Open tokens',
            tab: 'tokens',
        });
    }

    const save = () => {
        router.post(
            `${BASE}/evidence`,
            {
                provider_id: providerId,
                model_id: model,
                price_evidence_url: url,
                price_evidence_note: note,
                valid_days: days,
                data_handling: handling,
                capabilities: caps,
                cost_class: costClass,
                ...(costClass === 'credit-limited'
                    ? {
                          credit_daily_cap: Number(creditCap),
                          credit_hard_cap_attested: creditAttested,
                      }
                    : {}),
            },
            {
                preserveScroll: true,
                onSuccess: () => {
                    setNote('');
                    setModel('');
                    setConfirmed(false);
                    setCreditAttested(false);
                },
            },
        );
    };

    const saveAll = () => {
        router.post(
            `${BASE}/evidence/bulk`,
            {
                provider_id: providerId,
                model_ids: bulkModels,
                price_evidence_url: url,
                price_evidence_note: note,
                valid_days: days,
                data_handling: handling,
                capabilities: caps,
                attest_pricing: confirmed,
            },
            {
                preserveScroll: true,
                onSuccess: () => {
                    setNote('');
                    setModel('');
                    setConfirmed(false);
                    setPicked([]);
                },
            },
        );
    };

    const saveRule = () => {
        router.post(
            `${BASE}/rules`,
            {
                provider_id: providerId,
                model_pattern: rulePattern,
                price_evidence_url: ruleUrl,
                price_evidence_note: ruleNote,
                valid_days: 30,
                data_handling: handling,
                capabilities: ['chat'],
                attest_pricing: ruleConfirmed,
            },
            {
                preserveScroll: true,
                onSuccess: () => {
                    setRulePattern('');
                    setRuleNote('');
                    setRuleConfirmed(false);
                },
            },
        );
    };

    const renewRule = (id: string) => {
        if (
            !window.confirm(
                'Re-check the pricing page first. Renew this rule for 30 days?',
            )
        ) {
            return;
        }
        router.post(
            `${BASE}/rules/${id}/renew`,
            { attest_pricing: true },
            { preserveScroll: true },
        );
    };

    const renew = (id: string, credit = false) => {
        if (
            !window.confirm(
                credit
                    ? 'Re-check the credit page first. Confirm this account still cannot bill beyond the free credits, then renew for 30 days?'
                    : 'Re-check the evidence page first. Renew for 30 days?',
            )
        ) {
            return;
        }
        router.post(
            `${BASE}/evidence/${id}/renew`,
            credit
                ? { attest_pricing: true, credit_hard_cap_attested: true }
                : { attest_pricing: true },
            { preserveScroll: true },
        );
    };

    const copyToken = async () => {
        if (!newToken) {
            return;
        }
        try {
            await navigator.clipboard.writeText(newToken);
            setCopied(true);
        } catch {
            setCopied(false);
        }
    };

    const startEvidence = (id: string) => {
        setProviderId(id);
        setModel('');
        setConfirmed(false);
        setRuleConfirmed(false);
        setCreditAttested(false);
        setPicked([]);
        setUrl(
            PRICING_HINTS[providers.find((p) => p.id === id)?.preset ?? ''] ??
                '',
        );
        setTab('models');
    };

    const tabs: { key: Tab; label: string }[] = [
        { key: 'providers', label: 'AI workspace' },
        { key: 'models', label: 'Free models' },
        { key: 'tokens', label: 'API tokens' },
        { key: 'playground', label: 'Playground' },
        { key: 'activity', label: 'Activity' },
    ];

    return (
        <>
            <Head title="KMJ TECHNO — ModelFabric & AI" />
            <div className="owner-main p-3 sm:p-4">
                <section className="owner-hero">
                    <img src="/assets/locked/owner-earth.webp" alt="" />
                    <div>
                        <p>Free cloud AI</p>
                        <h1>ModelFabric &amp; AI</h1>
                        <h2>
                            Verified-zero routing for KMJ products and the
                            coding worker
                        </h2>
                        <p className="owner-hero-description">
                            A model is used only after you prove it is free
                            today (or it is credit-limited with a hard cap) and
                            its provider is healthy. No paid fallback.
                        </p>
                        <div className="owner-hero-actions">
                            {'href' in next ? (
                                <a className="owner-primary" href={next.href}>
                                    <Zap size={16} />
                                    {next.action}
                                    <ChevronRight size={16} />
                                </a>
                            ) : (
                                <button
                                    type="button"
                                    className="owner-primary"
                                    onClick={() => {
                                        openWorkflowStep(next.tab as Tab);
                                    }}
                                >
                                    <Zap size={16} />
                                    {next.action}
                                    <ChevronRight size={16} />
                                </button>
                            )}
                            {tab !== 'providers' && (
                                <button
                                    type="button"
                                    onClick={() => setTab('providers')}
                                >
                                    <Boxes size={16} />
                                    AI workspace
                                </button>
                            )}
                        </div>
                    </div>
                    <aside>
                        <strong>
                            <b>Model</b>Fabric
                        </strong>
                        <p>
                            <LockKeyhole className="mr-1 inline h-3 w-3" />
                            Paid inference cannot be enabled from this page
                        </p>
                        <div>
                            <span>
                                <b>{providers.length}</b>Providers
                            </span>
                            <span>
                                <b>{plans.chat.routes.length}</b>Free models
                            </span>
                            <span>
                                <b>0</b>Paid fallback
                            </span>
                        </div>
                    </aside>
                </section>

                {status ? (
                    <p
                        role="status"
                        className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm"
                    >
                        {status}
                    </p>
                ) : null}

                <section
                    className="owner-stats"
                    aria-label="ModelFabric snapshot"
                >
                    <StatTile
                        icon={Server}
                        tone="cyan"
                        label="Providers healthy"
                        value={`${healthy} / ${providers.length}`}
                        detail="Passed Test connection"
                    />
                    <StatTile
                        icon={ShieldCheck}
                        tone="green"
                        label="Free models approved"
                        value={String(plans.chat.routes.length)}
                        detail={`${currentEvidence} with your evidence`}
                    />
                    <StatTile
                        icon={LockKeyhole}
                        tone="purple"
                        label="Private-source routes"
                        value={String(plans.privateSource.routes.length)}
                        detail="Need no-training proof"
                    />
                    <StatTile
                        icon={KeyRound}
                        tone="amber"
                        label="API tokens"
                        value={String(activeTokens)}
                        detail={`${chatTokens} chat · ${codingTokens} coding`}
                    />
                    <StatTile
                        icon={Activity}
                        tone="green"
                        label="Requests (24 h)"
                        value={String(requests24h)}
                        detail={`${okRequests24h} answered`}
                    />
                </section>

                <section className="owner-panel">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex items-start gap-3 text-sm">
                            <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
                            <span>
                                <strong className="block text-[10px] tracking-wide text-red-500 uppercase">
                                    {workflow === 'coding'
                                        ? 'Secure coding · next step'
                                        : 'General chat · next step'}
                                </strong>
                                {next.text}
                            </span>
                        </div>
                        <nav
                            aria-label="ModelFabric sections"
                            className="flex gap-1.5 overflow-x-auto"
                        >
                            {tabs.map((item) => (
                                <button
                                    key={item.key}
                                    type="button"
                                    className="kmj-admin-tab"
                                    aria-current={
                                        tab === item.key ? 'page' : undefined
                                    }
                                    onClick={() => openWorkflowStep(item.key)}
                                >
                                    {item.label}
                                </button>
                            ))}
                        </nav>
                    </div>
                </section>

                {tab === 'providers' ? (
                    <AiProviders
                        embedded
                        canManage={canManage}
                        presets={providerPresets}
                        providers={providers}
                        renderRoutingControls={(id) => {
                            const provider = providers.find(
                                (item) => item.id === id,
                            );
                            if (!provider) return null;
                            return (
                                <>
                                    {provider.error_code &&
                                    errorHelp(provider.error_code) ? (
                                        <p
                                            className="text-muted-foreground text-xs"
                                            data-testid="modelfabric-error-help"
                                        >
                                            {errorHelp(provider.error_code)}
                                        </p>
                                    ) : null}
                                    <details className="rounded-lg border p-2">
                                        <summary className="cursor-pointer text-sm font-medium">
                                            Usage and routing limits
                                        </summary>
                                        <ProviderLimits
                                            provider={provider}
                                            canManage={canManage}
                                        />
                                    </details>
                                    {canManage &&
                                    provider.free_tier === 'allowlist' ? (
                                        <button
                                            type="button"
                                            className={ghostButton}
                                            onClick={() =>
                                                startEvidence(provider.id)
                                            }
                                        >
                                            Review free models
                                        </button>
                                    ) : null}
                                </>
                            );
                        }}
                    />
                ) : null}

                {tab === 'providers' ? (
                    <details className="owner-panel">
                        <summary className="cursor-pointer text-base font-bold">
                            Setup checklist and advanced readiness
                        </summary>
                        <div className="mt-4 grid gap-3">
                            <section
                                aria-label="Choose your AI workflow"
                                data-testid="modelfabric-workflow-readiness"
                                className="grid gap-3 lg:grid-cols-2"
                            >
                                <div
                                    className={`owner-panel space-y-4 ${workflow === 'chat' ? 'ring-1 ring-red-500/50' : ''}`}
                                >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <h2 className="flex items-center gap-2 text-base font-bold">
                                            <Zap
                                                size={18}
                                                className="text-cyan-400"
                                            />{' '}
                                            General AI chat
                                        </h2>
                                        <StatusPill
                                            tone={
                                                generalReady && chatTokens > 0
                                                    ? 'ok'
                                                    : 'warn'
                                            }
                                        >
                                            {generalReady && chatTokens > 0
                                                ? 'Ready to test'
                                                : 'Setup required'}
                                        </StatusPill>
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="bg-muted/25 rounded-xl border p-3">
                                            <div className="text-xl font-bold tabular-nums">
                                                {plans.chat.routes.length}
                                            </div>
                                            <div className="text-muted-foreground text-xs">
                                                Eligible chat routes
                                            </div>
                                        </div>
                                        <div className="bg-muted/25 rounded-xl border p-3">
                                            <div className="text-xl font-bold tabular-nums">
                                                {chatTokens}
                                            </div>
                                            <div className="text-muted-foreground text-xs">
                                                Active chat tokens
                                            </div>
                                        </div>
                                    </div>
                                    <p className="text-muted-foreground text-sm">
                                        For non-confidential prompts only.
                                    </p>
                                    <button
                                        type="button"
                                        className={
                                            workflow === 'chat'
                                                ? primaryButton
                                                : ghostButton
                                        }
                                        onClick={() => {
                                            setWorkflow('chat');
                                            setConfirmed(false);
                                            setRuleConfirmed(false);
                                            setCreditAttested(false);
                                            if (
                                                generalReady &&
                                                chatTokens === 0
                                            )
                                                setTokenPrivate(false);
                                            setTab(
                                                !generalReady
                                                    ? 'models'
                                                    : chatTokens === 0
                                                      ? 'tokens'
                                                      : 'playground',
                                            );
                                        }}
                                    >
                                        {!generalReady
                                            ? 'Review free routes'
                                            : chatTokens === 0
                                              ? 'Create chat token'
                                              : 'Test chat'}{' '}
                                        <ArrowRight size={15} />
                                    </button>
                                </div>
                                <div
                                    className={`owner-panel space-y-4 ${workflow === 'coding' ? 'ring-1 ring-red-500/50' : ''}`}
                                >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <h2 className="flex items-center gap-2 text-base font-bold">
                                            <LockKeyhole
                                                size={18}
                                                className="text-violet-400"
                                            />{' '}
                                            Secure coding
                                        </h2>
                                        <StatusPill
                                            tone={
                                                privateReady && codingTokens > 0
                                                    ? 'ok'
                                                    : 'warn'
                                            }
                                        >
                                            {privateReady && codingTokens > 0
                                                ? 'Route and token ready'
                                                : 'Blocked'}
                                        </StatusPill>
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="bg-muted/25 rounded-xl border p-3">
                                            <div className="text-xl font-bold tabular-nums">
                                                {
                                                    plans.privateSource.routes
                                                        .length
                                                }
                                            </div>
                                            <div className="text-muted-foreground text-xs">
                                                Eligible coding routes
                                            </div>
                                        </div>
                                        <div className="bg-muted/25 rounded-xl border p-3">
                                            <div className="text-xl font-bold tabular-nums">
                                                {codingTokens}
                                            </div>
                                            <div className="text-muted-foreground text-xs">
                                                Active coding tokens
                                            </div>
                                        </div>
                                    </div>
                                    <p className="text-muted-foreground text-sm">
                                        Separate source-transfer consent and
                                        worker activation required.
                                    </p>
                                    {!privateReady ? (
                                        <p className="text-sm leading-relaxed">
                                            Review exact-model pricing, code
                                            capability and no-training evidence.
                                            A chat token cannot authorize
                                            private source.
                                        </p>
                                    ) : null}
                                    <button
                                        type="button"
                                        className={
                                            workflow === 'coding'
                                                ? primaryButton
                                                : ghostButton
                                        }
                                        onClick={() => {
                                            setWorkflow('coding');
                                            if (!privateReady) {
                                                setConfirmed(false);
                                                setRuleConfirmed(false);
                                                setCreditAttested(false);
                                                setTab('models');
                                            } else if (codingTokens === 0) {
                                                setTokenPrivate(true);
                                                setTab('tokens');
                                            } else {
                                                router.visit(
                                                    '/services/kmj-codebridge',
                                                );
                                            }
                                        }}
                                    >
                                        {!privateReady
                                            ? 'Review coding evidence'
                                            : codingTokens === 0
                                              ? 'Create coding token'
                                              : 'Open CodeBridge'}{' '}
                                        <ArrowRight size={15} />
                                    </button>
                                </div>
                            </section>
                            <section
                                className="owner-panel"
                                aria-label="ModelFabric setup journey"
                                data-testid="modelfabric-setup-journey"
                            >
                                <div className="flex flex-wrap items-center justify-between gap-4">
                                    <div>
                                        <h2 className="flex items-center gap-2 text-base font-bold">
                                            <ShieldCheck
                                                size={18}
                                                className="text-red-500"
                                            />{' '}
                                            Guided setup
                                        </h2>
                                        <p className="text-muted-foreground mt-1 text-xs">
                                            Complete one workflow at a time. No
                                            step runs inference automatically.
                                        </p>
                                    </div>
                                    <div
                                        className="flex gap-1 rounded-xl border p-1"
                                        aria-label="Choose setup workflow"
                                    >
                                        {(['chat', 'coding'] as const).map(
                                            (mode) => (
                                                <button
                                                    key={mode}
                                                    type="button"
                                                    aria-pressed={
                                                        workflow === mode
                                                    }
                                                    className={`rounded-lg px-3 py-2 text-xs font-bold transition ${workflow === mode ? 'bg-red-600 text-white' : 'text-muted-foreground hover:bg-muted'}`}
                                                    onClick={() =>
                                                        setWorkflow(mode)
                                                    }
                                                >
                                                    {mode === 'chat'
                                                        ? 'General chat'
                                                        : 'Secure coding'}
                                                </button>
                                            ),
                                        )}
                                    </div>
                                </div>
                                <div className="mt-4 flex items-center gap-3">
                                    <div
                                        role="progressbar"
                                        aria-label="Setup evidence"
                                        aria-valuemin={0}
                                        aria-valuemax={setupJourney.length}
                                        aria-valuenow={completedSteps}
                                        className="bg-muted h-2 flex-1 overflow-hidden rounded-full"
                                    >
                                        <div
                                            className="h-full rounded-full bg-red-600 transition-all"
                                            style={{
                                                width: `${(completedSteps / setupJourney.length) * 100}%`,
                                            }}
                                        />
                                    </div>
                                    <span className="text-muted-foreground text-xs tabular-nums">
                                        {completedSteps} / {setupJourney.length}{' '}
                                        evidenced
                                    </span>
                                </div>
                                <ol className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
                                    {setupJourney.map((step, index) => (
                                        <li
                                            key={step.title}
                                            className={`flex flex-col gap-3 rounded-xl border p-4 ${index === activeStep ? 'border-red-500/60 bg-red-500/5' : 'border-border'}`}
                                        >
                                            <div className="flex items-center justify-between gap-2">
                                                <strong className="text-xs">
                                                    {index + 1}. {step.title}
                                                </strong>
                                                <StatusPill
                                                    tone={
                                                        step.complete
                                                            ? 'ok'
                                                            : 'warn'
                                                    }
                                                >
                                                    {step.complete
                                                        ? 'Evidence found'
                                                        : index === activeStep
                                                          ? 'Next action'
                                                          : 'Pending'}
                                                </StatusPill>
                                            </div>
                                            <p className="text-muted-foreground flex-1 text-xs leading-5">
                                                {step.detail}
                                            </p>
                                            {step.href ? (
                                                <a
                                                    className={ghostButton}
                                                    href={step.href}
                                                >
                                                    Open setup{' '}
                                                    <ChevronRight size={13} />
                                                </a>
                                            ) : (
                                                <button
                                                    type="button"
                                                    className={ghostButton}
                                                    onClick={() =>
                                                        openWorkflowStep(
                                                            step.tab ?? 'providers',
                                                        )
                                                    }
                                                >
                                                    {step.complete
                                                        ? 'Review'
                                                        : 'Open step'}{' '}
                                                    <ChevronRight size={13} />
                                                </button>
                                            )}
                                        </li>
                                    ))}
                                </ol>
                            </section>
                            <section
                                className="owner-panel"
                                aria-label="To do"
                                data-testid="modelfabric-todo"
                            >
                                <p className="text-sm font-black">
                                    To do today
                                </p>
                                {todos.length === 0 ? (
                                    <p className="text-muted-foreground mt-1 text-sm">
                                        Nothing needs your attention. Approvals,
                                        providers and tokens are all current.
                                    </p>
                                ) : (
                                    <ul className="mt-2 divide-y text-sm">
                                        {todos.map((todo) => (
                                            <li
                                                key={todo.key}
                                                className="flex flex-wrap items-center justify-between gap-2 py-2"
                                            >
                                                <span>
                                                    <StatusPill
                                                        tone={todo.tone}
                                                    >
                                                        {todo.tone === 'bad'
                                                            ? 'now'
                                                            : 'soon'}
                                                    </StatusPill>{' '}
                                                    {todo.text}
                                                </span>
                                                {todo.href ? (
                                                    <a
                                                        className={ghostButton}
                                                        href={todo.href}
                                                    >
                                                        {todo.action}
                                                    </a>
                                                ) : (
                                                    <button
                                                        type="button"
                                                        className={ghostButton}
                                                        onClick={() =>
                                                            setTab(
                                                                todo.tab ??
                                                                    'models',
                                                            )
                                                        }
                                                    >
                                                        {todo.action}
                                                    </button>
                                                )}
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </section>
                            <details className="owner-panel" id="routes">
                                <summary className="cursor-pointer text-sm font-bold">
                                    Routing diagnostics &amp; provider
                                    eligibility
                                </summary>
                                <section
                                    className="mt-4 grid gap-4 md:grid-cols-2"
                                    aria-label="Route plan"
                                >
                                    <PlanCard
                                        title="General chat"
                                        note="Used by CodeBridge chat and Kristi guided features."
                                        plan={plans.chat}
                                    />
                                    <PlanCard
                                        title="Private source code"
                                        note="Needs proof the provider does not train on submitted data. Your consent for source transfer is still separate."
                                        plan={plans.privateSource}
                                    />
                                </section>
                            </details>
                            <div className="owner-panel flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <h2 className="text-sm font-bold">
                                        Provider management
                                    </h2>
                                    <p className="text-muted-foreground text-sm">
                                        {healthy} of {providers.length}{' '}
                                        providers healthy. Review connection
                                        errors, quotas and model evidence in
                                        Providers.
                                    </p>
                                </div>
                                <button
                                    type="button"
                                    className={ghostButton}
                                    onClick={() => setTab('providers')}
                                >
                                    Manage providers <ArrowRight size={15} />
                                </button>
                            </div>
                        </div>
                    </details>
                ) : null}

                {tab === 'models' ? (
                    <Card
                        id="evidence-form"
                        title="Approve a free model"
                        label="Price evidence"
                        help={`Open the provider's own page, confirm this exact model is free, then record it. Approval expires after at most ${maxEvidenceDays} days and can be revoked at any time. A free account does not make every model free.`}
                    >
                        {workflow === 'coding' ? (
                            <div className="mb-4 rounded-xl border border-violet-500/25 bg-violet-500/5 p-4 text-sm">
                                <h3 className="flex items-center gap-2 font-bold">
                                    <LockKeyhole size={16} /> Secure coding
                                    eligibility
                                </h3>
                                <p className="text-muted-foreground mt-2 leading-relaxed">
                                    Select the exact discovered model. Verify
                                    zero-cost pricing, select Code capability,
                                    and select documented no-training handling
                                    only when supported by the provider.
                                    Source-transfer consent and device
                                    activation are separate.
                                </p>
                            </div>
                        ) : null}
                        {canManage && allowlistProviders.length > 0 ? (
                            <form
                                className="grid gap-4 md:grid-cols-2"
                                onSubmit={(event) => {
                                    event.preventDefault();
                                    if (canSave) {
                                        save();
                                    }
                                }}
                            >
                                <label className="text-sm font-medium">
                                    Provider
                                    <select
                                        className={fieldClass}
                                        value={providerId}
                                        onChange={(e) => {
                                            setProviderId(e.target.value);
                                            setModel('');
                                            setConfirmed(false);
                                            setRuleConfirmed(false);
                                            setCreditAttested(false);
                                            setPicked([]);
                                        }}
                                    >
                                        {allowlistProviders.map((provider) => (
                                            <option
                                                key={provider.id}
                                                value={provider.id}
                                            >
                                                {provider.name}
                                            </option>
                                        ))}
                                    </select>
                                </label>
                                <label className="text-sm font-medium">
                                    Model{' '}
                                    <span className="text-muted-foreground text-xs font-normal">
                                        (pick from{' '}
                                        {selected?.discovered_model_count ?? 0}{' '}
                                        found)
                                    </span>
                                    <input
                                        className={fieldClass}
                                        list="modelfabric-models"
                                        value={model}
                                        onChange={(e) => {
                                            setModel(e.target.value);
                                            setConfirmed(false);
                                            setCreditAttested(false);
                                        }}
                                        placeholder="Start typing a model name"
                                        autoComplete="off"
                                    />
                                    <datalist id="modelfabric-models">
                                        {(
                                            selected?.discovered_models ?? []
                                        ).map((name) => (
                                            <option key={name} value={name} />
                                        ))}
                                    </datalist>
                                    {model !== '' && !modelKnown ? (
                                        <span className="text-xs text-amber-600 dark:text-amber-300">
                                            Not in the last discovery: pick a
                                            listed model or run Test connection.
                                        </span>
                                    ) : null}
                                </label>
                                <label className="text-sm font-medium md:col-span-2">
                                    Provider page that shows this model is free
                                    (https)
                                    <input
                                        className={fieldClass}
                                        type="url"
                                        value={url}
                                        onChange={(e) => setUrl(e.target.value)}
                                        placeholder="https://provider.example/pricing"
                                    />
                                    {hint ? (
                                        <span className="mt-1 flex flex-wrap items-center gap-3 text-xs font-normal">
                                            <button
                                                type="button"
                                                className="font-bold underline"
                                                onClick={() => setUrl(hint)}
                                            >
                                                Use suggested page
                                            </button>
                                            <a
                                                className="inline-flex items-center gap-1 font-bold underline"
                                                href={hint}
                                                target="_blank"
                                                rel="noreferrer noopener"
                                            >
                                                Open it{' '}
                                                <ExternalLink className="h-3 w-3" />
                                            </a>
                                            <span className="text-muted-foreground">
                                                Suggestion only: you must verify
                                                it.
                                            </span>
                                        </span>
                                    ) : null}
                                </label>
                                <label className="text-sm font-medium md:col-span-2">
                                    What the page says (10–280 characters)
                                    <input
                                        className={fieldClass}
                                        value={note}
                                        maxLength={280}
                                        onChange={(e) =>
                                            setNote(e.target.value)
                                        }
                                        placeholder="e.g. Free tier lists this model at zero cost with N requests per minute"
                                    />
                                </label>
                                <label className="text-sm font-medium">
                                    Approval valid for (days, max{' '}
                                    {maxEvidenceDays})
                                    <input
                                        className={fieldClass}
                                        type="number"
                                        min={1}
                                        max={maxEvidenceDays}
                                        value={days}
                                        onChange={(e) =>
                                            setDays(Number(e.target.value))
                                        }
                                    />
                                </label>
                                <label className="text-sm font-medium">
                                    Data handling
                                    <select
                                        className={fieldClass}
                                        value={handling}
                                        onChange={(e) =>
                                            setHandling(e.target.value)
                                        }
                                    >
                                        <option value="unknown">
                                            Unknown (never used for private
                                            source)
                                        </option>
                                        <option value="no-training-documented">
                                            Provider documents no training on my
                                            data
                                        </option>
                                    </select>
                                </label>
                                <label className="text-sm font-medium">
                                    Cost type
                                    <select
                                        className={fieldClass}
                                        value={costClass}
                                        onChange={(e) =>
                                            setCostClass(
                                                e.target.value as
                                                    | 'free'
                                                    | 'credit-limited',
                                            )
                                        }
                                    >
                                        <option value="free">
                                            Free tier (no cost)
                                        </option>
                                        <option value="credit-limited">
                                            Credit-limited (free credits that
                                            run out)
                                        </option>
                                    </select>
                                </label>
                                {costClass === 'credit-limited' ? (
                                    <>
                                        <label className="text-sm font-medium">
                                            KMJ daily request cap (required)
                                            <input
                                                className={fieldClass}
                                                type="number"
                                                min={1}
                                                value={creditCap}
                                                onChange={(e) =>
                                                    setCreditCap(e.target.value)
                                                }
                                            />
                                        </label>
                                        <label className="flex items-start gap-2 text-sm md:col-span-2">
                                            <input
                                                type="checkbox"
                                                className="mt-1"
                                                checked={creditAttested}
                                                onChange={(e) =>
                                                    setCreditAttested(
                                                        e.target.checked,
                                                    )
                                                }
                                            />
                                            This provider account has no payment
                                            method or a hard cap, so it cannot
                                            bill me beyond the free credits, and
                                            the page shows the credit amount.
                                        </label>
                                    </>
                                ) : null}
                                <fieldset className="text-sm md:col-span-2">
                                    <legend className="font-medium">
                                        What this model may be used for
                                    </legend>
                                    <div className="mt-1 flex flex-wrap gap-4">
                                        {[
                                            'chat',
                                            'tools',
                                            'code',
                                            'vision',
                                        ].map((cap) => (
                                            <label
                                                key={cap}
                                                className="flex items-center gap-2"
                                            >
                                                <input
                                                    type="checkbox"
                                                    checked={caps.includes(cap)}
                                                    onChange={(e) =>
                                                        setCaps(
                                                            e.target.checked
                                                                ? [...caps, cap]
                                                                : caps.filter(
                                                                      (item) =>
                                                                          item !==
                                                                          cap,
                                                                  ),
                                                        )
                                                    }
                                                />
                                                {cap}
                                            </label>
                                        ))}
                                    </div>
                                    <p className="text-muted-foreground mt-1 text-xs">
                                        Tick <strong>code</strong> to let this
                                        model serve the coding worker.
                                    </p>
                                </fieldset>
                                {listedModels.length > 1 ? (
                                    <fieldset className="text-sm md:col-span-2">
                                        <legend className="font-medium">
                                            Approve several at once (tick only
                                            models the page shows as free)
                                        </legend>
                                        <div className="mt-1 grid max-h-48 gap-1 overflow-y-auto sm:grid-cols-2">
                                            {listedModels.map((id) => (
                                                <label
                                                    key={id}
                                                    className="flex items-center gap-2 text-xs"
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={picked.includes(
                                                            id,
                                                        )}
                                                        onChange={(e) =>
                                                            setPicked(
                                                                e.target.checked
                                                                    ? [
                                                                          ...picked,
                                                                          id,
                                                                      ]
                                                                    : picked.filter(
                                                                          (
                                                                              item,
                                                                          ) =>
                                                                              item !==
                                                                              id,
                                                                      ),
                                                            )
                                                        }
                                                    />
                                                    {id}
                                                </label>
                                            ))}
                                        </div>
                                    </fieldset>
                                ) : null}
                                <label className="flex items-start gap-2 text-sm md:col-span-2">
                                    <input
                                        type="checkbox"
                                        className="mt-1"
                                        checked={confirmed}
                                        onChange={(e) =>
                                            setConfirmed(e.target.checked)
                                        }
                                    />
                                    I opened this page myself and it shows the
                                    model(s) I approve are free today.
                                </label>
                                <div className="flex flex-wrap items-center gap-3 md:col-span-2">
                                    <button
                                        type="submit"
                                        className={primaryButton}
                                        disabled={!canSave}
                                    >
                                        Save approval
                                    </button>
                                    {listedModels.length > 1 ? (
                                        <button
                                            type="button"
                                            className={primaryButton}
                                            disabled={!canBulk}
                                            onClick={saveAll}
                                        >
                                            Approve {bulkModels.length} selected
                                            model(s)
                                        </button>
                                    ) : null}
                                    {!canSave ? (
                                        <span className="text-muted-foreground text-xs">
                                            Pick a listed model, add an https
                                            page and a short note, then tick the
                                            confirmation.
                                        </span>
                                    ) : null}
                                </div>
                                {errors
                                    ? Object.values(errors).map((message) => (
                                          <p
                                              key={message}
                                              role="alert"
                                              className="text-sm text-red-500 md:col-span-2"
                                          >
                                              {message}
                                          </p>
                                      ))
                                    : null}
                            </form>
                        ) : (
                            <p className="text-sm">
                                {canManage
                                    ? 'Connect a provider with an allowlist tier (Groq, Gemini, Cerebras, Mistral, SambaNova, Hugging Face, NVIDIA, GitHub Models) and run Test connection first.'
                                    : 'You can view approvals; managing them needs organization manager rights.'}
                            </p>
                        )}

                        <h3 className="mt-6 text-sm font-black">
                            Approved models
                        </h3>
                        <ul className="mt-3 space-y-2 text-sm">
                            {evidence.length === 0 ? (
                                <li className="text-muted-foreground">
                                    No model approved yet.
                                </li>
                            ) : null}
                            {evidence.map((row) => (
                                <li
                                    key={row.id}
                                    className="flex flex-wrap items-center justify-between gap-2 rounded-xl border p-3"
                                >
                                    <span>
                                        <strong>{row.model_id}</strong>{' '}
                                        <StatusPill
                                            tone={
                                                row.current
                                                    ? 'ok'
                                                    : row.revoked
                                                      ? 'bad'
                                                      : 'warn'
                                            }
                                        >
                                            {row.current
                                                ? 'current'
                                                : row.revoked
                                                  ? 'revoked'
                                                  : 'expired'}
                                        </StatusPill>{' '}
                                        <span className="text-muted-foreground text-xs">
                                            until{' '}
                                            {formatIstDate(row.expires_at)} ·{' '}
                                            {row.data_handling} ·{' '}
                                            {row.capabilities.join(', ')} ·{' '}
                                            {row.cost_class === 'credit-limited'
                                                ? `credit-limited, cap ${row.credit_daily_cap ?? 0}/day · `
                                                : ''}
                                        </span>
                                        <a
                                            className="text-xs font-bold underline"
                                            href={row.price_evidence_url}
                                            rel="noreferrer noopener"
                                            target="_blank"
                                        >
                                            evidence
                                        </a>
                                    </span>
                                    {canManage && !row.revoked ? (
                                        <button
                                            type="button"
                                            className="inline-flex items-center gap-1 text-xs font-bold"
                                            onClick={() =>
                                                renew(
                                                    row.id,
                                                    row.cost_class ===
                                                        'credit-limited',
                                                )
                                            }
                                        >
                                            Renew 30 days
                                        </button>
                                    ) : null}
                                    {canManage && row.current ? (
                                        <button
                                            type="button"
                                            className="inline-flex items-center gap-1 text-xs font-bold text-red-500"
                                            onClick={() =>
                                                router.delete(
                                                    `${BASE}/evidence/${row.id}`,
                                                    { preserveScroll: true },
                                                )
                                            }
                                        >
                                            <Trash2 className="h-3 w-3" />{' '}
                                            Revoke
                                        </button>
                                    ) : null}
                                </li>
                            ))}
                        </ul>
                    </Card>
                ) : null}

                {tab === 'models' && allowlistProviders.length > 0 ? (
                    <Card
                        id="auto-rules"
                        title="Auto-approve rule"
                        label="Automation"
                        help="Attest once that every chat model matching a pattern is free today, and matching models, including new ones, are approved for you until the rule expires (30 days). Image, audio, live and embedding models are never included. Use the provider and pricing page chosen in the form above."
                    >
                        {canManage ? (
                            <div className="grid gap-3 md:grid-cols-2">
                                <label className="text-sm md:col-span-2">
                                    <span className="font-medium">
                                        Model pattern (needs at least 10 letters
                                        before the first *)
                                    </span>
                                    <input
                                        className={fieldClass}
                                        value={rulePattern}
                                        placeholder="models/gemini-2.5-flash*"
                                        onChange={(e) =>
                                            setRulePattern(
                                                e.target.value.trim(),
                                            )
                                        }
                                    />
                                </label>
                                <label className="text-sm">
                                    <span className="font-medium">
                                        Pricing page (https)
                                    </span>
                                    <input
                                        className={fieldClass}
                                        value={ruleUrl}
                                        placeholder="https://ai.google.dev/gemini-api/docs/pricing"
                                        onChange={(e) =>
                                            setRuleUrl(e.target.value.trim())
                                        }
                                    />
                                </label>
                                <label className="text-sm">
                                    <span className="font-medium">
                                        What the page says
                                    </span>
                                    <input
                                        className={fieldClass}
                                        value={ruleNote}
                                        placeholder="Free tier lists these models as free of charge"
                                        onChange={(e) =>
                                            setRuleNote(e.target.value)
                                        }
                                    />
                                </label>
                                <p className="text-muted-foreground text-xs md:col-span-2">
                                    {selected
                                        ? `${ruleMatches.length} listed model(s) of ${selected.name} match now.`
                                        : 'Pick a provider in the form above.'}
                                    {ruleMatches.length > 50
                                        ? ' Too many (max 50): narrow the pattern.'
                                        : ''}
                                </p>
                                <label className="flex items-start gap-2 text-sm md:col-span-2">
                                    <input
                                        type="checkbox"
                                        className="mt-1"
                                        checked={ruleConfirmed}
                                        onChange={(e) =>
                                            setRuleConfirmed(e.target.checked)
                                        }
                                    />
                                    I opened this page myself and it shows every
                                    chat model matching this pattern is free
                                    today, and the account is on the free tier
                                    with no billing.
                                </label>
                                <div className="md:col-span-2">
                                    <button
                                        type="button"
                                        className={primaryButton}
                                        disabled={
                                            !canRule ||
                                            ruleMatches.length === 0 ||
                                            ruleMatches.length > 50
                                        }
                                        onClick={saveRule}
                                    >
                                        Save auto-approve rule
                                    </button>
                                </div>
                            </div>
                        ) : null}
                        <ul className="mt-4 space-y-2 text-sm">
                            {rules.length === 0 ? (
                                <li className="text-muted-foreground">
                                    No rule yet.
                                </li>
                            ) : null}
                            {rules.map((rule) => (
                                <li
                                    key={rule.id}
                                    className="flex flex-wrap items-center justify-between gap-2 rounded-xl border p-3"
                                >
                                    <span>
                                        <strong>{rule.model_pattern}</strong>{' '}
                                        <StatusPill
                                            tone={
                                                rule.active
                                                    ? 'ok'
                                                    : rule.revoked
                                                      ? 'bad'
                                                      : 'warn'
                                            }
                                        >
                                            {rule.active
                                                ? 'active'
                                                : rule.revoked
                                                  ? 'revoked'
                                                  : 'expired'}
                                        </StatusPill>{' '}
                                        <span className="text-muted-foreground text-xs">
                                            {rule.matches} match now · until{' '}
                                            {formatIstDate(rule.expires_at)}
                                        </span>
                                    </span>
                                    {canManage && !rule.revoked ? (
                                        <span className="flex gap-3 text-xs font-bold">
                                            <button
                                                type="button"
                                                onClick={() =>
                                                    renewRule(rule.id)
                                                }
                                            >
                                                Renew 30 days
                                            </button>
                                            <button
                                                type="button"
                                                className="text-red-500"
                                                onClick={() =>
                                                    router.delete(
                                                        `${BASE}/rules/${rule.id}`,
                                                        {
                                                            preserveScroll: true,
                                                        },
                                                    )
                                                }
                                            >
                                                Revoke
                                            </button>
                                        </span>
                                    ) : null}
                                </li>
                            ))}
                        </ul>
                    </Card>
                ) : null}

                {tab === 'tokens' ? (
                    <Card
                        id="tokens"
                        title="ModelFabric API tokens (OpenAI-compatible)"
                        label="API tokens"
                        help="The caller never chooses a provider or model: ModelFabric picks only from your approved free models and says NO_FREE_ROUTE_AVAILABLE when none qualifies. Private-source tokens reach only models with documented no-training handling. Tokens are stored as a hash and shown once."
                    >
                        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3">
                            <p className="text-muted-foreground text-xs">
                                Tokens are optional for ordinary CodeBridge
                                tools. A coding token alone does not authorize
                                source transfer or enable a device worker.
                            </p>
                            <a
                                className={ghostButton}
                                href="/services/kmj-codebridge#setup"
                            >
                                Back to CodeBridge setup
                            </a>
                        </div>
                        {newToken ? (
                            <div
                                className="mb-4 rounded-xl border border-emerald-500/40 bg-emerald-500/5 p-4"
                                data-testid="modelfabric-new-token"
                            >
                                <p className="text-xs font-bold text-emerald-700 dark:text-emerald-300">
                                    Copy this token now. It will not be shown
                                    again.
                                </p>
                                <p className="mt-2 font-mono text-xs break-all">
                                    {newToken}
                                </p>
                                <button
                                    type="button"
                                    className={`${ghostButton} mt-3`}
                                    onClick={copyToken}
                                >
                                    <Copy className="h-3 w-3" />{' '}
                                    {copied ? 'Copied' : 'Copy token'}
                                </button>
                            </div>
                        ) : null}
                        {canManage ? (
                            <form
                                className="grid gap-3 md:grid-cols-4"
                                onSubmit={(event) => {
                                    event.preventDefault();
                                    router.post(
                                        `${BASE}/tokens`,
                                        {
                                            name: tokenName,
                                            valid_days: Number(tokenDays),
                                            private_source: tokenPrivate,
                                        },
                                        { preserveScroll: true },
                                    );
                                    setTokenName('');
                                }}
                            >
                                <label className="text-sm font-medium">
                                    Name
                                    <input
                                        className={fieldClass}
                                        value={tokenName}
                                        onChange={(e) =>
                                            setTokenName(e.target.value)
                                        }
                                        placeholder="coding-worker"
                                        minLength={3}
                                        maxLength={80}
                                        required
                                    />
                                </label>
                                <label className="text-sm font-medium">
                                    Valid days (1-90)
                                    <input
                                        className={fieldClass}
                                        type="number"
                                        min={1}
                                        max={90}
                                        value={tokenDays}
                                        onChange={(e) =>
                                            setTokenDays(e.target.value)
                                        }
                                    />
                                </label>
                                <label className="flex items-end gap-2 pb-2 text-sm">
                                    <input
                                        type="checkbox"
                                        checked={tokenPrivate}
                                        onChange={(e) =>
                                            setTokenPrivate(e.target.checked)
                                        }
                                    />
                                    Private source (secure coding)
                                </label>
                                <div className="flex items-end">
                                    <button
                                        type="submit"
                                        className={primaryButton}
                                        disabled={
                                            tokenPrivate
                                                ? !privateReady
                                                : !generalReady
                                        }
                                    >
                                        Create token
                                    </button>
                                </div>
                                {tokenPrivate && !privateReady ? (
                                    <p
                                        className="text-xs font-bold text-amber-600 md:col-span-4 dark:text-amber-300"
                                        data-testid="modelfabric-private-warning"
                                    >
                                        No eligible private-source route is
                                        available, so a private-source token
                                        would answer NO_FREE_ROUTE_AVAILABLE for
                                        every request. Untick Private source
                                        only for general chat with
                                        non-confidential prompts. Never submit
                                        private code using a chat token.
                                    </p>
                                ) : null}
                            </form>
                        ) : null}
                        <ConnectGuide origin={origin} token={newToken} />
                        <ul className="mt-3 divide-y text-sm">
                            {tokens.length === 0 ? (
                                <li className="py-2">No token created yet.</li>
                            ) : null}
                            {tokens.map((token) => (
                                <li
                                    key={token.id}
                                    className="flex items-center justify-between gap-2 py-2"
                                >
                                    <span>
                                        <strong>{token.name}</strong>{' '}
                                        <StatusPill
                                            tone={token.active ? 'ok' : 'muted'}
                                        >
                                            {token.active
                                                ? 'active'
                                                : 'inactive'}
                                        </StatusPill>{' '}
                                        <span className="text-muted-foreground text-xs">
                                            {token.prefix}… ·{' '}
                                            {token.private_source
                                                ? 'private source'
                                                : 'general'}{' '}
                                            · expires{' '}
                                            {formatIstDate(token.expires_at)}
                                            {token.last_used_at
                                                ? ` · last used ${formatIstStamp(token.last_used_at)}`
                                                : ' · never used'}
                                        </span>
                                    </span>
                                    {canManage && token.active ? (
                                        <button
                                            type="button"
                                            aria-label={`Revoke ${token.name}`}
                                            onClick={() =>
                                                router.delete(
                                                    `${BASE}/tokens/${token.id}`,
                                                    { preserveScroll: true },
                                                )
                                            }
                                        >
                                            <Trash2 className="h-4 w-4 text-red-500" />
                                        </button>
                                    ) : null}
                                </li>
                            ))}
                        </ul>
                    </Card>
                ) : null}

                {tab === 'playground' ? (
                    <ModelFabricSafePlayground
                        canManage={canManage}
                        routeReady={generalReady}
                        hasActiveToken={activeTokens > 0}
                    />
                ) : null}

                {tab === 'activity' ? (
                    <Card
                        title="Routing activity (last 24 hours)"
                        label="Routing activity"
                        help="Metadata only: no prompt or response is stored. Failover tries at most 3 approved routes, then cools a rate-limited or failing provider down. Easy work goes to lighter models, hard coding to stronger ones, and a provider near its reported limit is deprioritised before it runs out. Discovery refreshes automatically every 6 hours."
                    >
                        <ul
                            className="divide-y text-sm"
                            data-testid="modelfabric-analytics"
                        >
                            {analytics.length === 0 ? (
                                <li className="py-2">
                                    No provider connected yet.
                                </li>
                            ) : null}
                            {analytics.map((row) => (
                                <li key={row.provider} className="py-2">
                                    <strong>{row.provider}</strong> ·{' '}
                                    {row.requests} request(s), {row.ok} ok
                                    {row.p50_ms !== null
                                        ? ` · p50 ${row.p50_ms} ms, p95 ${row.p95_ms} ms`
                                        : ''}
                                    {row.last_error
                                        ? ` · last error ${row.last_error}`
                                        : ''}
                                    {row.cooling_until
                                        ? ` · cooling down until ${formatIstClock(row.cooling_until)} IST`
                                        : ''}
                                </li>
                            ))}
                        </ul>
                    </Card>
                ) : null}

                {generalReady ? null : (
                    <p className="text-muted-foreground flex items-center gap-2 text-xs">
                        <Circle className="h-3 w-3" /> Until a model is approved
                        the API answers NO_FREE_ROUTE_AVAILABLE and sends
                        nothing to any provider.
                    </p>
                )}
            </div>
        </>
    );
}
