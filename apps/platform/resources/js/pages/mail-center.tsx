import AppLayout from '@/layouts/app-layout';
import { Head, Link, router, usePage } from '@inertiajs/react';
import { useMemo, useState } from 'react';
import {
    ArrowLeft,
    CheckCircle2,
    ChevronRight,
    FileText,
    Inbox,
    LockKeyhole,
    Mail,
    Search,
    Send,
    ShieldCheck,
    Users,
} from 'lucide-react';

type Template = {
    kind: string;
    category: string;
    subject: string;
    heading: string;
    intro: string;
    notice: string;
};

type MailCenterProps = {
    audience: 'owner' | 'team';
    templates: Template[];
    mailboxConnection: 'not_connected';
    transportCanAttempt: boolean;
    testEnabled: boolean;
};

type Folder = 'templates' | 'inbox' | 'sent' | 'drafts';

const folders: { id: Folder; label: string; icon: typeof Mail }[] = [
    { id: 'templates', label: 'Templates', icon: FileText },
    { id: 'inbox', label: 'Inbox', icon: Inbox },
    { id: 'sent', label: 'Sent', icon: Send },
    { id: 'drafts', label: 'Drafts', icon: Mail },
];

export default function MailCenter({
    audience,
    templates,
    mailboxConnection,
    transportCanAttempt,
    testEnabled,
}: MailCenterProps) {
    const { flash } = usePage().props;
    const [folder, setFolder] = useState<Folder>('templates');
    const [selected, setSelected] = useState(templates[0]?.kind ?? '');
    const [search, setSearch] = useState('');
    const [sending, setSending] = useState(false);
    const isOwner = audience === 'owner';
    const back = isOwner ? '/operator' : '/dashboard';
    const endpoint = isOwner ? '/operator/mail/preview' : '/team/mail/preview';
    const activeTemplate = templates.find((item) => item.kind === selected);
    const filtered = useMemo(() => {
        const needle = search.trim().toLowerCase();
        if (!needle) return templates;
        return templates.filter((item) =>
            [item.subject, item.heading, item.category, item.intro]
                .join(' ')
                .toLowerCase()
                .includes(needle),
        );
    }, [search, templates]);
    const flashStatus =
        typeof flash === 'object' &&
        flash !== null &&
        'status' in flash &&
        typeof flash.status === 'string'
            ? flash.status
            : null;

    const sendPreview = () => {
        if (!activeTemplate || !testEnabled || !transportCanAttempt || sending)
            return;
        setSending(true);
        router.post(
            endpoint,
            { kind: activeTemplate.kind },
            {
                preserveScroll: true,
                onFinish: () => setSending(false),
            },
        );
    };

    return (
        <AppLayout
            breadcrumbs={[
                { title: isOwner ? 'Command Center' : 'Dashboard', href: back },
                {
                    title: 'KMJ Mail',
                    href: isOwner ? '/operator/mail' : '/team/mail',
                },
            ]}
        >
            <Head title="KMJ Mail · Enterprise communications" />
            <div
                className="owner-admin-page kmj-admin-shell mx-auto flex w-full max-w-[1500px] min-w-0 flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8"
                data-test="kmj-mail-center"
            >
                <header className="owner-admin-hero kmj-admin-hero overflow-hidden rounded-[1.6rem] border p-5 sm:p-7">
                    <Link
                        href={back}
                        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-2 text-xs"
                    >
                        <ArrowLeft size={15} aria-hidden="true" /> Back to
                        {isOwner ? ' Command Center' : ' dashboard'}
                    </Link>
                    <div className="mt-5 flex flex-wrap items-start justify-between gap-4">
                        <div className="max-w-2xl">
                            <p className="flex items-center gap-2 text-xs font-bold tracking-[0.16em] text-red-500 uppercase">
                                <ShieldCheck size={16} aria-hidden="true" />
                                KMJ TECHNO · Communications
                            </p>
                            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
                                KMJ Mail
                            </h1>
                            <p className="text-muted-foreground mt-3 max-w-2xl text-sm leading-7">
                                A focused, Gmail-inspired communication
                                workspace in the locked KMJ Command OS.
                                Templates are original KMJ messages. Your
                                personal Gmail or another employee’s mailbox is
                                not connected or shared.
                            </p>
                        </div>
                        <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-xs font-semibold text-red-500">
                            {isOwner ? 'Platform Owner' : 'My organization'}
                            <span className="text-muted-foreground mt-1 block font-normal">
                                Permission-scoped experience
                            </span>
                        </div>
                    </div>
                    <div className="mt-6 grid gap-3 sm:grid-cols-3">
                        <div className="bg-background/50 rounded-xl border p-4">
                            <span className="text-muted-foreground text-xs">
                                Available templates
                            </span>
                            <strong className="mt-1 block text-2xl font-black tabular-nums">
                                {templates.length}
                            </strong>
                        </div>
                        <div className="bg-background/50 rounded-xl border p-4">
                            <span className="text-muted-foreground text-xs">
                                Gmail mailbox
                            </span>
                            <strong className="mt-1 flex items-center gap-2 text-sm font-semibold">
                                <LockKeyhole size={15} aria-hidden="true" />
                                {mailboxConnection === 'not_connected'
                                    ? 'Not connected'
                                    : 'Unknown'}
                            </strong>
                        </div>
                        <div className="bg-background/50 rounded-xl border p-4">
                            <span className="text-muted-foreground text-xs">
                                Outbound mailer
                            </span>
                            <strong className="mt-1 flex items-center gap-2 text-sm font-semibold">
                                {transportCanAttempt ? (
                                    <CheckCircle2
                                        size={15}
                                        className="text-emerald-500"
                                        aria-hidden="true"
                                    />
                                ) : (
                                    <LockKeyhole size={15} aria-hidden="true" />
                                )}
                                {transportCanAttempt
                                    ? 'Configured to attempt'
                                    : 'Not ready to attempt'}
                            </strong>
                            <span className="text-muted-foreground mt-1 block text-[11px]">
                                Not inbox-delivery proof
                            </span>
                        </div>
                    </div>
                </header>

                {flashStatus && (
                    <p
                        role="status"
                        className="rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm"
                    >
                        {flashStatus}
                    </p>
                )}

                <div className="grid min-h-[590px] gap-3 lg:grid-cols-[190px_minmax(250px,340px)_minmax(0,1fr)]">
                    <nav
                        aria-label="KMJ Mail folders"
                        className="bg-card min-w-0 rounded-2xl border p-3"
                    >
                        <p className="text-muted-foreground px-3 pb-3 text-[11px] font-bold tracking-[0.15em] uppercase">
                            Workspace
                        </p>
                        <div className="grid grid-cols-2 gap-1 sm:grid-cols-4 lg:grid-cols-1">
                            {folders.map(({ id, label, icon: Icon }) => (
                                <button
                                    key={id}
                                    type="button"
                                    onClick={() => setFolder(id)}
                                    aria-current={
                                        folder === id ? 'page' : undefined
                                    }
                                    className={
                                        'flex min-h-11 items-center gap-2 rounded-xl px-3 text-left text-sm transition ' +
                                        (folder === id
                                            ? 'bg-red-500/10 font-semibold text-red-500'
                                            : 'text-muted-foreground hover:bg-muted/70 hover:text-foreground')
                                    }
                                >
                                    <Icon size={16} aria-hidden="true" />
                                    <span>{label}</span>
                                    {id !== 'templates' && (
                                        <LockKeyhole
                                            size={11}
                                            className="ml-auto opacity-60"
                                            aria-label="Not connected"
                                        />
                                    )}
                                </button>
                            ))}
                        </div>
                        <div className="mt-6 rounded-xl border border-dashed p-3">
                            <p className="flex items-center gap-2 text-xs font-semibold">
                                <Users size={14} aria-hidden="true" />
                                Privacy boundary
                            </p>
                            <p className="text-muted-foreground mt-2 text-xs leading-5">
                                Mailboxes require individual OAuth consent.
                                Organization membership never grants access to
                                the owner’s Gmail.
                            </p>
                        </div>
                    </nav>

                    <section
                        aria-label="Mail messages and templates"
                        className="bg-card min-w-0 rounded-2xl border p-3"
                    >
                        <div className="px-2 py-2">
                            <h2 className="text-base font-bold">
                                {folder === 'templates'
                                    ? 'Message templates'
                                    : folders.find((item) => item.id === folder)
                                          ?.label}
                            </h2>
                            <p className="text-muted-foreground mt-1 text-xs">
                                {folder === 'templates'
                                    ? 'Preview first. Send only to your own verified account when enabled.'
                                    : 'No Gmail connection or synchronized messages are available.'}
                            </p>
                        </div>
                        {folder === 'templates' ? (
                            <>
                                <label className="relative mt-3 block">
                                    <Search
                                        size={16}
                                        aria-hidden="true"
                                        className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 -translate-y-1/2"
                                    />
                                    <span className="sr-only">
                                        Find a template
                                    </span>
                                    <input
                                        type="search"
                                        aria-label="Find a template"
                                        value={search}
                                        onChange={(e) =>
                                            setSearch(e.target.value)
                                        }
                                        placeholder="Search mail templates"
                                        className="bg-background min-h-11 w-full rounded-xl border pr-3 pl-10 text-sm outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                                    />
                                </label>
                                <div className="mt-3 space-y-2">
                                    {filtered.map((item) => (
                                        <button
                                            type="button"
                                            key={item.kind}
                                            onClick={() =>
                                                setSelected(item.kind)
                                            }
                                            aria-pressed={
                                                selected === item.kind
                                            }
                                            className={
                                                'flex w-full min-w-0 items-start gap-3 rounded-xl border p-3 text-left transition ' +
                                                (selected === item.kind
                                                    ? 'border-red-500/50 bg-red-500/5'
                                                    : 'hover:bg-muted/30 hover:border-red-500/30')
                                            }
                                        >
                                            <span className="mt-1 grid size-8 shrink-0 place-items-center rounded-lg bg-red-500/10 text-red-500">
                                                <Mail
                                                    size={15}
                                                    aria-hidden="true"
                                                />
                                            </span>
                                            <span className="min-w-0 flex-1">
                                                <span className="block text-[10px] font-bold tracking-[0.1em] text-red-500 uppercase">
                                                    {item.category}
                                                </span>
                                                <span className="mt-1 block text-sm font-bold">
                                                    {item.subject}
                                                </span>
                                                <span className="text-muted-foreground mt-1 block text-xs leading-5">
                                                    {item.heading}
                                                </span>
                                            </span>
                                            <ChevronRight
                                                size={14}
                                                className="text-muted-foreground mt-2 shrink-0"
                                                aria-hidden="true"
                                            />
                                        </button>
                                    ))}
                                    {filtered.length === 0 && (
                                        <p className="text-muted-foreground px-3 py-8 text-center text-sm">
                                            No templates match this search.
                                        </p>
                                    )}
                                </div>
                            </>
                        ) : (
                            <div className="mt-7 rounded-2xl border border-dashed p-5 text-center">
                                <LockKeyhole
                                    size={28}
                                    className="mx-auto text-red-500"
                                    aria-hidden="true"
                                />
                                <h3 className="mt-3 font-semibold">
                                    No mailbox connected
                                </h3>
                                <p className="text-muted-foreground mt-2 text-xs leading-6">
                                    Real Gmail Inbox, Sent and Drafts need
                                    per-user Google OAuth with least-privilege
                                    scopes and protected token storage. No fake
                                    messages are displayed.
                                </p>
                            </div>
                        )}
                    </section>

                    <section
                        aria-label="Selected KMJ email preview"
                        className="bg-card min-w-0 overflow-hidden rounded-2xl border"
                    >
                        {folder === 'templates' && activeTemplate ? (
                            <>
                                <div className="flex flex-wrap items-center justify-between gap-3 border-b p-4 sm:p-5">
                                    <div className="min-w-0">
                                        <p className="text-[11px] font-bold tracking-[0.12em] text-red-500 uppercase">
                                            Read-only preview
                                        </p>
                                        <h2 className="mt-1 text-base font-bold">
                                            {activeTemplate.subject}
                                        </h2>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={sendPreview}
                                        disabled={
                                            !testEnabled ||
                                            !transportCanAttempt ||
                                            sending
                                        }
                                        className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-semibold text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-40"
                                    >
                                        <Send size={15} aria-hidden="true" />
                                        {sending
                                            ? 'Queueing...'
                                            : 'Send test to myself'}
                                    </button>
                                </div>
                                <div className="bg-[#edf0f4] p-4 sm:p-6">
                                    <div className="mx-auto max-w-xl overflow-hidden rounded-xl border border-[#dee3e9] bg-white shadow-sm">
                                        <div className="h-1 bg-[#c7193d]" />
                                        <div className="bg-[#101722] p-6 sm:p-8">
                                            <img
                                                src="/assets/brand/kmj-email-lockup-dark.png"
                                                width="260"
                                                alt="KMJ TECHNO"
                                                className="h-auto max-w-full"
                                            />
                                            <div className="mt-5 border-t border-white/20 pt-5 text-[11px] font-bold tracking-[0.12em] text-[#b5bfcb] uppercase">
                                                {activeTemplate.category}
                                            </div>
                                        </div>
                                        <div className="space-y-5 p-6 text-[#172236] sm:p-8">
                                            <p className="text-xs font-bold tracking-[0.12em] text-[#c7193d] uppercase">
                                                Test preview · No action
                                                required
                                            </p>
                                            <h3 className="text-2xl font-black tracking-tight sm:text-3xl">
                                                {activeTemplate.heading}
                                            </h3>
                                            <p className="text-sm leading-7 text-[#47566a]">
                                                Hello,
                                            </p>
                                            <p className="text-sm leading-7 text-[#47566a]">
                                                {activeTemplate.intro}
                                            </p>
                                            <div className="border-l-4 border-[#c7193d] bg-[#fff7f8] px-4 py-4 text-xs leading-6 text-[#66515a]">
                                                {activeTemplate.notice}
                                            </div>
                                        </div>
                                        <div className="border-t border-[#e5e9ef] bg-[#f9fafc] p-6 text-[#4c596e]">
                                            <p className="font-bold">
                                                KMJ TECHNO
                                            </p>
                                            <p className="mt-1 text-[11px] font-bold tracking-wider">
                                                INNOVATE | BUILD | SCALE
                                            </p>
                                            <p className="mt-3 text-xs">
                                                kmjtechno.com · Official service
                                                communications
                                            </p>
                                        </div>
                                    </div>
                                </div>
                                {!testEnabled && (
                                    <p className="text-muted-foreground border-t px-5 py-4 text-xs leading-6">
                                        Self-test sending is disabled until the
                                        owner approves a verified transport and
                                        enables the private feature flag. No
                                        mail was sent.
                                    </p>
                                )}
                            </>
                        ) : (
                            <div className="grid min-h-[450px] place-items-center p-7 text-center">
                                <div>
                                    <LockKeyhole
                                        size={33}
                                        className="text-muted-foreground mx-auto"
                                        aria-hidden="true"
                                    />
                                    <p className="mt-3 text-sm font-semibold">
                                        {folder === 'templates'
                                            ? 'Select a message'
                                            : 'Gmail connection required'}
                                    </p>
                                    <p className="text-muted-foreground mt-2 max-w-sm text-xs leading-6">
                                        No personal or staff mailbox data is
                                        surfaced without an explicit, authorized
                                        connection.
                                    </p>
                                </div>
                            </div>
                        )}
                    </section>
                </div>
            </div>
        </AppLayout>
    );
}
