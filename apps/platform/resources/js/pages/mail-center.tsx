import { Head, Link, router, usePage } from '@inertiajs/react';
import MailAiCopilot from '@/components/mail-ai-copilot';
import '../../css/kmj-mail-approved.css';
import { useMemo, useState } from 'react';
import {
    Archive,
    HardDrive,
    Mail,
    SlidersHorizontal,
    Sparkles,
    X,
    ArrowLeft,
    ChevronRight,
    Forward,
    ChevronLeft,
    FileText,
    Inbox,
    LockKeyhole,
    MailOpen,
    Pencil,
    RotateCcw,
    Search,
    Send,
    Star,
    RefreshCw,
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
    starred: boolean;
    at: string;
};
type ThreadItem = {
    id: number;
    from_id: number;
    to_id: number | null;
    recipient_email: string | null;
    sender_email: string | null;
    delivery_state: string | null;
    starred: boolean;
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
type Folder = 'inbox' | 'sent' | 'drafts' | 'archive' | 'starred' | 'trash';
type View = 'mail' | 'compose' | 'templates' | 'staff';

type Props = {
    audience: 'owner' | 'staff';
    workspaceMode: 'native_internal';
    templates: Template[];
    mailbox: {
        items: MailItem[];
        unread: number;
        total: number;
        page: number;
        page_size: number;
        has_more: boolean;
    };
    mailMetrics: {
        total_messages: number;
        unread: number;
        mail_text_bytes: number;
    };
    recentSent: { total: number; items: MailItem[] } | null;
    folder: Folder;
    q: string;
    selectedThread: { items: ThreadItem[]; thread_id: string } | null;
    selectedMessageId: number | null;
    directory: Contact[];
    staff: {
        user_id: number;
        name: string;
        email: string;
        sender_alias: string | null;
    }[];
    myUserId: number;
    externalMailEnabled: boolean;
    externalOutbound: {
        state: 'not_activated' | 'ready_to_queue';
        from: string | null;
    };
    transportCanAttempt: boolean;
    testEnabled: boolean;
};

const folderDefs: { id: Folder; label: string; icon: typeof Inbox }[] = [
    { id: 'inbox', label: 'Inbox', icon: Inbox },
    { id: 'sent', label: 'Sent', icon: Send },
    { id: 'drafts', label: 'Drafts', icon: FileText },
    { id: 'archive', label: 'Archive', icon: Archive },
    { id: 'starred', label: 'Starred', icon: Star },
    { id: 'trash', label: 'Trash', icon: Trash2 },
];

export default function MailCenter({
    audience,
    templates,
    mailbox,
    mailMetrics,
    recentSent,
    folder,
    q,
    selectedThread,
    selectedMessageId,
    directory,
    staff,
    myUserId,
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
    const [mailTab, setMailTab] = useState<
        'primary' | 'team' | 'updates' | 'system'
    >('primary');
    const [composerMinimized, setComposerMinimized] = useState(false);
    const [search, setSearch] = useState(q);
    const [busy, setBusy] = useState(false);
    const [selectedIds, setSelectedIds] = useState<number[]>([]);
    const [recipientId, setRecipientId] = useState('');
    const [recipientType, setRecipientType] = useState<'external' | 'internal'>(
        'external',
    );
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
        nextPage = 1,
    ) => {
        setView('mail');
        setSelectedIds([]);
        router.get(
            base,
            {
                folder: nextFolder,
                ...(searchTerm.trim() ? { q: searchTerm.trim() } : {}),
                ...(message ? { message } : {}),
                ...(nextPage > 1 ? { page: nextPage } : {}),
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
        setComposerMinimized(false);
        setView('compose');
    };

    const startReply = () => {
        const latest = selectedThread?.items.at(-1);
        if (!latest) return;
        const other =
            latest.from_id === myUserId ? latest.to_id : latest.from_id;
        const external =
            latest.recipient_email ??
            (latest.from_id !== myUserId ? latest.sender_email : null);
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
        setComposerMinimized(false);
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
        setComposerMinimized(false);
        setView('compose');
    };

    const submit = (action: 'send' | 'draft') => {
        if (busy) return;
        const external = recipientType === 'external';
        if (
            action === 'send' &&
            (!subject.trim() ||
                !body.trim() ||
                (external
                    ? !recipientEmail.trim() ||
                      externalOutbound.state !== 'ready_to_queue'
                    : !recipientId))
        )
            return;

        const key = clientKey || crypto.randomUUID();
        setClientKey(key);
        setBusy(true);
        const destination = external
            ? { recipient_email: recipientEmail.trim() }
            : recipientId
              ? { recipient_id: Number(recipientId) }
              : {};
        const params =
            action === 'send'
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
            base +
                (action === 'draft'
                    ? '/drafts'
                    : external
                      ? '/send-external'
                      : '/send'),
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

    const manageMessages = (
        action:
            | 'star'
            | 'unstar'
            | 'read'
            | 'unread'
            | 'archive'
            | 'unarchive'
            | 'trash'
            | 'restore',
        ids: number[] = selectedIds,
    ) => {
        if (busy || ids.length === 0) return;
        setBusy(true);
        router.post(
            base + '/messages/manage',
            { ids, action, folder },
            {
                preserveScroll: true,
                onFinish: () => setBusy(false),
                onSuccess: () => setSelectedIds([]),
            },
        );
    };

    const forwardMessage = () => {
        const current =
            selectedThread?.items.find(
                (item) => item.id === selectedMessageId,
            ) ?? selectedThread?.items.at(-1);
        if (!current) return;
        setRecipientType('external');
        setRecipientEmail('');
        setRecipientId('');
        setClientKey(crypto.randomUUID());
        setSubject(
            current.subject.toLowerCase().startsWith('fwd:')
                ? current.subject
                : 'Fwd: ' + current.subject,
        );
        setBody(
            [
                '',
                '',
                '---------- Forwarded KMJ message ----------',
                'From: ' +
                    (current.sender_email ?? contactName(current.from_id)),
                'Date: ' + current.at,
                'Subject: ' + current.subject,
                '',
                current.body,
            ]
                .join('\n')
                .slice(0, 12000),
        );
        setDraftId(null);
        setReplyId(null);
        setComposerMinimized(false);
        setView('compose');
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

    const updateStaffSenderAlias = (
        staffId: number,
        currentAlias: string | null,
    ) => {
        if (!isOwner || busy) return;
        setBusy(true);
        router.post(
            '/operator/mail/staff/' + staffId + '/sender-alias',
            {
                sender_alias:
                    (aliasDrafts[staffId] ?? currentAlias ?? '').trim() || null,
            },
            { preserveScroll: true, onFinish: () => setBusy(false) },
        );
    };
    const deliveryLabel = (state: string | null) => {
        switch (state) {
            case 'queued':
                return 'Queued for SMTP';
            case 'submitting':
                return 'Submission status unknown';
            case 'mta_accepted':
                return 'Accepted by mail server';
            case 'failed':
                return 'Submission failed';
            case 'blocked':
                return 'Blocked by security policy';
            default:
                return null;
        }
    };

    const selected =
        selectedThread?.items.find((item) => item.id === selectedMessageId) ??
        selectedThread?.items.at(-1);
    const latestSent = recentSent?.items[0] ?? null;
    const sentRecipientName = (item: MailItem) =>
        item.recipient_email ?? contactName(item.recipient_user_id);
    // These are UI filters on the current page only, not invented server-side
    // priority or spam classifiers. The actual full mailbox remains accessible.
    const visibleItems = useMemo(() => {
        if (mailTab === 'primary') return mailbox.items;
        return mailbox.items.filter((item) => {
            if (mailTab === 'team') return item.recipient_user_id !== null;
            if (mailTab === 'updates') {
                return /update|release|status|progress|milestone/i.test(
                    item.subject,
                );
            }
            return /system|security|password|verification|notice|alert/i.test(
                item.subject,
            );
        });
    }, [mailTab, mailbox.items]);
    const allPageSelected =
        visibleItems.length > 0 &&
        visibleItems.every((item) => selectedIds.includes(item.id));

    // app.tsx already mounts AppLayout (owner: OwnerModuleShell; staff: sidebar).
    // Nesting AppLayout here duplicates the entire top bar and sidebar.
    return (
        <>
            <Head title="KMJ Mail · Enterprise inbox and correspondence" />
            <div
                data-test="kmj-native-mail"
                className="owner-admin-page kmj-admin-shell kmj-mail-approved-shell mx-auto flex w-full max-w-[1720px] min-w-0 flex-col gap-3 px-3 py-4 sm:px-5 lg:px-6"
            >
                <header
                    className="kmj-mail-hero"
                    aria-label="KMJ Mail Enterprise"
                >
                    <div className="kmj-mail-globe" aria-hidden="true" />
                    <div className="kmj-mail-hero-top">
                        <div className="kmj-mail-hero-brand">
                            <div className="kmj-mail-hero-icon">
                                <MailOpen aria-hidden="true" />
                            </div>
                            <div>
                                <p className="kmj-mail-eyebrow">
                                    KMJ TECHNO / ENTERPRISE COMMUNICATIONS
                                </p>
                                <h1>
                                    KMJ Mail <span>Enterprise</span>
                                </h1>
                                <p className="kmj-mail-hero-subtitle">
                                    Secure, private and AI-powered team mail for
                                    your organization.
                                </p>
                            </div>
                        </div>
                        <div className="kmj-mail-secure-panel">
                            <ShieldCheck size={26} aria-hidden="true" />
                            <div>
                                <strong>Private &amp; Secure</strong>
                                <small>
                                    Authorized KMJ team mail · AI by consent
                                </small>
                            </div>
                        </div>
                    </div>
                    <div
                        className="kmj-mail-metrics"
                        aria-label="Live private mailbox metrics"
                    >
                        <div className="kmj-mail-metric">
                            <span className="kmj-mail-metric-icon">
                                <Inbox size={22} />
                            </span>
                            <div>
                                <small>Unread</small>
                                <strong>
                                    {mailMetrics.unread.toLocaleString()}
                                </strong>
                            </div>
                        </div>
                        <div className="kmj-mail-metric">
                            <span className="kmj-mail-metric-icon">
                                <Mail size={22} />
                            </span>
                            <div>
                                <small>Total Messages</small>
                                <strong>
                                    {mailMetrics.total_messages.toLocaleString()}
                                </strong>
                            </div>
                        </div>
                        <div className="kmj-mail-metric">
                            <span className="kmj-mail-metric-icon">
                                <Users size={22} />
                            </span>
                            <div>
                                <small>Team Recipients</small>
                                <strong>
                                    {
                                        directory.filter(
                                            (person) => person.id !== myUserId,
                                        ).length
                                    }
                                </strong>
                            </div>
                        </div>
                        <div className="kmj-mail-metric">
                            <span className="kmj-mail-metric-icon">
                                <HardDrive size={22} />
                            </span>
                            <div>
                                <small>Stored Mail Text (approx.)</small>
                                <strong>
                                    {mailMetrics.mail_text_bytes < 1024
                                        ? mailMetrics.mail_text_bytes + ' B'
                                        : mailMetrics.mail_text_bytes < 1048576
                                          ? (
                                                mailMetrics.mail_text_bytes /
                                                1024
                                            ).toFixed(1) + ' KB'
                                          : (
                                                mailMetrics.mail_text_bytes /
                                                1048576
                                            ).toFixed(1) + ' MB'}
                                </strong>
                            </div>
                        </div>
                        <div className="kmj-mail-metric">
                            <span className="kmj-mail-metric-icon">
                                <Send size={22} />
                            </span>
                            <div>
                                <small>Mail Transport</small>
                                <strong className="kmj-mail-metric-status">
                                    <span
                                        className={
                                            externalOutbound.state ===
                                            'ready_to_queue'
                                                ? 'is-ready'
                                                : 'is-offline'
                                        }
                                    />
                                    {externalOutbound.state === 'ready_to_queue'
                                        ? 'SMTP ready'
                                        : 'Not activated'}
                                </strong>
                                <em>Acceptance ≠ inbox delivery</em>
                            </div>
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

                <div
                    className={
                        'kmj-mail-workspace-grid grid min-h-[640px] min-w-0 gap-3 ' +
                        (view === 'compose'
                            ? 'lg:grid-cols-[205px_minmax(0,1fr)] 2xl:grid-cols-[205px_minmax(0,1fr)_330px]'
                            : 'lg:grid-cols-[205px_minmax(285px,390px)_minmax(0,1fr)] 2xl:grid-cols-[205px_335px_minmax(0,1fr)_330px]')
                    }
                >
                    <aside
                        aria-label="Mail folders"
                        className="kmj-mail-folders from-card to-background min-w-0 rounded-2xl border border-slate-700/40 bg-gradient-to-b p-3 shadow-[0_18px_40px_-30px_rgba(0,0,0,0.8)]"
                    >
                        <button
                            type="button"
                            onClick={startCompose}
                            className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#e32143] to-[#b91035] px-4 text-sm font-bold text-white shadow-[0_12px_25px_-15px_rgba(240,42,76,0.9)] transition hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500"
                        >
                            <Pencil className="size-4" /> Compose
                        </button>
                        <nav
                            aria-label="Private mail folders"
                            className="mt-4 grid grid-cols-2 gap-1 sm:grid-cols-3 lg:grid-cols-1"
                        >
                            {folderDefs.map(({ id, label, icon: Icon }) => (
                                <button
                                    key={id}
                                    type="button"
                                    onClick={() => navigate(id, undefined, '')}
                                    aria-current={
                                        folder === id &&
                                        (view === 'mail' || view === 'compose')
                                            ? 'page'
                                            : undefined
                                    }
                                    className={
                                        'flex min-h-11 items-center gap-3 rounded-xl px-3 text-left text-[13px] font-medium transition focus-visible:outline-2 focus-visible:outline-red-500 ' +
                                        (folder === id &&
                                        (view === 'mail' || view === 'compose')
                                            ? 'border border-red-500/25 bg-red-500/10 font-bold text-red-400 shadow-[inset_3px_0_0_0_#e52945]'
                                            : 'text-muted-foreground hover:bg-muted/70 hover:text-foreground border border-transparent')
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
                        <div className="kmj-mail-search-labels mt-4 border-t border-white/10 pt-3">
                            <div className="flex items-center justify-between gap-2 px-2 text-xs font-bold">
                                <span>Labels</span>
                                <span className="text-[10px] font-normal text-slate-400">
                                    Quick search
                                </span>
                            </div>
                            {[
                                ['CodeBridge', '#4a9cff'],
                                ['CloudOS', '#a458ed'],
                                ['OmniDesk', '#f59d28'],
                                ['Licensing', '#21b995'],
                                ['Support', '#ef4068'],
                                ['Marketing', '#e745a2'],
                            ].map(([name, color]) => (
                                <button
                                    key={name}
                                    type="button"
                                    title={'Search current folder for ' + name}
                                    onClick={() =>
                                        navigate(folder, undefined, name)
                                    }
                                    className="flex min-h-8 w-full items-center gap-2 rounded-lg px-2 text-left text-xs text-slate-300 hover:bg-white/[0.06]"
                                >
                                    <span
                                        aria-hidden="true"
                                        className="size-3.5 shrink-0 rounded-sm"
                                        style={{ background: color }}
                                    />
                                    {name}
                                </button>
                            ))}
                        </div>
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
                        <div
                            id="kmj-mail-help"
                            className="mt-5 rounded-xl border border-white/10 bg-gradient-to-br from-[#182131] to-[#111822] p-3 text-xs leading-5 text-slate-300"
                        >
                            <p className="flex items-center gap-2 font-bold text-white">
                                <LockKeyhole
                                    size={14}
                                    className="text-[#ff6076]"
                                />
                                Private by default
                            </p>
                            <p className="mt-2">
                                Only authorized KMJ staff can open private team
                                mail. External incoming mail, attachments and
                                CC/BCC require separate verified services.
                            </p>
                        </div>
                    </aside>

                    <section
                        aria-label="Mail list"
                        className={
                            'kmj-mail-list bg-card/90 min-w-0 overflow-hidden rounded-2xl border border-slate-700/40 p-3 shadow-[0_18px_40px_-30px_rgba(0,0,0,0.8)]'
                        }
                    >
                        <div className="kmj-mail-list-head flex items-center justify-between gap-2 px-2 pt-2">
                            <div>
                                <h2 className="text-lg font-extrabold tracking-tight">
                                    {view === 'templates'
                                        ? 'Original KMJ templates'
                                        : view === 'staff'
                                          ? 'Staff access'
                                          : view === 'compose'
                                            ? folderDefs.find(
                                                  (f) => f.id === folder,
                                              )?.label
                                            : folderDefs.find(
                                                  (f) => f.id === folder,
                                              )?.label}
                                </h2>
                                <p className="text-muted-foreground mt-1 text-xs">
                                    {view === 'mail' || view === 'compose'
                                        ? 'Your private mailbox · ' +
                                          mailbox.total +
                                          ' messages'
                                        : view === 'templates'
                                          ? 'Readable, reusable, fully KMJ-branded.'
                                          : 'KMJ internal workspace mail'}
                                </p>
                            </div>
                        </div>
                        {(view === 'mail' || view === 'compose') && (
                            <>
                                <div
                                    className="kmj-mail-tabs"
                                    role="tablist"
                                    aria-label="On-page message filters"
                                >
                                    {(
                                        [
                                            ['primary', 'Primary'],
                                            ['team', 'Team'],
                                            ['updates', 'Updates'],
                                            ['system', 'System'],
                                        ] as const
                                    ).map(([tab, label]) => (
                                        <button
                                            type="button"
                                            role="tab"
                                            key={tab}
                                            aria-selected={mailTab === tab}
                                            onClick={() => {
                                                setMailTab(tab);
                                                setSelectedIds([]);
                                            }}
                                        >
                                            {label}
                                        </button>
                                    ))}
                                    <button
                                        type="button"
                                        title="Clear filter"
                                        aria-label="Show all messages on this page"
                                        onClick={() => setMailTab('primary')}
                                    >
                                        <SlidersHorizontal className="size-4" />
                                    </button>
                                </div>
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
                                <div className="kmj-mail-toolbar bg-background/30 mt-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border p-2">
                                    <label className="flex items-center gap-2 text-xs font-semibold">
                                        <input
                                            type="checkbox"
                                            aria-label="Select all visible messages"
                                            checked={allPageSelected}
                                            onChange={() =>
                                                setSelectedIds(
                                                    allPageSelected
                                                        ? []
                                                        : visibleItems.map(
                                                              (item) => item.id,
                                                          ),
                                                )
                                            }
                                            disabled={
                                                mailbox.items.length === 0
                                            }
                                            className="size-4 accent-red-500"
                                        />
                                        Select page
                                    </label>
                                    <div className="flex items-center gap-2">
                                        <span className="text-muted-foreground text-xs">
                                            {mailTab === 'primary'
                                                ? mailbox.total + ' total'
                                                : visibleItems.length +
                                                  ' on this page'}
                                        </span>
                                        <button
                                            type="button"
                                            onClick={() =>
                                                navigate(
                                                    folder,
                                                    undefined,
                                                    q,
                                                    mailbox.page,
                                                )
                                            }
                                            className="flex min-h-9 items-center gap-1 rounded-lg border px-2 text-xs font-semibold"
                                            aria-label="Refresh mail list"
                                        >
                                            <RefreshCw className="size-3.5" />
                                            Refresh
                                        </button>
                                    </div>
                                </div>
                                {selectedIds.length > 0 && (
                                    <div className="mt-2 flex flex-wrap items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/5 p-2">
                                        <span className="text-xs font-bold text-red-500">
                                            {selectedIds.length} selected
                                        </span>
                                        {(folder === 'inbox' ||
                                            folder === 'archive') && (
                                            <>
                                                <button
                                                    type="button"
                                                    disabled={busy}
                                                    onClick={() =>
                                                        manageMessages('read')
                                                    }
                                                    className="rounded-lg border px-2 py-2 text-xs"
                                                >
                                                    Mark read
                                                </button>
                                                <button
                                                    type="button"
                                                    disabled={busy}
                                                    onClick={() =>
                                                        manageMessages('unread')
                                                    }
                                                    className="rounded-lg border px-2 py-2 text-xs"
                                                >
                                                    Mark unread
                                                </button>
                                            </>
                                        )}
                                        {folder === 'inbox' && (
                                            <button
                                                type="button"
                                                disabled={busy}
                                                onClick={() =>
                                                    manageMessages('archive')
                                                }
                                                className="rounded-lg border px-2 py-2 text-xs"
                                            >
                                                Archive
                                            </button>
                                        )}
                                        {folder === 'archive' && (
                                            <button
                                                type="button"
                                                disabled={busy}
                                                onClick={() =>
                                                    manageMessages('unarchive')
                                                }
                                                className="rounded-lg border px-2 py-2 text-xs"
                                            >
                                                To inbox
                                            </button>
                                        )}
                                        {folder !== 'trash' &&
                                            folder !== 'drafts' && (
                                                <button
                                                    type="button"
                                                    disabled={busy}
                                                    onClick={() =>
                                                        manageMessages(
                                                            folder === 'starred'
                                                                ? 'unstar'
                                                                : 'star',
                                                        )
                                                    }
                                                    className="rounded-lg border px-2 py-2 text-xs"
                                                >
                                                    {folder === 'starred'
                                                        ? 'Unstar'
                                                        : 'Star'}
                                                </button>
                                            )}
                                        {folder === 'trash' ? (
                                            <button
                                                type="button"
                                                disabled={busy}
                                                onClick={() =>
                                                    manageMessages('restore')
                                                }
                                                className="rounded-lg border px-2 py-2 text-xs"
                                            >
                                                Restore
                                            </button>
                                        ) : (
                                            <button
                                                type="button"
                                                disabled={busy}
                                                onClick={() =>
                                                    manageMessages('trash')
                                                }
                                                className="rounded-lg border px-2 py-2 text-xs"
                                            >
                                                Move to Trash
                                            </button>
                                        )}
                                    </div>
                                )}
                                <div className="kmj-mail-message-list mt-3 space-y-1.5">
                                    {visibleItems.map((item) => (
                                        <div
                                            key={item.id}
                                            className="flex items-start gap-2"
                                        >
                                            <input
                                                type="checkbox"
                                                aria-label={
                                                    'Select ' +
                                                    (item.subject || 'message')
                                                }
                                                checked={selectedIds.includes(
                                                    item.id,
                                                )}
                                                onChange={(event) =>
                                                    setSelectedIds(
                                                        (previous) =>
                                                            event.target.checked
                                                                ? [
                                                                      ...previous,
                                                                      item.id,
                                                                  ]
                                                                : previous.filter(
                                                                      (id) =>
                                                                          id !==
                                                                          item.id,
                                                                  ),
                                                    )
                                                }
                                                className="mt-5 size-4 shrink-0 accent-red-500"
                                            />
                                            <button
                                                type="button"
                                                onClick={() =>
                                                    navigate(
                                                        folder,
                                                        item.id,
                                                        q,
                                                        mailbox.page,
                                                    )
                                                }
                                                aria-current={
                                                    selected?.id === item.id
                                                        ? 'true'
                                                        : undefined
                                                }
                                                className={
                                                    'hover:bg-muted/50 min-w-0 flex-1 rounded-xl border p-4 text-left shadow-sm transition hover:border-red-500/40 focus-visible:outline-2 focus-visible:outline-red-500 ' +
                                                    (selected?.id === item.id
                                                        ? 'border-red-500/50 bg-red-500/5'
                                                        : 'border-border/70 bg-background/35')
                                                }
                                            >
                                                <div className="flex items-center justify-between gap-2">
                                                    <span className="flex min-w-0 items-center gap-1.5 truncate text-[13px] font-semibold">
                                                        <span
                                                            aria-hidden="true"
                                                            className="kmj-mail-sender-avatar"
                                                        >
                                                            {(
                                                                item.sender_email ??
                                                                item.recipient_email ??
                                                                contactName(
                                                                    item.sender_user_id,
                                                                )
                                                            )
                                                                .slice(0, 1)
                                                                .toUpperCase()}
                                                        </span>
                                                        {item.unread && (
                                                            <span className="size-2 rounded-full bg-red-500" />
                                                        )}
                                                        {item.starred && (
                                                            <Star className="size-3 fill-amber-400 text-amber-400" />
                                                        )}
                                                        {item.folder ===
                                                            'inbox' ||
                                                        item.folder ===
                                                            'archive'
                                                            ? (item.sender_email ??
                                                              contactName(
                                                                  item.sender_user_id,
                                                              ))
                                                            : (item.recipient_email ??
                                                              contactName(
                                                                  item.recipient_user_id,
                                                              ))}
                                                    </span>
                                                    <span className="text-muted-foreground shrink-0 text-[11px] tabular-nums">
                                                        {item.at.slice(0, 16)}
                                                    </span>
                                                </div>
                                                {deliveryLabel(
                                                    item.delivery_state,
                                                ) && (
                                                    <span
                                                        className={
                                                            'mt-2 inline-block rounded-md border px-2 py-1 text-[10px] font-semibold ' +
                                                            (item.delivery_state ===
                                                                'failed' ||
                                                            item.delivery_state ===
                                                                'blocked'
                                                                ? 'border-red-500/30 bg-red-500/10 text-red-400'
                                                                : item.delivery_state ===
                                                                        'queued' ||
                                                                    item.delivery_state ===
                                                                        'submitting'
                                                                  ? 'border-amber-500/25 bg-amber-500/10 text-amber-300'
                                                                  : 'border-slate-500/25 bg-slate-500/10 text-slate-300')
                                                        }
                                                    >
                                                        {deliveryLabel(
                                                            item.delivery_state,
                                                        )}
                                                    </span>
                                                )}
                                                <div className="mt-2 truncate text-[15px] leading-6 font-bold">
                                                    {item.subject ||
                                                        '(No subject)'}
                                                </div>
                                                <p className="text-muted-foreground mt-1 line-clamp-2 text-[13px] leading-[21px]">
                                                    {item.snippet}
                                                </p>
                                            </button>
                                        </div>
                                    ))}
                                    {visibleItems.length === 0 && (
                                        <div className="rounded-xl border border-dashed px-4 py-6 text-center">
                                            <MailOpen className="text-muted-foreground mx-auto size-7" />
                                            <p className="mt-2 text-sm font-semibold">
                                                No messages in this folder
                                            </p>
                                            <p className="text-muted-foreground mt-1 text-xs">
                                                Private internal messages appear
                                                in this folder. External inbound
                                                is not active.
                                            </p>
                                        </div>
                                    )}
                                    {visibleItems.length === 0 &&
                                        folder === 'inbox' &&
                                        recentSent &&
                                        recentSent.items.length > 0 && (
                                            <section
                                                className="kmj-mail-recent-sent-list"
                                                aria-label="Recent messages from your Sent folder"
                                            >
                                                <div className="kmj-mail-recent-sent-head">
                                                    <strong>Recent Sent</strong>
                                                    <small>
                                                        {recentSent.total} in
                                                        Sent · Not inbox mail
                                                    </small>
                                                </div>
                                                {recentSent.items.map(
                                                    (item) => (
                                                        <button
                                                            key={item.id}
                                                            type="button"
                                                            className="kmj-mail-recent-sent-row"
                                                            onClick={() =>
                                                                navigate(
                                                                    'sent',
                                                                    item.id,
                                                                    '',
                                                                )
                                                            }
                                                        >
                                                            <span
                                                                className="kmj-mail-sender-avatar"
                                                                aria-hidden="true"
                                                            >
                                                                {sentRecipientName(
                                                                    item,
                                                                )
                                                                    .slice(0, 1)
                                                                    .toUpperCase()}
                                                            </span>
                                                            <span className="min-w-0 flex-1">
                                                                <strong>
                                                                    {item.subject ||
                                                                        '(No subject)'}
                                                                </strong>
                                                                <small>
                                                                    {
                                                                        item.snippet
                                                                    }
                                                                </small>
                                                            </span>
                                                            <ChevronRight className="size-4 shrink-0 text-slate-500" />
                                                        </button>
                                                    ),
                                                )}
                                            </section>
                                        )}
                                </div>
                                {mailbox.total > mailbox.page_size && (
                                    <div className="mt-4 flex items-center justify-between gap-2 border-t pt-3">
                                        <span className="text-muted-foreground text-xs">
                                            {Math.min(
                                                (mailbox.page - 1) *
                                                    mailbox.page_size +
                                                    1,
                                                mailbox.total,
                                            )}
                                            –
                                            {Math.min(
                                                mailbox.page *
                                                    mailbox.page_size,
                                                mailbox.total,
                                            )}{' '}
                                            of {mailbox.total}
                                        </span>
                                        <div className="flex gap-2">
                                            <button
                                                type="button"
                                                disabled={mailbox.page <= 1}
                                                onClick={() =>
                                                    navigate(
                                                        folder,
                                                        undefined,
                                                        q,
                                                        mailbox.page - 1,
                                                    )
                                                }
                                                className="flex min-h-9 items-center gap-1 rounded-lg border px-3 text-xs disabled:opacity-40"
                                            >
                                                <ChevronLeft className="size-3.5" />
                                                Previous
                                            </button>
                                            <button
                                                type="button"
                                                disabled={!mailbox.has_more}
                                                onClick={() =>
                                                    navigate(
                                                        folder,
                                                        undefined,
                                                        q,
                                                        mailbox.page + 1,
                                                    )
                                                }
                                                className="flex min-h-9 items-center gap-1 rounded-lg border px-3 text-xs disabled:opacity-40"
                                            >
                                                Next
                                                <ChevronRight className="size-3.5" />
                                            </button>
                                        </div>
                                    </div>
                                )}
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
                                            <div className="mt-3 flex flex-wrap gap-2">
                                                <label className="min-w-0 flex-1 text-xs font-semibold">
                                                    Approved @kmjtechno.com
                                                    sender alias
                                                    <input
                                                        type="email"
                                                        maxLength={254}
                                                        aria-label={
                                                            'Sender alias for ' +
                                                            person.name
                                                        }
                                                        value={
                                                            aliasDrafts[
                                                                person.user_id
                                                            ] ??
                                                            person.sender_alias ??
                                                            ''
                                                        }
                                                        placeholder="colleague@kmjtechno.com"
                                                        onChange={(event) =>
                                                            setAliasDrafts(
                                                                (old) => ({
                                                                    ...old,
                                                                    [person.user_id]:
                                                                        event
                                                                            .target
                                                                            .value,
                                                                }),
                                                            )
                                                        }
                                                        className="bg-background mt-2 min-h-11 w-full rounded-xl border px-3 text-xs"
                                                    />
                                                </label>
                                                <button
                                                    type="button"
                                                    disabled={busy}
                                                    onClick={() =>
                                                        updateStaffSenderAlias(
                                                            person.user_id,
                                                            person.sender_alias,
                                                        )
                                                    }
                                                    className="min-h-11 self-end rounded-xl border px-3 text-xs font-semibold"
                                                >
                                                    Save alias
                                                </button>
                                            </div>
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
                        className="kmj-mail-reader bg-card/95 min-w-0 overflow-hidden rounded-2xl border border-slate-700/40 shadow-[0_18px_40px_-30px_rgba(0,0,0,0.8)]"
                    >
                        {view === 'compose' ? (
                            <div
                                className={
                                    'kmj-mail-compose-overlay-layout ' +
                                    (composerMinimized ? 'is-minimized' : '')
                                }
                            >
                                <div className="kmj-mail-compose-underlay">
                                    <p className="text-[10px] font-bold tracking-[0.15em] text-red-400 uppercase">
                                        PRIVATE CONVERSATION
                                    </p>
                                    <h2 className="mt-2 text-xl font-extrabold">
                                        {selectedThread?.items[0]?.subject ??
                                            'Start a new conversation'}
                                    </h2>
                                    <div className="kmj-mail-message-brand mt-6 flex items-center gap-3 rounded-t-xl p-4">
                                        <img
                                            src="/assets/brand/kmj-logo-horizontal-readable.svg"
                                            width="180"
                                            height="45"
                                            alt="KMJ TECHNO — INNOVATE | BUILD | SCALE"
                                            className="h-9 w-auto object-contain"
                                        />
                                        <div className="ml-auto text-right text-xs">
                                            <strong>KMJ Mail Enterprise</strong>
                                            <small className="block">
                                                Official correspondence
                                            </small>
                                        </div>
                                    </div>
                                    <div className="rounded-b-xl border border-t-0 border-white/10 p-5 text-sm leading-7 whitespace-pre-wrap">
                                        {selectedThread?.items.at(-1)?.body ??
                                            'Your message appears here after selecting a conversation.'}
                                    </div>
                                </div>
                                <div className="kmj-mail-floating-compose">
                                    <div className="p-5 sm:p-6">
                                        <div className="kmj-mail-compose-head">
                                            <strong className="flex items-center gap-2 text-sm">
                                                <Pencil className="size-4" />
                                                {draftId
                                                    ? 'Edit draft'
                                                    : replyId
                                                      ? 'Reply'
                                                      : 'New message'}
                                            </strong>
                                            <div className="flex items-center gap-2">
                                                <button
                                                    type="button"
                                                    onClick={() =>
                                                        setComposerMinimized(
                                                            (old) => !old,
                                                        )
                                                    }
                                                    aria-label={
                                                        composerMinimized
                                                            ? 'Expand composer'
                                                            : 'Minimize composer'
                                                    }
                                                    title={
                                                        composerMinimized
                                                            ? 'Expand'
                                                            : 'Minimize'
                                                    }
                                                    className="rounded-md border border-white/20 px-2 text-sm"
                                                >
                                                    {composerMinimized
                                                        ? '+'
                                                        : '−'}
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() =>
                                                        setView('mail')
                                                    }
                                                    aria-label="Close compose window"
                                                    className="rounded-md border border-white/20 p-1"
                                                >
                                                    <X className="size-4" />
                                                </button>
                                            </div>
                                        </div>
                                        <div className="space-y-4">
                                            <div
                                                role="group"
                                                aria-label="Recipient type"
                                            >
                                                <p className="mb-2 text-xs font-semibold">
                                                    Send to
                                                </p>
                                                <div className="flex flex-wrap gap-2">
                                                    <button
                                                        type="button"
                                                        aria-pressed={
                                                            recipientType ===
                                                            'external'
                                                        }
                                                        onClick={() =>
                                                            setRecipientType(
                                                                'external',
                                                            )
                                                        }
                                                        className={
                                                            'min-h-11 rounded-xl border px-4 text-sm font-semibold ' +
                                                            (recipientType ===
                                                            'external'
                                                                ? 'border-red-500 bg-red-500/10 text-red-500'
                                                                : 'text-muted-foreground hover:text-foreground')
                                                        }
                                                    >
                                                        Email address · Gmail /
                                                        Outlook / Any
                                                    </button>
                                                    <button
                                                        type="button"
                                                        aria-pressed={
                                                            recipientType ===
                                                            'internal'
                                                        }
                                                        onClick={() =>
                                                            setRecipientType(
                                                                'internal',
                                                            )
                                                        }
                                                        className={
                                                            'min-h-11 rounded-xl border px-4 text-sm font-semibold ' +
                                                            (recipientType ===
                                                            'internal'
                                                                ? 'border-red-500 bg-red-500/10 text-red-500'
                                                                : 'text-muted-foreground hover:text-foreground')
                                                        }
                                                    >
                                                        KMJ colleague
                                                    </button>
                                                </div>
                                            </div>
                                            {recipientType === 'external' ? (
                                                <div className="space-y-2">
                                                    <label className="block text-xs font-semibold">
                                                        To · external email
                                                        address
                                                        <input
                                                            type="email"
                                                            aria-label="External recipient email address"
                                                            inputMode="email"
                                                            autoComplete="email"
                                                            maxLength={254}
                                                            placeholder="someone@gmail.com"
                                                            value={
                                                                recipientEmail
                                                            }
                                                            onChange={(event) =>
                                                                setRecipientEmail(
                                                                    event.target
                                                                        .value,
                                                                )
                                                            }
                                                            className="bg-background mt-2 min-h-12 w-full rounded-xl border px-3 text-sm"
                                                        />
                                                    </label>
                                                    <div className="text-muted-foreground rounded-xl border border-dashed px-4 py-3 text-xs leading-5">
                                                        <strong className="text-foreground block">
                                                            From:{' '}
                                                            {externalOutbound.from ??
                                                                'KMJ domain sender (not activated)'}
                                                        </strong>
                                                        {externalOutbound.state ===
                                                        'ready_to_queue'
                                                            ? 'You can queue one external email. Postfix acceptance will appear in Sent; recipient Inbox delivery is not guaranteed.'
                                                            : 'External sending is not activated for this mailbox. You can save an external draft, but the Send action is disabled until KMJ mail transport and sender authorization are approved.'}
                                                    </div>
                                                </div>
                                            ) : (
                                                <label className="block text-xs font-semibold">
                                                    To · verified KMJ colleague
                                                    <select
                                                        aria-label="KMJ recipient"
                                                        value={recipientId}
                                                        onChange={(event) =>
                                                            setRecipientId(
                                                                event.target
                                                                    .value,
                                                            )
                                                        }
                                                        className="bg-background mt-2 min-h-12 w-full rounded-xl border px-3 text-sm"
                                                    >
                                                        <option value="">
                                                            Select an approved
                                                            team member
                                                        </option>
                                                        {directory.map(
                                                            (person) => (
                                                                <option
                                                                    key={
                                                                        person.id
                                                                    }
                                                                    value={
                                                                        person.id
                                                                    }
                                                                >
                                                                    {
                                                                        person.name
                                                                    }{' '}
                                                                    ·{' '}
                                                                    {
                                                                        person.role
                                                                    }
                                                                </option>
                                                            ),
                                                        )}
                                                    </select>
                                                </label>
                                            )}
                                            <label className="block text-xs font-semibold">
                                                Subject
                                                <input
                                                    value={subject}
                                                    onChange={(e) =>
                                                        setSubject(
                                                            e.target.value,
                                                        )
                                                    }
                                                    maxLength={180}
                                                    aria-label="Mail subject"
                                                    placeholder="What is this about?"
                                                    className="bg-background mt-2 min-h-12 w-full rounded-xl border px-3 text-sm"
                                                />
                                            </label>
                                            <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-fuchsia-500/25 bg-fuchsia-500/5 p-2">
                                                <span className="flex items-center gap-2 text-xs font-bold text-fuchsia-200">
                                                    <Sparkles className="size-4" />{' '}
                                                    KMJ AI · Write with AI
                                                </span>
                                                <a
                                                    href="#kmj-ai-copilot"
                                                    className="rounded-lg border border-fuchsia-500/40 bg-fuchsia-500/20 px-3 py-1.5 text-xs font-semibold text-fuchsia-100"
                                                >
                                                    Open Copilot
                                                </a>
                                            </div>
                                            <label className="block text-xs font-semibold">
                                                Message
                                                <textarea
                                                    value={body}
                                                    onChange={(e) =>
                                                        setBody(e.target.value)
                                                    }
                                                    maxLength={12000}
                                                    rows={6}
                                                    aria-label="Message body"
                                                    placeholder="Write a clear, professional message..."
                                                    className="bg-background mt-2 w-full resize-y rounded-xl border p-4 text-sm leading-6"
                                                />
                                                <span className="text-muted-foreground mt-1 block text-right text-[11px]">
                                                    {body.length}/12,000
                                                </span>
                                            </label>
                                            <p className="text-muted-foreground rounded-xl border border-dashed p-3 text-xs leading-5">
                                                Recipient privacy is enforced.
                                                This release supports one
                                                external recipient per message;
                                                CC/BCC and attachments require
                                                separately reviewed transport
                                                and scanning.
                                            </p>
                                            <div className="flex flex-wrap items-center justify-end gap-2 border-t border-white/10 pt-3">
                                                <button
                                                    type="button"
                                                    onClick={() =>
                                                        submit('send')
                                                    }
                                                    disabled={
                                                        busy ||
                                                        (recipientType ===
                                                        'external'
                                                            ? !recipientEmail.trim() ||
                                                              externalOutbound.state !==
                                                                  'ready_to_queue'
                                                            : !recipientId) ||
                                                        !subject.trim() ||
                                                        !body.trim()
                                                    }
                                                    className="flex min-h-11 items-center gap-2 rounded-xl bg-red-600 px-5 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-40"
                                                >
                                                    <Send className="size-4" />{' '}
                                                    {recipientType ===
                                                    'external'
                                                        ? 'Queue external email'
                                                        : 'Send internally'}
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() =>
                                                        submit('draft')
                                                    }
                                                    disabled={busy}
                                                    className="min-h-11 rounded-xl border px-5 text-sm font-semibold"
                                                >
                                                    Save draft
                                                </button>
                                            </div>
                                        </div>
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
                                            <div className="flex items-center gap-3">
                                                <img
                                                    src="/assets/brand/kmj-sender-avatar.png"
                                                    width="64"
                                                    height="64"
                                                    className="size-16 shrink-0 object-contain"
                                                    alt="KMJ TECHNO"
                                                />
                                                <div className="min-w-0">
                                                    <p className="text-[27px] leading-8 font-extrabold tracking-tight">
                                                        <span className="text-[#ff263f]">
                                                            KMJ
                                                        </span>{' '}
                                                        <span className="text-white">
                                                            TECHNO
                                                        </span>
                                                    </p>
                                                    <p className="text-[13px] leading-5 font-bold text-white">
                                                        INNOVATE{' '}
                                                        <span className="text-[#ff314a]">
                                                            |
                                                        </span>{' '}
                                                        BUILD{' '}
                                                        <span className="text-[#ff314a]">
                                                            |
                                                        </span>{' '}
                                                        SCALE
                                                    </p>
                                                </div>
                                            </div>
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
                            <div className="p-4 sm:p-5">
                                <div className="kmj-mail-reader-toolbar flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
                                    <button
                                        type="button"
                                        onClick={() =>
                                            navigate(
                                                folder,
                                                undefined,
                                                q,
                                                mailbox.page,
                                            )
                                        }
                                        className="flex min-h-9 items-center gap-2 rounded-lg border border-white/15 px-3 text-xs"
                                    >
                                        <ArrowLeft className="size-4" />
                                        Back to {folder}
                                    </button>
                                    <span className="text-[11px] text-slate-400">
                                        Private owner-scoped thread
                                    </span>
                                </div>
                                <div className="border-border/60 flex flex-wrap items-center justify-between gap-3 border-b py-4">
                                    <div>
                                        <p className="text-[11px] font-bold tracking-widest text-red-500 uppercase">
                                            PRIVATE CONVERSATION
                                        </p>
                                        <h2 className="mt-2 text-2xl font-black tracking-tight">
                                            {selectedThread.items[0].subject}
                                        </h2>
                                    </div>
                                    <div className="kmj-mail-read-actions flex flex-wrap gap-2">
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
                                        {folder !== 'drafts' &&
                                            folder !== 'trash' &&
                                            selected && (
                                                <>
                                                    <button
                                                        type="button"
                                                        onClick={forwardMessage}
                                                        className="flex min-h-10 items-center gap-1 rounded-xl border px-3 text-xs font-semibold"
                                                    >
                                                        <Forward className="size-3.5" />
                                                        Forward
                                                    </button>
                                                    <button
                                                        type="button"
                                                        disabled={busy}
                                                        onClick={() =>
                                                            manageMessages(
                                                                selected.starred
                                                                    ? 'unstar'
                                                                    : 'star',
                                                                [selected.id],
                                                            )
                                                        }
                                                        className="flex min-h-10 items-center gap-1 rounded-xl border px-3 text-xs font-semibold"
                                                    >
                                                        <Star className="size-3.5" />
                                                        {selected.starred
                                                            ? 'Unstar'
                                                            : 'Star'}
                                                    </button>
                                                    {(selected.folder ===
                                                        'inbox' ||
                                                        selected.folder ===
                                                            'archive') && (
                                                        <button
                                                            type="button"
                                                            disabled={busy}
                                                            onClick={() =>
                                                                manageMessages(
                                                                    'unread',
                                                                    [
                                                                        selected.id,
                                                                    ],
                                                                )
                                                            }
                                                            className="min-h-10 rounded-xl border px-3 text-xs font-semibold"
                                                        >
                                                            Mark unread
                                                        </button>
                                                    )}
                                                    {selected.folder ===
                                                        'inbox' && (
                                                        <button
                                                            type="button"
                                                            disabled={busy}
                                                            onClick={() =>
                                                                manageMessages(
                                                                    'archive',
                                                                    [
                                                                        selected.id,
                                                                    ],
                                                                )
                                                            }
                                                            className="flex min-h-10 items-center gap-1 rounded-xl border px-3 text-xs font-semibold"
                                                        >
                                                            <Archive className="size-3.5" />
                                                            Archive
                                                        </button>
                                                    )}
                                                    {selected.folder ===
                                                        'archive' && (
                                                        <button
                                                            type="button"
                                                            disabled={busy}
                                                            onClick={() =>
                                                                manageMessages(
                                                                    'unarchive',
                                                                    [
                                                                        selected.id,
                                                                    ],
                                                                )
                                                            }
                                                            className="min-h-10 rounded-xl border px-3 text-xs font-semibold"
                                                        >
                                                            To inbox
                                                        </button>
                                                    )}
                                                </>
                                            )}
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
                                <div className="kmj-mail-message-brand mt-4 flex flex-wrap items-center justify-between gap-4 rounded-t-xl p-4">
                                    <img
                                        src="/assets/brand/kmj-logo-horizontal-readable.svg"
                                        width="210"
                                        height="55"
                                        alt="KMJ TECHNO — INNOVATE | BUILD | SCALE"
                                        className="h-11 w-auto object-contain"
                                    />
                                    <div className="text-right">
                                        <strong className="block text-base">
                                            KMJ Mail Enterprise
                                        </strong>
                                        <small className="text-[11px]">
                                            Private official correspondence
                                        </small>
                                    </div>
                                </div>
                                <div className="kmj-mail-thread-messages mt-0 space-y-4">
                                    {selectedThread.items.map((item) => (
                                        <article
                                            key={item.id}
                                            className="border-border/70 bg-background/50 rounded-2xl border p-5 shadow-sm"
                                        >
                                            <div className="flex flex-wrap items-start justify-between gap-2 border-b pb-3">
                                                <div className="text-xs">
                                                    <strong className="block">
                                                        {item.from_id ===
                                                        myUserId
                                                            ? 'You'
                                                            : (item.sender_email ??
                                                              contactName(
                                                                  item.from_id,
                                                              ))}
                                                    </strong>
                                                    <span className="text-muted-foreground">
                                                        To{' '}
                                                        {item.recipient_email ??
                                                            contactName(
                                                                item.to_id,
                                                            )}
                                                    </span>
                                                    {deliveryLabel(
                                                        item.delivery_state,
                                                    ) && (
                                                        <span className="mt-2 block text-[11px] font-semibold text-red-500">
                                                            {deliveryLabel(
                                                                item.delivery_state,
                                                            )}
                                                            {item.delivery_state ===
                                                            'mta_accepted'
                                                                ? ' · Not inbox delivery proof'
                                                                : ''}
                                                        </span>
                                                    )}
                                                </div>
                                                <span className="text-muted-foreground text-[11px]">
                                                    {item.at.slice(0, 19)}
                                                </span>
                                            </div>
                                            <p className="mt-5 text-[15px] leading-8 break-words whitespace-pre-wrap">
                                                {item.body}
                                            </p>
                                        </article>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="relative flex min-h-[560px] flex-col overflow-hidden bg-gradient-to-b from-[#121d2b]/60 via-transparent to-[#182334]/25">
                                <div className="flex items-center justify-between gap-3 border-b border-white/10 px-5 py-4 sm:px-6">
                                    <div>
                                        <p className="text-[10px] font-bold tracking-[0.18em] text-red-400 uppercase">
                                            KMJ MAIL / READING WORKSPACE
                                        </p>
                                        <p className="mt-1 text-sm font-semibold">
                                            {
                                                folderDefs.find(
                                                    (item) =>
                                                        item.id === folder,
                                                )?.label
                                            }{' '}
                                            conversations
                                        </p>
                                    </div>
                                    <div className="text-muted-foreground rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs">
                                        {mailbox.total} in this folder
                                    </div>
                                </div>
                                <div className="relative flex flex-1 items-center justify-center p-6 sm:p-10">
                                    <div className="w-full max-w-[470px]">
                                        <div className="flex size-16 items-center justify-center rounded-2xl border border-red-500/20 bg-gradient-to-br from-red-500/15 to-[#1d2939] shadow-[0_20px_45px_-25px_rgba(223,33,68,0.6)]">
                                            <MailOpen className="size-8 text-[#ff4763]" />
                                        </div>
                                        <p className="mt-7 text-[11px] font-bold tracking-[0.2em] text-red-400 uppercase">
                                            PRIVATE COMMUNICATIONS
                                        </p>
                                        <h2 className="mt-2 text-2xl leading-tight font-black tracking-tight sm:text-[30px]">
                                            {mailbox.items.length
                                                ? 'Your next conversation starts here.'
                                                : 'A clear space for every conversation.'}
                                        </h2>
                                        <p className="text-muted-foreground mt-3 max-w-md text-sm leading-7">
                                            {mailbox.items.length
                                                ? 'Choose a message to view its full thread, sender details and delivery status.'
                                                : 'This folder has no matching private messages. Compose a new message or choose another folder.'}
                                        </p>
                                        {folder === 'inbox' && latestSent && (
                                            <section
                                                className="kmj-mail-recent-sent-reader mt-6"
                                                aria-label="Real recent sent message preview"
                                            >
                                                <div className="kmj-mail-message-brand flex items-center justify-between gap-3 p-3">
                                                    <img
                                                        src="/assets/brand/kmj-logo-horizontal-readable.svg"
                                                        width="168"
                                                        height="44"
                                                        alt="KMJ TECHNO"
                                                        className="h-8 w-auto object-contain"
                                                    />
                                                    <span className="text-right text-[11px] font-bold">
                                                        Official Correspondence
                                                    </span>
                                                </div>
                                                <div className="p-4">
                                                    <span className="text-[10px] font-bold tracking-wider text-rose-400 uppercase">
                                                        From your Sent folder ·
                                                        Not Inbox
                                                    </span>
                                                    <h3 className="mt-2 text-base font-extrabold text-white">
                                                        {latestSent.subject ||
                                                            '(No subject)'}
                                                    </h3>
                                                    <p className="mt-1 text-xs text-slate-300">
                                                        To:{' '}
                                                        {sentRecipientName(
                                                            latestSent,
                                                        )}
                                                    </p>
                                                    <p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-200">
                                                        {latestSent.snippet}
                                                    </p>
                                                    {deliveryLabel(
                                                        latestSent.delivery_state,
                                                    ) && (
                                                        <p className="mt-2 text-[11px] font-semibold text-amber-200">
                                                            {deliveryLabel(
                                                                latestSent.delivery_state,
                                                            )}
                                                        </p>
                                                    )}
                                                    <button
                                                        type="button"
                                                        onClick={() =>
                                                            navigate(
                                                                'sent',
                                                                latestSent.id,
                                                                '',
                                                            )
                                                        }
                                                        className="mt-4 inline-flex min-h-9 items-center gap-2 rounded-lg border border-rose-400/35 bg-rose-500/15 px-3 text-xs font-bold text-white hover:bg-rose-500/25"
                                                    >
                                                        <MailOpen className="size-4" />
                                                        Open real Sent
                                                        conversation
                                                    </button>
                                                </div>
                                            </section>
                                        )}
                                        <div className="mt-6 flex flex-wrap gap-3">
                                            {mailbox.items.length > 0 && (
                                                <button
                                                    type="button"
                                                    onClick={() =>
                                                        navigate(
                                                            folder,
                                                            mailbox.items[0].id,
                                                            q,
                                                            mailbox.page,
                                                        )
                                                    }
                                                    className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-gradient-to-r from-[#e62446] to-[#b40c32] px-4 text-sm font-bold text-white transition hover:brightness-110"
                                                >
                                                    <MailOpen className="size-4" />
                                                    Open latest message
                                                </button>
                                            )}
                                            <button
                                                type="button"
                                                onClick={startCompose}
                                                className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-white/15 bg-white/[0.04] px-4 text-sm font-semibold hover:bg-white/[0.08]"
                                            >
                                                <Pencil className="size-4" />
                                                New message
                                            </button>
                                        </div>
                                        {mailbox.items.length > 0 && (
                                            <button
                                                type="button"
                                                onClick={() =>
                                                    navigate(
                                                        folder,
                                                        mailbox.items[0].id,
                                                        q,
                                                        mailbox.page,
                                                    )
                                                }
                                                className="mt-8 w-full rounded-2xl border border-white/10 bg-white/[0.035] p-4 text-left transition hover:border-red-500/30 hover:bg-white/[0.06]"
                                            >
                                                <span className="text-muted-foreground text-[10px] font-bold tracking-[0.2em] uppercase">
                                                    MOST RECENT ·{' '}
                                                    {mailbox.items[0].at.slice(
                                                        0,
                                                        16,
                                                    )}
                                                </span>
                                                <span className="mt-2 block truncate text-sm font-bold">
                                                    {mailbox.items[0].subject ||
                                                        '(No subject)'}
                                                </span>
                                                <span className="text-muted-foreground mt-1 line-clamp-2 block text-[13px] leading-6">
                                                    {mailbox.items[0].snippet}
                                                </span>
                                            </button>
                                        )}
                                        <p className="text-muted-foreground mt-6 flex items-center gap-2 text-xs">
                                            <ShieldCheck className="size-4 shrink-0 text-red-400" />
                                            Private records. Owner-controlled
                                            team access.
                                        </p>
                                    </div>
                                </div>
                            </div>
                        )}
                    </section>
                    <MailAiCopilot
                        base={base}
                        selectedMessageId={selected?.id ?? null}
                        onUseCompose={(suggestedSubject, suggestedBody) => {
                            startCompose();
                            setSubject(suggestedSubject);
                            setBody(suggestedBody);
                        }}
                        onUseReply={(suggestedBody) => {
                            if (!selected) return;
                            startReply();
                            setBody(suggestedBody);
                        }}
                    />
                </div>
            </div>
        </>
    );
}
