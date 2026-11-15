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
    url: string;
    helper: string;
};

const guides: Guide[] = [
    {
        key: 'groq',
        url: 'https://console.groq.com/keys',
        helper: 'Create a GroqCloud API key. Only owner-approved free models can run.',
    },
    {
        key: 'gemini',
        url: 'https://aistudio.google.com/apikey',
        helper: 'Create a Gemini API authorization key. Verify the free model allowlist.',
    },
    {
        key: 'mistral',
        url: 'https://console.mistral.ai/api-keys/',
        helper: 'Use your Mistral workspace key. Paid or unverified models stay blocked.',
    },
    {
        key: 'huggingface',
        url: 'https://huggingface.co/settings/tokens',
        helper: 'Create a restricted Hugging Face token. Check the free model allowlist.',
    },
];

export default function AiProviderConnectHub({
    presets,
    oauthBusy,
    onConnectOpenRouter,
    onChooseKeyProvider,
}: {
    presets: Preset[];
    oauthBusy: boolean;
    onConnectOpenRouter: () => void;
    onChooseKeyProvider: (preset: string) => void;
}) {
    const supported = new Set(presets.map((preset) => preset.key));

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
                                >
                                    <h4 className="font-bold">
                                        {provider?.label}
                                    </h4>
                                    <p className="text-muted-foreground mt-1 flex-1 text-sm leading-6">
                                        {guide.helper}
                                    </p>
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
                                        Get key &amp; connect
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
