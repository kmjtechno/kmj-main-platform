import { createInertiaApp, usePage } from '@inertiajs/react';
import type { ComponentProps } from 'react';
import OwnerModuleShell from '../resources/js/layouts/owner-module-shell';
import MailCenter from '../resources/js/pages/mail-center';
import '../resources/css/app.css';

// Visual-only fixture; never a Laravel route, login, or mail provider.
const sentItem = {
    id: 7,
    thread_id: 'synthetic-thread',
    folder: 'sent',
    subject: 'Synthetic sent-only record',
    snippet: 'This fixture belongs only to Sent.',
    sender_user_id: 1,
    recipient_user_id: null,
    recipient_email: 'recipient@example.invalid',
    sender_email: 'info@example.invalid',
    delivery_state: 'mta_accepted',
    unread: false,
    starred: false,
    at: '2026-11-25T09:00:00Z',
};

const folder =
    new URLSearchParams(location.search).get('folder') === 'sent'
        ? 'sent'
        : 'inbox';

const props: ComponentProps<typeof MailCenter> = {
    audience: 'owner',
    workspaceMode: 'native_internal',
    templates: [],
    mailbox: {
        items: folder === 'sent' ? [sentItem] : [],
        unread: 0,
        total: folder === 'sent' ? 1 : 0,
        page: 1,
        page_size: 40,
        has_more: false,
    },
    mailMetrics: { total_messages: 1, unread: 0, mail_text_bytes: 32 },
    folder,
    q: '',
    selectedThread: null,
    selectedMessageId: null,
    directory: [],
    staff: [],
    myUserId: 1,
    externalMailEnabled: false,
    externalInboundPilotConfigured: false,
    externalInbox:
        folder === 'inbox'
            ? { total: 0, unread: 0, matching: 0, items: [], selected: null }
            : null,
    externalOutbound: { state: 'not_activated', from: null },
    transportCanAttempt: false,
    testEnabled: false,
};

function Preview() {
    return (
        <OwnerModuleShell>
            <MailCenter
                {...(usePage().props as unknown as ComponentProps<
                    typeof MailCenter
                >)}
            />
        </OwnerModuleShell>
    );
}

void createInertiaApp({
    page: {
        component: 'mail-center',
        props: {
            ...props,
            errors: {},
            auth: {
                user: {
                    id: 1,
                    name: 'KMJ QA Owner',
                    email: 'owner@example.invalid',
                    email_verified_at: null,
                    created_at: '2026-01-01',
                    updated_at: '2026-01-01',
                },
            },
            operator: { enabled: true },
            // A stale client prop must never appear in Inbox.
            recentSent: { total: 1, items: [sentItem] },
        },
        url: '/operator/mail?folder=' + folder,
        version: 'mail-visual-fixture',
        clearHistory: false,
        encryptHistory: false,
    },
    resolve: () => Preview,
});
