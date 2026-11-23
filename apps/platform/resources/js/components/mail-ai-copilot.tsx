import { useState } from 'react';
import {
    ArrowRight,
    BookOpenText,
    CheckCircle2,
    Copy,
    Languages,
    LoaderCircle,
    MessageSquareReply,
    ShieldCheck,
    Sparkles,
    WandSparkles,
} from 'lucide-react';

export type MailAiMode = 'compose' | 'explain' | 'reply';
type AiResponse = {
    mode: MailAiMode;
    subject: string | null;
    text: string;
    needs_review: true;
};

type Props = {
    base: string;
    selectedMessageId: number | null;
    onUseCompose: (subject: string, body: string) => void;
    onUseReply: (body: string) => void;
};

const actions: {
    id: MailAiMode;
    label: string;
    icon: typeof Sparkles;
}[] = [
    { id: 'compose', label: 'Write with AI', icon: WandSparkles },
    { id: 'explain', label: 'Explain in Hindi', icon: Languages },
    { id: 'reply', label: 'Smart Reply', icon: MessageSquareReply },
];

export default function MailAiCopilot({
    base,
    selectedMessageId,
    onUseCompose,
    onUseReply,
}: Props) {
    const [mode, setMode] = useState<MailAiMode>('compose');
    const [instruction, setInstruction] = useState('');
    const [tone, setTone] = useState('professional');
    const [language, setLanguage] = useState('english');
    const [consent, setConsent] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<AiResponse | null>(null);

    const selectMode = (next: MailAiMode) => {
        setMode(next);
        setResult(null);
        setError(null);
        setConsent(false);
    };

    const generate = async () => {
        if (busy || !consent || (mode === 'compose' && !instruction.trim())) {
            return;
        }
        if (mode !== 'compose' && selectedMessageId === null) {
            setError('Select one of your messages first.');
            return;
        }
        setBusy(true);
        setError(null);
        setResult(null);
        try {
            // Same-origin Laravel session + CSRF cookie. No API keys in browser.
            const xsrf = document.cookie
                .split('; ')
                .find((value) => value.startsWith('XSRF-TOKEN='))
                ?.slice('XSRF-TOKEN='.length);
            const response = await fetch(base + '/ai/generate', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    ...(xsrf
                        ? { 'X-XSRF-TOKEN': decodeURIComponent(xsrf) }
                        : {}),
                },
                body: JSON.stringify({
                    mode,
                    instruction,
                    tone,
                    language,
                    ...(mode !== 'compose'
                        ? { message_id: selectedMessageId }
                        : {}),
                    consent_to_ai_processing: consent,
                }),
            });
            const data: unknown = await response.json();
            if (!response.ok) {
                const code =
                    typeof data === 'object' &&
                    data !== null &&
                    'error' in data &&
                    typeof data.error === 'string'
                        ? data.error
                        : 'AI_REQUEST_FAILED';
                setError(
                    code === 'NO_PRIVATE_AI_ROUTE_AVAILABLE'
                        ? 'No verified private free AI model is connected. Configure one in ModelFabric with no-training evidence.'
                        : code === 'AI_REQUEST_FAILED'
                          ? 'AI is unavailable. Please check your connection or sign-in.'
                          : code.replaceAll('_', ' '),
                );
                return;
            }
            if (
                typeof data !== 'object' ||
                data === null ||
                !('text' in data) ||
                typeof data.text !== 'string' ||
                !('mode' in data) ||
                data.mode !== mode
            ) {
                setError('AI returned an unexpected response. No draft was used.');
                return;
            }
            const parsed = data as AiResponse;
            setResult(parsed);
        } catch {
            setError('AI request failed. No email was sent or saved.');
        } finally {
            setBusy(false);
        }
    };

    return (
        <aside
            aria-label="KMJ Mail AI Copilot"
            className="min-w-0 rounded-2xl border border-fuchsia-400/25 bg-gradient-to-b from-[#171729] via-[#101626] to-[#111927] p-4 text-slate-100 shadow-[0_20px_40px_-28px_rgba(193,56,157,0.55)]"
        >
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <div className="rounded-xl border border-fuchsia-400/25 bg-fuchsia-500/10 p-2">
                        <Sparkles className="size-5 text-fuchsia-300" />
                    </div>
                    <div>
                        <h2 className="text-sm font-extrabold">KMJ AI Copilot</h2>
                        <p className="text-[11px] text-slate-400">
                            Hinglish → professional mail
                        </p>
                    </div>
                </div>
                <span className="rounded-full border border-fuchsia-500/30 px-2 py-1 text-[10px] font-bold text-fuchsia-200">
                    Review-first
                </span>
            </div>

            <div className="mt-5 grid grid-cols-3 gap-1.5">
                {actions.map((action) => {
                    const Icon = action.icon;
                    return (
                        <button
                            key={action.id}
                            type="button"
                            aria-pressed={mode === action.id}
                            onClick={() => selectMode(action.id)}
                            className={
                                'flex min-h-16 flex-col items-center justify-center gap-1.5 rounded-xl border p-1 text-center text-[11px] font-semibold transition ' +
                                (mode === action.id
                                    ? 'border-fuchsia-400/60 bg-fuchsia-500/20 text-white'
                                    : 'border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/[0.08]')
                            }
                        >
                            <Icon className="size-4" />
                            {action.id === 'compose'
                                ? 'Compose'
                                : action.id === 'explain'
                                  ? 'Hindi'
                                  : 'Reply'}
                        </button>
                    );
                })}
            </div>

            <div className="mt-5 space-y-3">
                <div className="flex items-center justify-between gap-2">
                    <label
                        htmlFor="kmj-mail-ai-instruction"
                        className="text-xs font-bold text-slate-200"
                    >
                        {mode === 'compose'
                            ? 'AI ko Hinglish mein samjhaiye'
                            : mode === 'explain'
                              ? 'Hindi explanation'
                              : 'Reply kaise dena hai?'}
                    </label>
                    {mode === 'explain' && (
                        <BookOpenText className="size-4 text-fuchsia-300" />
                    )}
                </div>
                <textarea
                    id="kmj-mail-ai-instruction"
                    rows={4}
                    maxLength={2000}
                    value={instruction}
                    onChange={(event) => setInstruction(event.target.value)}
                    placeholder={
                        mode === 'compose'
                            ? 'Client ko politely batao project ready hai aur payment approval chahiye...'
                            : mode === 'explain'
                              ? 'Is email mein kya kaha hai, deadline aur action Hindi mein batao.'
                              : 'Thank you bolo, kal update denge, tone professional rakho...'
                    }
                    className="w-full resize-y rounded-xl border border-fuchsia-500/25 bg-[#0a1020] p-3 text-sm leading-6 text-white placeholder:text-slate-500 focus:border-fuchsia-400 focus:outline-none"
                />
                {mode !== 'explain' && (
                    <div className="grid grid-cols-2 gap-2">
                        <label className="text-[11px] font-semibold text-slate-300">
                            Tone
                            <select
                                value={tone}
                                onChange={(event) => setTone(event.target.value)}
                                className="mt-1 w-full rounded-lg border border-white/15 bg-[#111827] p-2 text-xs"
                            >
                                <option value="professional">Professional</option>
                                <option value="formal">Formal</option>
                                <option value="friendly">Friendly</option>
                                <option value="firm">Firm</option>
                            </select>
                        </label>
                        <label className="text-[11px] font-semibold text-slate-300">
                            Output
                            <select
                                value={language}
                                onChange={(event) =>
                                    setLanguage(event.target.value)
                                }
                                className="mt-1 w-full rounded-lg border border-white/15 bg-[#111827] p-2 text-xs"
                            >
                                <option value="english">English</option>
                                <option value="hindi">Hindi</option>
                                <option value="hinglish">Hinglish</option>
                            </select>
                        </label>
                    </div>
                )}
                {mode !== 'compose' && selectedMessageId === null && (
                    <p role="status" className="text-xs text-amber-300">
                        Select a private message in the reading pane first.
                    </p>
                )}
                <label className="flex items-start gap-2 rounded-xl border border-fuchsia-500/15 bg-white/[0.03] p-3 text-[11px] leading-5 text-slate-300">
                    <input
                        type="checkbox"
                        checked={consent}
                        onChange={(event) => setConsent(event.target.checked)}
                        className="mt-1 size-4 shrink-0 accent-fuchsia-500"
                    />
                    I consent to sending my instructions
                    {mode !== 'compose' ? ' and selected email content' : ''}{' '}
                    to a verified private AI provider for this request.
                </label>
                <button
                    type="button"
                    onClick={generate}
                    disabled={
                        busy ||
                        !consent ||
                        (mode === 'compose' && !instruction.trim()) ||
                        (mode !== 'compose' && selectedMessageId === null)
                    }
                    className="flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-fuchsia-600 to-rose-600 px-4 text-sm font-bold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {busy ? (
                        <LoaderCircle className="size-4 animate-spin" />
                    ) : (
                        <Sparkles className="size-4" />
                    )}
                    {busy
                        ? 'AI is preparing...'
                        : mode === 'compose'
                          ? 'Generate email draft'
                          : mode === 'explain'
                            ? 'Explain in Hindi'
                            : 'Suggest a reply'}
                </button>
                {error && (
                    <p role="alert" className="rounded-lg border border-amber-500/25 bg-amber-500/10 p-3 text-xs text-amber-200">
                        {error}
                    </p>
                )}
            </div>

            {result && (
                <div aria-live="polite" className="mt-5 rounded-xl border border-fuchsia-400/35 bg-fuchsia-500/[0.07] p-3">
                    <p className="flex items-center gap-2 text-xs font-bold text-fuchsia-200">
                        <CheckCircle2 className="size-4" />
                        {mode === 'explain'
                            ? 'Hindi explanation'
                            : 'Editable AI suggestion'}
                    </p>
                    {result.subject && (
                        <h3 className="mt-3 text-sm font-semibold">
                            {result.subject}
                        </h3>
                    )}
                    <p className="mt-3 max-h-72 overflow-y-auto text-[13px] leading-6 whitespace-pre-wrap text-slate-100">
                        {result.text}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                        {mode === 'compose' && (
                            <button
                                type="button"
                                onClick={() =>
                                    onUseCompose(result.subject ?? '', result.text)
                                }
                                className="flex min-h-9 items-center gap-1.5 rounded-lg bg-fuchsia-600 px-3 text-xs font-bold"
                            >
                                Use in Compose
                                <ArrowRight className="size-3.5" />
                            </button>
                        )}
                        {mode === 'reply' && (
                            <button
                                type="button"
                                onClick={() => onUseReply(result.text)}
                                className="flex min-h-9 items-center gap-1.5 rounded-lg bg-fuchsia-600 px-3 text-xs font-bold"
                            >
                                Use in Reply
                                <ArrowRight className="size-3.5" />
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={() => void navigator.clipboard.writeText(result.text)}
                            className="flex min-h-9 items-center gap-1.5 rounded-lg border border-white/20 px-3 text-xs"
                        >
                            <Copy className="size-3.5" />
                            Copy
                        </button>
                    </div>
                    <p className="mt-3 flex gap-2 text-[11px] leading-5 text-slate-400">
                        <ShieldCheck className="size-4 shrink-0" />
                        AI can make mistakes. Check facts, recipients and tone.
                        AI cannot send your email.
                    </p>
                </div>
            )}
            <p className="mt-5 text-[11px] leading-5 text-slate-400">
                ModelFabric only: verified free routes with documented no-training
                handling. No fallback to unknown or paid providers.
            </p>
        </aside>
    );
}
