import { useState, type FormEvent } from 'react';
import { Head, Link, router, useForm } from '@inertiajs/react';
import OperatorModuleNavigation from '@/components/operator-module-navigation';
import {
    CommercialProductForm,
    ProductManager,
    type ManagedProduct,
} from '@/components/operator-product-manager';
import {
    BadgeIndianRupee,
    Search,
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
    lifecycle: string;
    is_public: boolean;
    purchase_enabled: boolean;
    licensing_enabled: boolean;
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
    canonicalProductCount: number;
    missingCanonicalSlugs: string[];
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
    canonicalProductCount,
    missingCanonicalSlugs,
    recentOrders,
    products,
}: OperatorProps) {
    const [catalogSearch, setCatalogSearch] = useState('');
    const [catalogFilter, setCatalogFilter] = useState<
        'all' | 'public' | 'missing_policy' | 'licensed'
    >('all');
    const visibleProducts = catalogProducts.filter((product) => {
        const search = catalogSearch.trim().toLowerCase();
        const matchesSearch =
            search === '' ||
            `${product.name} ${product.slug}`.toLowerCase().includes(search);
        const matchesState =
            catalogFilter === 'all' ||
            (catalogFilter === 'public' && product.is_public) ||
            (catalogFilter === 'missing_policy' &&
                product.active_policy_count === 0) ||
            (catalogFilter === 'licensed' &&
                product.active_entitlement_count > 0);

        return matchesSearch && matchesState;
    });
    const missingPolicyCount = catalogProducts.filter(
        (product) => product.active_policy_count === 0,
    ).length;
    const publishedCount = catalogProducts.filter(
        (product) => product.is_public,
    ).length;

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
                                Registered products are listed below. Missing
                                canonical registrations are reported separately.
                                No product gains a licence or payment access
                                merely by appearing here.
                            </p>
                        </div>
                        <span className="text-muted-foreground rounded-full border px-3 py-1 text-[10px] font-bold">
                            {catalogProducts.length} registered /{' '}
                            {canonicalProductCount} canonical
                        </span>
                    </div>
                    {missingCanonicalSlugs.length > 0 && (
                        <div
                            role="status"
                            className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4"
                        >
                            <p className="text-sm font-bold">
                                {missingCanonicalSlugs.length} canonical
                                products are not registered in this database
                            </p>
                            <p className="text-muted-foreground mt-1 text-xs leading-5">
                                Missing records are not customer licenses.
                                Reconcile the canonical catalog in staging,
                                verify existing product settings, then perform
                                an audited production sync.
                            </p>
                            <div className="mt-3 flex flex-wrap gap-2">
                                {missingCanonicalSlugs.map((slug) => (
                                    <span
                                        key={slug}
                                        className="rounded-lg border px-2 py-1 font-mono text-[11px]"
                                    >
                                        {slug}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                    <div className="mt-5 grid gap-3 sm:grid-cols-3">
                        <div className="bg-background/50 rounded-xl border p-3">
                            <p className="text-muted-foreground text-xs">
                                Registered products
                            </p>
                            <p className="mt-1 text-2xl font-black">
                                {catalogProducts.length}
                            </p>
                        </div>
                        <div className="bg-background/50 rounded-xl border p-3">
                            <p className="text-muted-foreground text-xs">
                                Public product pages
                            </p>
                            <p className="mt-1 text-2xl font-black">
                                {publishedCount}
                            </p>
                        </div>
                        <div className="bg-background/50 rounded-xl border p-3">
                            <p className="text-muted-foreground text-xs">
                                Missing active entitlement policy
                            </p>
                            <p className="mt-1 text-2xl font-black">
                                {missingPolicyCount}
                            </p>
                        </div>
                    </div>
                    <div className="mt-5 grid gap-3 md:grid-cols-[1fr_auto]">
                        <label className="relative block">
                            <Search className="text-muted-foreground absolute top-3 left-3 size-4" />
                            <span className="sr-only">
                                Search product inventory
                            </span>
                            <input
                                value={catalogSearch}
                                onChange={(event) =>
                                    setCatalogSearch(event.target.value)
                                }
                                className="bg-background h-11 w-full rounded-xl border pr-3 pl-10 text-sm"
                                placeholder="Find a product by name or slug"
                            />
                        </label>
                        <label className="flex items-center gap-2 text-xs">
                            <span className="sr-only">
                                Product inventory filter
                            </span>
                            <select
                                value={catalogFilter}
                                onChange={(event) =>
                                    setCatalogFilter(
                                        event.target
                                            .value as typeof catalogFilter,
                                    )
                                }
                                className="bg-background h-11 rounded-xl border px-3 text-sm"
                            >
                                <option value="all">
                                    All registered products
                                </option>
                                <option value="public">
                                    Published catalog
                                </option>
                                <option value="missing_policy">
                                    Missing policy
                                </option>
                                <option value="licensed">
                                    With active entitlements
                                </option>
                            </select>
                        </label>
                    </div>
                    <p
                        className="text-muted-foreground mt-2 text-xs"
                        role="status"
                    >
                        {visibleProducts.length} of {catalogProducts.length}{' '}
                        products shown. Public listing does not grant customer
                        access.
                    </p>
                    <div className="mt-3 overflow-hidden rounded-xl border">
                        <div className="divide-y">
                            {visibleProducts.map((product) => (
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
                                    <div className="space-y-1 text-xs">
                                        <div className="font-bold tracking-wide uppercase">
                                            {product.status}
                                        </div>
                                        <div className="text-muted-foreground">
                                            {product.lifecycle}
                                        </div>
                                        <div className="text-muted-foreground">
                                            {product.is_public
                                                ? 'Public catalog'
                                                : 'Internal / hidden'}
                                        </div>
                                    </div>
                                    <div>
                                        <p className="text-muted-foreground">
                                            Policies:{' '}
                                            <strong className="text-foreground">
                                                {product.active_policy_count}
                                            </strong>
                                        </p>
                                        <p className="text-muted-foreground mt-1">
                                            Purchase:{' '}
                                            {product.purchase_enabled
                                                ? 'Configured'
                                                : 'Disabled'}
                                        </p>
                                        <p className="text-muted-foreground mt-1">
                                            Licensing:{' '}
                                            {product.licensing_enabled
                                                ? 'Enabled'
                                                : 'Disabled'}
                                        </p>
                                    </div>
                                    <div>
                                        <span className="text-muted-foreground">
                                            Actual active entitlements:{' '}
                                        </span>
                                        <strong className="text-foreground">
                                            {product.active_entitlement_count}
                                        </strong>
                                        <Link
                                            href={`/products/${encodeURIComponent(product.slug)}`}
                                            className="mt-2 block font-semibold text-red-500"
                                        >
                                            Public product view
                                        </Link>
                                    </div>
                                </div>
                            ))}
                            {visibleProducts.length === 0 && (
                                <p className="text-muted-foreground p-6 text-center text-sm">
                                    No products match this search or filter.
                                </p>
                            )}
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
