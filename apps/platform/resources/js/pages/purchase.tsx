import { featureLabel } from '@/lib/customer-labels';
import { formatIstDate } from '@/lib/format-ist-date-time';
import { minorDigits } from '@/lib/money-minor';
import { orderProgress } from '@/lib/order-progress';
import type { FormEvent } from 'react';
import { Head, Link, useForm } from '@inertiajs/react';
import {
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
    features: string[];
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
        detail: 'KMJ tells you the price. After you agree and pay, KMJ confirms it.',
    },
    {
        title: 'Access activated',
        detail: 'KMJ then switches on your product, and it appears on My Services.',
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

    const selectedProduct = products.find(
        (product) => product.id === form.data.product_id,
    );

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
                <section className="bg-card rounded-2xl border p-5 sm:p-7">
                    <h1 className="text-3xl font-black tracking-tight">
                        Purchase Center
                    </h1>
                    <p className="text-muted-foreground mt-2 max-w-2xl text-sm leading-6">
                        Ask to buy a KMJ product for your organization. Nothing
                        is charged on this page, and sending a request does not
                        switch anything on.
                    </p>
                </section>

                <div className="grid gap-6 xl:grid-cols-[1fr_1.35fr]">
                    <section className="bg-card rounded-2xl border p-5 sm:p-6">
                        <div className="flex items-center gap-2">
                            <ShoppingCart className="h-5 w-5 text-red-500" />
                            <h2 className="font-bold">Request a purchase</h2>
                        </div>
                        <ol className="text-muted-foreground mt-3 space-y-2 text-sm leading-6">
                            {purchaseSteps.map((step, index) => (
                                <li key={step.title}>
                                    <span className="text-foreground font-bold">
                                        {index + 1}. {step.title}.
                                    </span>{' '}
                                    {step.detail}
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
                                            No organization that can buy
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
                                            No product is open for purchase
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

                            {selectedProduct && (
                                <div
                                    className="bg-muted/40 rounded-xl border p-4 text-sm"
                                    data-testid="purchase-plan-summary"
                                >
                                    <dl className="space-y-3">
                                        <div>
                                            <dt className="font-bold">Price</dt>
                                            <dd className="text-muted-foreground">
                                                Not published yet. KMJ sends you
                                                the price, and you pay only if
                                                you agree.
                                            </dd>
                                        </div>
                                        <div>
                                            <dt className="font-bold">
                                                What gets switched on
                                            </dt>
                                            <dd className="text-muted-foreground">
                                                {selectedProduct.features
                                                    .map(featureLabel)
                                                    .join(', ') ||
                                                    'KMJ confirms this with the price.'}
                                            </dd>
                                        </div>
                                    </dl>
                                </div>
                            )}

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
                                className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-bold text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                <ShoppingCart className="h-4 w-4" />
                                {form.processing
                                    ? 'Submitting…'
                                    : 'Request purchase'}
                            </button>
                        </form>
                    </section>

                    <section className="bg-card rounded-2xl border p-5 sm:p-6">
                        <h2 className="font-bold">Your requests</h2>
                        <p className="text-muted-foreground mt-1 text-sm">
                            Activated products appear on{' '}
                            <Link className="underline" href="/dashboard">
                                My Services
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
                                                    : 'Price not confirmed yet'}
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
