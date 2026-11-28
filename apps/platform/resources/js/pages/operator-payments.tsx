import { Head, Link } from '@inertiajs/react';
import { useState } from 'react';
import '../../css/owner-payments-premium.css';
import OperatorModuleNavigation from '@/components/operator-module-navigation';
import PaymentGatewayOnboarding from '@/components/payment-gateway-onboarding';
import PaymentNextStep from '@/components/payment-next-step';
import WebhookSetupGuide from '@/components/webhook-setup-guide';
import OperatorPaymentSettings, {
    type OwnerGatewaySetting,
} from '@/components/operator-payment-settings';
import {
    ArrowLeft,
    BadgeCheck,
    CreditCard,
    Globe2,
    KeyRound,
    LockKeyhole,
    ShieldCheck,
} from 'lucide-react';

type Gateway = {
    id: string;
    label: string;
    merchant_approval: string;
    sandbox_credentials_present: boolean;
    webhook_secret_stored: boolean;
    webhook_verification_configured: boolean;
    webhook_receiver_url: string;
    webhook_events_received: number;
    webhook_last_received_at: string | null;
    recent_events: {
        event_type: string;
        status: string;
        received_at: string | null;
        order_ref: string | null;
        payment_ref: string | null;
    }[];
    international_approval_recorded: boolean;
    live_transaction_verified: boolean;
    status: string;
};

type PaymentReadiness = {
    live_charging_enabled: boolean;
    providers: Gateway[];
};

export default function OperatorPayments({
    paymentReadiness,
    gatewaySettings,
}: {
    paymentReadiness: PaymentReadiness;
    gatewaySettings: OwnerGatewaySetting[];
}) {
    const [selectedProvider, setSelectedProvider] =
        useState<OwnerGatewaySetting['provider']>('razorpay');

    const visibleGateways = paymentReadiness.providers.filter(
        (gateway) => gateway.id === 'razorpay' || gateway.id === 'cashfree',
    );
    const selectedGateway = visibleGateways.find(
        (gateway) => gateway.id === selectedProvider,
    );

    return (
        <>
            <Head title="KMJ TECHNO — Payment Gateway Control" />
            <main className="owner-admin-page kmj-admin-shell kmj-owner-payments flex min-w-0 flex-1 flex-col gap-6 p-4 sm:p-6 lg:p-8">
                <div className="w-full">
                    <OperatorModuleNavigation active="payments" />
                </div>
                <header className="flex w-full flex-col gap-4">
                    <Link
                        href="/operator"
                        className="text-muted-foreground hover:text-foreground inline-flex w-fit items-center gap-2 text-sm"
                    >
                        <ArrowLeft className="h-4 w-4" />
                        Back to Super Admin
                    </Link>
                    <div className="owner-admin-hero kmj-admin-hero rounded-[1.65rem] p-6 sm:p-8">
                        <div className="flex flex-wrap items-center gap-3">
                            <CreditCard className="h-8 w-8 text-red-500" />
                            <h1 className="text-2xl font-black tracking-tight sm:text-3xl">
                                Payment Gateway Control
                            </h1>
                        </div>
                        <p className="text-muted-foreground mt-3 max-w-3xl text-sm leading-6">
                            KMJ TECHNO international commerce. Merchant
                            approval, credential configuration, transaction
                            proof and license entitlement are separate security
                            gates.
                        </p>
                        <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-amber-500/25 bg-amber-500/10 px-4 py-2 text-xs font-semibold text-amber-200">
                            <LockKeyhole className="h-4 w-4" />
                            {paymentReadiness.live_charging_enabled
                                ? 'Live payments require audited settlement verification'
                                : 'Live charging disabled until reconciled end-to-end tests pass'}
                        </div>
                    </div>
                </header>

                <section
                    className="kmj-pay-metrics"
                    aria-label="Payment readiness summary"
                >
                    {[
                        {
                            label: 'Live charging',
                            value: paymentReadiness.live_charging_enabled
                                ? 'Enabled'
                                : 'Locked',
                            note: 'Stays locked until end-to-end tests pass',
                        },
                        ...visibleGateways.map((gateway) => ({
                            label: `${gateway.label} test keys`,
                            value: gateway.sandbox_credentials_present
                                ? 'Saved'
                                : 'Missing',
                            note: 'Stored encrypted; connection not proven by this alone',
                        })),
                        ...visibleGateways.map((gateway) => ({
                            label: `${gateway.label} webhook`,
                            value: gateway.webhook_verification_configured
                                ? 'Delivery proven'
                                : 'Not proven',
                            note: `${gateway.webhook_events_received} signed event(s) received`,
                        })),
                    ].map((metric) => (
                        <div
                            key={metric.label}
                            className="kmj-admin-metric p-5"
                        >
                            <p className="text-muted-foreground text-sm">
                                {metric.label}
                            </p>
                            <p className="mt-2 text-2xl font-bold tracking-tight">
                                {metric.value}
                            </p>
                            <p className="text-muted-foreground mt-1 text-xs leading-5">
                                {metric.note}
                            </p>
                        </div>
                    ))}
                </section>

                <PaymentNextStep
                    gatewaySettings={gatewaySettings}
                    readiness={visibleGateways}
                    provider={selectedProvider}
                />
                <PaymentGatewayOnboarding
                    gatewaySettings={gatewaySettings}
                    provider={selectedProvider}
                    onProviderChange={setSelectedProvider}
                />
                <OperatorPaymentSettings
                    gatewaySettings={gatewaySettings}
                    selectedProvider={selectedProvider}
                />
                {selectedGateway ? (
                    <section aria-label="Webhook setup" id="webhook-setup">
                        <WebhookSetupGuide gateway={selectedGateway} />
                    </section>
                ) : null}
                <section className="grid w-full gap-4 md:grid-cols-2">
                    {paymentReadiness.providers
                        .filter(
                            (gateway) =>
                                gateway.id === 'razorpay' ||
                                gateway.id === 'cashfree',
                        )
                        .map((gateway) => (
                            <article
                                key={gateway.id}
                                className="bg-card rounded-2xl border p-5"
                            >
                                <div className="flex items-start justify-between gap-3">
                                    <div>
                                        <h2 className="text-lg font-bold">
                                            {gateway.label}
                                        </h2>
                                        <p className="text-muted-foreground mt-1 text-xs font-medium">
                                            {gateway.id === 'razorpay' ||
                                            gateway.id === 'cashfree'
                                                ? 'Primary payment provider'
                                                : 'Optional global provider'}
                                        </p>
                                    </div>
                                    <span className="border-border text-muted-foreground rounded-full border px-3 py-1 text-xs font-semibold">
                                        {gateway.status ===
                                        'sandbox_validation_required'
                                            ? 'Test credentials present'
                                            : gateway.status ===
                                                'credentials_required'
                                              ? 'Configuration required'
                                              : 'Not integrated'}
                                    </span>
                                </div>
                                <dl className="text-foreground/90 mt-5 grid gap-3 text-sm">
                                    <div className="flex items-center justify-between gap-3">
                                        <dt className="text-muted-foreground flex items-center gap-2">
                                            <BadgeCheck className="h-4 w-4" />
                                            Merchant status
                                        </dt>
                                        <dd className="text-right text-xs">
                                            {gateway.merchant_approval ===
                                            'reported_by_owner_not_api_verified'
                                                ? 'Owner reported approved'
                                                : 'Not verified'}
                                        </dd>
                                    </div>
                                    <div className="flex items-center justify-between gap-3">
                                        <dt className="text-muted-foreground flex items-center gap-2">
                                            <KeyRound className="h-4 w-4" />
                                            Server credentials
                                        </dt>
                                        <dd className="text-right text-xs">
                                            {gateway.sandbox_credentials_present
                                                ? 'Present, testing pending'
                                                : 'Not configured'}
                                        </dd>
                                    </div>
                                    <div className="flex items-center justify-between gap-3">
                                        <dt className="text-muted-foreground flex items-center gap-2">
                                            <Globe2 className="h-4 w-4" />
                                            Cross-border approval
                                        </dt>
                                        <dd className="text-right text-xs">
                                            {gateway.international_approval_recorded
                                                ? 'Recorded, test still required'
                                                : 'Not verified'}
                                        </dd>
                                    </div>
                                    <div className="flex items-center justify-between gap-3">
                                        <dt className="text-muted-foreground flex items-center gap-2">
                                            <ShieldCheck className="h-4 w-4" />
                                            Live payment evidence
                                        </dt>
                                        <dd className="text-right text-xs">
                                            {gateway.live_transaction_verified
                                                ? 'Verified'
                                                : 'Not verified'}
                                        </dd>
                                    </div>
                                </dl>
                            </article>
                        ))}
                </section>

                <details className="bg-card w-full rounded-2xl border p-5">
                    <summary className="text-foreground cursor-pointer text-sm font-semibold">
                        Other payment options (planned, not integrated)
                    </summary>
                    <div className="mt-4 flex flex-wrap gap-2">
                        {paymentReadiness.providers
                            .filter(
                                (gateway) =>
                                    gateway.id !== 'razorpay' &&
                                    gateway.id !== 'cashfree',
                            )
                            .map((gateway) => (
                                <span
                                    key={gateway.id}
                                    className="border-border text-muted-foreground rounded-lg border px-3 py-2 text-xs"
                                >
                                    {gateway.label} · Not integrated
                                </span>
                            ))}
                    </div>
                </details>
                <section className="bg-card w-full rounded-2xl border border-white/10 p-6">
                    <h2 className="text-lg font-bold">
                        Required before accepting money
                    </h2>
                    <p className="text-muted-foreground mt-2 text-sm leading-6">
                        Configure secrets only in the approved server secret
                        store, verify merchant-side international methods,
                        complete sandbox order and webhook tests, reconcile
                        captured amounts and currency against our commercial
                        ledger, then authorize production activation with a
                        signed and auditable owner action.
                    </p>
                    <p className="text-muted-foreground mt-3 text-sm">
                        Only owner-initiated sandbox INR 1 order probes are
                        available. No customer money is captured, API secrets
                        stay hidden, and unverified webhooks cannot activate
                        licenses.
                    </p>
                </section>
            </main>
        </>
    );
}
