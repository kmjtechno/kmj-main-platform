import { minorDigits, toMinorUnits } from '@/lib/money-minor';
import { type FormEvent, useState } from 'react';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogTitle,
    DialogTrigger,
} from '@/components/ui/dialog';
import { Head, Link, router, useForm } from '@inertiajs/react';
import OperatorCommandOs from '@/components/operator-command-os';
import OperatorControlOverview from '@/components/operator-control-overview';

type FulfillmentState =
    | 'awaiting_confirmation'
    | 'ready'
    | 'entitled'
    | 'blocked_no_policy';

type RecentOrder = {
    id: string;
    organization_id: string;
    product_id: string;
    status: string;
    currency: string | null;
    amount_minor: number | null;
    created_at: string | null;
    fulfillment_state: FulfillmentState;
    entitlement_id: string | null;
    refunded_minor: number;
    can_manage_license: boolean;
};

type CatalogProduct = {
    id: string;
    slug: string;
    name: string;
    status: string;
    lifecycle: string;
    is_public: boolean;
    purchase_enabled: boolean;
    licensing_enabled: boolean;
    active_policy_count: number;
    active_entitlement_count: number;
};

type OperatorProps = {
    ownerView: 'dashboard' | 'command-center';
    metrics: {
        users: number;
        organizations: number;
        entitlements: number;
        orders: number;
        confirmed_orders: number;
        confirmed_inr_revenue_minor: number;
    };
    catalogProducts: CatalogProduct[];
    canonicalProductCount: number;
    missingCanonicalSlugs: string[];
    recentOrders: RecentOrder[];
};

const fulfillmentLabels: Record<FulfillmentState, string> = {
    awaiting_confirmation: 'Awaiting confirmation',
    ready: 'Ready for fulfillment',
    entitled: 'Entitlement active',
    blocked_no_policy: 'Blocked · no active policy',
};

function canIssueSandboxLicense(order: RecentOrder): boolean {
    return (
        order.fulfillment_state === 'entitled' &&
        order.entitlement_id !== null &&
        order.can_manage_license
    );
}

/**
 * Requires a conscious owner action before sending access-granting requests.
 * Server-side owner/passkey and fulfillment checks stay authoritative.
 */
function ConfirmOwnerAction({
    orderId,
    action,
}: {
    orderId: string;
    action: 'fulfill' | 'sandbox-license';
}) {
    const [open, setOpen] = useState(false);
    const grantingAccess = action === 'fulfill';
    const label = grantingAccess
        ? 'Issue entitlement'
        : 'Issue sandbox license';
    const path = `/operator/orders/${orderId}/${action}`;

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <button
                    type="button"
                    data-test={
                        grantingAccess
                            ? 'fulfill-order'
                            : 'issue-sandbox-license'
                    }
                    className={
                        grantingAccess
                            ? 'inline-flex rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-[10px] font-bold text-red-500 transition hover:bg-red-500/15'
                            : 'inline-flex rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-[10px] font-bold text-emerald-600 transition hover:bg-emerald-500/15 dark:text-emerald-400'
                    }
                >
                    {label}
                </button>
            </DialogTrigger>
            <DialogContent className="border-red-900 bg-[#0b1119] text-white">
                <DialogTitle>Confirm {label.toLowerCase()}</DialogTitle>
                <DialogDescription className="text-slate-300">
                    {grantingAccess
                        ? 'Verify organization, product and independent payment evidence before granting access. Recorded orders do not prove gateway settlement.'
                        : 'Issues a test-only sandbox license. This is not a paid production commercial license.'}
                </DialogDescription>
                <p className="text-xs break-all text-slate-400">
                    Order: {orderId}
                </p>
                <div className="flex flex-wrap justify-end gap-3">
                    <button
                        type="button"
                        onClick={() => setOpen(false)}
                        className="rounded-lg border border-white/30 px-4 py-2 text-xs"
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        data-test="confirm-owner-commercial-action"
                        onClick={() => {
                            setOpen(false);
                            router.post(path, {}, { preserveScroll: true });
                        }}
                        className="rounded-lg bg-red-600 px-4 py-2 text-xs font-semibold text-white"
                    >
                        Confirm {label.toLowerCase()}
                    </button>
                </div>
            </DialogContent>
        </Dialog>
    );
}

function ManualPaymentConfirmation({ order }: { order: RecentOrder }) {
    const form = useForm({
        currency: 'INR',
        amount_minor: '',
        confirmation_reference: '',
    });
    // The person types the normal amount (e.g. 1499.50); the server contract
    // still receives integer minor units, converted without floating point.
    const minor = toMinorUnits(form.data.amount_minor, form.data.currency);
    const digits = minorDigits(form.data.currency);

    const submit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (minor === null) return;
        form.transform((data) => ({ ...data, amount_minor: String(minor) }));
        form.post(`/operator/orders/${order.id}/confirm`, {
            preserveScroll: true,
        });
    };

    return (
        <form onSubmit={submit} className="grid min-w-64 gap-2">
            <div className="grid grid-cols-[72px_1fr] gap-2">
                <input
                    value={form.data.currency}
                    onChange={(event) =>
                        form.setData(
                            'currency',
                            event.target.value.toUpperCase(),
                        )
                    }
                    maxLength={3}
                    className="bg-background h-9 rounded-lg border px-2 text-xs font-bold uppercase"
                    aria-label="Currency"
                    required
                />
                <input
                    type="text"
                    inputMode="decimal"
                    value={form.data.amount_minor}
                    onChange={(event) =>
                        form.setData('amount_minor', event.target.value)
                    }
                    placeholder={`Amount received (e.g. ${digits === 0 ? '1499' : '1499.00'})`}
                    className="h-9 rounded-lg border border-white/10 bg-black/20 px-2 text-xs text-white"
                    aria-label="Amount received in normal currency units"
                    required
                />
            </div>
            {form.data.amount_minor !== '' && (
                <div
                    className={
                        minor === null
                            ? 'text-[10px] text-red-500'
                            : 'text-[10px] text-slate-400'
                    }
                    role="status"
                >
                    {minor === null
                        ? `Enter a valid amount with at most ${digits} decimal place(s).`
                        : `Will record ${form.data.currency} ${(minor / 10 ** digits).toFixed(digits)} (${minor} minor units).`}
                </div>
            )}
            <input
                value={form.data.confirmation_reference}
                onChange={(event) =>
                    form.setData('confirmation_reference', event.target.value)
                }
                placeholder="UTR / payment reference"
                className="h-9 rounded-lg border border-white/10 bg-black/20 px-2 text-xs text-white"
                aria-label="Payment confirmation reference"
                required
            />
            <button
                type="submit"
                disabled={form.processing || minor === null}
                className="inline-flex h-9 items-center justify-center rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 text-[10px] font-bold text-amber-600 transition hover:bg-amber-500/15 disabled:opacity-50 dark:text-amber-400"
            >
                Confirm payment evidence
            </button>
            {(form.errors.currency ||
                form.errors.amount_minor ||
                form.errors.confirmation_reference) && (
                <div className="text-[10px] text-red-500">
                    {form.errors.currency ||
                        form.errors.amount_minor ||
                        form.errors.confirmation_reference}
                </div>
            )}
        </form>
    );
}

/**
 * Records a refund the owner already made in the payment provider dashboard.
 * It moves no money, does not change the order, and does not revoke any license.
 * The server (Super Admin + passkey + confirmed-amount cap) stays authoritative.
 */
/**
 * After a refund is recorded, the owner may revoke the access that order gave. This is a separate,
 * explicit and audited step: a refund record alone never changes a license or entitlement.
 */
function RefundRevokeAccess({ order }: { order: RecentOrder }) {
    const [busy, setBusy] = useState(false);

    return (
        <button
            type="button"
            data-test="revoke-access-after-refund"
            disabled={busy}
            className="mt-1 rounded-lg border border-red-500/40 px-3 py-1 text-[10px] font-semibold text-red-400 disabled:opacity-50"
            onClick={() => {
                if (
                    !window.confirm(
                        'Revoke the access this order gave? This ends the active entitlement for this organization and product. A refund record alone does not do this.',
                    )
                ) {
                    return;
                }
                setBusy(true);
                router.post(
                    `/operator/orders/${order.id}/refund-revoke-access`,
                    {},
                    { preserveScroll: true, onFinish: () => setBusy(false) },
                );
            }}
        >
            Revoke access
        </button>
    );
}

function RefundRecord({ order }: { order: RecentOrder }) {
    const [open, setOpen] = useState(false);
    const currency = order.currency ?? 'INR';
    const digits = minorDigits(currency);
    const form = useForm({
        amount_minor: '',
        reason: '',
        provider_refund_reference: '',
        request_key: '',
    });
    const minor = toMinorUnits(form.data.amount_minor, currency);
    const remaining = (order.amount_minor ?? 0) - order.refunded_minor;

    const submit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (minor === null || minor < 1 || minor > remaining) return;
        form.transform((data) => ({
            ...data,
            amount_minor: String(minor),
            request_key: `refund:${order.id}:${crypto.randomUUID()}`,
        }));
        form.post(`/operator/orders/${order.id}/refund-record`, {
            preserveScroll: true,
            onSuccess: () => {
                form.reset();
                setOpen(false);
            },
        });
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <button
                    type="button"
                    data-test="record-refund"
                    className="mt-2 inline-flex rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[10px] font-bold text-amber-600 transition hover:bg-amber-500/15 dark:text-amber-400"
                >
                    Record refund
                </button>
            </DialogTrigger>
            <DialogContent className="border-red-900 bg-[#0b1119] text-white">
                <DialogTitle>Record refund already made</DialogTitle>
                <DialogDescription className="text-slate-300">
                    Only records a refund you already issued in the payment
                    provider dashboard. This does not send money, change the
                    order, or revoke the license.
                </DialogDescription>
                <p className="text-xs break-all text-slate-400">
                    Order: {order.id} · Refunded so far {currency}{' '}
                    {(order.refunded_minor / 10 ** digits).toFixed(digits)} ·
                    Remaining {currency}{' '}
                    {(remaining / 10 ** digits).toFixed(digits)}
                </p>
                <form onSubmit={submit} className="grid gap-2">
                    <input
                        type="text"
                        inputMode="decimal"
                        value={form.data.amount_minor}
                        onChange={(event) =>
                            form.setData('amount_minor', event.target.value)
                        }
                        placeholder="Refund amount (normal currency units)"
                        className="h-9 rounded-lg border border-white/10 bg-black/20 px-2 text-xs text-white"
                        aria-label="Refund amount"
                        required
                    />
                    {form.data.amount_minor !== '' &&
                        (minor === null || minor < 1 || minor > remaining) && (
                            <div
                                className="text-[10px] text-red-500"
                                role="status"
                            >
                                Enter a valid amount up to the remaining{' '}
                                {(remaining / 10 ** digits).toFixed(digits)}.
                            </div>
                        )}
                    <input
                        value={form.data.reason}
                        onChange={(event) =>
                            form.setData('reason', event.target.value)
                        }
                        placeholder="Reason"
                        maxLength={240}
                        className="h-9 rounded-lg border border-white/10 bg-black/20 px-2 text-xs text-white"
                        aria-label="Refund reason"
                        required
                    />
                    <input
                        value={form.data.provider_refund_reference}
                        onChange={(event) =>
                            form.setData(
                                'provider_refund_reference',
                                event.target.value,
                            )
                        }
                        placeholder="Provider refund reference (optional)"
                        maxLength={120}
                        className="h-9 rounded-lg border border-white/10 bg-black/20 px-2 text-xs text-white"
                        aria-label="Provider refund reference"
                    />
                    <button
                        type="submit"
                        data-test="confirm-record-refund"
                        disabled={
                            form.processing ||
                            minor === null ||
                            minor < 1 ||
                            minor > remaining
                        }
                        className="rounded-lg bg-red-600 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
                    >
                        Record refund
                    </button>
                    {(form.errors as Record<string, string | undefined>)
                        .refund && (
                        <div className="text-[10px] text-red-500" role="alert">
                            {(form.errors as Record<string, string>).refund}
                        </div>
                    )}
                </form>
            </DialogContent>
        </Dialog>
    );
}

export default function Operator({
    ownerView,
    metrics,
    catalogProducts,
    canonicalProductCount,
    missingCanonicalSlugs,
    recentOrders,
}: OperatorProps) {
    return (
        <>
            <Head
                title={
                    ownerView === 'dashboard'
                        ? 'KMJ Enterprise Command OS · Super Admin'
                        : 'KMJ Command Center · Super Admin'
                }
            />
            <div className="owner-dashboard-page kmj-admin-shell kmj-os-page flex h-full min-w-0 flex-1 flex-col gap-6 overflow-x-auto p-0 sm:p-0">
                {ownerView === 'dashboard' ? (
                    <>
                        <OperatorCommandOs
                            metrics={metrics}
                            catalogProducts={catalogProducts}
                            recentOrders={recentOrders}
                            missingCanonicalSlugs={missingCanonicalSlugs}
                        />

                        <details className="kmj-os-advanced rounded-2xl border p-4 sm:p-6">
                            <summary className="cursor-pointer text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500">
                                Advanced owner insights and audit-safe legacy
                                controls
                            </summary>
                            <Link
                                href="/operator/products"
                                className="border-border hover:bg-accent ml-2 inline-flex min-h-10 items-center rounded-lg border px-3 text-xs font-semibold"
                            >
                                Product Management
                            </Link>
                            <div className="mt-5">
                                <OperatorControlOverview
                                    products={catalogProducts}
                                    orders={recentOrders}
                                    canonicalProductCount={
                                        canonicalProductCount
                                    }
                                    missingCanonicalSlugs={
                                        missingCanonicalSlugs
                                    }
                                />
                            </div>
                        </details>
                    </>
                ) : (
                    <section
                        className="bg-card mx-3 mt-3 rounded-2xl border p-4 sm:mx-6 sm:mt-6 sm:p-6"
                        aria-label="Owner task-first Command Center"
                    >
                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                                <p className="text-muted-foreground text-xs font-bold tracking-wide uppercase">
                                    KMJ TECHNO · Protected Owner Workspace
                                </p>
                                <h1 className="mt-1 text-2xl font-bold">
                                    Command Center
                                </h1>
                                <p className="text-muted-foreground mt-2 max-w-2xl text-sm">
                                    Manage owner workspaces, review real catalog
                                    and order evidence, and open governed tools.
                                </p>
                            </div>
                            <Link
                                href="/super-admin"
                                className="border-border hover:bg-accent inline-flex min-h-10 items-center rounded-lg border px-4 py-2 text-sm font-semibold"
                            >
                                Back to Enterprise Dashboard
                            </Link>
                        </div>
                        <div className="mt-6">
                            <OperatorControlOverview
                                products={catalogProducts}
                                orders={recentOrders}
                                canonicalProductCount={canonicalProductCount}
                                missingCanonicalSlugs={missingCanonicalSlugs}
                            />
                        </div>
                    </section>
                )}

                <section
                    id="commercial-orders"
                    className="bg-card rounded-2xl border p-5 sm:p-6"
                >
                    <div className="flex items-center justify-between gap-4">
                        <div>
                            <h2 className="font-bold">
                                Recent commercial orders
                            </h2>
                            <p className="text-muted-foreground mt-1 text-xs">
                                Confirm external payment evidence, then fulfill
                                entitlement and license access explicitly.
                            </p>
                        </div>
                        <span className="text-muted-foreground rounded-full border px-3 py-1 text-[10px] font-bold">
                            Manual owner action
                        </span>
                    </div>
                    {recentOrders.length === 0 ? (
                        <div className="text-muted-foreground mt-6 rounded-xl border border-dashed p-8 text-center text-sm">
                            No commercial orders yet.
                        </div>
                    ) : (
                        <div className="mt-5 overflow-hidden rounded-xl border">
                            <div className="divide-y">
                                {recentOrders.map((order) => (
                                    <div
                                        key={order.id}
                                        className="grid gap-3 px-4 py-4 text-xs lg:grid-cols-[1.15fr_0.9fr_0.65fr_1fr_0.8fr_1.35fr] lg:items-center"
                                    >
                                        <div>
                                            <div className="font-bold">
                                                {order.id}
                                            </div>
                                            <div className="text-muted-foreground mt-1">
                                                Org {order.organization_id}
                                            </div>
                                        </div>
                                        <div className="text-muted-foreground">
                                            Product {order.product_id}
                                        </div>
                                        <div className="font-semibold tracking-wide uppercase">
                                            {order.status}
                                        </div>
                                        <div>
                                            <span
                                                className="inline-flex rounded-full border px-2.5 py-1 text-[10px] font-bold"
                                                data-test="fulfillment-state"
                                            >
                                                {
                                                    fulfillmentLabels[
                                                        order.fulfillment_state
                                                    ]
                                                }
                                            </span>
                                        </div>
                                        <div className="font-bold lg:text-right">
                                            {order.amount_minor !== null &&
                                            order.currency
                                                ? `${order.currency} ${(order.amount_minor / 100).toFixed(2)}`
                                                : 'Pending'}
                                        </div>
                                        <div className="lg:text-right">
                                            {order.status === 'requested' ? (
                                                <ManualPaymentConfirmation
                                                    order={order}
                                                />
                                            ) : order.fulfillment_state ===
                                              'ready' ? (
                                                <ConfirmOwnerAction
                                                    orderId={order.id}
                                                    action="fulfill"
                                                />
                                            ) : canIssueSandboxLicense(
                                                  order,
                                              ) ? (
                                                <ConfirmOwnerAction
                                                    orderId={order.id}
                                                    action="sandbox-license"
                                                />
                                            ) : (
                                                <span className="text-muted-foreground text-[10px] font-semibold">
                                                    No action
                                                </span>
                                            )}
                                            {order.status === 'confirmed' &&
                                                order.amount_minor !== null &&
                                                order.refunded_minor <
                                                    order.amount_minor && (
                                                    <RefundRecord
                                                        order={order}
                                                    />
                                                )}
                                            {order.refunded_minor > 0 &&
                                                order.fulfillment_state ===
                                                    'entitled' && (
                                                    <RefundRevokeAccess
                                                        order={order}
                                                    />
                                                )}
                                            {order.refunded_minor > 0 && (
                                                <div
                                                    className="text-muted-foreground mt-1 text-[10px]"
                                                    data-test="refunded-total"
                                                >
                                                    Refunded {order.currency}{' '}
                                                    {(
                                                        order.refunded_minor /
                                                        100
                                                    ).toFixed(2)}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </section>
            </div>
        </>
    );
}
