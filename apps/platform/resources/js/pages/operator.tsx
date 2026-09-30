import type { DragEvent, FormEvent } from 'react';
import { useEffect, useState } from 'react';
import { Head, Link, router, useForm } from '@inertiajs/react';
import {
    BadgeIndianRupee,
    Building2,
    ExternalLink,
    Eye,
    EyeOff,
    GripVertical,
    KeyRound,
    PackagePlus,
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

type ManagedProduct = {
    id: string;
    status: string;
    slug: string;
    name: string;
    lifecycle: string;
    is_public: boolean;
    sort_order: number;
    image_path: string | null;
    summary: string | null;
    purchase_enabled: boolean;
    licensing_enabled: boolean;
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

const productLifecycleOptions = [
    ['available', 'Available'],
    ['preview', 'Preview'],
    ['public-beta', 'Public beta'],
    ['research', 'Research'],
    ['planned', 'Planned'],
    ['retired', 'Retired'],
] as const;

function CommercialProductForm() {
    const form = useForm({
        name: '',
        slug: '',
        lifecycle: 'planned',
        is_public: false,
        image_path: '',
        summary: '',
        purchase_enabled: false,
        licensing_enabled: false,
    });

    const submit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        form.post('/operator/products', {
            preserveScroll: true,
            onSuccess: () => form.reset(),
        });
    };

    return (
        <form onSubmit={submit} className="grid gap-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <label className="space-y-1.5 text-xs font-semibold">
                    <span>Product name</span>
                    <input
                        value={form.data.name}
                        onChange={(event) =>
                            form.setData('name', event.target.value)
                        }
                        placeholder="KMJ Product"
                        className="bg-background h-10 w-full rounded-lg border px-3 text-sm"
                        required
                    />
                </label>
                <label className="space-y-1.5 text-xs font-semibold">
                    <span>Product slug</span>
                    <input
                        value={form.data.slug}
                        onChange={(event) =>
                            form.setData('slug', event.target.value)
                        }
                        placeholder="kmj-product"
                        className="bg-background h-10 w-full rounded-lg border px-3 text-sm"
                        pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
                        required
                    />
                </label>
                <label className="space-y-1.5 text-xs font-semibold">
                    <span>Lifecycle</span>
                    <select
                        value={form.data.lifecycle}
                        onChange={(event) => {
                            const lifecycle = event.target.value;
                            form.setData('lifecycle', lifecycle);
                            if (lifecycle !== 'available') {
                                form.setData('purchase_enabled', false);
                            }
                        }}
                        className="bg-background h-10 w-full rounded-lg border px-3 text-sm"
                    >
                        {productLifecycleOptions.map(([value, label]) => (
                            <option key={value} value={value}>
                                {label}
                            </option>
                        ))}
                    </select>
                </label>
                <label className="space-y-1.5 text-xs font-semibold">
                    <span>Image path</span>
                    <input
                        value={form.data.image_path}
                        onChange={(event) =>
                            form.setData('image_path', event.target.value)
                        }
                        placeholder="/assets/products/product.webp"
                        className="bg-background h-10 w-full rounded-lg border px-3 text-sm"
                    />
                </label>
            </div>

            <label className="space-y-1.5 text-xs font-semibold">
                <span>Customer-facing summary</span>
                <textarea
                    value={form.data.summary}
                    onChange={(event) =>
                        form.setData('summary', event.target.value)
                    }
                    rows={3}
                    maxLength={2000}
                    className="bg-background w-full rounded-lg border px-3 py-2 text-sm"
                    placeholder="Verified product summary"
                />
            </label>

            <div className="flex flex-wrap items-center gap-4 text-xs font-semibold">
                <label className="flex items-center gap-2">
                    <input
                        type="checkbox"
                        checked={form.data.is_public}
                        onChange={(event) =>
                            form.setData('is_public', event.target.checked)
                        }
                    />
                    Publicly visible
                </label>
                <label className="flex items-center gap-2">
                    <input
                        type="checkbox"
                        checked={form.data.purchase_enabled}
                        disabled={form.data.lifecycle !== 'available'}
                        onChange={(event) =>
                            form.setData(
                                'purchase_enabled',
                                event.target.checked,
                            )
                        }
                    />
                    Purchase enabled
                </label>
                <label className="flex items-center gap-2">
                    <input
                        type="checkbox"
                        checked={form.data.licensing_enabled}
                        onChange={(event) =>
                            form.setData(
                                'licensing_enabled',
                                event.target.checked,
                            )
                        }
                    />
                    Licensing enabled
                </label>
                <button
                    type="submit"
                    disabled={form.processing}
                    className="ml-auto inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-red-600 px-4 text-xs font-bold text-white transition hover:bg-red-500 disabled:opacity-50"
                >
                    <PackagePlus className="h-4 w-4" />
                    Create product
                </button>
            </div>

            {Object.keys(form.errors).length > 0 && (
                <div className="text-xs text-red-500">
                    {Object.values(form.errors)[0]}
                </div>
            )}
        </form>
    );
}

function ManagedProductEditor({
    product,
    products,
    onDragStart,
    onDrop,
}: {
    product: ManagedProduct;
    products: ManagedProduct[];
    onDragStart: (productId: string) => void;
    onDrop: (productId: string) => void;
}) {
    const form = useForm({
        name: product.name,
        lifecycle: product.lifecycle,
        is_public: product.is_public,
        image_path: product.image_path ?? '',
        summary: product.summary ?? '',
        purchase_enabled: product.purchase_enabled,
        licensing_enabled: product.licensing_enabled,
    });

    const save = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        form.put(`/operator/products/${product.id}`, {
            preserveScroll: true,
        });
    };

    const move = (offset: -1 | 1) => {
        const index = products.findIndex((item) => item.id === product.id);
        const target = index + offset;
        if (index < 0 || target < 0 || target >= products.length) return;
        const ids = products.map((item) => item.id);
        [ids[index], ids[target]] = [ids[target], ids[index]];
        router.post(
            '/operator/products/reorder',
            { ids },
            { preserveScroll: true },
        );
    };

    return (
        <form
            onSubmit={save}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event: DragEvent<HTMLFormElement>) => {
                event.preventDefault();
                onDrop(product.id);
            }}
            className="group grid gap-4 rounded-2xl border border-white/[0.08] bg-white/[0.025] p-4 transition hover:border-red-500/30 hover:bg-white/[0.04] xl:grid-cols-[1.1fr_.75fr_.85fr_auto]"
        >
            <div className="flex items-center gap-2 xl:col-span-4">
                <button
                    type="button"
                    draggable
                    onDragStart={() => onDragStart(product.id)}
                    aria-label={`Drag ${product.name} to reorder`}
                    className="text-muted-foreground hover:text-foreground cursor-grab rounded-lg border p-2 active:cursor-grabbing"
                >
                    <GripVertical className="h-4 w-4" />
                </button>
                <span className="text-muted-foreground rounded-full border px-2.5 py-1 text-[10px] font-black tracking-wide uppercase">
                    {product.status}
                </span>
                <span className="text-muted-foreground text-[10px] font-bold">
                    Order {product.sort_order}
                </span>
                {product.is_public ? (
                    <Link
                        href={`/products/${product.slug}`}
                        target="_blank"
                        className="ml-auto inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[10px] font-bold transition hover:border-red-500/30 hover:text-red-500"
                    >
                        Public preview
                        <ExternalLink className="h-3 w-3" />
                    </Link>
                ) : (
                    <span className="text-muted-foreground ml-auto text-[10px] font-bold">
                        Hidden from public catalog
                    </span>
                )}
            </div>
            <div className="grid gap-2">
                <input
                    value={form.data.name}
                    onChange={(event) =>
                        form.setData('name', event.target.value)
                    }
                    aria-label={`Name for ${product.name}`}
                    className="h-9 rounded-lg border border-white/10 bg-black/20 px-3 text-sm font-bold text-white"
                    required
                />
                <div className="text-muted-foreground text-[11px]">
                    {product.slug}
                </div>
                <textarea
                    value={form.data.summary}
                    onChange={(event) =>
                        form.setData('summary', event.target.value)
                    }
                    aria-label={`Summary for ${product.name}`}
                    rows={2}
                    maxLength={2000}
                    placeholder="Customer-facing summary"
                    className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-xs text-white"
                />
            </div>

            <div className="grid content-start gap-2">
                <select
                    value={form.data.lifecycle}
                    onChange={(event) => {
                        const lifecycle = event.target.value;
                        form.setData('lifecycle', lifecycle);
                        if (lifecycle !== 'available') {
                            form.setData('purchase_enabled', false);
                        }
                    }}
                    aria-label={`Lifecycle for ${product.name}`}
                    className="h-9 rounded-lg border border-white/10 bg-black/20 px-2 text-xs text-white"
                >
                    {productLifecycleOptions.map(([value, label]) => (
                        <option key={value} value={value}>
                            {label}
                        </option>
                    ))}
                </select>
                <input
                    value={form.data.image_path}
                    onChange={(event) =>
                        form.setData('image_path', event.target.value)
                    }
                    aria-label={`Image path for ${product.name}`}
                    placeholder="/assets/products/..."
                    className="h-9 rounded-lg border border-white/10 bg-black/20 px-2 text-xs text-white"
                />
            </div>

            <div className="grid content-start gap-2 text-xs">
                <label className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
                    Public
                    <input
                        type="checkbox"
                        checked={form.data.is_public}
                        onChange={(event) =>
                            form.setData('is_public', event.target.checked)
                        }
                    />
                </label>
                <label className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
                    Purchase
                    <input
                        type="checkbox"
                        checked={form.data.purchase_enabled}
                        disabled={form.data.lifecycle !== 'available'}
                        onChange={(event) =>
                            form.setData(
                                'purchase_enabled',
                                event.target.checked,
                            )
                        }
                    />
                </label>
                <label className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
                    Licensing
                    <input
                        type="checkbox"
                        checked={form.data.licensing_enabled}
                        onChange={(event) =>
                            form.setData(
                                'licensing_enabled',
                                event.target.checked,
                            )
                        }
                    />
                </label>
            </div>

            <div className="flex flex-col gap-2">
                <button
                    type="submit"
                    disabled={form.processing}
                    className="rounded-lg bg-red-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50"
                >
                    Save
                </button>
                <div className="flex gap-1">
                    <button
                        type="button"
                        aria-label={`Move ${product.name} up`}
                        disabled={products[0]?.id === product.id}
                        onClick={() => move(-1)}
                        className="rounded-lg border px-3 py-2 text-xs font-bold disabled:opacity-30"
                    >
                        ↑
                    </button>
                    <button
                        type="button"
                        aria-label={`Move ${product.name} down`}
                        disabled={
                            products[products.length - 1]?.id === product.id
                        }
                        onClick={() => move(1)}
                        className="rounded-lg border px-3 py-2 text-xs font-bold disabled:opacity-30"
                    >
                        ↓
                    </button>
                </div>
            </div>

            {Object.keys(form.errors).length > 0 && (
                <div className="text-xs text-red-500 xl:col-span-4">
                    {Object.values(form.errors)[0]}
                </div>
            )}
        </form>
    );
}

function ProductManager({ products }: { products: ManagedProduct[] }) {
    const [orderedProducts, setOrderedProducts] = useState(products);
    const [draggedId, setDraggedId] = useState<string | null>(null);
    const [reordering, setReordering] = useState(false);

    useEffect(() => {
        setOrderedProducts(products);
    }, [products]);

    const drop = (targetId: string) => {
        if (draggedId === null || draggedId === targetId || reordering) {
            setDraggedId(null);
            return;
        }

        const sourceIndex = orderedProducts.findIndex(
            (product) => product.id === draggedId,
        );
        const targetIndex = orderedProducts.findIndex(
            (product) => product.id === targetId,
        );

        if (sourceIndex < 0 || targetIndex < 0) {
            setDraggedId(null);
            return;
        }

        const next = [...orderedProducts];
        const [moved] = next.splice(sourceIndex, 1);
        next.splice(targetIndex, 0, moved);
        setOrderedProducts(next);
        setDraggedId(null);
        setReordering(true);

        router.post(
            '/operator/products/reorder',
            { ids: next.map((product) => product.id) },
            {
                preserveScroll: true,
                onError: () => setOrderedProducts(products),
                onFinish: () => setReordering(false),
            },
        );
    };

    const publicCount = orderedProducts.filter(
        (product) => product.is_public,
    ).length;
    const purchasableCount = orderedProducts.filter(
        (product) => product.purchase_enabled,
    ).length;
    const licensingCount = orderedProducts.filter(
        (product) => product.licensing_enabled,
    ).length;
    const hiddenCount = orderedProducts.length - publicCount;

    return (
        <section
            id="product-manager"
            className="relative scroll-mt-6 overflow-hidden rounded-[1.75rem] border border-red-500/15 bg-gradient-to-br from-[#0b0c10] via-[#08090c] to-red-950/20 p-5 text-white shadow-[0_24px_80px_rgba(0,0,0,.18)] sm:p-6"
        >
            <div className="pointer-events-none absolute -top-28 right-0 h-64 w-64 rounded-full bg-red-600/10 blur-3xl" />
            <div className="relative mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
                <div>
                    <div className="text-[10px] font-black tracking-[.14em] text-red-500 uppercase">
                        Governed product authority
                    </div>
                    <h2 className="mt-2 text-xl font-black">Product manager</h2>
                    <p className="text-muted-foreground mt-1 max-w-2xl text-xs leading-5">
                        Edit lifecycle, public visibility, artwork, purchase and
                        licensing controls. Drag products to change the exact
                        landing-page and portfolio order.
                    </p>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[10px] font-black sm:grid-cols-5">
                    <span className="rounded-xl border border-white/10 bg-white/[0.035] px-3 py-2.5">
                        {orderedProducts.length} products
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2.5 text-emerald-300">
                        <Eye className="h-3 w-3" /> {publicCount} public
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.035] px-3 py-2.5 text-white/60">
                        <EyeOff className="h-3 w-3" /> {hiddenCount} hidden
                    </span>
                    <span className="rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-red-300">
                        {purchasableCount} purchasable
                    </span>
                    <span className="rounded-xl border border-white/10 bg-white/[0.035] px-3 py-2.5 text-white/70">
                        {licensingCount} licensed
                    </span>
                    {reordering ? (
                        <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-amber-600 dark:text-amber-400">
                            Saving order…
                        </span>
                    ) : null}
                </div>
            </div>
            <div className="relative mb-4 rounded-xl border border-white/[0.07] bg-white/[0.025] px-4 py-3 text-[11px] leading-5 text-white/50">
                Changes here are the governed source for public visibility,
                lifecycle, artwork and landing-page order. Purchase remains
                fail-closed unless the product is Available.
            </div>
            <div className="relative grid gap-3">
                {orderedProducts.map((product) => (
                    <ManagedProductEditor
                        key={product.id}
                        product={product}
                        products={orderedProducts}
                        onDragStart={setDraggedId}
                        onDrop={drop}
                    />
                ))}
            </div>
        </section>
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

                <section className="bg-card rounded-2xl border p-5 sm:p-6">
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
