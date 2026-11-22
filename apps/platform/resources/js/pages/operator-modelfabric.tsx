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

type Provider = {
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
    providers: Provider[];
    evidence: Evidence[];
    analytics: Analytics[];
    plans: { chat: Plan; privateSource: Plan };
};

const BASE = '/operator/modelfabric';

type Tab = 'start' | 'models' | 'tokens' | 'activity';

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

export default function OperatorModelFabric({
    newToken,
    tokens,
    status,
    canManage,
    maxEvidenceDays,
    providers,
    evidence,
    analytics,
    plans,
}: Props) {
    const { errors } = usePage().props as { errors?: Record<string, string> };
    const allowlistProviders = providers.filter(
        (provider) => provider.free_tier === 'allowlist',
    );
    const [tab, setTab] = useState<Tab>(newToken ? 'tokens' : 'start');
    const [tokenName, setTokenName] = useState('');
    const [tokenDays, setTokenDays] = useState('30');
    const [tokenPrivate, setTokenPrivate] = useState(true);
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
    const [picked, setPicked] = useState<string[]>([]);
    const [hfFree, setHfFree] = useState(false);
    const selected = providers.find((provider) => provider.id === providerId);
    const hint = selected ? PRICING_HINTS[selected.preset] : undefined;
    const modelKnown = !!selected?.discovered_models.includes(model);
    const origin =
        typeof window === 'undefined'
            ? 'https://kmjtechno.com'
            : window.location.origin;

    const healthy = providers.filter((p) => p.health === 'ok').length;
    const currentEvidence = evidence.filter((row) => row.current).length;
    const activeTokens = tokens.filter((token) => token.active).length;
    const requests24h = analytics.reduce((sum, row) => sum + row.requests, 0);
    const okRequests24h = analytics.reduce((sum, row) => sum + row.ok, 0);
    const generalReady = plans.chat.status !== 'NO_FREE_ROUTE_AVAILABLE';
    const canSave =
        canManage &&
        modelKnown &&
        url.startsWith('https://') &&
        note.trim().length >= 10 &&
        confirmed;

    const listedModels = (selected?.discovered_models ?? []).slice(0, 200);
    const bulkModels = picked
        .filter((id) => listedModels.includes(id))
        .slice(0, 50);
    const canBulk =
        canManage &&
        bulkModels.length > 0 &&
        url.startsWith('https://') &&
        note.trim().length >= 10 &&
        confirmed;

    const next = (() => {
        if (providers.length === 0) {
            return {
                text: 'Connect your first AI provider (Gemini, Groq or OpenRouter).',
                action: 'Open provider connect page',
                href: '/services/kmj-codebridge/ai-providers',
            };
        }
        if (healthy === 0) {
            return {
                text: 'No provider is healthy. Run Test connection on the provider page.',
                action: 'Open provider connect page',
                href: '/services/kmj-codebridge/ai-providers',
            };
        }
        if (currentEvidence === 0 && allowlistProviders.length > 0) {
            return {
                text: 'Approve at least one free model: open its provider page, confirm it is free, then save the evidence.',
                action: 'Verify a free model',
                tab: 'models' as Tab,
            };
        }
        if (activeTokens === 0) {
            return {
                text: 'Create an API token so the coding worker can use these routes.',
                action: 'Create API token',
                tab: 'tokens' as Tab,
            };
        }

        return {
            text: 'Everything needed is set up. Watch usage in the Activity tab.',
            action: 'Open Activity',
            tab: 'activity' as Tab,
        };
    })();

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
            },
            {
                preserveScroll: true,
                onSuccess: () => {
                    setNote('');
                    setModel('');
                    setConfirmed(false);
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

    const connectOAuth = (kind: 'openrouter' | 'huggingface') => {
        router.post(
            `/services/kmj-codebridge/ai-providers/connect/${kind}`,
            kind === 'huggingface'
                ? { free_account_confirmed: true, return_to: 'modelfabric' }
                : { return_to: 'modelfabric' },
            { preserveScroll: true },
        );
    };

    const renew = (id: string) => {
        if (
            !window.confirm(
                'Re-check the evidence page first. Renew for 30 days?',
            )
        ) {
            return;
        }
        router.post(
            `${BASE}/evidence/${id}/renew`,
            { attest_pricing: true },
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
        setUrl(
            PRICING_HINTS[providers.find((p) => p.id === id)?.preset ?? ''] ??
                '',
        );
        setTab('models');
    };

    const tabs: { key: Tab; label: string }[] = [
        { key: 'start', label: 'Overview' },
        { key: 'models', label: 'Free models' },
        { key: 'tokens', label: 'API tokens' },
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
                            today and its provider is healthy. No paid fallback,
                            no local LLM.
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
                                    onClick={() => setTab(next.tab as Tab)}
                                >
                                    <Zap size={16} />
                                    {next.action}
                                    <ChevronRight size={16} />
                                </button>
                            )}
                            <a href="/services/kmj-codebridge/ai-providers">
                                <Boxes size={16} />
                                Connect providers
                            </a>
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
                        detail="Active for the coding worker"
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
                                    Next step
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
                                    onClick={() => setTab(item.key)}
                                >
                                    {item.label}
                                </button>
                            ))}
                        </nav>
                    </div>
                </section>

                {tab === 'start' ? (
                    <>
                        <section
                            id="routes"
                            className="grid gap-4 md:grid-cols-2"
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
                        <Card
                            id="providers"
                            title="Providers"
                            label="Providers"
                            help="Add keys or connect OpenRouter on the provider connect page. Gemini and Groq need your price evidence per model; OpenRouter admits only models ending in :free."
                        >
                            <div className="grid gap-3 md:grid-cols-3">
                                {providers.length === 0 ? (
                                    <p className="text-sm">
                                        No provider connected yet.
                                    </p>
                                ) : null}
                                {providers.map((provider) => (
                                    <div
                                        key={provider.id}
                                        className="rounded-xl border p-4 text-sm"
                                    >
                                        <div className="flex items-center justify-between gap-2">
                                            <strong>{provider.name}</strong>
                                            <StatusPill
                                                tone={
                                                    provider.health === 'ok'
                                                        ? 'ok'
                                                        : 'bad'
                                                }
                                            >
                                                {provider.health}
                                            </StatusPill>
                                        </div>
                                        <p className="text-muted-foreground mt-1 text-xs">
                                            {provider.host} · tier{' '}
                                            {provider.free_tier}
                                        </p>
                                        <p className="mt-3 text-2xl font-black">
                                            {provider.models.length}
                                            <span className="text-muted-foreground text-xs font-normal">
                                                {' '}
                                                usable of{' '}
                                                {
                                                    provider.discovered_model_count
                                                }{' '}
                                                found
                                            </span>
                                        </p>
                                        {provider.error_code ? (
                                            <p className="mt-1 text-xs text-red-500">
                                                Last error:{' '}
                                                {provider.error_code}
                                            </p>
                                        ) : null}
                                        <ProviderLimits
                                            provider={provider}
                                            canManage={canManage}
                                        />
                                        {canManage &&
                                        provider.free_tier === 'allowlist' ? (
                                            <button
                                                type="button"
                                                className={`${ghostButton} mt-3`}
                                                onClick={() =>
                                                    startEvidence(provider.id)
                                                }
                                            >
                                                Approve a free model
                                            </button>
                                        ) : null}
                                    </div>
                                ))}
                            </div>
                            {canManage ? (
                                <div className="mt-4 rounded-xl border p-4 text-sm">
                                    <h3 className="font-black">
                                        Connect a provider with one click
                                    </h3>
                                    <p className="text-muted-foreground mt-1 text-xs">
                                        You come back to this page afterwards.
                                        Connecting never approves a model: each
                                        model still needs your price evidence.
                                    </p>
                                    <div className="mt-3 flex flex-wrap items-start gap-4">
                                        <button
                                            type="button"
                                            className={primaryButton}
                                            onClick={() =>
                                                connectOAuth('openrouter')
                                            }
                                        >
                                            Connect OpenRouter
                                        </button>
                                        <div className="max-w-md">
                                            <label className="flex items-start gap-2 text-xs">
                                                <input
                                                    type="checkbox"
                                                    className="mt-0.5"
                                                    checked={hfFree}
                                                    onChange={(e) =>
                                                        setHfFree(
                                                            e.target.checked,
                                                        )
                                                    }
                                                />
                                                My Hugging Face account is a
                                                Free account with no payment
                                                method.
                                            </label>
                                            <button
                                                type="button"
                                                className={`${primaryButton} mt-2`}
                                                disabled={!hfFree}
                                                onClick={() =>
                                                    connectOAuth('huggingface')
                                                }
                                            >
                                                Connect Hugging Face
                                            </button>
                                        </div>
                                    </div>
                                    {errors?.provider ? (
                                        <p
                                            role="alert"
                                            className="mt-3 text-xs text-red-500"
                                        >
                                            {errors.provider}
                                        </p>
                                    ) : null}
                                </div>
                            ) : null}
                            <a
                                className="mt-4 inline-block text-xs font-bold underline"
                                href="/services/kmj-codebridge/ai-providers"
                            >
                                Add a provider with an API key (Gemini, Groq,
                                Mistral…)
                            </a>
                        </Card>
                    </>
                ) : null}

                {tab === 'models' ? (
                    <Card
                        id="evidence-form"
                        title="Approve a free model"
                        label="Price evidence"
                        help={`Open the provider's own page, confirm this exact model is free, then record it. Approval expires after at most ${maxEvidenceDays} days and can be revoked at any time. A free account does not make every model free.`}
                    >
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
                                        onChange={(e) =>
                                            setModel(e.target.value)
                                        }
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
                                    ? 'Connect a provider with an allowlist tier (Groq, Gemini, Cerebras, Mistral, SambaNova, Hugging Face, NVIDIA) and run Test connection first.'
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
                                            {new Date(
                                                row.expires_at,
                                            ).toLocaleDateString()}{' '}
                                            · {row.data_handling} ·{' '}
                                            {row.capabilities.join(', ')} ·{' '}
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
                                            onClick={() => renew(row.id)}
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

                {tab === 'tokens' ? (
                    <Card
                        id="tokens"
                        title="ModelFabric API tokens (OpenAI-compatible)"
                        label="API tokens"
                        help="The caller never chooses a provider or model: ModelFabric picks only from your approved free models and says NO_FREE_ROUTE_AVAILABLE when none qualifies. Private-source tokens reach only models with documented no-training handling. Tokens are stored as a hash and shown once."
                    >
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
                                    Private source (stricter)
                                </label>
                                <div className="flex items-end">
                                    <button
                                        type="submit"
                                        className={primaryButton}
                                    >
                                        Create token
                                    </button>
                                </div>
                            </form>
                        ) : null}
                        <pre className="bg-muted mt-4 overflow-x-auto rounded-xl p-3 text-xs">
                            {`curl ${origin}/api/modelfabric/v1/chat/completions \\
  -H "Authorization: Bearer <your token>" \\
  -H "Content-Type: application/json" \\
  -d '{"messages":[{"role":"user","content":"ping"}]}'`}
                        </pre>
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
                                            {new Date(
                                                token.expires_at,
                                            ).toLocaleDateString()}
                                            {token.last_used_at
                                                ? ` · last used ${new Date(token.last_used_at).toLocaleString()}`
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
                                        ? ` · cooling down until ${new Date(row.cooling_until).toLocaleTimeString()}`
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
