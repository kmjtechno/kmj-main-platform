import { router } from '@inertiajs/react';
import { Check, Copy, KeyRound, Webhook } from 'lucide-react';
import { useEffect, useState } from 'react';

export type WebhookGateway = {
    id: string;
    label: string;
    webhook_secret_stored: boolean;
    webhook_verification_configured: boolean;
    webhook_receiver_url: string;
    webhook_events_received: number;
    webhook_last_received_at: string | null;
};

const RAZORPAY_EVENTS = ['payment.captured', 'payment.failed', 'order.paid'];

function copy(text: string) {
    void navigator.clipboard?.writeText(text);
}

function CopyButton({
    text,
    label = 'Copy',
}: {
    text: string;
    label?: string;
}) {
    return (
        <button
            type="button"
            className="border-border inline-flex min-h-9 items-center gap-1 rounded-lg border px-2"
            onClick={() => copy(text)}
        >
            <Copy className="h-3 w-3" />
            {label}
        </button>
    );
}

function xsrfHeader(): Record<string, string> {
    const token = document.cookie
        .split('; ')
        .find((item) => item.startsWith('XSRF-TOKEN='))
        ?.split('=')
        .slice(1)
        .join('=');

    return token ? { 'X-XSRF-TOKEN': decodeURIComponent(token) } : {};
}

export default function WebhookSetupGuide({
    gateway,
}: {
    gateway: WebhookGateway;
}) {
    const [secret, setSecret] = useState<string | null>(null);
    const [confirming, setConfirming] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const proven = gateway.webhook_verification_configured;
    const razorpay = gateway.id === 'razorpay';

    // While waiting for the first signed event, refresh the readiness numbers by themselves.
    useEffect(() => {
        if (proven) return;
        const timer = window.setInterval(() => {
            if (document.visibilityState === 'visible') {
                router.reload({
                    only: ['paymentReadiness'],
                });
            }
        }, 5000);

        return () => window.clearInterval(timer);
    }, [proven]);

    async function generate() {
        if (gateway.webhook_secret_stored && !confirming) {
            setConfirming(true);
            return;
        }
        setBusy(true);
        setError(null);
        try {
            const response = await fetch(
                `/operator/payments/gateways/${gateway.id}/webhook-secret`,
                {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        Accept: 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        ...xsrfHeader(),
                    },
                },
            );
            if (!response.ok) throw new Error(String(response.status));
            const body = (await response.json()) as { webhook_secret?: string };
            setSecret(body.webhook_secret ?? null);
            setConfirming(false);
            router.reload({
                only: ['paymentReadiness', 'gatewaySettings'],
            });
        } catch {
            setError(
                'Could not generate a secret. Reload the page, confirm your password again and retry.',
            );
        } finally {
            setBusy(false);
        }
    }

    const status = proven
        ? `Delivery proven: ${gateway.webhook_events_received} signed event(s) received, last ${gateway.webhook_last_received_at ?? 'n/a'}.`
        : gateway.webhook_events_received > 0
          ? `${gateway.webhook_events_received} signed event(s) received, but no webhook secret is stored here yet.`
          : 'No signed event received yet. This page checks again every few seconds.';

    return (
        <div
            className="bg-card kmj-admin-module-card rounded-2xl border p-5 text-sm"
            data-testid={`webhook-${gateway.id}`}
        >
            <p className="text-foreground flex items-center gap-2 font-semibold">
                <Webhook className="h-4 w-4" />
                Webhook setup ({gateway.label})
                {proven ? <Check className="h-4 w-4 text-emerald-500" /> : null}
            </p>

            {razorpay ? (
                <ol className="text-muted-foreground mt-3 list-decimal space-y-3 pl-4 leading-5">
                    <li>
                        <span className="text-foreground font-medium">
                            Generate your webhook secret here.
                        </span>{' '}
                        It is saved encrypted and shown only once.
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                            <button
                                type="button"
                                disabled={busy}
                                className="border-border inline-flex min-h-9 items-center gap-1 rounded-lg border px-3 font-medium"
                                onClick={() => void generate()}
                            >
                                <KeyRound className="h-3 w-3" />
                                {confirming
                                    ? 'Confirm: replace the stored secret'
                                    : gateway.webhook_secret_stored
                                      ? 'Regenerate secret'
                                      : 'Generate secret'}
                            </button>
                            {confirming ? (
                                <span>
                                    The old secret stops working. Update the
                                    Razorpay webhook with the new one.
                                </span>
                            ) : null}
                        </div>
                        {secret ? (
                            <div className="mt-2 flex items-center gap-2">
                                <code
                                    className="bg-muted min-w-0 flex-1 overflow-x-auto rounded px-2 py-1"
                                    data-testid="generated-webhook-secret"
                                >
                                    {secret}
                                </code>
                                <CopyButton text={secret} />
                            </div>
                        ) : gateway.webhook_secret_stored ? (
                            <p className="mt-2">
                                A secret is stored. It cannot be shown again;
                                regenerate if you lost it.
                            </p>
                        ) : null}
                        {error ? (
                            <p className="mt-2 text-red-500">{error}</p>
                        ) : null}
                    </li>
                    <li>
                        <span className="text-foreground font-medium">
                            In Razorpay Dashboard (Test Mode) → Account &amp;
                            Settings → Webhooks → Add New Webhook, fill:
                        </span>
                        <dl className="mt-2 grid gap-2">
                            <div>
                                <dt className="text-foreground">Webhook URL</dt>
                                <dd className="mt-1 flex items-center gap-2">
                                    <code className="bg-muted min-w-0 flex-1 overflow-x-auto rounded px-2 py-1">
                                        {gateway.webhook_receiver_url}
                                    </code>
                                    <CopyButton
                                        text={gateway.webhook_receiver_url}
                                    />
                                </dd>
                            </div>
                            <div>
                                <dt className="text-foreground">Secret</dt>
                                <dd>
                                    Paste the secret from step 1. Do not leave
                                    it empty: Razorpay then sends no signature
                                    and KMJ rejects the event.
                                </dd>
                            </div>
                            <div>
                                <dt className="text-foreground">Alert Email</dt>
                                <dd>
                                    Any address that should get failure alerts.
                                </dd>
                            </div>
                            <div>
                                <dt className="text-foreground">
                                    Active Events
                                </dt>
                                <dd>
                                    Tick only {RAZORPAY_EVENTS.join(', ')}.
                                    Untick the Subscription events.
                                </dd>
                            </div>
                        </dl>
                    </li>
                    <li>
                        <span className="text-foreground font-medium">
                            Click Create Webhook, then make one Test Mode
                            payment (or trigger a test event if the dashboard
                            offers it).
                        </span>{' '}
                        This card turns to &quot;Delivery proven&quot; by itself
                        once the first signed event arrives.
                    </li>
                </ol>
            ) : (
                <div className="text-muted-foreground mt-2 leading-5">
                    <div className="flex items-center gap-2">
                        <code className="bg-muted min-w-0 flex-1 overflow-x-auto rounded px-2 py-1">
                            {gateway.webhook_receiver_url}
                        </code>
                        <CopyButton text={gateway.webhook_receiver_url} />
                    </div>
                    <p className="mt-2">
                        Cashfree signs webhooks with the client secret, so no
                        separate secret is needed.
                    </p>
                </div>
            )}

            <p className="text-foreground mt-3 leading-5" role="status">
                {status}
            </p>
        </div>
    );
}
