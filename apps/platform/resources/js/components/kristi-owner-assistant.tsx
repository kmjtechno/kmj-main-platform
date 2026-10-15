import { Link } from '@inertiajs/react';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Bot, Mic, MicOff, Send, ShieldCheck, Volume2, VolumeX, X } from 'lucide-react';

type SpeechResult = { results: ArrayLike<ArrayLike<{ transcript: string }>> };
type BrowserRecognition = {
    lang: string;
    continuous: boolean;
    interimResults: boolean;
    onresult: ((event: SpeechResult) => void) | null;
    onerror: (() => void) | null;
    onend: (() => void) | null;
    start(): void;
    stop(): void;
};
type SpeechWindow = Window & {
    SpeechRecognition?: new () => BrowserRecognition;
    webkitSpeechRecognition?: new () => BrowserRecognition;
};
type ChatMessage = { kind: 'kristi' | 'owner'; text: string };

const shortcuts = [
    { label: 'Review orders', href: '/operator#commercial-orders' },
    { label: 'Manage products', href: '/operator/products' },
    { label: 'Licensing center', href: '/operator/kslp' },
    { label: 'Operations', href: '/operator/ops' },
];

function guidance(
    query: string,
    counts: { orders: number; products: number; customers: number },
    language: 'en-IN' | 'hi-IN',
): string {
    const value = query.toLocaleLowerCase();
    const hindi = language === 'hi-IN' || /[\u0900-\u097f]/.test(value);
    if (/payment|order|revenue|भुगतान|ऑर्डर|आर्डर|पेमेंट/.test(value)) {
        return hindi
            ? `अभी के ऑपरेटर रिकॉर्ड में ${counts.orders} ऑर्डर हैं। भुगतान की पुष्टि और लाइसेंस प्रक्रिया के लिए Commercial Orders खोलें। यह बैंक सेटलमेंट रिपोर्ट नहीं है।`
            : `The operator snapshot has ${counts.orders} orders. Review payment evidence and fulfillment in Commercial Orders. This is not a provider settlement report.`;
    }
    if (/catalog|product|उत्पाद|प्रोडक्ट|कैटलॉग/.test(value)) {
        return hindi
            ? `कैटलॉग में ${counts.products} प्रोडक्ट रिकॉर्ड हैं। प्रकाशन और लाइसेंसिंग स्थिति जाँचने के लिए Product Management खोलें।`
            : `The owner catalog has ${counts.products} product records. Open Product Management to review publication and licensing policies.`;
    }
    if (/customer|people|user|ग्राहक|कस्टमर|यूजर/.test(value)) {
        return hindi
            ? `प्लेटफ़ॉर्म रिकॉर्ड में ${counts.customers} उपयोगकर्ता हैं। अधिकृत खोज के लिए Customers & Organizations खोलें।`
            : `The platform snapshot reports ${counts.customers} users. Open Customers & Organizations for an authorized directory search.`;
    }
    if (/license|entitlement|लाइसेंस|अधिकार/.test(value)) {
        return hindi
            ? 'लाइसेंस और एंटाइटलमेंट की स्थिति Licensing Center में देखें। जारी करने या रद्द करने से पहले अलग स्पष्ट अनुमति जरूरी है।'
            : 'Open Licensing Center for entitlements and audit history. Issuing or revoking rights needs a separate authorized confirmation.';
    }
    if (/server|health|backup|status|सर्वर|बैकअप|स्टेटस/.test(value)) {
        return hindi
            ? 'सर्वर और बैकअप की वास्तविक जानकारी Operations & Audit में देखें। इस डैशबोर्ड से मैं सर्वर को बिना प्रमाण Healthy नहीं बता सकती।'
            : 'Open Operations & Audit for actual server and backup evidence. This dashboard cannot independently prove live health.';
    }
    return hindi
        ? 'मैं Products, Customers, Orders, Licensing और Operations खोलने में मदद कर सकती हूँ। वास्तविक जनरेटिव AI अभी कनेक्ट नहीं है; यह सुरक्षित guided mode है।'
        : 'I can guide you to Products, Customers, Orders, Licensing or Operations. Generative AI is not connected; this is a local guided assistant.';
}

export default function KristiOwnerAssistant({
    counts,
}: {
    counts: { orders: number; products: number; customers: number };
}) {
    const [messages, setMessages] = useState<ChatMessage[]>([
        {
            kind: 'kristi',
            text: 'Hello! I am Kristi. I can guide you through KMJ products, customers, orders and platform operations. Text guidance is available now; live AI reasoning is not connected.',
        },
    ]);
    const [draft, setDraft] = useState('');
    const [listening, setListening] = useState(false);
    const [voiceLanguage, setVoiceLanguage] = useState<'en-IN' | 'hi-IN'>('en-IN');
    const [voiceAvailable, setVoiceAvailable] = useState(false);
    const [voiceNotice, setVoiceNotice] = useState('');
    const [expanded, setExpanded] = useState(true);
    const recognition = useRef<BrowserRecognition | null>(null);
    const chatEnd = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        const browser = window as SpeechWindow;
        setVoiceAvailable(Boolean(browser.SpeechRecognition || browser.webkitSpeechRecognition));
        return () => {
            recognition.current?.stop();
            window.speechSynthesis?.cancel();
        };
    }, []);

    useEffect(() => {
        if (expanded) chatEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, [messages, expanded]);

    function send(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const clean = draft.trim().slice(0, 400);
        if (!clean) return;
        const additions: ChatMessage[] = [
            { kind: 'owner', text: clean },
            { kind: 'kristi', text: guidance(clean, counts, voiceLanguage) },
        ];
        setMessages((previous) => [...previous, ...additions].slice(-18));
        setDraft('');
    }

    function toggleMicrophone() {
        if (listening) {
            recognition.current?.stop();
            return;
        }
        const browser = window as SpeechWindow;
        const Recognition = browser.SpeechRecognition || browser.webkitSpeechRecognition;
        if (!Recognition) {
            setVoiceNotice('Speech input is not available in this browser. Text chat remains available.');
            return;
        }
        const session = new Recognition();
        recognition.current = session;
        session.lang = voiceLanguage;
        session.continuous = false;
        session.interimResults = false;
        session.onresult = (event) => {
            const transcript = event.results[0]?.[0]?.transcript ?? '';
            setDraft(transcript.slice(0, 400));
            setVoiceNotice('Transcript ready. Review the text and select Send.');
        };
        session.onerror = () => {
            setListening(false);
            setVoiceNotice('Voice input was declined or interrupted; no action was taken.');
        };
        session.onend = () => setListening(false);
        try {
            session.start();
            setVoiceNotice('Browser dictation may use your browser provider. Audio is not sent to KMJ AI by this preview.');
            setListening(true);
        } catch {
            setListening(false);
            setVoiceNotice('Microphone could not start. Use text chat.');
        }
    }

    function speakLast() {
        if (!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) {
            setVoiceNotice('Audio playback is not supported in this browser.');
            return;
        }
        window.speechSynthesis.cancel();
        const last = [...messages].reverse().find((message) => message.kind === 'kristi');
        if (!last) return;
        const utterance = new SpeechSynthesisUtterance(last.text);
        utterance.lang = voiceLanguage;
        utterance.rate = 0.97;
        window.speechSynthesis.speak(utterance);
    }

    return (
        <aside className="kmj-os-kristi" aria-label="Kristi text and voice assistant">
            <header className="kmj-os-kristi-head">
                <div className="flex items-center gap-3">
                    <span className="grid size-10 place-items-center rounded-xl border border-fuchsia-500/35 bg-fuchsia-500/10 text-fuchsia-300">
                        <Bot className="size-5" aria-hidden="true" />
                    </span>
                    <div>
                        <h2 className="text-xl font-extrabold tracking-tight">Kristi</h2>
                        <p className="text-xs text-slate-400">KMJ Intelligent Copilot</p>
                    </div>
                </div>
                <span className="rounded-full border border-amber-500/35 bg-amber-500/10 px-2.5 py-1 text-[11px] font-semibold text-amber-200">Guided mode</span>
            </header>
            <div className="kmj-os-kristi-art" aria-hidden="true">
                <img src="/assets/admin/kristi-neon.svg" alt="" className="h-full w-full object-cover" />
                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#0c0c18] to-transparent px-4 pb-4 pt-10">
                    <p className="font-bold">Text + Voice</p>
                    <p className="mt-1 text-xs text-slate-300">Hindi & English guided navigation</p>
                </div>
            </div>
            <div className="kmj-os-kristi-chat">
                <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-bold tracking-wider text-slate-300 uppercase">Conversation</p>
                    <button type="button" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded} className="rounded-lg border border-white/10 px-2.5 py-1.5 text-xs hover:bg-white/10">
                        {expanded ? 'Collapse' : 'Expand'}
                    </button>
                </div>
                {expanded && (
                    <div className="kmj-os-chat-history mt-3" role="log" aria-live="polite" aria-relevant="additions text">
                        {messages.map((message, index) => (
                            <p key={index} className={message.kind === 'kristi' ? 'kmj-os-chat-bubble assistant' : 'kmj-os-chat-bubble owner'}>
                                {message.text}
                            </p>
                        ))}
                        <div ref={chatEnd} />
                    </div>
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                    {shortcuts.map((shortcut) => (
                        <Link key={shortcut.href} href={shortcut.href} className="rounded-lg border border-white/15 bg-white/[0.035] px-2.5 py-2 text-xs font-medium hover:border-red-400/40 hover:bg-white/10">
                            {shortcut.label}
                        </Link>
                    ))}
                </div>
            </div>
            <div className="kmj-os-voice">
                <button type="button" onClick={toggleMicrophone} disabled={!voiceAvailable} aria-label={listening ? 'Stop voice dictation' : 'Start voice dictation'} aria-pressed={listening} className="kmj-os-mic" title="Tap to dictate; browser microphone permission required">
                    {listening ? <MicOff className="size-6" aria-hidden="true" /> : <Mic className="size-6" aria-hidden="true" />}
                </button>
                <div className="min-w-0 flex-1">
                    <p className="text-sm font-bold">{listening ? 'Listening…' : 'Voice chat'}</p>
                    <p className="text-xs text-slate-400">{voiceAvailable ? 'Tap to dictate, then review & send' : 'Text chat available; microphone unsupported'}</p>
                </div>
                <button
                    type="button"
                    disabled={listening}
                    onClick={() => setVoiceLanguage((current) => current === 'en-IN' ? 'hi-IN' : 'en-IN')}
                    className="rounded-lg border border-white/15 px-2 py-2 text-xs hover:bg-white/10 disabled:opacity-40"
                    aria-label="Change voice language between Hindi and English"
                    title="Voice language"
                >
                    {voiceLanguage === 'en-IN' ? 'EN' : 'हिंदी'}
                </button>
                <button type="button" onClick={speakLast} className="rounded-xl border border-white/15 p-2.5 hover:bg-white/10" aria-label="Read Kristi's last message aloud" title="Speak last assistant message">
                    <Volume2 className="size-4" aria-hidden="true" />
                </button>
                <button type="button" onClick={() => { window.speechSynthesis?.cancel(); setVoiceNotice('Audio playback stopped.'); }} className="rounded-xl border border-white/15 p-2.5 hover:bg-white/10" aria-label="Stop speaking">
                    <VolumeX className="size-4" aria-hidden="true" />
                </button>
            </div>
            {voiceNotice && (
                <p className="mx-4 mb-2 flex items-start gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs leading-5 text-slate-300" role="status">
                    <span className="flex-1">{voiceNotice}</span>
                    <button type="button" aria-label="Dismiss notice" onClick={() => setVoiceNotice('')}><X className="size-3.5" aria-hidden="true" /></button>
                </p>
            )}
            <form className="kmj-os-kristi-form" onSubmit={send}>
                <label className="sr-only" htmlFor="kmj-kristi-ask">Ask Kristi</label>
                <input
                    id="kmj-kristi-ask"
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    maxLength={400}
                    placeholder="Ask Kristi anything about KMJ…"
                    className="min-w-0 flex-1 bg-transparent px-2 py-3 text-sm text-white placeholder:text-slate-500 focus:outline-none"
                />
                <button type="submit" aria-label="Send message to Kristi" disabled={!draft.trim()} className="grid size-10 shrink-0 place-items-center rounded-xl bg-red-600 text-white hover:bg-red-500 disabled:opacity-40">
                    <Send className="size-4" aria-hidden="true" />
                </button>
            </form>
            <p className="px-5 pb-4 pt-2 text-[11px] leading-4 text-slate-400">
                <ShieldCheck className="mr-1 inline size-3" aria-hidden="true" />
                Read-only guidance. No autonomous payments, licenses or production changes.
            </p>
        </aside>
    );
}
