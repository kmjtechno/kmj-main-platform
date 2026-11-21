import { Head, Link, router, usePage } from '@inertiajs/react';
import {
    ArrowLeft,
    Check,
    Circle,
    Copy,
    ExternalLink,
    Gauge,
    LockKeyhole,
    Trash2,
} from 'lucide-react';
import { useMemo, useState } from 'react';

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
        'Needs evidence that the provider does not train on your data',
    no_capable_model: 'No evidenced model has the needed capability',
    model_discovery_stale: 'Discovery is stale: run Test connection',
    provider_disabled: 'Provider is disabled',
    auth_failed: 'Provider rejected the key',
};

const reasonText = (reason: string) =>
    REASONS[reason] ?? reason.replaceAll('_', ' ');

const inputClass =
    'mt-1 w-full rounded-md border border-white/15 bg-black/40 p-2.5 text-sm focus:border-red-400 focus:outline-none';
const primaryButton =
    'rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40';

function Badge({
    tone,
    children,
}: {
    tone: 'ok' | 'warn' | 'bad' | 'muted';
    children: React.ReactNode;
}) {
    const tones = {
        ok: 'border-emerald-400/40 bg-emerald-500/10 text-emerald-200',
        warn: 'border-amber-400/40 bg-amber-500/10 text-amber-200',
        bad: 'border-red-400/40 bg-red-500/10 text-red-200',
        muted: 'border-white/15 bg-white/5 text-white/70',
    };

    return (
        <span
            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${tones[tone]}`}
        >
            {children}
        </span>
    );
}

function Step({
    done,
    title,
    detail,
    href,
}: {
    done: boolean;
    title: string;
    detail: string;
    href: string;
}) {
    return (
        <a
            href={href}
            className={`flex items-start gap-3 rounded-lg border p-3 text-sm ${done ? 'border-emerald-400/30 bg-emerald-500/5' : 'border-white/10'}`}
        >
            {done ? (
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
            ) : (
                <Circle className="mt-0.5 h-4 w-4 shrink-0 text-white/40" />
            )}
            <span>
                <strong className="block">{title}</strong>
                <span className="text-muted-foreground text-xs">{detail}</span>
            </span>
        </a>
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
        <div className="kmj-admin-metric p-5" data-testid="modelfabric-plan">
            <p className="text-muted-foreground text-sm">{title}</p>
            <p
                className={`mt-2 text-xl font-bold ${none ? 'text-amber-300' : 'text-emerald-300'}`}
            >
                {none
                    ? 'NO_FREE_ROUTE_AVAILABLE'
                    : `${plan.routes.length} verified-zero route(s)`}
            </p>
            <p className="text-muted-foreground mt-1 text-xs">{note}</p>
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
                        className="text-muted-foreground"
                    >
                        <Badge tone="warn">{reason.provider}</Badge>{' '}
                        {reasonText(reason.reason)}
                    </li>
                ))}
            </ul>
            {grouped.some(([, models]) => models.length > 2) ? (
                <button
                    type="button"
                    className="mt-2 text-xs underline"
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
    const canSave =
        canManage &&
        modelKnown &&
        url.startsWith('https://') &&
        note.trim().length >= 10 &&
        confirmed;

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
        document
            .getElementById('evidence-form')
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    return (
        <>
            <Head title="KMJ TECHNO — ModelFabric & AI" />
            <main className="owner-admin-page kmj-admin-shell flex min-w-0 flex-1 flex-col gap-6 p-4 sm:p-6 lg:p-8">
                <Link
                    href="/operator"
                    className="text-muted-foreground hover:text-foreground inline-flex w-fit items-center gap-2 text-sm"
                >
                    <ArrowLeft className="h-4 w-4" />
                    Back to Super Admin
                </Link>
                <header className="owner-admin-hero kmj-admin-hero rounded-[1.65rem] p-6 sm:p-8">
                    <div className="flex flex-wrap items-center gap-3">
                        <Gauge className="h-8 w-8 text-red-500" />
                        <h1 className="text-2xl font-black tracking-tight sm:text-3xl">
                            ModelFabric &amp; AI
                        </h1>
                    </div>
                    <p className="text-muted-foreground mt-3 max-w-3xl text-sm leading-6">
                        Cloud-only, verified-zero model routing. A model is
                        routable only with current free-tier evidence and a
                        healthy provider. Unknown price is never free. There is
                        no paid fallback and no local LLM.
                    </p>
                    <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-amber-500/25 bg-amber-500/10 px-4 py-2 text-xs font-semibold text-amber-200">
                        <LockKeyhole className="h-4 w-4" />
                        Paid inference cannot be enabled from this page
                    </div>
                </header>

                {status ? (
                    <p
                        role="status"
                        className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm"
                    >
                        {status}
                    </p>
                ) : null}

                <nav
                    aria-label="Setup progress"
                    className="grid gap-3 md:grid-cols-4"
                >
                    <Step
                        done={healthy > 0}
                        title="1. Connect providers"
                        detail={`${healthy} of ${providers.length} healthy`}
                        href="#providers"
                    />
                    <Step
                        done={currentEvidence > 0}
                        title="2. Verify free models"
                        detail={`${currentEvidence} model(s) with current evidence`}
                        href="#evidence-form"
                    />
                    <Step
                        done={plans.chat.status !== 'NO_FREE_ROUTE_AVAILABLE'}
                        title="3. Routes ready"
                        detail={`${plans.chat.routes.length} general, ${plans.privateSource.routes.length} private-source`}
                        href="#routes"
                    />
                    <Step
                        done={activeTokens > 0}
                        title="4. Create API token"
                        detail={`${activeTokens} active token(s)`}
                        href="#tokens"
                    />
                </nav>

                <section
                    id="routes"
                    className="grid gap-4 md:grid-cols-2"
                    aria-label="Route plan"
                >
                    <PlanCard
                        title="General chat routes"
                        note="Used by CodeBridge chat and Kristi guided features."
                        plan={plans.chat}
                    />
                    <PlanCard
                        title="Private source code routes"
                        note="Needs current evidence that the provider documents no training on submitted data. Owner consent for source transfer is still separate."
                        plan={plans.privateSource}
                    />
                </section>

                <section
                    id="providers"
                    aria-label="Providers"
                    className="kmj-admin-metric p-5"
                >
                    <h2 className="text-lg font-bold">Providers</h2>
                    <p className="text-muted-foreground mt-1 text-xs">
                        Add keys or connect OpenRouter on the{' '}
                        <Link
                            className="underline"
                            href="/services/kmj-codebridge/ai-providers"
                        >
                            provider connect page
                        </Link>
                        . Allowlist providers need price evidence per model;
                        OpenRouter admits only models ending in :free.
                    </p>
                    <div className="mt-4 grid gap-3 md:grid-cols-3">
                        {providers.length === 0 ? (
                            <p className="text-sm">
                                No provider connected yet.
                            </p>
                        ) : null}
                        {providers.map((provider) => (
                            <div
                                key={provider.id}
                                className="rounded-lg border border-white/10 p-4 text-sm"
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <strong>{provider.name}</strong>
                                    <Badge
                                        tone={
                                            provider.health === 'ok'
                                                ? 'ok'
                                                : 'bad'
                                        }
                                    >
                                        {provider.health}
                                    </Badge>
                                </div>
                                <p className="text-muted-foreground mt-1 text-xs">
                                    {provider.host} · tier {provider.free_tier}
                                </p>
                                <p className="mt-3 text-2xl font-bold">
                                    {provider.models.length}
                                    <span className="text-muted-foreground text-xs font-normal">
                                        {' '}
                                        usable of{' '}
                                        {provider.discovered_model_count}{' '}
                                        discovered
                                    </span>
                                </p>
                                {provider.error_code ? (
                                    <p className="mt-1 text-xs text-red-300">
                                        Last error: {provider.error_code}
                                    </p>
                                ) : null}
                                {canManage &&
                                provider.free_tier === 'allowlist' ? (
                                    <button
                                        type="button"
                                        className="mt-3 rounded-md border border-white/20 px-3 py-1.5 text-xs font-semibold"
                                        onClick={() =>
                                            startEvidence(provider.id)
                                        }
                                    >
                                        Add price evidence
                                    </button>
                                ) : null}
                            </div>
                        ))}
                    </div>
                </section>

                <section
                    id="evidence-form"
                    aria-label="Price evidence"
                    className="kmj-admin-metric p-5"
                >
                    <h2 className="text-lg font-bold">
                        Verify a free model (price evidence)
                    </h2>
                    <p className="text-muted-foreground mt-1 text-xs">
                        Open the provider&apos;s own page, confirm this exact
                        model is free, then record it. Evidence expires after at
                        most {maxEvidenceDays} days and can be revoked at any
                        time. A free account does not make every model free.
                    </p>

                    {canManage && allowlistProviders.length > 0 ? (
                        <form
                            className="mt-4 grid gap-4 md:grid-cols-2"
                            onSubmit={(event) => {
                                event.preventDefault();
                                if (canSave) {
                                    save();
                                }
                            }}
                        >
                            <label className="text-sm">
                                Provider
                                <select
                                    className={inputClass}
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
                            <label className="text-sm">
                                Model{' '}
                                <span className="text-muted-foreground text-xs">
                                    (pick from{' '}
                                    {selected?.discovered_model_count ?? 0}{' '}
                                    discovered)
                                </span>
                                <input
                                    className={inputClass}
                                    list="modelfabric-models"
                                    value={model}
                                    onChange={(e) => setModel(e.target.value)}
                                    placeholder="Start typing a model name"
                                    autoComplete="off"
                                />
                                <datalist id="modelfabric-models">
                                    {(selected?.discovered_models ?? []).map(
                                        (name) => (
                                            <option key={name} value={name} />
                                        ),
                                    )}
                                </datalist>
                                {model !== '' && !modelKnown ? (
                                    <span className="text-xs text-amber-300">
                                        Not in the last discovery: choose a
                                        listed model or run Test connection.
                                    </span>
                                ) : null}
                            </label>
                            <label className="text-sm md:col-span-2">
                                Provider page that shows this model is free
                                (https)
                                <input
                                    className={inputClass}
                                    type="url"
                                    value={url}
                                    onChange={(e) => setUrl(e.target.value)}
                                    placeholder="https://provider.example/pricing"
                                />
                                {hint ? (
                                    <span className="mt-1 flex flex-wrap items-center gap-3 text-xs">
                                        <button
                                            type="button"
                                            className="underline"
                                            onClick={() => setUrl(hint)}
                                        >
                                            Use suggested page
                                        </button>
                                        <a
                                            className="inline-flex items-center gap-1 underline"
                                            href={hint}
                                            target="_blank"
                                            rel="noreferrer noopener"
                                        >
                                            Open it{' '}
                                            <ExternalLink className="h-3 w-3" />
                                        </a>
                                        <span className="text-muted-foreground">
                                            Suggestion only: you must verify it.
                                        </span>
                                    </span>
                                ) : null}
                            </label>
                            <label className="text-sm md:col-span-2">
                                What the page says (10–280 characters)
                                <input
                                    className={inputClass}
                                    value={note}
                                    maxLength={280}
                                    onChange={(e) => setNote(e.target.value)}
                                    placeholder="e.g. Free tier lists this model with 0 cost and N requests per minute"
                                />
                            </label>
                            <label className="text-sm">
                                Valid for (days, max {maxEvidenceDays})
                                <input
                                    className={inputClass}
                                    type="number"
                                    min={1}
                                    max={maxEvidenceDays}
                                    value={days}
                                    onChange={(e) =>
                                        setDays(Number(e.target.value))
                                    }
                                />
                            </label>
                            <label className="text-sm">
                                Data handling
                                <select
                                    className={inputClass}
                                    value={handling}
                                    onChange={(e) =>
                                        setHandling(e.target.value)
                                    }
                                >
                                    <option value="unknown">
                                        Unknown (never used for private source)
                                    </option>
                                    <option value="no-training-documented">
                                        Provider documents no training on my
                                        data
                                    </option>
                                </select>
                            </label>
                            <fieldset className="text-sm md:col-span-2">
                                <legend>Capabilities</legend>
                                <div className="mt-1 flex flex-wrap gap-4">
                                    {['chat', 'tools', 'code', 'vision'].map(
                                        (cap) => (
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
                                        ),
                                    )}
                                </div>
                                <p className="text-muted-foreground mt-1 text-xs">
                                    Tick <strong>code</strong> to let this model
                                    serve the coding worker.
                                </p>
                            </fieldset>
                            <label className="flex items-start gap-2 text-sm md:col-span-2">
                                <input
                                    type="checkbox"
                                    className="mt-1"
                                    checked={confirmed}
                                    onChange={(e) =>
                                        setConfirmed(e.target.checked)
                                    }
                                />
                                I opened this page myself and it shows this
                                exact model is free today.
                            </label>
                            <div className="md:col-span-2">
                                <button
                                    type="submit"
                                    className={primaryButton}
                                    disabled={!canSave}
                                >
                                    Save evidence
                                </button>
                                {!canSave ? (
                                    <span className="text-muted-foreground ml-3 text-xs">
                                        Pick a listed model, add an https page,
                                        a short note and tick the confirmation.
                                    </span>
                                ) : null}
                            </div>
                            {errors
                                ? Object.values(errors).map((message) => (
                                      <p
                                          key={message}
                                          role="alert"
                                          className="text-sm text-red-300 md:col-span-2"
                                      >
                                          {message}
                                      </p>
                                  ))
                                : null}
                        </form>
                    ) : (
                        <p className="mt-3 text-sm">
                            {canManage
                                ? 'Connect a provider with an allowlist tier (Groq, Gemini, Cerebras, Mistral, SambaNova, Hugging Face, NVIDIA) and run Test connection first.'
                                : 'You can view evidence; managing it needs organization manager rights.'}
                        </p>
                    )}

                    <ul className="mt-5 space-y-2 text-sm">
                        {evidence.length === 0 ? (
                            <li className="text-muted-foreground">
                                No evidence saved yet.
                            </li>
                        ) : null}
                        {evidence.map((row) => (
                            <li
                                key={row.id}
                                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 p-3"
                            >
                                <span>
                                    <strong>{row.model_id}</strong>{' '}
                                    <Badge
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
                                    </Badge>{' '}
                                    <span className="text-muted-foreground text-xs">
                                        until{' '}
                                        {new Date(
                                            row.expires_at,
                                        ).toLocaleDateString()}{' '}
                                        · {row.data_handling} ·{' '}
                                        {row.capabilities.join(', ')} ·{' '}
                                    </span>
                                    <a
                                        className="text-xs underline"
                                        href={row.price_evidence_url}
                                        rel="noreferrer noopener"
                                        target="_blank"
                                    >
                                        evidence
                                    </a>
                                </span>
                                {canManage && row.current ? (
                                    <button
                                        type="button"
                                        className="inline-flex items-center gap-1 text-xs text-red-300"
                                        onClick={() =>
                                            router.delete(
                                                `${BASE}/evidence/${row.id}`,
                                                { preserveScroll: true },
                                            )
                                        }
                                    >
                                        <Trash2 className="h-3 w-3" /> Revoke
                                    </button>
                                ) : null}
                            </li>
                        ))}
                    </ul>
                </section>

                <section
                    id="tokens"
                    aria-label="API tokens"
                    className="kmj-admin-metric p-5"
                >
                    <h2 className="text-lg font-bold">
                        ModelFabric API tokens (OpenAI-compatible)
                    </h2>
                    <p className="text-muted-foreground mt-1 text-xs">
                        The caller never chooses a provider or model:
                        ModelFabric routes only through verified-zero evidence
                        and answers NO_FREE_ROUTE_AVAILABLE otherwise.
                        Private-source tokens only reach models whose
                        no-training handling is documented. Tokens are stored as
                        a hash and shown once.
                    </p>
                    {newToken ? (
                        <div
                            className="mt-3 rounded-lg border border-emerald-400/40 p-3"
                            data-testid="modelfabric-new-token"
                        >
                            <p className="text-xs font-semibold text-emerald-200">
                                Copy this token now. It will not be shown again.
                            </p>
                            <p className="mt-2 font-mono text-xs break-all">
                                {newToken}
                            </p>
                            <button
                                type="button"
                                className="mt-2 inline-flex items-center gap-1 rounded-md border border-white/20 px-3 py-1.5 text-xs font-semibold"
                                onClick={copyToken}
                            >
                                <Copy className="h-3 w-3" />{' '}
                                {copied ? 'Copied' : 'Copy token'}
                            </button>
                        </div>
                    ) : null}
                    {canManage ? (
                        <form
                            className="mt-4 grid gap-3 md:grid-cols-4"
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
                            <label className="text-sm">
                                Name
                                <input
                                    className={inputClass}
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
                            <label className="text-sm">
                                Valid days (1-90)
                                <input
                                    className={inputClass}
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
                                <button type="submit" className={primaryButton}>
                                    Create token
                                </button>
                            </div>
                        </form>
                    ) : null}
                    <pre className="mt-4 overflow-x-auto rounded-lg bg-black/50 p-3 text-xs">
                        {`curl ${origin}/api/modelfabric/v1/chat/completions \\
  -H "Authorization: Bearer <your token>" \\
  -H "Content-Type: application/json" \\
  -d '{"messages":[{"role":"user","content":"ping"}]}'`}
                    </pre>
                    <ul className="mt-3 divide-y divide-white/10 text-sm">
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
                                    <Badge tone={token.active ? 'ok' : 'muted'}>
                                        {token.active ? 'active' : 'inactive'}
                                    </Badge>{' '}
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
                                        <Trash2 className="h-4 w-4" />
                                    </button>
                                ) : null}
                            </li>
                        ))}
                    </ul>
                </section>

                <section
                    aria-label="Routing activity"
                    className="kmj-admin-metric p-5"
                >
                    <h2 className="text-lg font-bold">
                        Routing activity (last 24 hours)
                    </h2>
                    <p className="text-muted-foreground mt-1 text-xs">
                        Metadata only: no prompt or response is stored. Failover
                        tries at most 3 verified-zero routes, then cools a
                        rate-limited or failing provider down. Easy work goes to
                        lighter models, hard coding to stronger ones, and a
                        provider near its reported limit is deprioritised before
                        it runs out. Discovery refreshes automatically every 6
                        hours.
                    </p>
                    <ul
                        className="mt-3 divide-y divide-white/10 text-sm"
                        data-testid="modelfabric-analytics"
                    >
                        {analytics.length === 0 ? (
                            <li className="py-2">No provider connected yet.</li>
                        ) : null}
                        {analytics.map((row) => (
                            <li key={row.provider} className="py-2">
                                <strong>{row.provider}</strong> · {row.requests}{' '}
                                request(s), {row.ok} ok
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
                </section>
            </main>
        </>
    );
}
