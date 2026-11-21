import { Head, Link, router, usePage } from '@inertiajs/react';
import {
    ArrowLeft,
    Gauge,
    LockKeyhole,
    ShieldCheck,
    Trash2,
} from 'lucide-react';
import { useState } from 'react';

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
            <ul className="mt-3 space-y-1 text-xs">
                {plan.routes.map((route) => (
                    <li key={`${route.provider}-${route.model}`}>
                        {route.provider} / {route.model} — {route.source}
                        {route.evidence_expires_at
                            ? `, evidence until ${new Date(route.evidence_expires_at).toLocaleDateString()}`
                            : ''}
                    </li>
                ))}
                {plan.reasons.map((reason) => (
                    <li
                        key={`${reason.provider}-${reason.reason}`}
                        className="text-muted-foreground"
                    >
                        {reason.provider}: {reason.reason}
                    </li>
                ))}
            </ul>
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
    const [providerId, setProviderId] = useState(
        allowlistProviders[0]?.id ?? '',
    );
    const [model, setModel] = useState('');
    const [url, setUrl] = useState('');
    const [note, setNote] = useState('');
    const [days, setDays] = useState(14);
    const [handling, setHandling] = useState('unknown');
    const [caps, setCaps] = useState<string[]>(['chat']);
    const selected = providers.find((provider) => provider.id === providerId);

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
            { preserveScroll: true, onSuccess: () => setNote('') },
        );
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

                <section
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
                        .
                    </p>
                    <ul className="mt-3 divide-y divide-white/10 text-sm">
                        {providers.length === 0 ? (
                            <li className="py-2">No provider connected yet.</li>
                        ) : null}
                        {providers.map((provider) => (
                            <li key={provider.id} className="py-2">
                                <strong>{provider.name}</strong> ·{' '}
                                {provider.host} · tier: {provider.free_tier} ·
                                health: {provider.health} ·{' '}
                                {provider.models.length} admitted of{' '}
                                {provider.discovered_model_count} discovered
                                {provider.error_code
                                    ? ` · last error ${provider.error_code}`
                                    : ''}
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

                <section
                    aria-label="API tokens"
                    className="kmj-admin-metric p-5"
                >
                    <h2 className="text-lg font-bold">
                        ModelFabric API tokens (OpenAI-compatible)
                    </h2>
                    <p className="text-muted-foreground mt-1 text-xs">
                        Base URL <code>/api/modelfabric/v1</code>, endpoints{' '}
                        <code>/chat/completions</code> (no streaming yet) and{' '}
                        <code>/models</code>. The caller never chooses a
                        provider or model: ModelFabric routes only through
                        verified-zero evidence and answers
                        NO_FREE_ROUTE_AVAILABLE otherwise. Private-source tokens
                        only reach models whose no-training handling is
                        documented. Tokens are stored as a hash and shown once.
                    </p>
                    {newToken ? (
                        <p
                            className="mt-3 rounded border border-emerald-400/40 p-3 font-mono text-xs break-all"
                            data-testid="modelfabric-new-token"
                        >
                            {newToken}
                        </p>
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
                                    className="mt-1 w-full rounded border border-white/15 bg-black/40 p-2"
                                    value={tokenName}
                                    onChange={(e) =>
                                        setTokenName(e.target.value)
                                    }
                                    minLength={3}
                                    maxLength={80}
                                    required
                                />
                            </label>
                            <label className="text-sm">
                                Valid days (1-90)
                                <input
                                    className="mt-1 w-full rounded border border-white/15 bg-black/40 p-2"
                                    type="number"
                                    min={1}
                                    max={90}
                                    value={tokenDays}
                                    onChange={(e) =>
                                        setTokenDays(e.target.value)
                                    }
                                />
                            </label>
                            <label className="flex items-end gap-2 text-sm">
                                <input
                                    type="checkbox"
                                    checked={tokenPrivate}
                                    onChange={(e) =>
                                        setTokenPrivate(e.target.checked)
                                    }
                                />
                                Private source (stricter routing)
                            </label>
                            <button
                                type="submit"
                                className="rounded bg-red-600 px-3 py-2 text-sm font-semibold"
                            >
                                Create token
                            </button>
                        </form>
                    ) : null}
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
                                    <strong>{token.name}</strong> ·{' '}
                                    {token.prefix}… ·{' '}
                                    {token.private_source
                                        ? 'private source'
                                        : 'general'}{' '}
                                    · {token.active ? 'active' : 'inactive'} ·
                                    expires{' '}
                                    {new Date(
                                        token.expires_at,
                                    ).toLocaleDateString()}
                                    {token.last_used_at
                                        ? ` · last used ${new Date(token.last_used_at).toLocaleString()}`
                                        : ''}
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
                    aria-label="Price evidence"
                    className="kmj-admin-metric p-5"
                >
                    <h2 className="flex items-center gap-2 text-lg font-bold">
                        <ShieldCheck className="h-5 w-5 text-emerald-400" />{' '}
                        Verified-zero price evidence
                    </h2>
                    <p className="text-muted-foreground mt-1 text-xs">
                        Record the provider&apos;s own pricing or rate-limit
                        page showing this exact model is free. Evidence expires
                        after at most {maxEvidenceDays} days and can be revoked
                        at any time. Only providers with an owner allowlist tier
                        qualify.
                    </p>

                    {canManage && allowlistProviders.length > 0 ? (
                        <form
                            className="mt-4 grid gap-3 md:grid-cols-2"
                            onSubmit={(event) => {
                                event.preventDefault();
                                save();
                            }}
                        >
                            <label className="text-sm">
                                Provider
                                <select
                                    className="mt-1 w-full rounded border border-white/15 bg-black/40 p-2"
                                    value={providerId}
                                    onChange={(e) =>
                                        setProviderId(e.target.value)
                                    }
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
                                Model (from last discovery)
                                <input
                                    list="modelfabric-models"
                                    className="mt-1 w-full rounded border border-white/15 bg-black/40 p-2"
                                    value={model}
                                    onChange={(e) => setModel(e.target.value)}
                                    required
                                />
                                <datalist id="modelfabric-models">
                                    {(selected?.discovered_models ?? []).map(
                                        (id) => (
                                            <option key={id} value={id} />
                                        ),
                                    )}
                                </datalist>
                            </label>
                            <label className="text-sm md:col-span-2">
                                Evidence page (https)
                                <input
                                    type="url"
                                    className="mt-1 w-full rounded border border-white/15 bg-black/40 p-2"
                                    value={url}
                                    onChange={(e) => setUrl(e.target.value)}
                                    placeholder="https://provider.example/pricing"
                                    required
                                />
                            </label>
                            <label className="text-sm md:col-span-2">
                                What the page says (10–280 chars)
                                <input
                                    className="mt-1 w-full rounded border border-white/15 bg-black/40 p-2"
                                    value={note}
                                    onChange={(e) => setNote(e.target.value)}
                                    minLength={10}
                                    maxLength={280}
                                    required
                                />
                            </label>
                            <label className="text-sm">
                                Valid for (days, max {maxEvidenceDays})
                                <input
                                    type="number"
                                    min={1}
                                    max={maxEvidenceDays}
                                    className="mt-1 w-full rounded border border-white/15 bg-black/40 p-2"
                                    value={days}
                                    onChange={(e) =>
                                        setDays(Number(e.target.value))
                                    }
                                />
                            </label>
                            <label className="text-sm">
                                Data handling
                                <select
                                    className="mt-1 w-full rounded border border-white/15 bg-black/40 p-2"
                                    value={handling}
                                    onChange={(e) =>
                                        setHandling(e.target.value)
                                    }
                                >
                                    <option value="unknown">
                                        Unknown (never used for private source)
                                    </option>
                                    <option value="no-training-documented">
                                        Provider documents no training on
                                        submitted data
                                    </option>
                                </select>
                            </label>
                            <fieldset className="text-sm md:col-span-2">
                                <legend>Capabilities</legend>
                                {['chat', 'tools', 'code', 'vision'].map(
                                    (cap) => (
                                        <label
                                            key={cap}
                                            className="mr-4 inline-flex items-center gap-1"
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
                            </fieldset>
                            <div className="md:col-span-2">
                                <button
                                    type="submit"
                                    className="rounded bg-red-600 px-4 py-2 text-sm font-semibold text-white"
                                >
                                    Save evidence
                                </button>
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
                                ? 'Connect a provider with an allowlist tier (Groq, Gemini, Cerebras, Mistral, SambaNova, Hugging Face) and run Test connection first.'
                                : 'You can view evidence; managing it needs organization manager rights.'}
                        </p>
                    )}

                    <ul className="mt-5 space-y-2 text-sm">
                        {evidence.map((row) => (
                            <li
                                key={row.id}
                                className="flex flex-wrap items-center justify-between gap-2 rounded border border-white/10 p-3"
                            >
                                <span>
                                    <strong>{row.model_id}</strong> —{' '}
                                    {row.current
                                        ? 'current'
                                        : row.revoked
                                          ? 'revoked'
                                          : 'expired'}{' '}
                                    until{' '}
                                    {new Date(
                                        row.expires_at,
                                    ).toLocaleDateString()}{' '}
                                    · {row.data_handling} ·{' '}
                                    <a
                                        className="underline"
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
            </main>
        </>
    );
}
