import { Head, Link, router, usePage } from '@inertiajs/react';
import { ArrowLeft, KeyRound, Plug, RefreshCw, Trash2 } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import AiProviderConnectHub from '@/components/ai-provider-connect-hub';
import '../../../css/ai-provider-connect.css';

export type Preset = {
    key: string;
    label: string;
    free_tier: 'allowlist' | 'model-suffix' | 'none';
    custom: boolean;
};

export type Provider = {
    id: string;
    name: string;
    preset: string;
    host: string;
    key_mask: string;
    enabled: boolean;
    free_tier: string;
    default_model: string | null;
    fallback_models: string[];
    models: string[];
    discovered_model_count: number;
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
    embedded?: boolean;
    renderRoutingControls?: (id: string) => ReactNode;
    status?: string | null;
    canManage: boolean;
    presets: Preset[];
    providers: Provider[];
};

const BASE = '/services/kmj-codebridge/ai-providers';
const FREE_TIER_TEXT: Record<string, string> = {
    allowlist: 'Only models you list as verified-free are admitted',
    'model-suffix': 'Only ":free" models are free',
    none: 'No free tier: inference is blocked',
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
    routingControls,
    compact = false,
}: {
    provider: Provider;
    canManage: boolean;
    routingControls?: ReactNode;
    compact?: boolean;
}) {
    const [busy, setBusy] = useState(false);
    const [newKey, setNewKey] = useState('');
    const [expanded, setExpanded] = useState(false);
    const [replaceVisible, setReplaceVisible] = useState(false);
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
        <article
            className="kmj-ai-managed-provider border-sidebar-border/70 dark:border-sidebar-border flex flex-col gap-3 rounded-2xl border p-5"
            data-compact={compact ? 'true' : undefined}
        >
            <header className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h2 className="text-base font-black">{provider.name}</h2>
                    <p className="text-muted-foreground text-xs">
                        {provider.host} ·{' '}
                        {provider.preset === 'kilo-free'
                            ? 'No API key'
                            : `key ${provider.key_mask}`}
                    </p>
                </div>
                <div className="flex gap-2 text-xs font-bold">
                    <span className="rounded-full border px-3 py-1">
                        {provider.error_code === 'provider_retired'
                            ? 'Retired'
                            : provider.health === 'ok'
                              ? provider.models.length > 0
                                  ? 'Ready'
                                  : 'Needs free-model evidence'
                              : provider.health === 'auth_failed'
                                ? 'Reconnect required'
                                : `Health: ${provider.health}`}
                    </span>
                    <span className="rounded-full border px-3 py-1">
                        {provider.error_code === 'provider_retired'
                            ? 'Inactive'
                            : provider.enabled
                              ? 'Enabled'
                              : 'Disabled'}
                    </span>
                </div>
            </header>

            <p className="kmj-ai-admission-summary text-sm" role="status">
                <strong>{provider.models.length}</strong> verified-free models
                admitted · {provider.discovered_model_count}{' '}
                {provider.preset === 'openrouter'
                    ? 'zero-prompt-price catalog candidates'
                    : 'catalog models'}{' '}
                {provider.health !== 'ok' ? ' cached' : ' discovered'}
                {provider.models.length === 0
                    ? ' · Inference blocked until verified-free admission'
                    : ' · Free-only policy active'}
            </p>

            <div className="flex flex-wrap items-center gap-2">
                {canManage && provider.error_code !== 'provider_retired' && (
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
                        className="inline-flex min-h-10 items-center gap-2 rounded-xl border px-3 text-sm font-semibold"
                    >
                        <RefreshCw className="h-4 w-4" aria-hidden="true" />
                        Recheck models
                    </button>
                )}
                <button
                    type="button"
                    aria-expanded={expanded}
                    aria-controls={`ai-provider-details-${provider.id}`}
                    onClick={() => {
                        setExpanded((current) => !current);
                        setReplaceVisible(false);
                        setNewKey('');
                    }}
                    className="inline-flex min-h-10 items-center rounded-xl border px-4 text-sm font-semibold"
                >
                    {expanded
                        ? 'Hide settings'
                        : canManage &&
                            provider.enabled &&
                            provider.error_code !== 'provider_retired' &&
                            provider.health !== 'ok'
                          ? 'Repair connection'
                          : 'Manage settings'}
                </button>
            </div>

            {compact ? (
                <details className="kmj-ai-advanced rounded-lg border p-2">
                    <summary className="cursor-pointer text-sm font-medium">
                        Model eligibility &amp; routing
                    </summary>
                    <div className="mt-2 flex flex-col gap-2">
                        {routingControls}
                    </div>
                </details>
            ) : (
                routingControls
            )}

            {expanded && (
                <div
                    id={`ai-provider-details-${provider.id}`}
                    className="kmj-ai-provider-details space-y-4 border-t pt-4"
                >
                    <p className="text-muted-foreground text-sm">
                        Credit balance: UNKNOWN (no authoritative API) ·{' '}
                        {creditText(provider.rate_limit)} ·{' '}
                        {FREE_TIER_TEXT[provider.free_tier]}
                        {provider.error_code
                            ? ` · last error: ${provider.error_code}`
                            : ''}
                    </p>
                    {canManage && (
                        <div className="flex flex-wrap items-center gap-2">
                            <button
                                type="button"
                                disabled={busy}
                                onClick={() =>
                                    patch({ enabled: !provider.enabled })
                                }
                                className="min-h-10 rounded-xl border px-3 text-sm font-semibold"
                            >
                                {provider.enabled
                                    ? 'Disable provider'
                                    : 'Enable provider'}
                            </button>
                            <span className="rounded-full border px-3 py-2 text-sm">
                                Zero-spend enforced
                            </span>
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
                                            router.delete(
                                                `${BASE}/${provider.id}`,
                                                {
                                                    ...options,
                                                    data: { confirm: 'DELETE' },
                                                },
                                            ),
                                        );
                                    }
                                }}
                                className="inline-flex min-h-10 items-center gap-2 rounded-xl border px-3 text-sm font-semibold text-red-400"
                            >
                                <Trash2
                                    className="h-4 w-4"
                                    aria-hidden="true"
                                />
                                Delete provider
                            </button>
                        </div>
                    )}

                    {provider.models.length === 0 ? (
                        <p
                            className="text-muted-foreground text-sm"
                            role="status"
                        >
                            {provider.discovered_model_count > 0
                                ? `${provider.discovered_model_count} ${provider.preset === 'openrouter' ? 'zero-prompt-price catalog candidates' : 'catalog models'} found, but none is currently admitted as verified free. Verify your free model allowlist and run “Test connection” again. Paid and unknown-price models cannot be selected.`
                                : 'No admitted free models yet. Run “Test connection” to discover models and verify the free-only policy.'}
                        </p>
                    ) : (
                        <div className="grid gap-3 md:grid-cols-2">
                            <label className="text-xs font-bold">
                                Verified-free default model
                                <select
                                    className="bg-background mt-1 block h-9 w-full rounded-xl border px-2"
                                    value={
                                        provider.default_model &&
                                        provider.models.includes(
                                            provider.default_model,
                                        )
                                            ? provider.default_model
                                            : ''
                                    }
                                    disabled={busy || !canManage}
                                    onChange={(event) =>
                                        patch({
                                            default_model:
                                                event.target.value || null,
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
                                <legend>
                                    Verified-free fallback models (max 5)
                                </legend>
                                <div className="mt-1 max-h-32 space-y-1 overflow-y-auto">
                                    {provider.models
                                        .filter(
                                            (model) =>
                                                model !==
                                                provider.default_model,
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
                                                    disabled={
                                                        busy || !canManage
                                                    }
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
                        <button
                            type="button"
                            onClick={() => {
                                setReplaceVisible((current) => !current);
                                setNewKey('');
                            }}
                            aria-expanded={replaceVisible}
                            aria-controls={`ai-provider-replace-key-${provider.id}`}
                            className="min-h-10 rounded-xl border px-3 text-sm font-semibold"
                        >
                            {replaceVisible
                                ? 'Cancel key replacement'
                                : 'Replace API key'}
                        </button>
                    )}
                    {canManage && replaceVisible && (
                        <div id={`ai-provider-replace-key-${provider.id}`}>
                            <form
                                className="flex flex-wrap items-end gap-2"
                                onSubmit={(event) => {
                                    event.preventDefault();
                                    if (newKey.length >= 8) {
                                        act(() =>
                                            router.patch(
                                                `${BASE}/${provider.id}`,
                                                {
                                                    api_key: newKey,
                                                    verify_connection: true,
                                                },
                                                {
                                                    ...options,
                                                    onSuccess: () => {
                                                        setNewKey('');
                                                        setReplaceVisible(
                                                            false,
                                                        );
                                                    },
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
                                        onChange={(event) =>
                                            setNewKey(event.target.value)
                                        }
                                        className="bg-background mt-1 block h-9 w-64 rounded-xl border px-3 font-normal"
                                    />
                                </label>
                                <button
                                    type="submit"
                                    disabled={busy || newKey.length < 8}
                                    className="inline-flex h-9 items-center gap-2 rounded-xl border px-3 text-xs font-bold"
                                >
                                    <KeyRound className="h-3.5 w-3.5" />
                                    Replace key &amp; verify
                                </button>
                            </form>
                        </div>
                    )}
                </div>
            )}
        </article>
    );
}

function AddProvider({
    presets,
    preferredPreset,
    onManualProviderChange,
}: {
    presets: Preset[];
    preferredPreset: { key: string; token: number } | null;
    onManualProviderChange: () => void;
}) {
    const [preset, setPreset] = useState(presets[0]?.key ?? 'groq');
    const formRef = useRef<HTMLFormElement>(null);
    const keyInputRef = useRef<HTMLInputElement>(null);
    const lastPreferredSelection = useRef<typeof preferredPreset>(null);
    const [name, setName] = useState('');
    const [apiKey, setApiKey] = useState('');
    const [baseUrl, setBaseUrl] = useState('');
    const [busy, setBusy] = useState(false);
    const errors = usePage().props.errors as Record<string, string>;
    const selected = presets.find((item) => item.key === preset);

    useEffect(() => {
        if (
            !preferredPreset ||
            !presets.some((item) => item.key === preferredPreset.key)
        ) {
            return;
        }
        if (lastPreferredSelection.current === preferredPreset) return;
        lastPreferredSelection.current = preferredPreset;
        // Never carry a draft credential across different provider accounts.
        setApiKey('');
        setBaseUrl('');
        setName('');
        setPreset(preferredPreset.key);
        // Official provider keys cannot be read across sites. Prepare and focus
        // the legitimate local form for the owner to finish on returning.
        const frame = window.requestAnimationFrame(() => {
            formRef.current?.scrollIntoView({
                behavior: 'smooth',
                block: 'center',
            });
            keyInputRef.current?.focus({ preventScroll: true });
        });
        return () => window.cancelAnimationFrame(frame);
    }, [preferredPreset, presets]);

    return (
        <form
            ref={formRef}
            id="ai-provider-key-form"
            aria-label="Connect provider with encrypted API key"
            className="kmj-ai-key-form border-sidebar-border/70 dark:border-sidebar-border grid gap-4 rounded-2xl border p-5 md:grid-cols-2"
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
                        verify_connection: true,
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
            <div className="md:col-span-2">
                <p className="text-xs font-bold tracking-wider text-red-400 uppercase">
                    Step 2 of 2 · Secure key verification
                </p>
                <h2
                    className="mt-1 flex items-center gap-2 text-lg font-black"
                    aria-live="polite"
                >
                    <Plug className="h-4 w-4" />
                    Finish {selected?.label ?? 'provider'} connection
                </h2>
                <p className="text-muted-foreground mt-1 text-sm">
                    Get a key from the official provider dashboard, paste it
                    below, then verify with a read-only model discovery call. No
                    inference or billed fallback will be started.
                </p>
            </div>
            <label className="text-xs font-bold">
                Provider
                <select
                    className="bg-background mt-1 block h-9 w-full rounded-xl border px-2"
                    value={preset}
                    onChange={(event) => {
                        setApiKey('');
                        setBaseUrl('');
                        setName('');
                        setPreset(event.target.value);
                        onManualProviderChange();
                    }}
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
                    value={name}
                    placeholder="Optional (defaults to the provider name)"
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
                    ref={keyInputRef}
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
                providers are always zero-spend; billed inference cannot be
                enabled here. Changes need a recent password confirmation.
            </p>
            <button
                type="submit"
                disabled={busy}
                className="h-10 rounded-xl border border-red-500/40 px-4 text-xs font-bold text-red-500 md:col-span-2"
            >
                {busy
                    ? 'Verifying securely…'
                    : `Save & verify ${selected?.label ?? 'provider'} connection`}
            </button>
        </form>
    );
}

export default function AiProviders({
    embedded = false,
    renderRoutingControls,
    status,
    canManage,
    presets,
    providers,
}: Props) {
    const errors = usePage().props.errors as Record<string, string>;
    const [preferredPreset, setPreferredPreset] = useState<{
        key: string;
        token: number;
    } | null>(null);
    const [oauthBusy, setOauthBusy] = useState(false);
    const [showKeyForm, setShowKeyForm] = useState(false);
    const [showConnect, setShowConnect] = useState(true);
    const [connectionFilter, setConnectionFilter] = useState<
        'all' | 'ready' | 'attention' | 'inactive'
    >('all');
    const [connectionSearch, setConnectionSearch] = useState('');
    const ready = (provider: Provider) =>
        provider.enabled &&
        provider.health === 'ok' &&
        provider.models.length > 0 &&
        provider.error_code !== 'provider_retired';
    const inactive = (provider: Provider) =>
        !provider.enabled || provider.error_code === 'provider_retired';
    const visibleProviders = providers.filter((provider) => {
        const matches = (
            provider.name +
            ' ' +
            provider.preset +
            ' ' +
            provider.host
        )
            .toLowerCase()
            .includes(connectionSearch.trim().toLowerCase());
        return (
            matches &&
            (connectionFilter === 'all' ||
                (connectionFilter === 'ready' && ready(provider)) ||
                (connectionFilter === 'attention' &&
                    !ready(provider) &&
                    !inactive(provider)) ||
                (connectionFilter === 'inactive' && inactive(provider)))
        );
    });
    const startOpenRouter = () => {
        if (oauthBusy) return;
        setOauthBusy(true);
        router.post(
            BASE + '/connect/openrouter',
            embedded ? { return_to: 'modelfabric' } : {},
            {
                preserveScroll: true,
                onFinish: () => setOauthBusy(false),
            },
        );
    };

    const startKiloFree = () => {
        if (oauthBusy) return;
        setOauthBusy(true);
        router.post(
            BASE + '/connect/kilo-free',
            { public_prompts_confirmed: true },
            { preserveScroll: true, onFinish: () => setOauthBusy(false) },
        );
    };

    const startHuggingFace = () => {
        if (oauthBusy) return;
        setOauthBusy(true);
        router.post(
            BASE + '/connect/huggingface',
            embedded
                ? { free_account_confirmed: true, return_to: 'modelfabric' }
                : { free_account_confirmed: true },
            {
                preserveScroll: true,
                onFinish: () => setOauthBusy(false),
            },
        );
    };

    return (
        <>
            {!embedded && <Head title="AI Providers" />}
            <div
                id={embedded ? 'provider-connections' : undefined}
                className="kmj-ai-providers owner-admin-surface flex h-full min-w-0 flex-1 flex-col gap-6 p-4 sm:p-6"
            >
                {!embedded && (
                    <Link
                        href="/services/kmj-codebridge"
                        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-2 text-xs font-bold"
                    >
                        <ArrowLeft className="h-3.5 w-3.5" />
                        Back to CodeBridge
                    </Link>
                )}
                <div>
                    {embedded ? (
                        <h2 className="text-2xl font-black">
                            Connect and manage AI
                        </h2>
                    ) : (
                        <h1 className="text-2xl font-black">AI Providers</h1>
                    )}
                    <p className="text-muted-foreground text-sm">
                        Connect an account, discover models and manage
                        verified-free routes in one place. Connection checks
                        never send a prompt.
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
                    <>
                        {embedded && providers.length > 0 && (
                            <button
                                type="button"
                                aria-expanded={showConnect}
                                aria-controls="modelfabric-connect-setup"
                                onClick={() =>
                                    setShowConnect((current) => !current)
                                }
                                className="min-h-11 self-start rounded-xl border px-4 text-sm font-semibold"
                            >
                                {showConnect
                                    ? 'Hide provider setup'
                                    : 'Connect or reconnect a provider'}
                            </button>
                        )}
                        {(!embedded ||
                            providers.length === 0 ||
                            showConnect) && (
                            <div
                                id={
                                    embedded
                                        ? 'modelfabric-connect-setup'
                                        : undefined
                                }
                                className="flex flex-col gap-4"
                            >
                                <AiProviderConnectHub
                                    presets={presets}
                                    compact={embedded}
                                    connectedPresets={providers.map(
                                        (provider) => provider.preset,
                                    )}
                                    oauthBusy={oauthBusy}
                                    onConnectOpenRouter={startOpenRouter}
                                    onConnectHuggingFace={startHuggingFace}
                                    onConnectKiloFree={startKiloFree}
                                    selectedPreset={
                                        preferredPreset?.key ?? null
                                    }
                                    onChooseKeyProvider={(key) => {
                                        setShowKeyForm(true);
                                        setPreferredPreset((prev) => ({
                                            key,
                                            token: (prev?.token ?? 0) + 1,
                                        }));
                                    }}
                                />
                                {showKeyForm ? (
                                    <div className="space-y-2">
                                        <button
                                            type="button"
                                            onClick={() => {
                                                setShowKeyForm(false);
                                                setPreferredPreset(null);
                                            }}
                                            className="min-h-10 rounded-xl border px-3 text-sm font-semibold"
                                        >
                                            Close key setup
                                        </button>
                                        <AddProvider
                                            presets={presets.filter(
                                                (preset) =>
                                                    preset.key !== 'kilo-free',
                                            )}
                                            preferredPreset={preferredPreset}
                                            onManualProviderChange={() =>
                                                setPreferredPreset(null)
                                            }
                                        />
                                    </div>
                                ) : (
                                    <button
                                        type="button"
                                        onClick={() => setShowKeyForm(true)}
                                        className="kmj-ai-manual-launcher min-h-11 self-start rounded-xl border px-4 text-sm font-semibold"
                                    >
                                        Connect another provider using an API
                                        key
                                    </button>
                                )}
                            </div>
                        )}
                    </>
                ) : (
                    <p className="text-muted-foreground text-sm">
                        Only organization owners can change providers.
                    </p>
                )}
                {embedded && (
                    <div
                        id="modelfabric-connected-providers"
                        className="kmj-ai-connections-header flex flex-col gap-3 rounded-2xl border p-4"
                    >
                        <div>
                            <p className="text-xs font-bold tracking-wider text-red-400 uppercase">
                                Connected accounts
                            </p>
                            <h2 className="text-xl font-black">
                                Your connected providers
                            </h2>
                            <p className="text-muted-foreground text-sm">
                                {providers.filter(ready).length} ready ·{' '}
                                {
                                    providers.filter(
                                        (provider) =>
                                            !ready(provider) &&
                                            !inactive(provider),
                                    ).length
                                }{' '}
                                need attention ·{' '}
                                {providers.filter(inactive).length} inactive
                            </p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                            <input
                                aria-label="Search connected providers"
                                placeholder="Find a connection…"
                                value={connectionSearch}
                                onChange={(event) =>
                                    setConnectionSearch(event.target.value)
                                }
                                className="min-w-0 flex-1 rounded-lg border px-3 py-2"
                            />
                            <div
                                aria-label="Connected provider filters"
                                className="flex flex-wrap gap-1"
                            >
                                {(
                                    [
                                        ['all', 'All'],
                                        ['ready', 'Ready'],
                                        ['attention', 'Needs attention'],
                                        ['inactive', 'Inactive'],
                                    ] as const
                                ).map(([value, label]) => (
                                    <button
                                        key={value}
                                        type="button"
                                        aria-pressed={
                                            connectionFilter === value
                                        }
                                        onClick={() =>
                                            setConnectionFilter(value)
                                        }
                                        className="kmj-ai-filter rounded-lg border px-3 text-sm font-semibold"
                                    >
                                        {label}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                )}
                <section
                    className={
                        embedded
                            ? 'kmj-ai-connection-list grid gap-2'
                            : 'grid gap-4'
                    }
                    aria-label="Configured providers"
                >
                    {providers.length === 0 && (
                        <p className="text-muted-foreground text-sm">
                            No cloud AI providers connected. An organization
                            owner must connect a verified-free cloud provider
                            before inference is available. Paid and
                            unknown-price inference stays blocked.
                        </p>
                    )}
                    {embedded &&
                        providers.length > 0 &&
                        visibleProviders.length === 0 && (
                            <p
                                role="status"
                                className="text-muted-foreground text-sm"
                            >
                                No connections match this filter.
                            </p>
                        )}
                    {(embedded ? visibleProviders : providers).map(
                        (provider) => (
                            <ProviderCard
                                key={provider.id}
                                provider={provider}
                                canManage={canManage}
                                compact={embedded}
                                routingControls={renderRoutingControls?.(
                                    provider.id,
                                )}
                            />
                        ),
                    )}
                </section>
            </div>
        </>
    );
}
