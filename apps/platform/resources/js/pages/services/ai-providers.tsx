import { Head, Link, router, usePage } from '@inertiajs/react';
import { ArrowLeft, KeyRound, Plug, RefreshCw, Trash2 } from 'lucide-react';
import { useState } from 'react';

type Preset = {
    key: string;
    label: string;
    free_tier: 'allowlist' | 'model-suffix' | 'none';
    custom: boolean;
};

type Provider = {
    id: string;
    name: string;
    preset: string;
    host: string;
    key_mask: string;
    enabled: boolean;
    free_only: boolean;
    free_tier: string;
    default_model: string | null;
    fallback_models: string[];
    models: string[];
    health: string;
    health_checked_at: string | null;
    error_code: string | null;
    rate_limit: {
        status?: string;
        requests_remaining?: number | null;
        tokens_remaining?: number | null;
    };
};

type Props = {
    status?: string | null;
    canManage: boolean;
    presets: Preset[];
    providers: Provider[];
};

const BASE = '/services/kmj-codebridge/ai-providers';
const FREE_TIER_TEXT: Record<string, string> = {
    allowlist: 'Only models you list as verified-free are admitted',
    'model-suffix': 'Only ":free" models are free',
    none: 'No free tier: blocked while Free-only is on',
};

function creditText(limit: Provider['rate_limit']): string {
    if (limit?.status !== 'verified') {
        return 'Rate limits: Unknown (not billing credits)';
    }

    return `Rate limit reported by provider: ${limit.requests_remaining ?? '–'} requests, ${limit.tokens_remaining ?? '–'} tokens left (not billing credits)`;
}

function ProviderCard({
    provider,
    canManage,
}: {
    provider: Provider;
    canManage: boolean;
}) {
    const [busy, setBusy] = useState(false);
    const [newKey, setNewKey] = useState('');
    const act = (run: () => void) => {
        setBusy(true);
        run();
    };
    const options = { preserveScroll: true, onFinish: () => setBusy(false) };
    const patch = (data: Record<string, string | boolean | string[] | null>) =>
        act(() => router.patch(`${BASE}/${provider.id}`, data, options));
    const toggleFallback = (model: string) => {
        const next = provider.fallback_models.includes(model)
            ? provider.fallback_models.filter((item) => item !== model)
            : [...provider.fallback_models, model];
        patch({ fallback_models: next });
    };

    return (
        <article className="border-sidebar-border/70 dark:border-sidebar-border flex flex-col gap-4 rounded-2xl border p-5">
            <header className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h2 className="text-base font-black">{provider.name}</h2>
                    <p className="text-muted-foreground text-xs">
                        {provider.host} · key {provider.key_mask}
                    </p>
                </div>
                <div className="flex gap-2 text-xs font-bold">
                    <span className="rounded-full border px-3 py-1">
                        Health: {provider.health}
                    </span>
                    <span className="rounded-full border px-3 py-1">
                        {provider.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                </div>
            </header>

            <p className="text-muted-foreground text-xs">
                {creditText(provider.rate_limit)} ·{' '}
                {FREE_TIER_TEXT[provider.free_tier]}
                {provider.error_code
                    ? ` · last error: ${provider.error_code}`
                    : ''}
            </p>

            {canManage && (
                <div className="flex flex-wrap gap-2">
                    <button
                        type="button"
                        disabled={busy}
                        onClick={() =>
                            act(() =>
                                router.post(
                                    `${BASE}/${provider.id}/test`,
                                    {},
                                    options,
                                ),
                            )
                        }
                        className="inline-flex h-9 items-center gap-2 rounded-xl border px-3 text-xs font-bold"
                    >
                        <RefreshCw className="h-3.5 w-3.5" />
                        Test connection &amp; discover models
                    </button>
                    <button
                        type="button"
                        disabled={busy}
                        onClick={() => patch({ enabled: !provider.enabled })}
                        className="h-9 rounded-xl border px-3 text-xs font-bold"
                    >
                        {provider.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <label className="flex h-9 items-center gap-2 rounded-xl border px-3 text-xs font-bold">
                        <input
                            type="checkbox"
                            checked={provider.free_only}
                            disabled={busy}
                            onChange={(event) =>
                                patch({ free_only: event.target.checked })
                            }
                        />
                        Free-only (zero spend)
                    </label>
                    <button
                        type="button"
                        disabled={busy}
                        onClick={() => {
                            if (
                                window.confirm(
                                    `Delete ${provider.name} and its stored key?`,
                                )
                            ) {
                                act(() =>
                                    router.delete(`${BASE}/${provider.id}`, {
                                        ...options,
                                        data: { confirm: 'DELETE' },
                                    }),
                                );
                            }
                        }}
                        className="inline-flex h-9 items-center gap-2 rounded-xl border px-3 text-xs font-bold text-red-500"
                    >
                        <Trash2 className="h-3.5 w-3.5" />
                        Delete
                    </button>
                </div>
            )}

            {provider.models.length === 0 ? (
                <p className="text-muted-foreground text-xs">
                    No models yet. Run “Test connection” to discover them.
                </p>
            ) : (
                <div className="grid gap-3 md:grid-cols-2">
                    <label className="text-xs font-bold">
                        Default model
                        <select
                            className="bg-background mt-1 block h-9 w-full rounded-xl border px-2"
                            value={provider.default_model ?? ''}
                            disabled={busy || !canManage}
                            onChange={(event) =>
                                patch({
                                    default_model: event.target.value || null,
                                })
                            }
                        >
                            <option value="">None</option>
                            {provider.models.map((model) => (
                                <option key={model} value={model}>
                                    {model}
                                </option>
                            ))}
                        </select>
                    </label>
                    <fieldset className="text-xs font-bold">
                        <legend>Fallback models (max 5)</legend>
                        <div className="mt-1 max-h-32 space-y-1 overflow-y-auto">
                            {provider.models
                                .filter(
                                    (model) => model !== provider.default_model,
                                )
                                .map((model) => (
                                    <label
                                        key={model}
                                        className="flex items-center gap-2 font-normal"
                                    >
                                        <input
                                            type="checkbox"
                                            checked={provider.fallback_models.includes(
                                                model,
                                            )}
                                            disabled={busy || !canManage}
                                            onChange={() =>
                                                toggleFallback(model)
                                            }
                                        />
                                        {model}
                                    </label>
                                ))}
                        </div>
                    </fieldset>
                </div>
            )}

            {canManage && (
                <form
                    className="flex flex-wrap items-end gap-2"
                    onSubmit={(event) => {
                        event.preventDefault();
                        if (newKey.length >= 8) {
                            act(() =>
                                router.patch(
                                    `${BASE}/${provider.id}`,
                                    { api_key: newKey },
                                    {
                                        ...options,
                                        onSuccess: () => setNewKey(''),
                                    },
                                ),
                            );
                        }
                    }}
                >
                    <label className="text-xs font-bold">
                        Replace API key
                        <input
                            type="password"
                            autoComplete="off"
                            value={newKey}
                            onChange={(event) => setNewKey(event.target.value)}
                            className="bg-background mt-1 block h-9 w-64 rounded-xl border px-3 font-normal"
                        />
                    </label>
                    <button
                        type="submit"
                        disabled={busy || newKey.length < 8}
                        className="inline-flex h-9 items-center gap-2 rounded-xl border px-3 text-xs font-bold"
                    >
                        <KeyRound className="h-3.5 w-3.5" />
                        Replace key
                    </button>
                </form>
            )}
        </article>
    );
}

function AddProvider({ presets }: { presets: Preset[] }) {
    const [preset, setPreset] = useState(presets[0]?.key ?? 'groq');
    const [name, setName] = useState('');
    const [apiKey, setApiKey] = useState('');
    const [baseUrl, setBaseUrl] = useState('');
    const [busy, setBusy] = useState(false);
    const errors = usePage().props.errors as Record<string, string>;
    const selected = presets.find((item) => item.key === preset);

    return (
        <form
            className="border-sidebar-border/70 dark:border-sidebar-border grid gap-3 rounded-2xl border p-5 md:grid-cols-2"
            onSubmit={(event) => {
                event.preventDefault();
                setBusy(true);
                router.post(
                    BASE,
                    {
                        preset,
                        name,
                        api_key: apiKey,
                        base_url: selected?.custom ? baseUrl : null,
                        free_only: true,
                    },
                    {
                        preserveScroll: true,
                        onSuccess: () => {
                            setName('');
                            setApiKey('');
                        },
                        onFinish: () => setBusy(false),
                    },
                );
            }}
        >
            <h2 className="flex items-center gap-2 text-base font-black md:col-span-2">
                <Plug className="h-4 w-4" /> Add provider
            </h2>
            <label className="text-xs font-bold">
                Provider
                <select
                    className="bg-background mt-1 block h-9 w-full rounded-xl border px-2"
                    value={preset}
                    onChange={(event) => setPreset(event.target.value)}
                >
                    {presets.map((item) => (
                        <option key={item.key} value={item.key}>
                            {item.label}
                        </option>
                    ))}
                </select>
            </label>
            <label className="text-xs font-bold">
                Name
                <input
                    required
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    className="bg-background mt-1 block h-9 w-full rounded-xl border px-3 font-normal"
                />
                {errors.name && (
                    <span className="text-red-500">{errors.name}</span>
                )}
            </label>
            {selected?.custom && (
                <label className="text-xs font-bold md:col-span-2">
                    HTTPS base URL (host must be owner-approved)
                    <input
                        required
                        value={baseUrl}
                        onChange={(event) => setBaseUrl(event.target.value)}
                        className="bg-background mt-1 block h-9 w-full rounded-xl border px-3 font-normal"
                    />
                    {errors.base_url && (
                        <span className="text-red-500">{errors.base_url}</span>
                    )}
                </label>
            )}
            <label className="text-xs font-bold md:col-span-2">
                API key (stored encrypted on the server; never shown again)
                <input
                    required
                    type="password"
                    autoComplete="off"
                    value={apiKey}
                    onChange={(event) => setApiKey(event.target.value)}
                    className="bg-background mt-1 block h-9 w-full rounded-xl border px-3 font-normal"
                />
                {errors.api_key && (
                    <span className="text-red-500">{errors.api_key}</span>
                )}
            </label>
            <p className="text-muted-foreground text-xs md:col-span-2">
                {selected ? FREE_TIER_TEXT[selected.free_tier] : ''}. New
                providers start in Free-only mode.
            </p>
            <button
                type="submit"
                disabled={busy}
                className="h-10 rounded-xl border border-red-500/40 px-4 text-xs font-bold text-red-500 md:col-span-2"
            >
                Add provider
            </button>
        </form>
    );
}

export default function AiProviders({
    status,
    canManage,
    presets,
    providers,
}: Props) {
    const errors = usePage().props.errors as Record<string, string>;

    return (
        <>
            <Head title="AI Providers" />
            <div className="flex h-full min-w-0 flex-1 flex-col gap-6 p-4 sm:p-6">
                <Link
                    href="/services/kmj-codebridge"
                    className="text-muted-foreground hover:text-foreground inline-flex items-center gap-2 text-xs font-bold"
                >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    Back to CodeBridge
                </Link>
                <div>
                    <h1 className="text-2xl font-black">AI Providers</h1>
                    <p className="text-muted-foreground text-sm">
                        Keys stay on the server, encrypted. Connection tests
                        only list models and never send a prompt. Credit status
                        is shown only when the provider reports it; otherwise it
                        is Unknown.
                    </p>
                </div>
                {status && (
                    <p
                        role="status"
                        className="rounded-xl border border-green-500/30 p-3 text-sm"
                    >
                        {status}
                    </p>
                )}
                {errors.provider && (
                    <p
                        role="alert"
                        className="rounded-xl border border-red-500/40 p-3 text-sm"
                    >
                        {errors.provider}
                    </p>
                )}
                {canManage ? (
                    <AddProvider presets={presets} />
                ) : (
                    <p className="text-muted-foreground text-sm">
                        Only organization owners can change providers.
                    </p>
                )}
                <section
                    className="grid gap-4"
                    aria-label="Configured providers"
                >
                    {providers.length === 0 && (
                        <p className="text-muted-foreground text-sm">
                            No providers yet. Local Ollama on your device stays
                            the primary zero-cost option.
                        </p>
                    )}
                    {providers.map((provider) => (
                        <ProviderCard
                            key={provider.id}
                            provider={provider}
                            canManage={canManage}
                        />
                    ))}
                </section>
            </div>
        </>
    );
}
