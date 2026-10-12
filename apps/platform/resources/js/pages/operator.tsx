import type { FormEvent } from 'react';
import { Head, Link, router, useForm } from '@inertiajs/react';
import OperatorModuleNavigation from '@/components/operator-module-navigation';
import {
    CommercialProductForm,
    ProductManager,
    type ManagedProduct,
} from '@/components/operator-product-manager';
import {
    BadgeIndianRupee,
    Building2,
    ExternalLink,
    KeyRound,
    ShieldCheck,
    ShoppingCart,
    Users,
} from 'lucide-react';

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
    can_manage_license: boolean;
};

type CatalogProduct = {
    id: string;
    slug: string;
    name: string;
    status: string;
    active_policy_count: number;
    active_entitlement_count: number;
};

type OperatorProps = {
    metrics: {
        users: number;
        organizations: number;
        entitlements: number;
        orders: number;
        confirmed_orders: number;
    };
    catalogProducts: CatalogProduct[];
    recentOrders: RecentOrder[];
    products: ManagedProduct[];
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

function Metric({
    icon: Icon,
    label,
    value,
}: {
    icon: typeof Users;
    label: string;
    value: number;
}) {
    return (
        <div className="bg-card rounded-2xl border p-5">
            <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground text-xs font-semibold">
                    {label}
                </span>
                <Icon className="h-4 w-4 text-red-500" />
            </div>
            <div className="mt-4 text-3xl font-black tracking-tight">
                {value}
            </div>
        </div>
    );
}

function ManualPaymentConfirmation({ order }: { order: RecentOrder }) {
    const form = useForm({
        currency: 'INR',
        amount_minor: '',
        confirmation_reference: '',
    });

    const submit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
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
                    type="number"
                    min="1"
                    step="1"
                    value={form.data.amount_minor}
                    onChange={(event) =>
                        form.setData('amount_minor', event.target.value)
                    }
                    placeholder="Amount in paise/cents"
                    className="h-9 rounded-lg border border-white/10 bg-black/20 px-2 text-xs text-white"
                    aria-label="Amount in minor currency units"
                    required
                />
            </div>
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
                disabled={form.processing}
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

export default function Operator({
    metrics,
    catalogProducts,
    recentOrders,
    products,
}: OperatorProps) {
    return (
        <>
            <Head title="Platform Operator" />
            <div className="flex h-full flex-1 flex-col gap-6 overflow-x-auto p-4 sm:p-6">
                <OperatorModuleNavigation active="overview" />
                <section className="from-background via-background overflow-hidden rounded-2xl border bg-gradient-to-br to-red-950/10 p-6 sm:p-8">
                    <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
                        <div className="max-w-2xl">
                            <div className="inline-flex items-center gap-2 rounded-full border border-red-500/15 bg-red-500/5 px-3 py-1 text-xs font-bold text-red-500">
                                <ShieldCheck className="h-3.5 w-3.5" />
                                Platform Owner · Passkey gated
                            </div>
                            <h1 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl">
                                KMJ Operator Console
                            </h1>
                            <p className="text-muted-foreground mt-3 max-w-xl text-sm leading-6">
                                Privileged platform authority is separated from
                                customer access. Manual payment evidence is
                                confirmed first; entitlement fulfillment and
                                license issuance remain explicit governed steps.
                            </p>
                        </div>
                        <div className="flex flex-wrap items-center gap-3">
                            <div className="rounded-xl border border-emerald-500/15 bg-emerald-500/5 px-4 py-3 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                                Owner authority verified
                            </div>
                            <Link
                                href="/operator/payments"
                                className="inline-flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs font-bold text-red-500 transition hover:bg-red-500/20"
                            >
                                Manage payment gateways
                                <ExternalLink className="h-4 w-4" />
                            </Link>
                        </div>
                    </div>
                </section>

                <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
                    <Metric icon={Users} label="Users" value={metrics.users} />
                    <Metric
                        icon={Building2}
                        label="Organizations"
                        value={metrics.organizations}
                    />
                    <Metric
                        icon={KeyRound}
                        label="Entitlements"
                        value={metrics.entitlements}
                    />
                    <Metric
                        icon={ShoppingCart}
                        label="Commercial orders"
                        value={metrics.orders}
                    />
                    <Metric
                        icon={BadgeIndianRupee}
                        label="Confirmed orders"
                        value={metrics.confirmed_orders}
                    />
                </section>

                <section className="bg-card rounded-2xl border p-5 sm:p-6">
                    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
                        <div>
                            <h2 className="font-bold">
                                Product & licensing matrix
                            </h2>
                            <p className="text-muted-foreground mt-1 text-xs">
                                Canonical products stay visible even before
                                commercial activation. Licensing remains
                                fail-closed until an active entitlement policy
                                exists.
                            </p>
                        </div>
                        <span className="text-muted-foreground rounded-full border px-3 py-1 text-[10px] font-bold">
                            {catalogProducts.length} canonical products
                        </span>
                    </div>
                    <div className="mt-5 overflow-hidden rounded-xl border">
                        <div className="divide-y">
                            {catalogProducts.map((product) => (
                                <div
                                    key={product.id}
                                    className="grid gap-3 px-4 py-3 text-xs md:grid-cols-[1.2fr_.9fr_.7fr_.7fr] md:items-center"
                                >
                                    <div>
                                        <div className="font-black">
                                            {product.name}
                                        </div>
                                        <div className="text-muted-foreground mt-1 font-mono text-[10px]">
                                            {product.slug}
                                        </div>
                                    </div>
                                    <div className="font-bold tracking-wide uppercase">
                                        {product.status}
                                    </div>
                                    <div>
                                        <span className="text-muted-foreground">
                                            Policies{' '}
                                        </span>
                                        <span className="font-black">
                                            {product.active_policy_count}
                                        </span>
                                    </div>
                                    <div>
                                        <span className="text-muted-foreground">
                                            Entitlements{' '}
                                        </span>
                                        <span className="font-black">
                                            {product.active_entitlement_count}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                <section className="bg-card rounded-2xl border p-5 sm:p-6">
                    <div className="mb-5">
                        <h2 className="font-bold">Commercial catalog</h2>
                        <p className="text-muted-foreground mt-1 text-xs">
                            Activate a product so customers can submit governed
                            purchase requests. Price is recorded only when
                            payment evidence is confirmed.
                        </p>
                    </div>
                    <CommercialProductForm />
                </section>

                <ProductManager products={products} />

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
                                                <button
                                                    type="button"
                                                    className="inline-flex rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-[10px] font-bold text-red-500 transition hover:bg-red-500/15"
                                                    data-test="fulfill-order"
                                                    onClick={() =>
                                                        router.post(
                                                            `/operator/orders/${order.id}/fulfill`,
                                                            {},
                                                            {
                                                                preserveScroll: true,
                                                            },
                                                        )
                                                    }
                                                >
                                                    Issue entitlement
                                                </button>
                                            ) : canIssueSandboxLicense(
                                                  order,
                                              ) ? (
                                                <button
                                                    type="button"
                                                    className="inline-flex rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-[10px] font-bold text-emerald-600 transition hover:bg-emerald-500/15 dark:text-emerald-400"
                                                    data-test="issue-sandbox-license"
                                                    onClick={() =>
                                                        router.post(
                                                            `/operator/orders/${order.id}/sandbox-license`,
                                                        )
                                                    }
                                                >
                                                    Issue sandbox license
                                                </button>
                                            ) : (
                                                <span className="text-muted-foreground text-[10px] font-semibold">
                                                    No action
                                                </span>
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
