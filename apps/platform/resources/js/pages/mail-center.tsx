import { Head, Link, router, usePage } from '@inertiajs/react';
import { useMemo, useState } from 'react';
import {
    ArrowLeft,
    Check,
    ChevronLeft,
    FileText,
    Inbox,
    KeyRound,
    LockKeyhole,
    MailOpen,
    Pencil,
    RotateCcw,
    Search,
    Send,
    ShieldCheck,
    Trash2,
    UserPlus,
    Users,
} from 'lucide-react';

type Contact = {
    id: number;
    name: string;
    role: string;
};
type MailItem = {
    id: number;
    thread_id: string;
    folder: string;
    subject: string;
    snippet: string;
    sender_user_id: number;
    recipient_user_id: number | null;
    recipient_email: string | null;
    sender_email: string | null;
    delivery_state: string | null;
    unread: boolean;
    at: string;
};
type ThreadItem = {
    id: number;
    from_id: number;
    to_id: number | null;
    recipient_email: string | null;
    sender_email: string | null;
    delivery_state: string | null;
    folder: string;
    subject: string;
    body: string;
    at: string;
};
type Template = {
    kind: string;
    subject: string;
    category: string;
    heading: string;
    intro: string;
    notice: string;
};
type Folder = 'inbox' | 'sent' | 'drafts' | 'trash';
type View = 'mail' | 'compose' | 'templates' | 'staff';

type Props = {
    audience: 'owner' | 'staff';
    workspaceMode: 'native_internal';
    templates: Template[];
    mailbox: { items: MailItem[]; unread: number };
    folder: Folder;
    q: string;
    selectedThread: { items: ThreadItem[]; thread_id: string } | null;
    directory: Contact[];
    staff: { user_id: number; name: string; email: string; sender_alias: string | null }[];
    myUserId: number;
    externalMailEnabled: boolean;
    externalOutbound: { state: 'not_activated' | 'ready_to_queue'; from: string | null };
    transportCanAttempt: boolean;
    testEnabled: boolean;
};

const folderDefs: { id: Folder; label: string; icon: typeof Inbox }[] = [
    { id: 'inbox', label: 'Inbox', icon: Inbox },
    { id: 'sent', label: 'Sent', icon: Send },
    { id: 'drafts', label: 'Drafts', icon: FileText },
    { id: 'trash', label: 'Trash', icon: Trash2 },
];

export default function MailCenter({
    audience,
    templates,
    mailbox,
    folder,
    q,
    selectedThread,
    directory,
    staff,
    myUserId,
    externalMailEnabled,
    externalOutbound,
}: Props) {
    const page = usePage();
    const flash = page.props.flash;
    const errors = page.props.errors;
    const status =
        flash &&
        typeof flash === 'object' &&
        'status' in flash &&
        typeof flash.status === 'string'
            ? flash.status
            : null;
    const errorText =
        errors && typeof errors === 'object'
            ? Object.values(errors).find((value) => typeof value === 'string')
            : null;

    const isOwner = audience === 'owner';
    const base = isOwner ? '/operator/mail' : '/team/mail';
    const [view, setView] = useState<View>('mail');
    const [search, setSearch] = useState(q);
    const [busy, setBusy] = useState(false);
    const [recipientId, setRecipientId] = useState('');
    const [recipientType, setRecipientType] = useState<'external' | 'internal'>('external');
    const [recipientEmail, setRecipientEmail] = useState('');
    const [clientKey, setClientKey] = useState('');
    const [aliasDrafts, setAliasDrafts] = useState<Record<number, string>>({});
    const [subject, setSubject] = useState('');
    const [body, setBody] = useState('');
    const [replyId, setReplyId] = useState<number | null>(null);
    const [draftId, setDraftId] = useState<number | null>(null);
    const [staffId, setStaffId] = useState('');
    const [templateKind, setTemplateKind] = useState(templates[0]?.kind ?? '');
    const [templateQuery, setTemplateQuery] = useState('');
    const activeTemplate = templates.find((t) => t.kind === templateKind);
    const filteredTemplates = useMemo(
        () =>
            templates.filter((t) =>
                (t.subject + ' ' + t.category + ' ' + t.heading)
                    .toLowerCase()
                    .includes(templateQuery.toLowerCase()),
            ),
        [templateQuery, templates],
    );
    const contactName = (id: number | null | undefined) =>
        directory.find((c) => c.id === id)?.name ??
        (id === myUserId ? 'You' : 'Team member');

    const navigate = (
        nextFolder: Folder,
        message?: number,
        searchTerm: string = search,
    ) => {
        setView('mail');
        router.get(
            base,
            {
                folder: nextFolder,
                ...(searchTerm.trim() ? { q: searchTerm.trim() } : {}),
                ...(message ? { message } : {}),
            },
            { preserveScroll: true },
        );
    };

    const startCompose = () => {
        setRecipientId('');
        setRecipientEmail('');
        setRecipientType('external');
        setClientKey(crypto.randomUUID());
        setSubject('');
        setBody('');
        setDraftId(null);
        setReplyId(null);
        setView('compose');
    };

    const startReply = () => {
        const latest = selectedThread?.items.at(-1);
        if (!latest) return;
        const other =
            latest.from_id === myUserId ? latest.to_id : latest.from_id;
        const external = latest.recipient_email ?? (latest.from_id !== myUserId ? latest.sender_email : null);
        if (external) {
            setRecipientType('external');
            setRecipientEmail(external);
            setRecipientId('');
        } else {
            if (other === null) return;
            setRecipientType('internal');
            setRecipientId(String(other));
            setRecipientEmail('');
        }
        setClientKey(crypto.randomUUID());
        setSubject(
            latest.subject.toLowerCase().startsWith('re:')
                ? latest.subject
                : 'Re: ' + latest.subject,
        );
        setBody('');
        setDraftId(null);
        setReplyId(latest.id);
        setView('compose');
    };

    const editDraft = () => {
        const selected = selectedThread?.items.find(
            (item) => item.folder === 'drafts',
        );
        if (!selected) return;
        setRecipientType(selected.recipient_email ? 'external' : 'internal');
        setRecipientEmail(selected.recipient_email ?? '');
        setRecipientId(selected.to_id === null ? '' : String(selected.to_id));
        setClientKey(crypto.randomUUID());
        setSubject(selected.subject);
        setBody(selected.body);
        setDraftId(selected.id);
        setReplyId(null);
        setView('compose');
    };

    const submit = (action: 'send' | 'draft') => {
        if (busy) return;
        const external = recipientType === 'external';
        if (
            action === 'send' &&
            (!subject.trim() || !body.trim() ||
                (external ? (!recipientEmail.trim() || externalOutbound.state !== 'ready_to_queue') : !recipientId))
        ) return;

        const key = clientKey || crypto.randomUUID();
        setClientKey(key);
        setBusy(true);
        const destination = external
            ? { recipient_email: recipientEmail.trim() }
            : recipientId ? { recipient_id: Number(recipientId) } : {};
        const params = action === 'send'
            ? {
                  ...destination,
                  subject,
                  body,
                  client_key: key,
                  ...(replyId ? { reply_to_id: replyId } : {}),
              }
            : {
                  ...destination,
                  recipient_type: recipientType,
                  ...(draftId ? { draft_id: draftId } : {}),
                  subject,
                  body,
              };
        router.post(
            base + (action === 'draft' ? '/drafts' : external ? '/send-external' : '/send'),
            params,
            {
                preserveScroll: true,
                onFinish: () => setBusy(false),
                onSuccess: () => setView('mail'),
            },
        );
    };

    const actOnMessage = (
        operation: 'trash' | 'restore' | 'send-draft',
        id: number,
    ) => {
        if (busy) return;
        setBusy(true);
        const path =
            operation === 'send-draft'
                ? base + '/drafts/' + id + '/send'
                : base + '/messages/' + id + '/' + operation;
        router.post(
            path,
            {},
            { preserveScroll: true, onFinish: () => setBusy(false) },
        );
    };

    const changeStaff = (action: 'grant' | 'revoke', id: number) => {
        if (!isOwner || busy) return;
        setBusy(true);
        router.post(
            action === 'grant'
                ? '/operator/mail/staff'
                : '/operator/mail/staff/' + id + '/revoke',
            action === 'grant' ? { target_user_id: id } : {},
            { onFinish: () => setBusy(false), preserveScroll: true },
        );
    };

    const updateStaffSenderAlias = (staffId: number, currentAlias: string | null) => {
        if (!isOwner || busy) return;
        setBusy(true);
        router.post(
            '/operator/mail/staff/' + staffId + '/sender-alias',
            { sender_alias: (aliasDrafts[staffId] ?? currentAlias ?? '').trim() || null },
            { preserveScroll: true, onFinish: () => setBusy(false) },
        );
    };
    const deliveryLabel = (state: string | null) => {
        switch (state) {
            case 'queued': return 'Queued for SMTP';
            case 'submitting': return 'Submission status unknown';
            case 'mta_accepted': return 'Accepted by mail server';
            case 'failed': return 'Submission failed';
            case 'blocked': return 'Blocked by security policy';
            default: return null;
        }
    };

    const selected = selectedThread?.items.at(-1);
    const back = isOwner ? '/operator' : '/dashboard';

    // app.tsx already mounts AppLayout (owner: OwnerModuleShell; staff: sidebar).
    // Nesting AppLayout here duplicates the entire top bar and sidebar.
    return (
        <>
            <Head title="KMJ Mail · Private enterprise communications" />
            <div
                data-test="kmj-native-mail"
                className="owner-admin-page kmj-admin-shell mx-auto flex w-full max-w-[1500px] min-w-0 flex-col gap-4 px-4 py-5 sm:px-6 lg:px-8"
            >
                <header className="owner-admin-hero kmj-admin-hero overflow-hidden rounded-[1.6rem] border p-5 sm:p-7">
                    <Link
                        href={back}
                        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-2 text-xs"
                    >
                        <ArrowLeft size={14} /> Back to workspace
                    </Link>
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
                        <div>
                            <div className="flex items-center gap-2 text-xs font-bold tracking-[0.14em] text-red-500 uppercase">
                                <ShieldCheck className="size-4" />
                                KMJ TECHNO · Enterprise Communications
                            </div>
                            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
                                KMJ Mail
                            </h1>
                            <p className="text-muted-foreground mt-2 max-w-3xl text-sm leading-6">
                                Your independent, private KMJ mail workspace.
                                Inbox, Sent, Drafts, threads, search and staff
                                permissions are powered by KMJ Main Platform. No
                                Gmail account, Google OAuth or external mail
                                provider is required for internal messages.
                            </p>
                        </div>
                        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs">
                            <span className="flex items-center gap-2 font-semibold text-red-500">
                                <LockKeyhole size={14} />
                                {isOwner ? 'Super Admin' : 'Approved KMJ Staff'}
                            </span>
                            <span className="text-muted-foreground mt-1 block">
                                Private internal delivery · On-platform
                            </span>
                        </div>
                    </div>
                    <div className="mt-5 grid gap-3 sm:grid-cols-3">
                        <div className="bg-background/45 rounded-xl border p-4">
                            <span className="text-muted-foreground text-xs">
                                Unread inbox
                            </span>
                            <strong className="mt-1 block text-2xl font-bold tabular-nums">
                                {mailbox.unread}
                            </strong>
                        </div>
                        <div className="bg-background/45 rounded-xl border p-4">
                            <span className="text-muted-foreground text-xs">
                                KMJ team recipients
                            </span>
                            <strong className="mt-1 block text-2xl font-bold tabular-nums">
                                {directory.length}
                            </strong>
                        </div>
                        <div className="bg-background/45 rounded-xl border p-4">
                            <span className="text-muted-foreground text-xs">
                                Internet mail
                            </span>
                            <strong className="mt-1 block text-sm font-semibold">
                                {externalMailEnabled
                                    ? 'Enabled'
                                    : 'Not enabled yet'}
                            </strong>
                            <span className="text-muted-foreground mt-1 block text-[11px]">
                                Domain routing needs separate delivery
                                verification
                            </span>
                        </div>
                    </div>
                </header>

                {status && (
                    <p
                        role="status"
                        className="rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm"
                    >
                        {status}
                    </p>
                )}
                {typeof errorText === 'string' && (
                    <p
                        role="alert"
                        className="rounded-xl border border-red-500/40 p-4 text-sm text-red-500"
                    >
                        {errorText}
                    </p>
                )}

                <div className="grid min-h-[570px] gap-3 lg:grid-cols-[195px_minmax(240px,360px)_minmax(0,1fr)]">
                    <aside
                        aria-label="Mail folders"
                        className="bg-card min-w-0 rounded-2xl border p-3"
                    >
                        <button
                            type="button"
                            onClick={startCompose}
                            className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-semibold text-white hover:bg-red-500"
                        >
                            <Pencil className="size-4" /> Compose
                        </button>
                        <nav
                            aria-label="Private mail folders"
                            className="mt-4 grid grid-cols-2 gap-1 sm:grid-cols-4 lg:grid-cols-1"
                        >
                            {folderDefs.map(({ id, label, icon: Icon }) => (
                                <button
                                    key={id}
                                    type="button"
                                    onClick={() => navigate(id, undefined, '')}
                                    aria-current={
                                        folder === id && view === 'mail'
                                            ? 'page'
                                            : undefined
                                    }
                                    className={
                                        'flex min-h-11 items-center gap-2 rounded-xl px-3 text-left text-sm transition ' +
                                        (folder === id && view === 'mail'
                                            ? 'bg-red-500/10 font-semibold text-red-500'
                                            : 'text-muted-foreground hover:bg-muted/70 hover:text-foreground')
                                    }
                                >
                                    <Icon className="size-4 shrink-0" />
                                    <span>{label}</span>
                                    {id === 'inbox' && mailbox.unread > 0 && (
                                        <span className="ml-auto rounded-lg bg-red-500 px-1.5 text-[10px] font-bold text-white">
                                            {mailbox.unread}
                                        </span>
                                    )}
                                </button>
                            ))}
                        </nav>
                        <div className="mt-4 border-t pt-4">
                            <button
                                type="button"
                                onClick={() => setView('templates')}
                                className="text-muted-foreground hover:text-foreground flex min-h-11 w-full items-center gap-2 rounded-xl px-3 text-sm"
                            >
                                <FileText className="size-4" /> Templates
                            </button>
                            {isOwner && (
                                <button
                                    type="button"
                                    onClick={() => setView('staff')}
                                    className="text-muted-foreground hover:text-foreground flex min-h-11 w-full items-center gap-2 rounded-xl px-3 text-sm"
                                >
                                    <Users className="size-4" /> Staff access
                                </button>
                            )}
                        </div>
                        <div className="text-muted-foreground mt-5 rounded-xl border border-dashed p-3 text-xs leading-5">
                            <p className="text-foreground flex items-center gap-2 font-bold">
                                <KeyRound size={14} /> Privacy by default
                            </p>
                            <p className="mt-2">
                                Only approved KMJ employees can receive internal
                                mail. Customer organization membership alone
                                grants no access. No customer inbox or external
                                Gmail data is shared.
                            </p>
                        </div>
                    </aside>

                    <section
                        aria-label="Mail list"
                        className="bg-card min-w-0 overflow-hidden rounded-2xl border p-3"
                    >
                        <div className="flex items-center justify-between gap-2 px-2 pt-2">
                            <div>
                                <h2 className="text-base font-bold">
                                    {view === 'templates'
                                        ? 'Original KMJ templates'
                                        : view === 'staff'
                                          ? 'Staff access'
                                          : view === 'compose'
                                            ? 'New message'
                                            : folderDefs.find(
                                                  (f) => f.id === folder,
                                              )?.label}
                                </h2>
                                <p className="text-muted-foreground mt-1 text-xs">
                                    {view === 'mail'
                                        ? 'Latest 40 items. Only your own private records.'
                                        : view === 'templates'
                                          ? 'Readable, reusable, fully KMJ-branded.'
                                          : 'KMJ internal workspace mail'}
                                </p>
                            </div>
                        </div>
                        {view === 'mail' && (
                            <>
                                <form
                                    className="mt-3 flex gap-2"
                                    onSubmit={(e) => {
                                        e.preventDefault();
                                        navigate(folder, undefined, search);
                                    }}
                                >
                                    <label className="relative min-w-0 flex-1">
                                        <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
                                        <span className="sr-only">
                                            Search private messages
                                        </span>
                                        <input
                                            aria-label="Search private messages"
                                            value={search}
                                            onChange={(e) =>
                                                setSearch(e.target.value)
                                            }
                                            maxLength={80}
                                            placeholder="Search messages"
                                            className="bg-background min-h-11 w-full rounded-xl border pr-2 pl-9 text-sm"
                                        />
                                    </label>
                                    <button
                                        type="submit"
                                        className="min-h-11 rounded-xl border px-3 text-xs font-semibold"
                                    >
                                        Find
                                    </button>
                                </form>
                                <div className="mt-3 space-y-1.5">
                                    {mailbox.items.map((item) => (
                                        <button
                                            type="button"
                                            key={item.id}
                                            onClick={() =>
                                                navigate(folder, item.id, q)
                                            }
                                            className={
                                                'w-full rounded-xl border p-3 text-left transition hover:border-red-500/40 ' +
                                                (selected?.id === item.id
                                                    ? 'border-red-500/50 bg-red-500/5'
                                                    : 'bg-background/30')
                                            }
                                        >
                                            <div className="flex items-center justify-between gap-2">
                                                <span className="flex min-w-0 items-center gap-1.5 text-xs font-semibold">
                                                    {item.unread && (
                                                        <span className="size-2 rounded-full bg-red-500" />
                                                    )}
                                                    {folder === 'inbox'
                                                        ? contactName(
                                                              item.sender_user_id,
                                                          )
                                                        : contactName(
                                                              item.recipient_user_id,
                                                          )}
                                                </span>
                                                <span className="text-muted-foreground shrink-0 text-[10px]">
                                                    {item.at.slice(0, 16)}
                                                </span>
                                            </div>
                                            <div className="mt-1 truncate text-sm font-bold">
                                                {item.subject || '(No subject)'}
                                            </div>
                                            <p className="text-muted-foreground mt-1 line-clamp-2 text-xs leading-5">
                                                {item.snippet}
                                            </p>
                                        </button>
                                    ))}
                                    {mailbox.items.length === 0 && (
                                        <div className="rounded-xl border border-dashed px-4 py-12 text-center">
                                            <MailOpen className="text-muted-foreground mx-auto size-7" />
                                            <p className="mt-2 text-sm font-semibold">
                                                No messages in this folder
                                            </p>
                                            <p className="text-muted-foreground mt-1 text-xs">
                                                Compose a message to an approved
                                                KMJ colleague.
                                            </p>
                                        </div>
                                    )}
                                </div>
                            </>
                        )}
                        {view === 'templates' && (
                            <>
                                <label className="mt-3 block">
                                    <span className="sr-only">
                                        Find templates
                                    </span>
                                    <input
                                        value={templateQuery}
                                        onChange={(e) =>
                                            setTemplateQuery(e.target.value)
                                        }
                                        placeholder="Find a template"
                                        className="bg-background min-h-11 w-full rounded-xl border px-3 text-sm"
                                    />
                                </label>
                                <div className="mt-3 space-y-2">
                                    {filteredTemplates.map((item) => (
                                        <button
                                            key={item.kind}
                                            type="button"
                                            onClick={() =>
                                                setTemplateKind(item.kind)
                                            }
                                            className={
                                                'w-full rounded-xl border px-3 py-4 text-left ' +
                                                (templateKind === item.kind
                                                    ? 'border-red-500/50 bg-red-500/5'
                                                    : '')
                                            }
                                        >
                                            <span className="block text-[10px] font-bold tracking-wider text-red-500">
                                                {item.category}
                                            </span>
                                            <strong className="mt-1 block text-sm">
                                                {item.subject}
                                            </strong>
                                        </button>
                                    ))}
                                </div>
                            </>
                        )}
                        {view === 'staff' && isOwner && (
                            <div className="mt-4 space-y-4">
                                <p className="text-muted-foreground text-xs leading-6">
                                    Give an existing, email-verified KMJ user
                                    internal staff mail access. This is not
                                    customer organization administration or
                                    Gmail delegation.
                                </p>
                                <Link
                                    href="/operator/directory"
                                    className="text-xs font-semibold text-red-500 underline"
                                >
                                    Find the verified user ID in Customers &amp;
                                    Orgs
                                </Link>
                                <form
                                    onSubmit={(e) => {
                                        e.preventDefault();
                                        if (/^[1-9]\d*$/.test(staffId))
                                            changeStaff(
                                                'grant',
                                                Number(staffId),
                                            );
                                    }}
                                    className="flex gap-2"
                                >
                                    <input
                                        aria-label="Verified user ID"
                                        inputMode="numeric"
                                        value={staffId}
                                        onChange={(e) =>
                                            setStaffId(e.target.value)
                                        }
                                        placeholder="Verified user ID"
                                        className="bg-background min-h-11 min-w-0 flex-1 rounded-xl border px-3 text-sm"
                                    />
                                    <button
                                        type="submit"
                                        disabled={
                                            busy || !/^[1-9]\d*$/.test(staffId)
                                        }
                                        className="min-h-11 rounded-xl bg-red-600 px-3 text-xs font-bold text-white disabled:opacity-40"
                                    >
                                        <UserPlus className="inline size-4" />{' '}
                                        Grant
                                    </button>
                                </form>
                                {staff.map((person) => (
                                    <div
                                        key={person.user_id}
                                        className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3"
                                    >
                                        <div>
                                            <strong className="block text-sm">
                                                {person.name}
                                            </strong>
                                            <span className="text-muted-foreground text-xs">
                                                ID {person.user_id} ·{' '}
                                                {person.email}
                                            </span>
                                        </div>
                                        <button
                                            type="button"
                                            disabled={busy}
                                            onClick={() => {
                                                if (
                                                    window.confirm(
                                                        'Revoke this staff member’s KMJ Mail access?',
                                                    )
                                                )
                                                    changeStaff(
                                                        'revoke',
                                                        person.user_id,
                                                    );
                                            }}
                                            className="min-h-10 rounded-xl border px-3 text-xs font-semibold text-red-500"
                                        >
                                            Revoke
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </section>

                    <section
                        aria-label="KMJ private message"
                        className="bg-card min-w-0 overflow-hidden rounded-2xl border"
                    >
                        {view === 'compose' ? (
                            <div className="p-5 sm:p-6">
                                <button
                                    type="button"
                                    onClick={() => setView('mail')}
                                    className="text-muted-foreground flex min-h-10 items-center gap-2 text-xs"
                                >
                                    <ChevronLeft className="size-4" /> Back to
                                    messages
                                </button>
                                <p className="mt-3 text-[11px] font-bold tracking-widest text-red-500 uppercase">
                                    KMJ PRIVATE MESSAGE
                                </p>
                                <h2 className="mt-2 text-2xl font-black">
                                    {draftId
                                        ? 'Edit your draft'
                                        : replyId
                                          ? 'Reply to conversation'
                                          : 'Compose'}
                                </h2>
                                <p className="text-muted-foreground mt-2 text-xs leading-6">
                                    Internal delivery only. Recipients must be
                                    verified KMJ staff or the Platform Owner. No
                                    external email address or SMTP relay is
                                    involved.
                                </p>
                                <div className="mt-6 space-y-4">
                                    <label className="block text-xs font-semibold">
                                        To · KMJ colleague
                                        <select
                                            aria-label="KMJ recipient"
                                            value={recipientId}
                                            onChange={(e) =>
                                                setRecipientId(e.target.value)
                                            }
                                            className="bg-background mt-2 min-h-12 w-full rounded-xl border px-3 text-sm"
                                        >
                                            <option value="">
                                                Select a verified recipient
                                            </option>
                                            {directory.map((person) => (
                                                <option
                                                    key={person.id}
                                                    value={person.id}
                                                >
                                                    {person.name} ·{' '}
                                                    {person.role}
                                                </option>
                                            ))}
                                        </select>
                                    </label>
                                    <label className="block text-xs font-semibold">
                                        Subject
                                        <input
                                            value={subject}
                                            onChange={(e) =>
                                                setSubject(e.target.value)
                                            }
                                            maxLength={180}
                                            aria-label="Mail subject"
                                            placeholder="What is this about?"
                                            className="bg-background mt-2 min-h-12 w-full rounded-xl border px-3 text-sm"
                                        />
                                    </label>
                                    <label className="block text-xs font-semibold">
                                        Message
                                        <textarea
                                            value={body}
                                            onChange={(e) =>
                                                setBody(e.target.value)
                                            }
                                            maxLength={12000}
                                            rows={11}
                                            aria-label="Message body"
                                            placeholder="Write a clear, professional message..."
                                            className="bg-background mt-2 w-full resize-y rounded-xl border p-4 text-sm leading-6"
                                        />
                                        <span className="text-muted-foreground mt-1 block text-right text-[11px]">
                                            {body.length}/12,000
                                        </span>
                                    </label>
                                    <div className="flex flex-wrap gap-2">
                                        <button
                                            type="button"
                                            onClick={() => submit('send')}
                                            disabled={
                                                busy ||
                                                !recipientId ||
                                                !subject.trim() ||
                                                !body.trim()
                                            }
                                            className="flex min-h-11 items-center gap-2 rounded-xl bg-red-600 px-5 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-40"
                                        >
                                            <Send className="size-4" /> Send
                                            internally
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => submit('draft')}
                                            disabled={busy}
                                            className="min-h-11 rounded-xl border px-5 text-sm font-semibold"
                                        >
                                            Save draft
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ) : view === 'templates' && activeTemplate ? (
                            <>
                                <div className="border-b p-5">
                                    <span className="text-xs font-bold tracking-widest text-red-500 uppercase">
                                        EMAIL TEMPLATE PREVIEW
                                    </span>
                                    <h2 className="mt-2 text-lg font-bold">
                                        {activeTemplate.subject}
                                    </h2>
                                </div>
                                <div className="bg-[#edf0f4] p-5">
                                    <div className="mx-auto max-w-xl overflow-hidden rounded-xl border bg-white shadow-sm">
                                        <div className="border-t-4 border-[#d61f42] bg-[#111927] p-6">
                                            <img
                                                src="/assets/brand/kmj-email-lockup-dark.png"
                                                width="220"
                                                alt="KMJ TECHNO"
                                            />
                                            <p className="mt-6 text-[11px] font-bold tracking-widest text-[#bec8d7] uppercase">
                                                {activeTemplate.category}
                                            </p>
                                        </div>
                                        <div className="space-y-5 p-6 text-[#172236]">
                                            <h3 className="text-2xl font-black">
                                                {activeTemplate.heading}
                                            </h3>
                                            <p className="text-sm leading-7">
                                                {activeTemplate.intro}
                                            </p>
                                            <p className="border-l-4 border-[#d61f42] bg-[#fff6f8] p-4 text-xs leading-6">
                                                {activeTemplate.notice}
                                            </p>
                                        </div>
                                        <p className="border-t bg-[#f9fafc] p-6 text-xs font-bold text-[#35445b]">
                                            KMJ TECHNO · INNOVATE | BUILD |
                                            SCALE
                                        </p>
                                    </div>
                                </div>
                            </>
                        ) : view === 'staff' ? (
                            <div className="grid min-h-[430px] place-items-center p-8 text-center">
                                <div>
                                    <ShieldCheck className="mx-auto size-8 text-red-500" />
                                    <h2 className="mt-3 text-lg font-bold">
                                        Owner-controlled staff access
                                    </h2>
                                    <p className="text-muted-foreground mt-2 max-w-sm text-sm leading-6">
                                        Access is verified against the KMJ
                                        internal staff authorization ledger on
                                        every request. Revoking access
                                        immediately blocks the staff mailbox.
                                    </p>
                                </div>
                            </div>
                        ) : selectedThread &&
                          selectedThread.items.length > 0 ? (
                            <div className="p-5 sm:p-6">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div>
                                        <p className="text-[11px] font-bold tracking-widest text-red-500 uppercase">
                                            PRIVATE CONVERSATION
                                        </p>
                                        <h2 className="mt-2 text-xl font-bold">
                                            {selectedThread.items[0].subject}
                                        </h2>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        {folder === 'drafts' ? (
                                            <>
                                                <button
                                                    type="button"
                                                    onClick={editDraft}
                                                    className="min-h-10 rounded-xl border px-3 text-xs font-semibold"
                                                >
                                                    Edit
                                                </button>
                                                <button
                                                    type="button"
                                                    disabled={busy || !selected}
                                                    onClick={() =>
                                                        selected &&
                                                        actOnMessage(
                                                            'send-draft',
                                                            selected.id,
                                                        )
                                                    }
                                                    className="min-h-10 rounded-xl bg-red-600 px-3 text-xs font-semibold text-white disabled:opacity-40"
                                                >
                                                    Send draft
                                                </button>
                                            </>
                                        ) : folder !== 'trash' ? (
                                            <button
                                                type="button"
                                                onClick={startReply}
                                                className="min-h-10 rounded-xl bg-red-600 px-3 text-xs font-semibold text-white"
                                            >
                                                Reply
                                            </button>
                                        ) : null}
                                        {folder === 'trash' ? (
                                            <button
                                                type="button"
                                                disabled={busy || !selected}
                                                onClick={() =>
                                                    selected &&
                                                    actOnMessage(
                                                        'restore',
                                                        selected.id,
                                                    )
                                                }
                                                className="flex min-h-10 items-center gap-1 rounded-xl border px-3 text-xs"
                                            >
                                                <RotateCcw className="size-3.5" />{' '}
                                                Restore
                                            </button>
                                        ) : (
                                            <button
                                                type="button"
                                                disabled={busy || !selected}
                                                onClick={() =>
                                                    selected &&
                                                    actOnMessage(
                                                        'trash',
                                                        selected.id,
                                                    )
                                                }
                                                className="flex min-h-10 items-center gap-1 rounded-xl border px-3 text-xs"
                                            >
                                                <Trash2 className="size-3.5" />{' '}
                                                Trash
                                            </button>
                                        )}
                                    </div>
                                </div>
                                <div className="mt-6 space-y-4">
                                    {selectedThread.items.map((item) => (
                                        <article
                                            key={item.id}
                                            className="bg-background/60 rounded-xl border p-4"
                                        >
                                            <div className="flex flex-wrap items-start justify-between gap-2 border-b pb-3">
                                                <div className="text-xs">
                                                    <strong className="block">
                                                        {item.from_id ===
                                                        myUserId
                                                            ? 'You'
                                                            : contactName(
                                                                  item.from_id,
                                                              )}
                                                    </strong>
                                                    <span className="text-muted-foreground">
                                                        To{' '}
                                                        {contactName(
                                                            item.to_id,
                                                        )}
                                                    </span>
                                                </div>
                                                <span className="text-muted-foreground text-[11px]">
                                                    {item.at.slice(0, 19)}
                                                </span>
                                            </div>
                                            <p className="mt-4 text-sm leading-7 break-words whitespace-pre-wrap">
                                                {item.body}
                                            </p>
                                        </article>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="grid min-h-[460px] place-items-center p-8 text-center">
                                <div>
                                    <Inbox className="text-muted-foreground mx-auto size-9" />
                                    <h2 className="mt-3 text-lg font-bold">
                                        Private. Clear. In control.
                                    </h2>
                                    <p className="text-muted-foreground mt-2 max-w-sm text-sm leading-6">
                                        Select a message to read a conversation
                                        or compose a new one. Your private KMJ
                                        mail is stored in the platform, not in
                                        Gmail.
                                    </p>
                                    <div className="mt-4 inline-flex items-center gap-2 text-xs text-red-500">
                                        <Check className="size-4" /> First-party
                                        access controls
                                    </div>
                                </div>
                            </div>
                        )}
                    </section>
                </div>
            </div>
        </>
    );
}
