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
    onChooseKeyProvider,
    selectedPreset,
    compact = false,
    connectedPresets = [],
}: {
    presets: Preset[];
    oauthBusy: boolean;
    onConnectOpenRouter: () => void;
    onConnectHuggingFace: () => void;
    onChooseKeyProvider: (preset: string) => void;
    selectedPreset: string | null;
    compact?: boolean;
    connectedPresets?: string[];
}) {
    const supported = new Set(presets.map((preset) => preset.key));
    const [hfFree, setHfFree] = useState(false);
    const [query, setQuery] = useState('');
    const [filter, setFilter] = useState<'available' | 'all' | 'oauth'>(
        'available',
    );
    const connected = new Set(connectedPresets);

    if (compact) {
        const visible = presets.filter((preset) => {
            const oauth =
                preset.key === 'openrouter' || preset.key === 'huggingface';
            return (
                (filter !== 'available' || !connected.has(preset.key)) &&
                (filter !== 'oauth' || oauth) &&
                (preset.label + ' ' + preset.key)
                    .toLowerCase()
                    .includes(query.trim().toLowerCase())
            );
        });
        return (
            <section
                aria-labelledby="modelfabric-discover-title"
                className="kmj-ai-directory rounded-2xl border p-4 sm:p-5"
            >
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <p className="text-xs font-bold tracking-wider text-red-400 uppercase">
                            Step 1 · Discover providers
                        </p>
                        <h2 id="modelfabric-discover-title" className="text-xl font-black">
                            AI provider directory
                        </h2>
                        <p className="text-muted-foreground text-sm">
                            {presets.filter((preset) => connected.has(preset.key)).length} of {presets.length} provider types connected. Choose a provider to start secure setup.
                        </p>
                    </div>
                    <span className="kmj-ai-zero-spend inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-bold">
                        <ShieldCheck aria-hidden="true" className="h-4 w-4" />
                        Free-only routing
                    </span>
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                    <input
                        aria-label="Search provider directory"
                        placeholder="Search providers…"
                        className="min-w-0 flex-1 rounded-xl border px-3 py-2"
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                    />
                    <div className="flex flex-wrap gap-1" aria-label="Provider directory filters">
                        {([
                            ['available', 'Not connected'],
                            ['all', 'All providers'],
                            ['oauth', 'One-click OAuth'],
                        ] as const).map(([value, label]) => (
                            <button
                                key={value}
                                type="button"
                                aria-pressed={filter === value}
                                onClick={() => setFilter(value)}
                                className="kmj-ai-filter rounded-lg border px-3 text-sm font-semibold"
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                </div>
                <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                    {visible.map((preset) => {
                        const isConnected = connected.has(preset.key);
                        const openRouter = preset.key === 'openrouter';
                        const huggingFace = preset.key === 'huggingface';
                        const guide = guides.find((item) => item.key === preset.key);
                        return (
                            <article
                                key={preset.key}
                                className="kmj-ai-directory-item flex min-w-0 flex-col gap-2 rounded-xl border p-3"
                                data-selected={selectedPreset === preset.key ? 'true' : undefined}
                            >
                                <div className="flex min-w-0 items-start gap-3">
                                    <span aria-hidden="true" className="kmj-ai-provider-monogram flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border text-sm font-black">
                                        {preset.label.slice(0, 2).toUpperCase()}
                                    </span>
                                    <div className="min-w-0 flex-1">
                                        <h3 className="font-bold break-words">{preset.label}</h3>
                                        <p className="text-muted-foreground text-xs">
                                            {isConnected ? 'Account added' : openRouter || huggingFace ? 'Account authorization' : 'API key setup'}
                                            {' · '}
                                            {preset.free_tier === 'none' ? 'Discovery only' : 'Free-only policy'}
                                        </p>
                                    </div>
                                </div>
                                {isConnected && !huggingFace ? (
                                    <a href="#modelfabric-connected-providers" className="kmj-ai-filter inline-flex min-h-10 items-center justify-center rounded-lg border px-3 text-sm font-semibold">
                                        Manage connection
                                    </a>
                                ) : openRouter ? (
                                    <button type="button" disabled={oauthBusy} aria-busy={oauthBusy} onClick={onConnectOpenRouter} className="kmj-ai-primary-action min-h-11 rounded-lg px-3 text-sm font-bold">
                                        Connect OpenRouter
                                    </button>
                                ) : huggingFace ? (
                                    <>
                                        <label className="flex items-start gap-2 text-xs">
                                            <input type="checkbox" checked={hfFree} onChange={(event) => setHfFree(event.target.checked)} />
                                            Free account, no payment method
                                        </label>
                                        <button type="button" disabled={oauthBusy || !hfFree} onClick={onConnectHuggingFace} className="kmj-ai-primary-action min-h-11 rounded-lg px-3 text-sm font-bold disabled:opacity-50">
                                            {isConnected ? 'Reconnect Hugging Face' : 'Connect Hugging Face'}
                                        </button>
                                    </>
                                ) : (
                                    <div className="flex flex-wrap items-center gap-2">
                                        <button type="button" onClick={() => onChooseKeyProvider(preset.key)} className="kmj-ai-filter min-h-10 flex-1 rounded-lg border px-3 text-sm font-semibold">
                                            Connect
                                        </button>
                                        {guide && (
                                            <a href={guide.url} target="_blank" rel="noopener noreferrer" aria-label={`Get ${preset.label} API key`} className="kmj-ai-filter inline-flex min-h-10 items-center gap-1 rounded-lg border px-3 text-xs font-semibold">
                                                Get key <ExternalLink className="h-3 w-3" />
                                            </a>
                                        )}
                                    </div>
                                )}
                            </article>
                        );
                    })}
                </div>
                {visible.length === 0 && (
                    <p role="status" className="text-muted-foreground mt-3 text-sm">
                        No providers match this filter. Try All providers or clear the search.
                    </p>
                )}
                <p className="text-muted-foreground mt-3 text-xs">
                    OAuth is offered only where supported. Discovery does not prove free inference eligibility.
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
