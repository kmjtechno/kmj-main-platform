import { formatIstDate } from '@/lib/format-ist-date-time';
import { minorDigits } from '@/lib/money-minor';
import { orderProgress } from '@/lib/order-progress';
import type { FormEvent } from 'react';
import { Head, Link, useForm } from '@inertiajs/react';
import {
    BadgeIndianRupee,
    Building2,
    CheckCircle2,
    Clock3,
    PackageCheck,
    ShoppingCart,
} from 'lucide-react';

type Organization = {
    id: string;
    name: string;
    role: string;
};

type Product = {
    id: string;
    slug: string;
    name: string;
};

type Order = {
    id: string;
    organization_id: string;
    organization_name: string;
    product_id: string;
    product_name: string;
    status: string;
    currency: string | null;
    amount_minor: number | null;
    created_at: string | null;
};

type PurchaseProps = {
    organizations: Organization[];
    products: Product[];
    recentOrders: Order[];
    requestKey: string;
};

const purchaseSteps = [
    {
        title: 'Request',
        detail: 'You send this request. No payment is taken on this page.',
    },
    {
        title: 'KMJ confirms payment',
        detail: 'A KMJ operator agrees price and payment with you, then confirms it.',
    },
    {
        title: 'Access activated',
        detail: 'After confirmation, access appears on your dashboard.',
    },
] as const;

function StatusBadge({ status }: { status: string }) {
    const confirmed = status === 'confirmed';

    return (
        <span
            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase ${
                confirmed
                    ? 'border-emerald-500/20 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400'
                    : 'border-amber-500/20 bg-amber-500/5 text-amber-600 dark:text-amber-400'
            }`}
        >
            {confirmed ? (
                <CheckCircle2 className="h-3 w-3" />
            ) : (
                <Clock3 className="h-3 w-3" />
            )}
            {orderProgress(status).label}
        </span>
    );
}

export default function Purchase({
    organizations,
    products,
    recentOrders,
    requestKey,
}: PurchaseProps) {
    const form = useForm({
        organization_id: organizations[0]?.id ?? '',
        product_id: products[0]?.id ?? '',
        idempotency_key: requestKey,
    });

    const canRequest =
        organizations.length > 0 && products.length > 0 && !form.processing;

    const submit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        form.post('/purchase/orders', {
            preserveScroll: true,
            onSuccess: () => {
                if (typeof crypto !== 'undefined' && crypto.randomUUID) {
                    form.setData('idempotency_key', crypto.randomUUID());
                }
            },
        });
    };

    return (
        <>
            <Head title="Purchase Center" />
            <div className="flex h-full flex-1 flex-col gap-6 overflow-x-auto p-4 sm:p-6">
                <section className="from-background via-background overflow-hidden rounded-2xl border bg-gradient-to-br to-emerald-950/10 p-6 sm:p-8">
                    <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
                        <div className="max-w-2xl">
                            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/5 px-3 py-1 text-xs font-bold text-emerald-600 dark:text-emerald-400">
                                <BadgeIndianRupee className="h-3.5 w-3.5" />
                                Purchase requests
                            </div>
                            <h1 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl">
                                KMJ Purchase Center
                            </h1>
                            <p className="text-muted-foreground mt-3 max-w-xl text-sm leading-6">
                                Request an active KMJ product for your
                                organization. Payment evidence is confirmed by a
                                Platform Owner before access is released through
                                the entitlement and licensing authority chain.
                            </p>
                        </div>
                        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-xs font-semibold text-amber-600 dark:text-amber-400">
                            Payment confirmation does not automatically grant
                            product access.
                        </div>
                    </div>
                </section>

                <div className="grid gap-6 xl:grid-cols-[1fr_1.35fr]">
                    <section className="bg-card rounded-2xl border p-5 sm:p-6">
                        <div className="flex items-center gap-2">
                            <ShoppingCart className="h-5 w-5 text-red-500" />
                            <h2 className="font-bold">Request a purchase</h2>
                        </div>
                        <p className="text-muted-foreground mt-1 text-xs">
                            Choose an organization and active commercial
                            product. Price/payment facts are confirmed
                            separately by the operator.
                        </p>
                        <ol className="mt-4 grid gap-2 text-xs sm:grid-cols-3">
                            {purchaseSteps.map((step, index) => (
                                <li
                                    key={step.title}
                                    className="bg-muted/30 rounded-lg border px-3 py-2"
                                >
                                    <span className="font-bold">
                                        {index + 1}. {step.title}
                                    </span>
                                    <span className="text-muted-foreground mt-1 block leading-5">
                                        {step.detail}
                                    </span>
                                </li>
                            ))}
                        </ol>

                        <form onSubmit={submit} className="mt-6 space-y-4">
                            <label className="block space-y-2 text-xs font-semibold">
                                <span className="flex items-center gap-2">
                                    <Building2 className="h-3.5 w-3.5 text-red-500" />
                                    Organization
                                </span>
                                <select
                                    value={form.data.organization_id}
                                    onChange={(event) =>
                                        form.setData(
                                            'organization_id',
                                            event.target.value,
                                        )
                                    }
                                    className="bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                    disabled={organizations.length === 0}
                                >
                                    {organizations.length === 0 ? (
                                        <option value="">
                                            No purchase-enabled organization
                                        </option>
                                    ) : (
                                        organizations.map((organization) => (
                                            <option
                                                key={organization.id}
                                                value={organization.id}
                                            >
                                                {organization.name} ·{' '}
                                                {organization.role}
                                            </option>
                                        ))
                                    )}
                                </select>
                                {organizations.length === 0 && (
                                    <span className="text-muted-foreground block text-xs font-normal">
                                        Your account has no organization that
                                        can purchase yet. Contact{' '}
                                        <a
                                            className="underline"
                                            href="mailto:info@kmjtechno.com"
                                        >
                                            info@kmjtechno.com
                                        </a>{' '}
                                        and we will help.
                                    </span>
                                )}
                            </label>

                            <label className="block space-y-2 text-xs font-semibold">
                                <span className="flex items-center gap-2">
                                    <PackageCheck className="h-3.5 w-3.5 text-red-500" />
                                    Product
                                </span>
                                <select
                                    value={form.data.product_id}
                                    onChange={(event) =>
                                        form.setData(
                                            'product_id',
                                            event.target.value,
                                        )
                                    }
                                    className="bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                    disabled={products.length === 0}
                                >
                                    {products.length === 0 ? (
                                        <option value="">
                                            No commercial product is active yet
                                        </option>
                                    ) : (
                                        products.map((product) => (
                                            <option
                                                key={product.id}
                                                value={product.id}
                                            >
                                                {product.name}
                                            </option>
                                        ))
                                    )}
                                </select>
                                {products.length === 0 && (
                                    <span className="text-muted-foreground block text-xs font-normal">
                                        No product is open for purchase yet.{' '}
                                        <Link
                                            className="underline"
                                            href="/products"
                                        >
                                            Browse the catalog
                                        </Link>
                                        .
                                    </span>
                                )}
                            </label>

                            {(form.errors.organization_id ||
                                form.errors.product_id ||
                                form.errors.idempotency_key) && (
                                <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-500">
                                    {form.errors.organization_id ||
                                        form.errors.product_id ||
                                        form.errors.idempotency_key}
                                </div>
                            )}

                            <button
                                type="submit"
                                disabled={!canRequest}
                                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-bold text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                <ShoppingCart className="h-4 w-4" />
                                {form.processing
                                    ? 'Submitting…'
                                    : 'Request purchase'}
                            </button>
                        </form>
                    </section>

                    <section className="bg-card rounded-2xl border p-5 sm:p-6">
                        <h2 className="font-bold">Your commercial requests</h2>
                        <p className="text-muted-foreground mt-1 text-xs">
                            Requested → payment confirmed → access activated.
                            Activated products appear on your{' '}
                            <Link className="underline" href="/dashboard">
                                dashboard
                            </Link>
                            .
                        </p>

                        {recentOrders.length === 0 ? (
                            <div className="text-muted-foreground mt-6 rounded-xl border border-dashed p-8 text-center text-sm">
                                No purchase requests yet.
                            </div>
                        ) : (
                            <div className="mt-5 space-y-3">
                                {recentOrders.map((order) => (
                                    <div
                                        key={order.id}
                                        className="bg-background/50 rounded-xl border p-4"
                                    >
                                        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                                            <div>
                                                <div className="font-bold">
                                                    {order.product_name}
                                                </div>
                                                <div className="text-muted-foreground mt-1 text-xs">
                                                    {order.organization_name}
                                                </div>
                                            </div>
                                            <StatusBadge
                                                status={order.status}
                                            />
                                        </div>
                                        <p className="text-muted-foreground mt-3 text-xs leading-5">
                                            {
                                                orderProgress(order.status)
                                                    .message
                                            }
                                        </p>
                                        <div className="text-muted-foreground mt-4 flex flex-wrap gap-x-5 gap-y-2 text-[11px]">
                                            <span>
                                                Order {order.id.slice(0, 8)}…
                                            </span>
                                            <span>
                                                Requested{' '}
                                                {formatIstDate(
                                                    order.created_at,
                                                )}
                                            </span>
                                            <span>
                                                {order.amount_minor !== null &&
                                                order.currency
                                                    ? `${order.currency} ${(order.amount_minor / 10 ** minorDigits(order.currency)).toFixed(minorDigits(order.currency))}`
                                                    : 'Amount pending operator confirmation'}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </section>
                </div>
            </div>
        </>
    );
}
