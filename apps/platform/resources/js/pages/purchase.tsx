import { Head, Link, useForm } from '@inertiajs/react';
import type { FormEvent } from 'react';
import { useMemo, useState } from 'react';
import {
    ArrowRight,
    BadgeCheck,
    Building2,
    Check,
    CheckCircle2,
    ClipboardList,
    Layers3,
    Search,
    ShieldCheck,
    ShoppingBag,
} from 'lucide-react';
import LockedBrand from '@/components/locked-brand';

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
    requestedProductSlug: string;
};

const actionStyle =
    'inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/[0.05] px-4 text-xs font-semibold text-white transition hover:border-red-500/50 hover:bg-red-500/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-400';
const panel = 'rounded-2xl border border-white/10 bg-[#111318] p-5';

export default function Purchase({
    organizations,
    products,
    recentOrders,
    requestKey,
    requestedProductSlug,
}: PurchaseProps) {
    const [query, setQuery] = useState('');
    const form = useForm({
        organization_id: organizations[0]?.id ?? '',
        product_ids: products
            .filter((product) => product.slug === requestedProductSlug)
            .map((product) => product.id),
        idempotency_key: requestKey,
    });
    const availableProducts = useMemo(
        () =>
            products.filter((product) =>
                [product.name, product.slug]
                    .join(' ')
                    .toLowerCase()
                    .includes(query.trim().toLowerCase()),
            ),
        [products, query],
    );
    const selectedProducts = products.filter((product) =>
        form.data.product_ids.includes(product.id),
    );
    const maxBundle = 10;
    const canRequest =
        organizations.length > 0 &&
        selectedProducts.length > 0 &&
        selectedProducts.length <= maxBundle &&
        !form.processing;

    const toggleProduct = (id: string) => {
        if (form.processing) return;
        if (form.data.product_ids.includes(id)) {
            form.setData(
                'product_ids',
                form.data.product_ids.filter((item) => item !== id),
            );
        } else if (form.data.product_ids.length < maxBundle) {
            form.setData('product_ids', [...form.data.product_ids, id]);
        }
    };

    const submit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (!canRequest) return;
        form.post('/purchase/bundles', {
            preserveScroll: true,
            onSuccess: () => {
                form.setData({
                    ...form.data,
                    product_ids: [],
                    idempotency_key:
                        typeof crypto !== 'undefined' && crypto.randomUUID
                            ? crypto.randomUUID()
                            : requestKey,
                });
            },
        });
    };
    const requestedCount = recentOrders.filter(
        (order) => order.status === 'requested',
    ).length;
    const confirmedCount = recentOrders.filter(
        (order) => order.status === 'confirmed',
    ).length;
    const currencyAmount = (order: Order): string => {
        if (order.amount_minor === null || !order.currency)
            return 'Price awaiting operator confirmation';
        return new Intl.NumberFormat('en', {
            style: 'currency',
            currency: order.currency,
        }).format(order.amount_minor / 100);
    };

    return (
        <>
            <Head title="Service Marketplace — KMJ TECHNO" />
            <main className="min-w-0 space-y-5 bg-[#090a0f] p-4 text-white sm:p-6 lg:p-8">
                <section className="rounded-2xl border border-red-500/20 bg-gradient-to-br from-[#1b1219] to-[#111318] p-5 sm:p-7">
                    <LockedBrand compact className="mb-4" />
                    <div className="flex flex-wrap items-center justify-between gap-4">
                        <div>
                            <div className="flex items-center gap-2 text-xs font-bold text-red-300">
                                <ShoppingBag className="h-4 w-4" />
                                Unified service marketplace
                            </div>
                            <h1 className="mt-3 text-2xl font-black sm:text-3xl">
                                Build your KMJ service bundle
                            </h1>
                            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-300">
                                Select one or several commercially eligible
                                services and request them together. Your
                                organization keeps separate product access,
                                licensing and entitlement policies.
                            </p>
                        </div>
                        <Link href="/dashboard" className={actionStyle}>
                            My services <ArrowRight className="h-4 w-4" />
                        </Link>
                    </div>
                </section>

                <div className="grid gap-3 sm:grid-cols-3">
                    {[
                        {
                            title: 'One selection',
                            detail: 'Request up to 10 services in one action',
                            icon: Layers3,
                        },
                        {
                            title: 'Governed approval',
                            detail: 'Operator verifies commercial terms and payment',
                            icon: ShieldCheck,
                        },
                        {
                            title: 'Separate entitlements',
                            detail: 'Access activates only after verified fulfillment',
                            icon: BadgeCheck,
                        },
                    ].map(({ title, detail, icon: Icon }) => (
                        <div key={title} className={panel}>
                            <Icon className="h-5 w-5 text-red-400" />
                            <h2 className="mt-3 text-sm font-bold">{title}</h2>
                            <p className="mt-1 text-xs leading-5 text-zinc-300">
                                {detail}
                            </p>
                        </div>
                    ))}
                </div>

                <form
                    onSubmit={submit}
                    className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_340px]"
                >
                    <section className={panel} aria-labelledby="choose-products-heading">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                                <h2
                                    id="choose-products-heading"
                                    className="text-lg font-bold"
                                >
                                    Available to request
                                </h2>
                                <p className="mt-1 text-xs text-zinc-400">
                                    Only products with active commercial
                                    fulfillment policies appear here.
                                </p>
                            </div>
                            <label className="flex min-h-10 items-center gap-2 rounded-lg border border-white/15 bg-[#090a0f] px-3">
                                <Search className="h-4 w-4 text-zinc-400" />
                                <span className="sr-only">Search available products</span>
                                <input
                                    type="search"
                                    value={query}
                                    onChange={(event) =>
                                        setQuery(event.target.value)
                                    }
                                    placeholder="Search products"
                                    className="w-40 border-0 bg-transparent py-2 text-xs text-white outline-none placeholder:text-zinc-400"
                                />
                            </label>
                        </div>

                        {products.length === 0 ? (
                            <div className="mt-5 rounded-xl border border-dashed border-white/15 p-8 text-center text-xs text-zinc-300">
                                No services are currently eligible for
                                commercial requests. Explore the public catalog
                                for product lifecycle details.
                                <div className="mt-4">
                                    <Link href="/products" className={actionStyle}>
                                        Browse all KMJ products
                                    </Link>
                                </div>
                            </div>
                        ) : (
                            <div className="mt-5 grid gap-3 sm:grid-cols-2">
                                {availableProducts.map((product) => {
                                    const selected =
                                        form.data.product_ids.includes(
                                            product.id,
                                        );
                                    return (
                                        <label
                                            key={product.id}
                                            className={
                                                'flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition ' +
                                                (selected
                                                    ? 'border-red-500/70 bg-red-500/10'
                                                    : 'border-white/10 bg-[#0b0d12] hover:border-white/30')
                                            }
                                        >
                                            <input
                                                type="checkbox"
                                                className="sr-only"
                                                checked={selected}
                                                disabled={
                                                    form.processing ||
                                                    (!selected &&
                                                        selectedProducts.length >=
                                                            maxBundle)
                                                }
                                                onChange={() =>
                                                    toggleProduct(product.id)
                                                }
                                            />
                                            <span
                                                aria-hidden="true"
                                                className={
                                                    'grid h-6 w-6 shrink-0 place-items-center rounded-md border ' +
                                                    (selected
                                                        ? 'border-red-500 bg-red-600 text-white'
                                                        : 'border-white/30 bg-white/5')
                                                }
                                            >
                                                {selected && (
                                                    <Check className="h-4 w-4" />
                                                )}
                                            </span>
                                            <span className="min-w-0">
                                                <span className="block text-sm font-bold text-white">
                                                    {product.name}
                                                </span>
                                                <span className="mt-1 block text-[11px] text-zinc-400">
                                                    {product.slug}
                                                </span>
                                                <Link
                                                    href={
                                                        '/products/' +
                                                        encodeURIComponent(
                                                            product.slug,
                                                        )
                                                    }
                                                    className="mt-3 inline-flex text-xs font-medium text-red-300 hover:underline"
                                                    onClick={(event) =>
                                                        event.stopPropagation()
                                                    }
                                                >
                                                    Product details
                                                </Link>
                                            </span>
                                        </label>
                                    );
                                })}
                            </div>
                        )}
                    </section>

                    <aside
                        className={panel + ' h-fit xl:sticky xl:top-4'}
                        aria-labelledby="bundle-summary-heading"
                    >
                        <h2
                            id="bundle-summary-heading"
                            className="text-lg font-bold"
                        >
                            Your service bundle
                        </h2>
                        <p className="mt-1 text-xs text-zinc-400">
                            {selectedProducts.length} of {maxBundle} products selected
                        </p>
                        <label className="mt-5 block text-xs font-semibold">
                            <span className="flex items-center gap-2">
                                <Building2 className="h-4 w-4 text-red-400" />
                                Purchase for organization
                            </span>
                            <select
                                aria-label="Purchase organization"
                                value={form.data.organization_id}
                                onChange={(event) =>
                                    form.setData(
                                        'organization_id',
                                        event.target.value,
                                    )
                                }
                                disabled={
                                    form.processing ||
                                    organizations.length === 0
                                }
                                className="mt-2 min-h-11 w-full rounded-xl border border-white/15 bg-[#090a0f] px-3 text-xs text-white"
                            >
                                {organizations.length === 0 && (
                                    <option value="">
                                        No authorized purchasing organization
                                    </option>
                                )}
                                {organizations.map((organization) => (
                                    <option
                                        key={organization.id}
                                        value={organization.id}
                                    >
                                        {organization.name} · {organization.role}
                                    </option>
                                ))}
                            </select>
                        </label>
                        <div className="mt-5 space-y-2" aria-live="polite">
                            {selectedProducts.length === 0 ? (
                                <p className="rounded-xl border border-dashed border-white/15 p-4 text-xs text-zinc-400">
                                    Select one or more products to continue.
                                </p>
                            ) : (
                                selectedProducts.map((product) => (
                                    <div
                                        key={product.id}
                                        className="flex items-center justify-between gap-3 rounded-lg border border-white/10 p-3 text-xs"
                                    >
                                        <span className="min-w-0 font-semibold">
                                            {product.name}
                                        </span>
                                        <button
                                            type="button"
                                            onClick={() =>
                                                toggleProduct(product.id)
                                            }
                                            disabled={form.processing}
                                            className="shrink-0 text-red-300 hover:text-red-200 disabled:opacity-40"
                                            aria-label={
                                                'Remove ' + product.name
                                            }
                                        >
                                            Remove
                                        </button>
                                    </div>
                                ))
                            )}
                        </div>
                        {(form.errors.product_ids ||
                            form.errors.organization_id ||
                            form.errors.idempotency_key) && (
                            <div
                                role="alert"
                                className="mt-4 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-200"
                            >
                                {form.errors.product_ids ||
                                    form.errors.organization_id ||
                                    form.errors.idempotency_key}
                            </div>
                        )}
                        <p className="mt-5 text-xs leading-5 text-zinc-300">
                            Final price and payment instructions are confirmed
                            by KMJ. This request is not a payment and does not
                            activate licenses automatically.
                        </p>
                        <button
                            type="submit"
                            className="mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-bold text-white hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={!canRequest}
                        >
                            <ShoppingBag className="h-4 w-4" />
                            {form.processing
                                ? 'Submitting securely…'
                                : 'Request ' +
                                  selectedProducts.length +
                                  (selectedProducts.length === 1
                                      ? ' service'
                                      : ' services')}
                        </button>
                        <p className="mt-3 text-[11px] leading-5 text-zinc-400">
                            One submission creates a separately tracked order
                            for each selected product.
                        </p>
                    </aside>
                </form>

                <section className={panel} aria-labelledby="orders-heading">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                            <h2 id="orders-heading" className="flex items-center gap-2 text-lg font-bold">
                                <ClipboardList className="h-5 w-5 text-red-400" />
                                Recent requests
                            </h2>
                            <p className="mt-1 text-xs text-zinc-400">
                                Only your authorized organizations and your own
                                commercial requests are shown.
                            </p>
                        </div>
                        <div className="flex flex-wrap gap-2 text-xs">
                            <span className="rounded-lg border border-amber-500/30 px-3 py-2 text-amber-300">
                                {requestedCount} requested
                            </span>
                            <span className="rounded-lg border border-emerald-500/30 px-3 py-2 text-emerald-300">
                                {confirmedCount} confirmed
                            </span>
                        </div>
                    </div>
                    {recentOrders.length === 0 ? (
                        <div className="mt-5 rounded-xl border border-dashed border-white/15 p-6 text-center text-xs text-zinc-400">
                            No purchase requests yet.
                        </div>
                    ) : (
                        <div className="mt-4 grid gap-3 md:grid-cols-2">
                            {recentOrders.map((order) => (
                                <article
                                    key={order.id}
                                    className="rounded-xl border border-white/10 bg-[#0b0d12] p-4"
                                >
                                    <div className="flex items-start justify-between gap-2">
                                        <div>
                                            <h3 className="text-sm font-semibold">
                                                {order.product_name}
                                            </h3>
                                            <p className="mt-1 text-xs text-zinc-400">
                                                {order.organization_name}
                                            </p>
                                        </div>
                                        <span
                                            className={
                                                'rounded-lg border px-2 py-1 text-[10px] capitalize ' +
                                                (order.status === 'confirmed'
                                                    ? 'border-emerald-500/30 text-emerald-300'
                                                    : 'border-amber-500/30 text-amber-300')
                                            }
                                        >
                                            {order.status === 'confirmed' && (
                                                <CheckCircle2 className="mr-1 inline h-3 w-3" />
                                            )}
                                            {order.status}
                                        </span>
                                    </div>
                                    <p className="mt-3 text-xs text-zinc-300">
                                        {currencyAmount(order)}
                                    </p>
                                    <p className="mt-2 text-[10px] text-zinc-500">
                                        Order {order.id.slice(0, 8)}…
                                    </p>
                                </article>
                            ))}
                        </div>
                    )}
                </section>

                <footer className="border-t border-white/10 pt-4 text-xs text-zinc-400">
                    Each order requires verified commercial approval and
                    explicit entitlement fulfillment before activation.
                </footer>
            </main>
        </>
    );
}
