import { Head } from '@inertiajs/react';
import {
    Archive,
    ArrowLeft,
    Clock3,
    FileEdit,
    Inbox,
    Mail,
    Menu,
    MoreHorizontal,
    Search,
    Send,
    ShieldCheck,
    Sparkles,
    Star,
    Trash2,
    WifiOff,
} from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

type Folder = 'inbox' | 'starred' | 'sent' | 'drafts' | 'archive' | 'spam' | 'trash';

export type MailMessage = {
    id: string;
    folder: Folder;
    sender_name: string;
    sender_email: string;
    subject: string;
    preview: string;
    body_text: string;
    received_at: string;
    read: boolean;
    starred: boolean;
};

export type MailWorkspaceProps = {
    account?: { address: string; display_name: string } | null;
    transportStatus?: 'not_configured' | 'connecting' | 'ready' | 'degraded';
    messages?: MailMessage[];
};

const folders: { key: Folder; title: string; icon: typeof Inbox }[] = [
    { key: 'inbox', title: 'Inbox', icon: Inbox },
    { key: 'starred', title: 'Starred', icon: Star },
    { key: 'sent', title: 'Sent', icon: Send },
    { key: 'drafts', title: 'Drafts', icon: FileEdit },
    { key: 'archive', title: 'Archive', icon: Archive },
    { key: 'spam', title: 'Spam', icon: ShieldCheck },
    { key: 'trash', title: 'Trash', icon: Trash2 },
];

function senderInitials(value: string): string {
    return value.trim().split(/\s+/).slice(0, 2).map((piece) => piece.charAt(0)).join('').toUpperCase() || '?';
}

function safeDate(value: string): string {
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? 'Unknown date'
        : new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date);
}

export default function KmjMailWorkspace({
    account = null,
    transportStatus = 'not_configured',
    messages = [],
}: MailWorkspaceProps) {
    const [folder, setFolder] = useState<Folder>('inbox');
    const [query, setQuery] = useState('');
    const [filter, setFilter] = useState<'all' | 'unread'>('all');
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [compose, setCompose] = useState(false);
    const [mobileNav, setMobileNav] = useState(false);
    const [recipient, setRecipient] = useState('');
    const [subject, setSubject] = useState('');
    const [body, setBody] = useState('');
    const searchRef = useRef<HTMLInputElement>(null);
    const ready = transportStatus === 'ready' && account !== null;

    const setComposeOpen = useCallback((open: boolean) => {
        setCompose(open);
        if (!open) {
            // Do not retain sensitive draft text when preview is dismissed.
            setRecipient('');
            setSubject('');
            setBody('');
        }
    }, []);

    // Keyboard shortcuts never intercept typing in editable fields.
    useEffect(() => {
        const onKeyDown = (event: KeyboardEvent) => {
            const target = event.target;
            const editing = target instanceof HTMLElement
                && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));
            if (event.key === 'Escape') {
                if (compose) setComposeOpen(false);
                else if (selectedId) setSelectedId(null);
                else setMobileNav(false);
                return;
            }
            if (editing || event.metaKey || event.ctrlKey || event.altKey) return;
            if (event.key === '/') {
                event.preventDefault();
                searchRef.current?.focus();
            }
            if (event.key.toLowerCase() === 'c') {
                event.preventDefault();
                setCompose(true);
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [compose, selectedId, setComposeOpen]);

    const scoped = ready ? messages : [];
    const visible = useMemo(() => {
        const needle = query.trim().toLocaleLowerCase();
        return scoped.filter((message) => (
            (folder === 'starred' ? message.starred : message.folder === folder)
            && (filter === 'all' || !message.read)
            && (!needle || [message.subject, message.sender_name, message.sender_email, message.preview]
                .some((value) => value.toLocaleLowerCase().includes(needle)))
        ));
    }, [scoped, folder, query, filter]);
    const selected = visible.find((message) => message.id === selectedId) ?? null;
    const unread = scoped.filter((message) => message.folder === 'inbox' && !message.read).length;

    const navigate = (next: Folder) => {
        setFolder(next);
        setSelectedId(null);
        setMobileNav(false);
    };

    return (
        <>
            <Head title="KMJ Mail" />
            <main className="flex h-full min-h-[650px] flex-1 flex-col overflow-hidden rounded-2xl border border-border bg-background text-foreground">
                <header className="flex min-h-[76px] items-center justify-between gap-3 border-b border-border bg-card px-4 sm:px-6">
                    <div className="flex min-w-0 items-center gap-3">
                        <button type="button" aria-label="Open folders" onClick={() => setMobileNav(!mobileNav)}
                            className="rounded-xl p-2 hover:bg-muted lg:hidden">
                            <Menu className="size-5" />
                        </button>
                        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-red-600 text-lg font-black tracking-tight text-white">K</span>
                        <div className="min-w-0">
                            <h1 className="text-lg font-black tracking-tight">KMJ <span className="text-red-500">Mail</span></h1>
                            <p className="text-muted-foreground truncate text-[11px]">{account?.address || 'Secure communications workspace'}</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 ${ready ? 'border-emerald-500/30 text-emerald-600' : 'border-amber-500/30 text-amber-600'}`}>
                            {ready ? <ShieldCheck className="size-3.5" /> : <WifiOff className="size-3.5" />}
                            {ready ? 'Transport reported ready' : 'Mail transport not connected'}
                        </span>
                    </div>
                </header>

                {!ready && (
                    <div role="status" className="flex items-start gap-3 border-b border-amber-500/15 bg-amber-500/5 px-4 py-3 text-sm sm:px-6">
                        <WifiOff className="mt-0.5 size-4 shrink-0 text-amber-600" />
                        <p><strong>Preview mode.</strong> No mailbox is connected. Messages, delivery and account access are not simulated. Sending is disabled until secure KMJ Mail backend acceptance is complete.</p>
                    </div>
                )}

                <div className="flex min-h-0 flex-1">
                    <aside className={`${mobileNav ? 'flex' : 'hidden'} w-56 shrink-0 flex-col border-r border-border bg-muted/20 p-3 lg:flex lg:w-60`}>
                        <button type="button" onClick={() => setCompose(true)}
                            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-bold text-white shadow-sm transition hover:bg-red-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600">
                            <FileEdit className="size-4" /> Compose
                        </button>
                        <nav aria-label="Mail folders" className="mt-6 space-y-1">
                            {folders.map(({ key, title, icon: Icon }) => (
                                <button key={key} type="button" aria-current={folder === key ? 'page' : undefined}
                                    onClick={() => navigate(key)}
                                    className={`flex min-h-10 w-full items-center justify-between rounded-xl px-3 text-left text-sm transition focus-visible:outline-2 focus-visible:outline-red-600 ${folder === key ? 'bg-red-500/10 font-bold text-red-600' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`}>
                                    <span className="flex items-center gap-3"><Icon className="size-4" />{title}</span>
                                    {key === 'inbox' && unread > 0 && <span className="rounded-md bg-red-600 px-2 py-0.5 text-xs text-white">{unread}</span>}
                                </button>
                            ))}
                        </nav>
                        <div className="mt-auto rounded-2xl border border-border bg-card p-4">
                            <div className="flex items-center gap-2 text-xs font-bold"><Sparkles className="size-4 text-red-500" /> Private AI</div>
                            <p className="text-muted-foreground mt-2 text-xs leading-5">Optional AI tools will require explicit consent. No email content is sent to an AI service by this UI.</p>
                        </div>
                    </aside>

                    <section className="flex min-w-0 flex-1 flex-col" aria-label="Mail list and reading pane">
                        <div className="flex flex-col gap-4 border-b border-border px-4 py-4 sm:px-6">
                            <div className="flex items-center justify-between gap-2">
                                <div>
                                    <p className="text-muted-foreground text-[11px] font-bold tracking-widest uppercase">Your workspace</p>
                                    <h2 className="mt-1 text-2xl font-black tracking-tight">{folders.find((item) => item.key === folder)?.title}</h2>
                                </div>
                                <span className="text-muted-foreground text-xs">{visible.length} messages</span>
                            </div>
                            <div className="flex flex-wrap items-center gap-3">
                                <label className="relative min-w-[180px] flex-1">
                                    <Search className="text-muted-foreground absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
                                    <span className="sr-only">Search mail</span>
                                    <input ref={searchRef} value={query} onChange={(e) => setQuery(e.target.value)}
                                        placeholder="Search messages  /" type="search" aria-label="Search mail"
                                        className="h-11 w-full rounded-xl border border-border bg-card pr-3 pl-10 text-sm outline-none focus-visible:ring-2 focus-visible:ring-red-500" />
                                </label>
                                <div role="group" aria-label="Message filter" className="flex rounded-xl border border-border bg-card p-1 text-xs">
                                    {(['all', 'unread'] as const).map((key) => (
                                        <button key={key} type="button" aria-pressed={filter === key}
                                            onClick={() => setFilter(key)} className={`rounded-lg px-3 py-2 font-semibold capitalize ${filter === key ? 'bg-muted text-foreground' : 'text-muted-foreground'}`}>{key}</button>
                                    ))}
                                </div>
                            </div>
                        </div>

                        <div className="grid min-h-[390px] flex-1 lg:grid-cols-[minmax(250px,0.9fr)_minmax(320px,1.25fr)]">
                            <div className={`${selected ? 'hidden lg:block' : 'block'} min-w-0 border-r border-border`}>
                                {visible.length ? (
                                    <ul aria-label="Messages" className="divide-y divide-border">
                                        {visible.map((item) => (
                                            <li key={item.id}>
                                                <button type="button" onClick={() => setSelectedId(item.id)}
                                                    aria-pressed={selectedId === item.id}
                                                    className={`flex w-full gap-3 px-4 py-4 text-left transition hover:bg-muted/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-red-600 ${selectedId === item.id ? 'bg-red-500/5' : ''}`}>
                                                    <span className="grid size-10 shrink-0 place-items-center rounded-full bg-muted text-xs font-bold">{senderInitials(item.sender_name)}</span>
                                                    <span className="min-w-0 flex-1">
                                                        <span className="flex justify-between gap-2">
                                                            <span className={`truncate text-sm ${!item.read ? 'font-bold' : 'font-medium'}`}>{item.sender_name}</span>
                                                            <span className="text-muted-foreground shrink-0 text-xs">{safeDate(item.received_at)}</span>
                                                        </span>
                                                        <span className="mt-1 flex items-center gap-2 truncate text-sm font-semibold">{item.starred && <Star aria-label="Starred" className="size-3.5 fill-amber-400 text-amber-400" />}{item.subject || '(no subject)'}</span>
                                                        <span className="text-muted-foreground mt-1 block truncate text-xs">{item.preview}</span>
                                                    </span>
                                                </button>
                                            </li>
                                        ))}
                                    </ul>
                                ) : (
                                    <div className="flex h-full min-h-72 flex-col items-center justify-center px-5 py-12 text-center">
                                        <span className="grid size-16 place-items-center rounded-2xl border bg-muted/40"><Inbox className="text-muted-foreground size-7" /></span>
                                        <h3 className="mt-4 font-bold">{ready ? 'Nothing in this view' : 'Your inbox is not connected yet'}</h3>
                                        <p className="text-muted-foreground mt-2 max-w-xs text-sm leading-6">{ready ? 'Try another folder or clear search filters.' : 'When KMJ Mail is provisioned, your authorized messages will appear here. No demo messages are shown as real mail.'}</p>
                                    </div>
                                )}
                            </div>

                            <div className={`${selected ? 'block' : 'hidden lg:flex'} min-w-0 flex-col`}>
                                {selected ? (
                                    <article className="p-5 sm:p-7">
                                        <button type="button" onClick={() => setSelectedId(null)} className="mb-5 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground lg:hidden"><ArrowLeft className="size-4" /> Back</button>
                                        <div className="flex items-start justify-between gap-3">
                                            <h3 className="text-2xl font-black tracking-tight">{selected.subject || '(no subject)'}</h3>
                                            <span className="rounded-lg border p-2 text-muted-foreground" aria-label="Read-only message"><MoreHorizontal className="size-4" /></span>
                                        </div>
                                        <div className="mt-6 flex items-center gap-3 border-b border-border pb-6">
                                            <span className="grid size-11 place-items-center rounded-full bg-muted text-sm font-bold">{senderInitials(selected.sender_name)}</span>
                                            <div className="min-w-0">
                                                <p className="text-sm font-bold">{selected.sender_name}</p>
                                                <p className="text-muted-foreground truncate text-xs">{selected.sender_email}</p>
                                            </div>
                                            <span className="text-muted-foreground ml-auto flex shrink-0 items-center gap-1 text-xs"><Clock3 className="size-3.5" /> {safeDate(selected.received_at)}</span>
                                        </div>
                                        <div className="mt-6 whitespace-pre-wrap break-words text-sm leading-7">{selected.body_text}</div>
                                        <div className="text-muted-foreground mt-10 rounded-xl border border-dashed p-4 text-xs">Read-only viewer: remote images, HTML scripts, tracking pixels, replies and mutations are disabled until the secure KMJ Mail backend is connected.</div>
                                    </article>
                                ) : (
                                    <div className="text-muted-foreground flex h-full min-h-72 flex-col items-center justify-center px-6 text-center">
                                        <Mail className="size-9 opacity-35" /><p className="mt-3 text-sm font-medium">Select a message to read</p>
                                        <p className="mt-2 text-xs">Plain text only · No remote content</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </section>
                </div>

                <Dialog open={compose} onOpenChange={setComposeOpen}>
                    <DialogContent className="w-full gap-0 overflow-hidden rounded-2xl p-0 sm:max-w-xl">
                        <DialogHeader className="border-b border-border px-5 py-5 text-left">
                            <DialogTitle>New message</DialogTitle>
                            <DialogDescription>Local preview only · Not saved or sent</DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 p-5">
                            <label className="block text-xs font-bold">To
                                <input type="email" value={recipient} onChange={(e) => setRecipient(e.target.value)} placeholder="name@example.com" className="mt-2 w-full rounded-lg border border-border bg-background p-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-red-500" />
                            </label>
                            <label className="block text-xs font-bold">Subject
                                <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject" className="mt-2 w-full rounded-lg border border-border bg-background p-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-red-500" />
                            </label>
                            <label className="block text-xs font-bold">Message
                                <textarea rows={8} value={body} onChange={(e) => setBody(e.target.value)} placeholder="Write your message..." className="mt-2 w-full resize-y rounded-lg border border-border bg-background p-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-red-500" />
                            </label>
                            <p className="text-muted-foreground text-xs">Draft contents are discarded on close. No remote storage or transmission is performed.</p>
                            <button type="button" disabled aria-disabled="true" title="Mail backend not connected"
                                className="flex min-h-11 items-center gap-2 rounded-xl bg-red-600 px-5 text-sm font-bold text-white opacity-50"><Send className="size-4" /> Send unavailable</button>
                        </div>
                    </DialogContent>
                </Dialog>
            </main>
        </>
    );
}
