import { Head } from '@inertiajs/react';
import {
    BadgeIndianRupee,
    Building2,
    KeyRound,
    ShieldCheck,
    ShoppingCart,
    Users,
} from 'lucide-react';

type RecentOrder = {
    id: string;
    organization_id: string;
    product_id: string;
    status: string;
    currency: string | null;
    amount_minor: number | null;
    created_at: string | null;
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
                                customer access. This console starts read-only
                                and will receive governed commerce, entitlement
                                and operations actions behind explicit
                                capability gates.
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
                                Read-only commercial evidence. Fulfillment
                                remains a separate governed action.
                            </p>
                        </div>
                        <span className="text-muted-foreground rounded-full border px-3 py-1 text-[10px] font-bold">
                            No auto-entitlement
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
                                        className="grid gap-3 px-4 py-4 text-xs sm:grid-cols-[1.2fr_1fr_1fr_auto] sm:items-center"
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
                                        <div className="text-right font-bold">
                                            {order.amount_minor !== null &&
                                            order.currency
                                                ? `${order.currency} ${(order.amount_minor / 100).toFixed(2)}`
                                                : 'Pending'}
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
