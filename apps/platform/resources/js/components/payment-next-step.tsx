import type { OwnerGatewaySetting } from '@/components/operator-payment-settings';
import { formatIstStamp } from '@/lib/format-ist-date-time';
import { ArrowRight, CheckCircle2, Circle, LockKeyhole } from 'lucide-react';

export type PaymentGatewayReadiness = {
    id: string;
    label: string;
    webhook_verification_configured: boolean;
    webhook_events_received: number;
    webhook_last_received_at: string | null;
    recent_events: {
        event_type: string;
        status: string;
        received_at: string | null;
        order_ref: string | null;
        payment_ref: string | null;
    }[];
};

type Step = {
    id: string;
    title: string;
    why: string;
    done: boolean;
    action: { label: string; href: string };
};

/** Pure derivation so the guidance can never claim more than the data proves. */
export function paymentSetupSteps(
    setting: OwnerGatewaySetting | undefined,
    readiness: PaymentGatewayReadiness | undefined,
    provider: string,
): Step[] {
    const keysSaved = Boolean(
        setting?.storage_ready &&
        setting.client_id_stored &&
        setting.client_secret_stored,
    );

    return [
        {
            id: 'merchant',
            title: 'Confirm your merchant account is in Test Mode',
            why: 'Open the provider dashboard, switch to Test Mode, then record your merchant status here. This is your own report; KMJ cannot verify it with the provider.',
            done: setting?.merchant_status === 'owner_reports_approved',
            action: {
                label: 'Record merchant status',
                href: `#gateway-settings-${provider}`,
            },
        },
        {
            id: 'keys',
            title: 'Save your TEST API keys',
            why: 'Paste the Test key ID and secret once. They are stored encrypted and are never shown again. Never share keys in chat.',
            done: keysSaved,
            action: {
                label: 'Save test keys',
                href: `#gateway-settings-${provider}`,
            },
        },
        {
            id: 'webhook-secret',
            title: 'Store the webhook secret',
            why: 'Razorpay: generate the secret in the Webhook setup card (shown once), then paste it into the Razorpay webhook. Cashfree signs with its client secret. KMJ uses it to check that events really come from the provider.',
            done: setting?.webhook_secret_stored === true,
            action: {
                label: 'Generate webhook secret',
                href: '#webhook-setup',
            },
        },
        {
            id: 'webhook-proof',
            title: 'Receive one signed webhook event',
            why: 'Send a test event from the provider dashboard to the KMJ webhook URL shown below. This step turns green only after a correctly signed event arrives.',
            done: readiness?.webhook_verification_configured === true,
            action: {
                label: 'Copy webhook URL',
                href: '#webhook-setup',
            },
        },
        {
            id: 'sandbox-order',
            title: 'Run the sandbox test order',
            why: 'Creates a ₹1 TEST order on the provider sandbox. No card is charged and no license is issued.',
            done: false,
            action: {
                label: 'Go to Test Connection',
                href: '#gateway-onboarding',
            },
        },
    ];
}

const goLive: { label: string; owner: boolean }[] = [
    {
        label: 'Provider merchant account approved for live payments',
        owner: true,
    },
    { label: 'Live API keys stored in the server secret store', owner: true },
    {
        label: 'Sandbox order, signed webhook and capture reconciled',
        owner: false,
    },
    { label: 'Refund handling proven in sandbox', owner: false },
    { label: 'Signed owner activation of live charging', owner: true },
];

export default function PaymentNextStep({
    gatewaySettings,
    readiness,
    provider,
}: {
    gatewaySettings: OwnerGatewaySetting[];
    readiness: PaymentGatewayReadiness[];
    provider: OwnerGatewaySetting['provider'];
}) {
    const setting = gatewaySettings.find((item) => item.provider === provider);
    const gateway = readiness.find((item) => item.id === provider);
    const steps = paymentSetupSteps(setting, gateway, provider);
    const doneCount = steps.filter((step) => step.done).length;
    const next = steps.find((step) => !step.done);
    const name = gateway?.label ?? provider;

    return (
        <section
            aria-label="Your next payment setup step"
            className="mx-auto w-full max-w-6xl rounded-2xl border border-emerald-500/25 bg-[#10171a] p-5 sm:p-6"
            id="payment-next-step"
        >
            <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs font-black tracking-widest text-emerald-300 uppercase">
                    {name} · Guided setup
                </p>
                <p className="text-xs font-semibold text-slate-300">
                    {doneCount} of {steps.length} steps done
                </p>
            </div>
            <div
                role="progressbar"
                aria-label={`${name} setup progress`}
                aria-valuemin={0}
                aria-valuemax={steps.length}
                aria-valuenow={doneCount}
                className="mt-3 h-2 overflow-hidden rounded-full bg-white/10"
            >
                <div
                    className="h-full rounded-full bg-emerald-400"
                    style={{ width: `${(doneCount / steps.length) * 100}%` }}
                />
            </div>

            {next ? (
                <div className="mt-5 rounded-xl border border-white/10 bg-black/20 p-4">
                    <p className="text-[11px] font-bold tracking-widest text-amber-300 uppercase">
                        Do this next
                    </p>
                    <h2 className="mt-1 text-lg font-black text-white">
                        {next.title}
                    </h2>
                    <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                        {next.why}
                    </p>
                    <a
                        href={next.action.href}
                        className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-xl bg-red-600 px-5 py-2 text-sm font-bold text-white hover:bg-red-500"
                    >
                        {next.action.label}
                        <ArrowRight className="size-4" />
                    </a>
                </div>
            ) : null}

            {gateway?.webhook_last_received_at ? (
                <p className="mt-3 text-xs text-slate-400">
                    Last signed webhook event:{' '}
                    {formatIstStamp(gateway.webhook_last_received_at)}
                </p>
            ) : null}

            <ol className="mt-5 grid gap-2 sm:grid-cols-2">
                {steps.map((step, index) => (
                    <li
                        key={step.id}
                        className="flex items-center gap-2 text-sm text-slate-200"
                    >
                        {step.done ? (
                            <CheckCircle2
                                className="size-4 shrink-0 text-emerald-400"
                                aria-label="Done"
                            />
                        ) : (
                            <Circle
                                className="size-4 shrink-0 text-slate-500"
                                aria-label="Not done"
                            />
                        )}
                        {index + 1}. {step.title}
                    </li>
                ))}
            </ol>

            <div className="mt-5 rounded-xl border border-white/10 bg-black/15 p-4">
                <h3 className="text-sm font-bold text-white">
                    Recent webhook events
                </h3>
                {gateway && gateway.recent_events.length > 0 ? (
                    <div className="mt-3 overflow-x-auto">
                        <table className="w-full text-left text-xs text-slate-300">
                            <thead className="text-slate-400">
                                <tr>
                                    <th className="py-1 pr-4 font-semibold">
                                        Received (IST)
                                    </th>
                                    <th className="py-1 pr-4 font-semibold">
                                        Event
                                    </th>
                                    <th className="py-1 pr-4 font-semibold">
                                        Order
                                    </th>
                                    <th className="py-1 pr-4 font-semibold">
                                        Payment
                                    </th>
                                    <th className="py-1 font-semibold">
                                        Status
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {gateway.recent_events.map((event, index) => (
                                    <tr
                                        key={`${event.received_at}-${index}`}
                                        className="border-t border-white/5"
                                    >
                                        <td className="py-1.5 pr-4 whitespace-nowrap">
                                            {formatIstStamp(event.received_at)}
                                        </td>
                                        <td className="py-1.5 pr-4">
                                            {event.event_type}
                                        </td>
                                        <td className="py-1.5 pr-4">
                                            {event.order_ref ?? '—'}
                                        </td>
                                        <td className="py-1.5 pr-4">
                                            {event.payment_ref ?? '—'}
                                        </td>
                                        <td className="py-1.5">
                                            {event.status === 'received'
                                                ? 'Received (not settled)'
                                                : event.status}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <p className="mt-2 text-xs text-slate-400">
                        No signed events yet. Send a test event from the
                        provider dashboard to see it here.
                    </p>
                )}
                <p className="mt-3 text-[11px] text-slate-500">
                    A received event proves delivery only. It does not settle an
                    order or issue a license.
                </p>
            </div>

            <details className="mt-5 rounded-xl border border-white/10 bg-black/15 p-4">
                <summary className="cursor-pointer text-sm font-bold text-white">
                    What is still needed before real money can be accepted
                </summary>
                <ul className="mt-3 space-y-2 text-xs leading-5 text-slate-300">
                    {goLive.map((item) => (
                        <li key={item.label} className="flex items-start gap-2">
                            <Circle className="mt-0.5 size-3.5 shrink-0 text-slate-500" />
                            <span>
                                {item.label}
                                {item.owner ? (
                                    <span className="ml-2 rounded-full border border-amber-500/30 px-2 py-0.5 text-[10px] font-bold text-amber-200">
                                        Owner action
                                    </span>
                                ) : null}
                            </span>
                        </li>
                    ))}
                </ul>
                <p className="mt-3 flex gap-2 text-xs text-amber-100">
                    <LockKeyhole className="mt-0.5 size-4 shrink-0" />
                    Live charging stays locked until every item above is proven.
                    Nothing on this page can switch it on.
                </p>
            </details>
        </section>
    );
}
