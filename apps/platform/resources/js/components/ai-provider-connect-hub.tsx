import { useState } from 'react';
import {
    ExternalLink,
    KeyRound,
    LockKeyhole,
    ShieldCheck,
    Zap,
} from 'lucide-react';

type Preset = {
    key: string;
    label: string;
    free_tier: 'allowlist' | 'model-suffix' | 'none';
    custom: boolean;
};

type Guide = {
    key: string;
    title: string;
    url: string;
    helper: string;
};

const guides: Guide[] = [
    {
        key: 'groq',
        title: 'Groq',
        url: 'https://console.groq.com/keys',
        helper: 'Create a GroqCloud API key. Only owner-approved free models can run.',
    },
    {
        key: 'gemini',
        title: 'Gemini',
        url: 'https://aistudio.google.com/apikey',
        helper: 'Create a Gemini API authorization key. Verify the free model allowlist.',
    },
    {
        key: 'mistral',
        title: 'Mistral',
        url: 'https://console.mistral.ai/api-keys/',
        helper: 'Use your Mistral workspace key. Paid or unverified models stay blocked.',
    },
    {
        key: 'sambanova',
        title: 'SambaNova',
        url: 'https://cloud.sambanova.ai/dashboard',
        helper: 'Choose the free plan and create a key. Exact account and model limits require verification.',
    },
    {
        key: 'cohere',
        title: 'Cohere',
        url: 'https://dashboard.cohere.com/api-keys',
        helper: 'Evaluation keys are limited to evaluation. Production requires a separate eligibility review.',
    },
    {
        key: 'zai',
        title: 'Z.ai GLM',
        url: 'https://z.ai/',
        helper: 'Discover models with an official API key. Inference is blocked pending qualification.',
    },
    {
        key: 'siliconflow',
        title: 'SiliconFlow',
        url: 'https://www.siliconflow.com/',
        helper: 'Use the international account and key. Inference is blocked pending qualification.',
    },
    {
        key: 'modelscope',
        title: 'ModelScope',
        url: 'https://www.modelscope.cn/',
        helper: 'Use an official inference token. Regional access and account binding require review.',
    },
    {
        key: 'anyapi',
        title: 'AnyAPI',
        url: 'https://anyapi.ai/',
        helper: 'Discover the account catalog; playground access is not proof of free API inference.',
    },
    {
        key: 'cerebras',
        title: 'Cerebras',
        url: 'https://cloud.cerebras.ai/',
        helper: 'Create a Cerebras API key. Only owner-approved free models can run.',
    },
    {
        key: 'nvidia',
        title: 'NVIDIA NIM',
        url: 'https://build.nvidia.com/',
        helper: 'Create an NVIDIA API Catalog key. Only owner-approved free models can run.',
    },
    {
        key: 'huggingface',
        title: 'Hugging Face',
        url: 'https://huggingface.co/settings/tokens',
        helper: 'Create a restricted Hugging Face token. Check the free model allowlist.',
    },
];

export default function AiProviderConnectHub({
    presets,
    oauthBusy,
    onConnectOpenRouter,
    onConnectHuggingFace,
    onConnectKiloFree,
    onChooseKeyProvider,
    selectedPreset,
    compact = false,
    connectedPresets = [],
}: {
    presets: Preset[];
    oauthBusy: boolean;
    onConnectOpenRouter: () => void;
    onConnectHuggingFace: () => void;
    onConnectKiloFree: () => void;
    onChooseKeyProvider: (preset: string) => void;
    selectedPreset: string | null;
    compact?: boolean;
    connectedPresets?: string[];
}) {
    const supported = new Set(presets.map((preset) => preset.key));
    const [hfFree, setHfFree] = useState(false);
    const [kiloPublic, setKiloPublic] = useState(false);
    const [query, setQuery] = useState('');
    const [hideConnected, setHideConnected] = useState(false);
    const [choice, setChoice] = useState('');
    const connected = new Set(connectedPresets);
    const oauthKeys = new Set(['openrouter', 'huggingface']);

    if (compact) {
        const selected = presets.find((preset) => preset.key === choice);
        const guide = guides.find((item) => item.key === choice);
        const visible = presets.filter(
            (preset) =>
                preset.key === choice ||
                ((!hideConnected || !connected.has(preset.key)) &&
                    (preset.label + ' ' + preset.key)
                        .toLowerCase()
                        .includes(query.trim().toLowerCase())),
        );

        return (
            <section
                aria-labelledby="modelfabric-discover-title"
                className="kmj-ai-directory rounded-2xl border p-4 sm:p-5"
            >
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <h2
                            id="modelfabric-discover-title"
                            className="text-xl font-black"
                        >
                            Add AI provider
                        </h2>
                        <p className="text-muted-foreground text-sm">
                            {presets.length} supported provider types. Choose a
                            provider to see its real connection method.
                        </p>
                    </div>
                    <span className="kmj-ai-zero-spend inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-bold">
                        <ShieldCheck aria-hidden="true" className="h-4 w-4" />
                        Free-only routing
                    </span>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2">
                    <label className="text-sm font-semibold">
                        Search provider directory
                        <input
                            placeholder="Search providers…"
                            className="mt-1 w-full rounded-xl border px-3 py-2"
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                        />
                    </label>
                    <label className="text-sm font-semibold">
                        Select provider
                        <select
                            className="mt-1 w-full rounded-xl border px-3 py-2"
                            value={choice}
                            onChange={(event) => setChoice(event.target.value)}
                        >
                            <option value="">Choose a provider</option>
                            {visible.map((preset) => (
                                <option key={preset.key} value={preset.key}>
                                    {preset.label}
                                    {preset.key === 'kilo-free'
                                        ? ' · No key required'
                                        : oauthKeys.has(preset.key)
                                          ? ' · OAuth'
                                          : ' · API key'}
                                    {connected.has(preset.key)
                                        ? ' · Connected'
                                        : ''}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label className="flex items-center gap-2 text-sm">
                        <input
                            type="checkbox"
                            checked={hideConnected}
                            onChange={(event) =>
                                setHideConnected(event.target.checked)
                            }
                        />
                        Hide connected providers
                    </label>
                    {visible.length === 0 && (
                        <p
                            role="status"
                            className="text-muted-foreground text-sm"
                        >
                            No matching providers. Clear the search or show
                            connected providers.
                        </p>
                    )}
                </div>
                {selected && (
                    <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3">
                        <div>
                            <h3 className="font-bold">{selected.label}</h3>
                            <p className="text-muted-foreground text-xs">
                                {selected.free_tier === 'none'
                                    ? 'Discovery only · inference blocked'
                                    : 'Free-only policy · eligibility checked separately'}
                            </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            {guide && (
                                <a
                                    href={guide.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="kmj-ai-filter inline-flex items-center gap-1 rounded-lg border px-3 text-sm font-semibold"
                                >
                                    Get API key
                                    <ExternalLink className="h-3 w-3" />
                                </a>
                            )}
                            {selected.key === 'kilo-free' ? (
                                <a
                                    href="#modelfabric-keyless-connect"
                                    className="kmj-ai-primary-action inline-flex min-h-11 items-center rounded-lg px-4 text-sm font-bold"
                                >
                                    Connect without a key
                                </a>
                            ) : oauthKeys.has(selected.key) ? (
                                <a
                                    href="#modelfabric-oauth-connect"
                                    className="kmj-ai-primary-action inline-flex min-h-11 items-center rounded-lg px-4 text-sm font-bold"
                                >
                                    Use account authorization
                                </a>
                            ) : (
                                <button
                                    type="button"
                                    onClick={() =>
                                        onChooseKeyProvider(selected.key)
                                    }
                                    className="kmj-ai-primary-action min-h-11 rounded-lg px-4 text-sm font-bold"
                                >
                                    Connect with API key
                                </button>
                            )}
                        </div>
                    </div>
                )}

                <div
                    id="modelfabric-oauth-connect"
                    className="mt-5 scroll-mt-4 border-t pt-4"
                >
                    <h3 className="flex items-center gap-2 text-base font-bold">
                        <Zap className="h-4 w-4 text-red-400" />
                        One-click OAuth
                    </h3>
                    <p className="text-muted-foreground mt-1 text-sm">
                        OpenRouter and Hugging Face support account
                        authorization here. Other providers use official API
                        keys.
                    </p>
                    <div className="mt-3 grid gap-3 md:grid-cols-2">
                        {supported.has('openrouter') && (
                            <article className="kmj-ai-directory-item rounded-xl border p-3">
                                <h4 className="font-bold">OpenRouter</h4>
                                <p className="text-muted-foreground mt-1 text-xs">
                                    Account authorization · free model discovery
                                </p>
                                <button
                                    type="button"
                                    disabled={oauthBusy}
                                    aria-busy={oauthBusy}
                                    onClick={onConnectOpenRouter}
                                    className="kmj-ai-primary-action mt-3 min-h-11 w-full rounded-lg px-3 text-sm font-bold"
                                >
                                    {connected.has('openrouter')
                                        ? 'Add OpenRouter account'
                                        : 'Connect OpenRouter'}
                                </button>
                            </article>
                        )}
                        {supported.has('huggingface') && (
                            <article className="kmj-ai-directory-item rounded-xl border p-3">
                                <h4 className="font-bold">Hugging Face</h4>
                                <p className="text-muted-foreground mt-1 text-xs">
                                    Account authorization · inference
                                    eligibility not guaranteed
                                </p>
                                <label className="mt-2 flex items-start gap-2 text-xs">
                                    <input
                                        type="checkbox"
                                        checked={hfFree}
                                        onChange={(event) =>
                                            setHfFree(event.target.checked)
                                        }
                                    />
                                    Free account, no payment method
                                </label>
                                <button
                                    type="button"
                                    disabled={oauthBusy || !hfFree}
                                    onClick={onConnectHuggingFace}
                                    className="kmj-ai-primary-action mt-3 min-h-11 w-full rounded-lg px-3 text-sm font-bold disabled:opacity-50"
                                >
                                    {connected.has('huggingface')
                                        ? 'Reconnect Hugging Face'
                                        : 'Connect Hugging Face'}
                                </button>
                            </article>
                        )}
                    </div>
                </div>
                {supported.has('kilo-free') && (
                    <article
                        id="modelfabric-keyless-connect"
                        className="kmj-ai-directory-item mt-4 rounded-xl border p-3"
                    >
                        <h3 className="font-bold">One-click without API key</h3>
                        <h4 className="mt-2 font-bold">Kilo Gateway</h4>
                        <p className="text-muted-foreground text-xs">
                            Free public chat · 200 requests/hour per IP shared across models.
                        </p>
                        <label className="mt-2 flex items-start gap-2 text-xs">
                            <input
                                type="checkbox"
                                checked={kiloPublic}
                                onChange={(event) =>
                                    setKiloPublic(event.target.checked)
                                }
                            />
                            Public, non-confidential prompts only; provider terms apply.
                        </label>
                        <button
                            type="button"
                            disabled={oauthBusy || !kiloPublic || connected.has('kilo-free')}
                            onClick={onConnectKiloFree}
                            className="kmj-ai-primary-action mt-3 min-h-11 rounded-lg px-4 text-sm font-bold disabled:opacity-50"
                        >
                            {connected.has('kilo-free')
                                ? 'Connected'
                                : 'Connect Kilo Free'}
                        </button>
                    </article>
                )}
                <p className="text-muted-foreground mt-3 text-xs">
                    Discovery does not prove free inference eligibility.
                </p>
            </section>
        );
    }

    return (
        <section
            aria-labelledby="ai-quick-connect-title"
            className="kmj-ai-connect-hub rounded-2xl border p-5 sm:p-6"
        >
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <p className="text-xs font-bold tracking-[0.12em] text-red-400 uppercase">
                        KMJ TECHNO · Secure provider connections
                    </p>
                    <h2
                        id="ai-quick-connect-title"
                        className="mt-1 text-xl font-black sm:text-2xl"
                    >
                        Connect an AI provider
                    </h2>
                    <p className="text-muted-foreground mt-2 max-w-3xl text-sm leading-6">
                        One-click account authorization where supported; guided
                        encrypted API-key setup everywhere else. No billable
                        inference or paid fallback is activated.
                    </p>
                </div>
                <span className="kmj-ai-zero-spend inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-bold">
                    <ShieldCheck aria-hidden="true" className="h-4 w-4" />
                    Free-only routing enforced
                </span>
            </div>

            {supported.has('openrouter') && (
                <div className="kmj-ai-oauth-panel mt-5 flex flex-wrap items-center justify-between gap-4 rounded-2xl border p-5">
                    <div className="max-w-2xl">
                        <h3 className="flex items-center gap-2 text-lg font-bold">
                            <Zap
                                className="h-5 w-5 text-red-400"
                                aria-hidden="true"
                            />
                            OpenRouter — connect with your account
                        </h3>
                        <p className="text-muted-foreground mt-1 text-sm leading-6">
                            One click starts OpenRouter sign-in. Choose Google
                            or GitHub there; KMJ then receives an API key
                            server-side and checks the free-only model catalog
                            without sending a prompt.
                        </p>
                    </div>
                    <button
                        type="button"
                        disabled={oauthBusy}
                        onClick={onConnectOpenRouter}
                        aria-busy={oauthBusy}
                        className="kmj-ai-primary-action inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-bold disabled:cursor-wait disabled:opacity-60"
                    >
                        <LockKeyhole className="h-4 w-4" aria-hidden="true" />
                        {oauthBusy
                            ? 'Opening secure sign-in…'
                            : 'Connect OpenRouter'}
                    </button>
                </div>
            )}

            {supported.has('huggingface') && (
                <div className="kmj-ai-oauth-panel mt-4 flex flex-wrap items-center justify-between gap-4 rounded-2xl border p-5">
                    <div className="max-w-2xl">
                        <h3 className="flex items-center gap-2 text-lg font-bold">
                            <Zap
                                className="h-5 w-5 text-red-400"
                                aria-hidden="true"
                            />
                            Hugging Face — connect with your account
                        </h3>
                        <p className="text-muted-foreground mt-1 text-sm leading-6">
                            One click opens Hugging Face sign-in (no app to
                            register, no key to copy). Hugging Face documents no
                            included inference credits for Free accounts, so
                            expect no free models here unless its pricing page
                            shows one. A PRO or pay-as-you-go account could be
                            billed, so connect a Free account only.
                        </p>
                        <label className="mt-2 flex items-start gap-2 text-xs font-medium">
                            <input
                                type="checkbox"
                                className="mt-0.5"
                                checked={hfFree}
                                onChange={(e) => setHfFree(e.target.checked)}
                            />
                            This Hugging Face account is a Free account with no
                            payment method.
                        </label>
                    </div>
                    <button
                        type="button"
                        disabled={oauthBusy || !hfFree}
                        onClick={onConnectHuggingFace}
                        className="kmj-ai-primary-action inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        <LockKeyhole className="h-4 w-4" aria-hidden="true" />
                        Connect Hugging Face
                    </button>
                </div>
            )}

            <div className="mt-5">
                <h3 className="text-base font-bold">
                    Other providers — guided key connection
                </h3>
                <p className="text-muted-foreground mt-1 text-sm">
                    These providers require their own key. The official
                    dashboard opens in a new tab and the KMJ connection form is
                    prepared below; the key is never read automatically from the
                    browser.
                </p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    {guides
                        .filter((guide) => supported.has(guide.key))
                        .map((guide) => {
                            const provider = presets.find(
                                (preset) => preset.key === guide.key,
                            );
                            return (
                                <article
                                    key={guide.key}
                                    className="kmj-ai-key-card flex flex-col rounded-xl border p-4"
                                    data-selected={
                                        selectedPreset === guide.key
                                            ? 'true'
                                            : undefined
                                    }
                                >
                                    <h4 className="font-bold">
                                        {provider?.label}
                                    </h4>
                                    <p className="text-muted-foreground mt-1 flex-1 text-sm leading-6">
                                        {guide.helper}
                                    </p>
                                    {selectedPreset === guide.key && (
                                        <p
                                            className="kmj-ai-selected-hint mt-2 text-sm"
                                            role="status"
                                        >
                                            Selected · Finish the secure
                                            connection below
                                        </p>
                                    )}
                                    <a
                                        href={guide.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        onClick={() =>
                                            onChooseKeyProvider(guide.key)
                                        }
                                        className="mt-4 inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-semibold"
                                    >
                                        <KeyRound
                                            className="h-4 w-4"
                                            aria-hidden="true"
                                        />
                                        Connect {guide.title}
                                        <ExternalLink
                                            className="h-3.5 w-3.5"
                                            aria-hidden="true"
                                        />
                                    </a>
                                </article>
                            );
                        })}
                </div>
            </div>
        </section>
    );
}
