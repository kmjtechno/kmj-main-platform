import { Head, router } from '@inertiajs/react';
import {
    BadgeIndianRupee,
    Building2,
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

type OperatorProps = {
    metrics: {
        users: number;
        organizations: number;
        entitlements: number;
        orders: number;
        confirmed_orders: number;
    };
    recentOrders: RecentOrder[];
};

const fulfillmentLabels: Record<FulfillmentState, string> = {
    awaiting_confirmation: 'Awaiting confirmation',
    ready: 'Ready for fulfillment',
    entitled: 'Entitlement active',
    blocked_no_policy: 'Blocked · no active policy',
};

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

export default function Operator({ metrics, recentOrders }: OperatorProps) {
    return (
        <>
            <Head title="Platform Operator" />
            <div className="flex h-full flex-1 flex-col gap-6 overflow-x-auto p-4 sm:p-6">
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
                                customer access. Confirmed orders can be fulfilled
                                into entitlements and handed directly into the
                                governed sandbox license lifecycle.
                            </p>
                        </div>
                        <div className="rounded-xl border border-emerald-500/15 bg-emerald-500/5 px-4 py-3 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                            Owner authority verified
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
                    <div className="flex items-center justify-between gap-4">
                        <div>
                            <h2 className="font-bold">
                                Recent commercial orders
                            </h2>
                            <p className="text-muted-foreground mt-1 text-xs">
                                Deterministic readiness, explicit entitlement
                                fulfillment and governed license handoff.
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
                                        className="grid gap-3 px-4 py-4 text-xs sm:grid-cols-[1.2fr_1fr_0.8fr_1.2fr_auto_auto] sm:items-center"
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
                                        <div className="font-bold sm:text-right">
                                            {order.amount_minor !== null &&
                                            order.currency
                                                ? `${order.currency} ${(order.amount_minor / 100).toFixed(2)}`
                                                : 'Pending'}
                                        </div>
                                        <div className="sm:text-right">
                                            {order.fulfillment_state ===
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
                                            ) : order.fulfillment_state ===
                                                  'entitled' &&
                                              order.entitlement_id &&
                                              order.can_manage_license ? (
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
