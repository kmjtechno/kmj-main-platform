import { useState } from 'react';

type Summary = {
    id: string;
    subject: string | null;
    from: { name: string | null; email: string }[];
    receivedAt: string;
    isRead: boolean;
    isFlagged: boolean;
    hasAttachment: boolean;
};

type InboxPage = {
    messages: Summary[];
    missing: string[];
    position: number;
    total: number;
};

export default function JmapOwnerInbox() {
    const [page, setPage] = useState<InboxPage | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    async function load(position: number) {
        if (busy) return;
        setBusy(true);
        setError('');
        setPage(null);
        try {
            const xsrf = document.cookie
                .split('; ')
                .find((value) => value.startsWith('XSRF-TOKEN='))
                ?.slice('XSRF-TOKEN='.length);
            const response = await fetch('/operator/mail/jmap/inbox', {
                method: 'POST',
                credentials: 'same-origin',
                cache: 'no-store',
                redirect: 'error',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    ...(xsrf
                        ? { 'X-XSRF-TOKEN': decodeURIComponent(xsrf) }
                        : {}),
                },
                body: JSON.stringify({ position }),
            });
            if (!response.ok) {
                setError(
                    response.status === 423 || response.status === 419
                        ? 'Confirm your session again before loading mail.'
                        : 'Inbox unavailable. No messages were loaded.',
                );
                return;
            }
            const result = (await response.json()) as {
                status: string;
                inbox: InboxPage;
            };
            if (
                result.status !== 'available' ||
                !Array.isArray(result.inbox?.messages) ||
                !Array.isArray(result.inbox?.missing) ||
                result.inbox.position !== position
            ) {
                throw new Error('Invalid inbox response');
            }
            setPage(result.inbox);
        } catch {
            setError('Inbox unavailable. No messages were loaded.');
        } finally {
            setBusy(false);
        }
    }

    return (
        <section
            aria-label="Native mail engine Inbox"
            className="mt-4 rounded-xl border p-4"
        >
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h3 className="text-sm font-semibold">
                        Native mail engine · Inbox pilot
                    </h3>
                    <p className="text-muted-foreground mt-1 text-xs">
                        Read-only summaries. No message bodies or attachments
                        are downloaded.
                    </p>
                </div>
                <button
                    type="button"
                    disabled={busy}
                    onClick={() => void load(0)}
                    className="min-h-10 rounded-lg border px-3 text-xs font-semibold disabled:opacity-50"
                >
                    {busy ? 'Loading…' : 'Load latest'}
                </button>
            </div>
            <div role="status" aria-live="polite" className="mt-2 text-xs">
                {error ||
                    (busy
                        ? 'Loading private inbox summaries…'
                        : page
                          ? page.total + ' messages in Inbox'
                          : 'Not loaded.')}
            </div>
            {page && (
                <>
                    <ul className="mt-2 divide-y">
                        {page.messages.map((message) => (
                            <li key={message.id} className="py-3">
                                <p className="text-sm font-semibold break-words">
                                    {message.subject || '(No subject)'}
                                </p>
                                <p className="text-muted-foreground text-xs break-all">
                                    {message.from
                                        .map(
                                            (sender) =>
                                                sender.name || sender.email,
                                        )
                                        .join(', ') || 'Unknown sender'}
                                </p>
                                <p className="text-muted-foreground mt-1 text-xs">
                                    {message.receivedAt} ·{' '}
                                    {message.isRead ? 'Read' : 'Unread'}
                                    {message.isFlagged ? ' · Starred' : ''}
                                    {message.hasAttachment
                                        ? ' · Has attachment'
                                        : ''}
                                </p>
                            </li>
                        ))}
                    </ul>
                    {page.messages.length === 0 && (
                        <p className="text-muted-foreground mt-2 text-xs">
                            No messages on this page.
                        </p>
                    )}
                    {page.missing.length > 0 && (
                        <p className="mt-2 text-xs">
                            Some messages changed during retrieval. Refresh
                            for the latest page.
                        </p>
                    )}
                    <div className="mt-3 flex flex-wrap gap-2">
                        <button
                            type="button"
                            disabled={busy || page.position === 0}
                            onClick={() =>
                                void load(Math.max(0, page.position - 40))
                            }
                            className="min-h-10 rounded-lg border px-3 text-xs disabled:opacity-50"
                        >
                            Previous
                        </button>
                        <button
                            type="button"
                            disabled={
                                busy ||
                                page.position + 40 >= page.total ||
                                page.position + 40 > 40000
                            }
                            onClick={() => void load(page.position + 40)}
                            className="min-h-10 rounded-lg border px-3 text-xs disabled:opacity-50"
                        >
                            Next
                        </button>
                        <button
                            type="button"
                            onClick={() => setPage(null)}
                            className="min-h-10 rounded-lg border px-3 text-xs"
                        >
                            Clear view
                        </button>
                    </div>
                </>
            )}
        </section>
    );
}
