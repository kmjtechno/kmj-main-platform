import { Activity, LockKeyhole, Play, ShieldCheck } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

type ApiReply = {
    modelfabric?: {
        status?: string;
        routes?: number;
        provider?: string;
        attempts?: number;
        profile?: string;
    };
    choices?: { message?: { content?: string } }[];
    model?: string;
};

type Props = {
    canManage: boolean;
    routeReady: boolean;
    hasActiveToken: boolean;
};

const API_ROOT = '/api/modelfabric/v1';
const MAX_PROMPT_CHARS = 1000;

/**
 * Reference UX: FreeLLMAPI Keys -> Models -> Playground.
 *
 * This is an explicitly initiated, same-origin ModelFabric smoke/playground,
 * NOT a connection to a third-party router or a raw provider API. The bearer
 * exists only in component memory; no storage, URL or analytics receives it.
 */
export default function ModelFabricSafePlayground({
    canManage,
    routeReady,
    hasActiveToken,
}: Props) {
    const [apiKey, setApiKey] = useState('');
    const [prompt, setPrompt] = useState(
        'Reply with one sentence: ModelFabric is ready.',
    );
    const [consent, setConsent] = useState(false);
    const [busy, setBusy] = useState<'check' | 'chat' | null>(null);
    const [verifiedRoutes, setVerifiedRoutes] = useState<number | null>(null);
    const [message, setMessage] = useState('');
    const [output, setOutput] = useState('');
    const [servedModel, setServedModel] = useState('');
    const [servedProvider, setServedProvider] = useState('');
    const [elapsedMs, setElapsedMs] = useState<number | null>(null);
    const inFlight = useRef<AbortController | null>(null);

    useEffect(
        () => () => {
            inFlight.current?.abort();
        },
        [],
    );

    const canChat =
        canManage &&
        routeReady &&
        verifiedRoutes !== null &&
        verifiedRoutes > 0 &&
        apiKey.trim().length > 0 &&
        consent &&
        prompt.trim().length > 0 &&
        prompt.length <= MAX_PROMPT_CHARS &&
        !busy;

    const explainFailure = (status: number) => {
        switch (status) {
            case 401:
                return 'Token invalid, revoked or expired. Create a new ModelFabric token.';
            case 403:
                return 'This token is not authorized for the requested scope.';
            case 429:
                return 'Request limit reached. Retry later.';
            case 503:
                return 'NO_FREE_ROUTE_AVAILABLE. No provider was called.';
            default:
                return (
                    'ModelFabric request was not accepted (HTTP ' +
                    status +
                    ').'
                );
        }
    };

    const request = async (sendPrompt: boolean) => {
        if (busy || !canManage || !apiKey.trim() || (sendPrompt && !canChat))
            return;
        setBusy(sendPrompt ? 'chat' : 'check');
        setMessage('');
        setOutput('');
        setServedProvider('');
        setServedModel('');
        setElapsedMs(null);
        const controller = new AbortController();
        inFlight.current = controller;
        const timeout = window.setTimeout(() => controller.abort(), 30000);
        const start = performance.now();

        try {
            // The URL is fixed and same-origin. Redirects are rejected so the
            // bearer cannot follow an untrusted Location header.
            const response = await fetch(
                API_ROOT + (sendPrompt ? '/chat/completions' : '/models'),
                {
                    method: sendPrompt ? 'POST' : 'GET',
                    redirect: 'error',
                    mode: 'same-origin',
                    credentials: 'same-origin',
                    cache: 'no-store',
                    referrerPolicy: 'no-referrer',
                    signal: controller.signal,
                    headers: {
                        Authorization: 'Bearer ' + apiKey.trim(),
                        Accept: 'application/json',
                        ...(!sendPrompt || consent
                            ? { 'X-ModelFabric-Public-Prompts': 'confirmed' }
                            : {}),
                        ...(sendPrompt
                            ? { 'Content-Type': 'application/json' }
                            : {}),
                    },
                    ...(sendPrompt
                        ? {
                              body: JSON.stringify({
                                  model: 'modelfabric-auto',
                                  stream: false,
                                  messages: [
                                      { role: 'user', content: prompt.trim() },
                                  ],
                              }),
                          }
                        : {}),
                },
            );
            if (!response.ok) {
                if (!sendPrompt) setVerifiedRoutes(null);
                setMessage(explainFailure(response.status));
                return;
            }
            const body = (await response.json()) as ApiReply;
            if (!sendPrompt) {
                const routes = body.modelfabric?.routes;
                if (
                    typeof routes !== 'number' ||
                    !Number.isSafeInteger(routes) ||
                    routes < 0
                ) {
                    setVerifiedRoutes(null);
                    setMessage('Invalid ModelFabric catalog response.');
                    return;
                }
                setVerifiedRoutes(routes);
                setMessage(
                    routes === 0
                        ? 'Token accepted. No verified-zero chat routes available.'
                        : 'Token accepted. ' +
                              routes +
                              ' verified-zero route(s) available.',
                );
                return;
            }
            const answer = body.choices?.[0]?.message?.content;
            if (typeof answer !== 'string' || answer.length === 0) {
                setMessage('ModelFabric returned an invalid completion.');
                return;
            }
            setOutput(answer.slice(0, 6000));
            setServedModel(
                typeof body.model === 'string' ? body.model.slice(0, 128) : '',
            );
            setServedProvider(
                typeof body.modelfabric?.provider === 'string'
                    ? body.modelfabric.provider.slice(0, 128)
                    : '',
            );
            setElapsedMs(Math.round(performance.now() - start));
            setMessage(
                'Verified route response received. This is not a deployment approval.',
            );
        } catch {
            setMessage(
                'The request could not be completed. Check connectivity and retry.',
            );
            if (!sendPrompt) setVerifiedRoutes(null);
        } finally {
            window.clearTimeout(timeout);
            if (inFlight.current === controller) inFlight.current = null;
            setBusy(null);
        }
    };

    return (
        <section
            className="owner-panel space-y-4"
            aria-label="ModelFabric safe playground"
            data-testid="modelfabric-safe-playground"
        >
            <div className="owner-panel-title">
                <h2>
                    <Play size={17} /> ModelFabric Playground
                </h2>
                <span className="text-muted-foreground text-xs">
                    Owner-initiated · verified-zero only
                </span>
            </div>
            <p className="text-muted-foreground text-sm leading-6">
                The FreeLLMAPI-style workflow is: connect a provider, discover
                models, approve current free pricing, create a scoped key, test
                the route, then inspect activity. This playground uses only
                KMJ&apos;s existing OpenAI-compatible API, not the upstream
                provider key. No requests run automatically.
            </p>
            {!hasActiveToken ? (
                <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs">
                    Create a ModelFabric API token in the API tokens tab first.
                    The one-time token cannot be retrieved later.
                </p>
            ) : null}
            {!routeReady ? (
                <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs">
                    NO_FREE_ROUTE_AVAILABLE: approve a current free model before
                    sending any prompt.
                </p>
            ) : null}
            <label className="block text-sm font-medium">
                ModelFabric bearer token
                <input
                    className="bg-background/45 border-border mt-1 min-h-10 w-full rounded-xl border px-3 text-sm outline-none focus-visible:ring-2"
                    type="password"
                    autoComplete="off"
                    spellCheck={false}
                    placeholder="Paste the one-time ModelFabric token"
                    value={apiKey}
                    onChange={(event) => {
                        setApiKey(event.target.value);
                        setVerifiedRoutes(null);
                        setOutput('');
                        setMessage('');
                        setConsent(false);
                    }}
                    disabled={!canManage || Boolean(busy)}
                />
                <span className="text-muted-foreground mt-1 block text-xs font-normal">
                    Only held in this tab&apos;s memory. Never copied into a
                    URL, localStorage, sessionStorage or request body.
                </span>
            </label>
            <div className="flex flex-wrap items-center gap-3">
                <button
                    type="button"
                    className="hover:bg-muted inline-flex min-h-10 items-center gap-2 rounded-xl border px-4 text-xs font-bold disabled:opacity-40"
                    disabled={!canManage || !apiKey.trim() || Boolean(busy)}
                    onClick={() => void request(false)}
                    data-testid="modelfabric-check-token"
                >
                    <ShieldCheck size={15} />
                    {busy === 'check'
                        ? 'Checking…'
                        : '1. Check token and routes'}
                </button>
                {verifiedRoutes !== null ? (
                    <span className="text-xs font-medium" role="status">
                        {verifiedRoutes > 0
                            ? verifiedRoutes + ' eligible route(s)'
                            : 'No eligible routes'}
                    </span>
                ) : null}
            </div>
            <label className="block text-sm font-medium">
                Test prompt (max {MAX_PROMPT_CHARS} characters)
                <textarea
                    className="bg-background/45 border-border mt-1 min-h-24 w-full rounded-xl border p-3 text-sm outline-none focus-visible:ring-2"
                    rows={3}
                    maxLength={MAX_PROMPT_CHARS}
                    value={prompt}
                    onChange={(event) => {
                        setPrompt(event.target.value);
                        setOutput('');
                    }}
                    disabled={!canManage || Boolean(busy)}
                />
            </label>
            <label className="flex items-start gap-2 text-xs leading-5">
                <input
                    type="checkbox"
                    className="mt-1"
                    checked={consent}
                    disabled={!canManage || Boolean(busy)}
                    onChange={(event) => setConsent(event.target.checked)}
                />
                <span>
                    I approve sending only this test prompt to a currently
                    verified-free provider. It contains no secrets, customer
                    data or private repository source. This consent does
                    <strong> not</strong> enable unattended coding,
                    private-source transfer or paid inference.
                </span>
            </label>
            <button
                type="button"
                className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-bold text-white transition hover:bg-red-500 disabled:opacity-40"
                onClick={() => void request(true)}
                disabled={!canChat}
                data-testid="modelfabric-send-test"
            >
                <Activity size={15} />
                {busy === 'chat' ? 'Testing…' : '2. Send one approved test'}
            </button>
            {message ? (
                <p role="status" className="text-xs">
                    {message}
                </p>
            ) : null}
            {output ? (
                <div
                    className="bg-muted/40 rounded-xl border p-4"
                    data-testid="modelfabric-playground-result"
                >
                    <p className="mb-2 text-xs font-bold">Response</p>
                    <p className="text-sm break-words whitespace-pre-wrap">
                        {output}
                    </p>
                    <p className="text-muted-foreground mt-3 text-xs">
                        {servedModel ? 'Model: ' + servedModel : ''}
                        {servedProvider ? ' · Provider: ' + servedProvider : ''}
                        {elapsedMs !== null
                            ? ' · Client elapsed: ' + elapsedMs + ' ms'
                            : ''}
                    </p>
                </div>
            ) : null}
            <p className="text-muted-foreground flex items-start gap-2 text-xs leading-5">
                <LockKeyhole size={15} className="mt-0.5 shrink-0" />
                No keys or prompts are persisted here. KMJ ModelFabric checks
                pricing evidence, data handling, quota and routing server-side;
                requests may be refused even after a successful token check. No
                response is proof of final provider billing or source-code
                authorization.
            </p>
        </section>
    );
}
