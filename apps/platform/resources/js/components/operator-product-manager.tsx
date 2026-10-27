import ProductContentEditor, {
    emptyProductContent,
    type ProductContent,
    type GenerationConfiguration,
} from '@/components/product-content-editor';
import type { DragEvent, FormEvent } from 'react';
import { useEffect, useState } from 'react';
import { Link, router, useForm, usePage } from '@inertiajs/react';
import {
    ExternalLink,
    Eye,
    EyeOff,
    GripVertical,
    PackagePlus,
} from 'lucide-react';

export type ManagedProduct = {
    id: string;
    status: string;
    slug: string;
    name: string;
    lifecycle: string;
    category: string;
    is_public: boolean;
    sort_order: number;
    image_path: string | null;
    summary: string | null;
    content?: Partial<ProductContent> | null;
    purchase_enabled: boolean;
    licensing_enabled: boolean;
};

const productLifecycleOptions = [
    ['available', 'Available'],
    ['preview', 'Preview'],
    ['public-beta', 'Public beta'],
    ['research', 'Research'],
    ['planned', 'Planned'],
    ['retired', 'Retired'],
] as const;

export const productCategoryOptions = [
    ['cloud', 'Cloud & Infrastructure'],
    ['cinema', 'Cinema & Immersive'],
    ['industrial', 'Industrial & Calibration'],
    ['developer', 'Developer & AI'],
    ['business', 'Business & Platform'],
    ['other', 'Other'],
] as const;

// Fully blank FAQ rows are editor placeholders, not public product content.
// Partial answers are intentionally preserved so server validation can flag them.
export function normalizedProductContent(
    content: ProductContent,
): ProductContent {
    return {
        ...content,
        features: content.features
            .map((feature) => feature.trim())
            .filter(Boolean),
        faqs: content.faqs
            .map((faq) => ({
                question: faq.question.trim(),
                answer: faq.answer.trim(),
            }))
            .filter((faq) => faq.question !== '' || faq.answer !== ''),
    };
}

export function CommercialProductForm({
    generation,
}: {
    generation?: GenerationConfiguration;
}) {
    const [studioBusy, setStudioBusy] = useState(false);
    const [slugEdited, setSlugEdited] = useState(false);
    const form = useForm({
        name: '',
        slug: '',
        lifecycle: 'planned',
        category: 'other',
        is_public: false,
        image_path: '',
        summary: '',
        content: emptyProductContent(),
        purchase_enabled: false,
        licensing_enabled: false,
    });

    const submit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        form.transform((data) => ({
            ...data,
            content: normalizedProductContent(data.content),
        }));
        form.post('/operator/products', {
            preserveScroll: true,
            onSuccess: () => {
                form.reset();
                setSlugEdited(false);
            },
        });
    };

    return (
        <form onSubmit={submit} className="grid gap-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <label className="space-y-1.5 text-xs font-semibold">
                    <span>Product name</span>
                    <input
                        value={form.data.name}
                        onChange={(event) => {
                            const name = event.target.value;
                            form.setData('name', name);
                            if (!slugEdited)
                                form.setData(
                                    'slug',
                                    name
                                        .toLowerCase()
                                        .normalize('NFKD')
                                        .replace(/[\u0300-\u036f]/g, '')
                                        .replace(/[^a-z0-9]+/g, '-')
                                        .replace(/^-|-$/g, '')
                                        .slice(0, 96),
                                );
                        }}
                        placeholder="KMJ Product"
                        className="bg-background h-10 w-full rounded-lg border px-3 text-sm"
                        required
                    />
                </label>
                <label className="space-y-1.5 text-xs font-semibold">
                    <span>Product slug</span>
                    <input
                        value={form.data.slug}
                        onChange={(event) => {
                            setSlugEdited(true);
                            form.setData('slug', event.target.value);
                        }}
                        placeholder="kmj-product"
                        className="bg-background h-10 w-full rounded-lg border px-3 text-sm"
                        pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
                        required
                    />
                </label>
                <label className="space-y-1.5 text-xs font-semibold">
                    <span>Lifecycle</span>
                    <select
                        aria-label="Lifecycle"
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
                <span>Category</span>
                <select
                    value={form.data.category}
                    onChange={(event) =>
                        form.setData('category', event.target.value)
                    }
                    className="bg-background h-10 w-full rounded-lg border px-3 text-sm"
                >
                    {productCategoryOptions.map(([value, label]) => (
                        <option key={value} value={value}>
                            {label}
                        </option>
                    ))}
                </select>
            </label>

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

            <ProductContentEditor
                name={form.data.name}
                category={form.data.category}
                summary={form.data.summary}
                imagePath={form.data.image_path}
                content={form.data.content}
                generation={generation}
                onContent={(content) => form.setData('content', content)}
                onImage={(path) => form.setData('image_path', path)}
                onSuggestedName={(name) => {
                    form.setData((current) => ({
                        ...current,
                        name,
                        slug: slugEdited
                            ? current.slug
                            : name
                                  .toLowerCase()
                                  .normalize('NFKD')
                                  .replace(/[\u0300-\u036f]/g, '')
                                  .replace(/[^a-z0-9]+/g, '-')
                                  .replace(/^-|-$/g, '')
                                  .slice(0, 96),
                        content: {
                            ...current.content,
                            image_alt:
                                current.content.image_alt === current.name
                                    ? name
                                    : current.content.image_alt,
                        },
                    }));
                }}
                onDraft={(summary, content) =>
                    form.setData((current) => ({
                        ...current,
                        summary,
                        content,
                    }))
                }
                onBusy={setStudioBusy}
            />
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
                    disabled={form.processing || studioBusy}
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

export function ManagedProductEditor({
    product,
    products,
    onDragStart,
    onDrop,
    allowReorder,
    generation,
    initiallyEditing = false,
}: {
    product: ManagedProduct;
    products: ManagedProduct[];
    onDragStart: (productId: string) => void;
    onDrop: (productId: string) => void;
    allowReorder: boolean;
    generation?: GenerationConfiguration;
    initiallyEditing?: boolean;
}) {
    const pageUrl = usePage().url;
    const [editing, setEditing] = useState(
        () =>
            initiallyEditing ||
            new URLSearchParams(pageUrl.split('?')[1] ?? '').get('edit') ===
                product.id,
    );
    const [studioBusy, setStudioBusy] = useState(false);
    const form = useForm({
        name: product.name,
        lifecycle: product.lifecycle,
        category: product.category,
        is_public: product.is_public,
        image_path: product.image_path ?? '',
        summary: product.summary ?? '',
        content: { ...emptyProductContent(), ...product.content },
        purchase_enabled: product.purchase_enabled,
        licensing_enabled: product.licensing_enabled,
    });

    useEffect(() => {
        if (initiallyEditing) {
            setEditing(true);
            document
                .getElementById(`catalog-product-${product.id}`)
                ?.scrollIntoView({ block: 'start' });
        }
    }, [initiallyEditing, product.id]);

    const save = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        form.transform((data) => ({
            ...data,
            content: normalizedProductContent(data.content),
        }));
        form.put(`/operator/products/${product.id}`, {
            preserveScroll: true,
            onSuccess: () => setEditing(false),
        });
    };

    const move = (offset: -1 | 1) => {
        if (!allowReorder) return;
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
            id={`catalog-product-${product.id}`}
            onSubmit={save}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event: DragEvent<HTMLFormElement>) => {
                event.preventDefault();
                if (allowReorder) onDrop(product.id);
            }}
            className="group grid gap-4 rounded-2xl border border-white/[0.08] bg-white/[0.025] p-4 transition hover:border-red-500/30 hover:bg-white/[0.04] xl:grid-cols-[1.1fr_.75fr_.85fr_auto]"
        >
            <div className="flex min-w-0 flex-wrap items-center gap-2 xl:col-span-4">
                <button
                    type="button"
                    draggable={allowReorder}
                    disabled={!allowReorder}
                    onDragStart={() => {
                        if (allowReorder) onDragStart(product.id);
                    }}
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
                <div className="min-w-0">
                    <div className="truncate text-sm font-bold">
                        {product.name}
                    </div>
                    <div className="text-muted-foreground truncate text-[11px]">
                        {product.category} · {product.lifecycle}
                    </div>
                </div>
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
                <button
                    type="button"
                    aria-expanded={editing}
                    aria-controls={`editor-${product.id}`}
                    onClick={() => setEditing((value) => !value)}
                    className="rounded-lg border border-red-500/30 px-3 py-2 text-xs font-bold text-red-400 hover:bg-red-500/10"
                >
                    {editing ? 'Close' : 'Edit'}
                </button>
            </div>
            {editing && (
                <div
                    id={`editor-${product.id}`}
                    className="grid gap-4 xl:col-span-4 xl:grid-cols-[1.1fr_.75fr_.85fr_auto]"
                >
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
                        <select
                            value={form.data.category}
                            onChange={(event) =>
                                form.setData('category', event.target.value)
                            }
                            aria-label={`Category for ${product.name}`}
                            className="h-9 rounded-lg border border-white/10 bg-black/20 px-2 text-xs text-white"
                        >
                            {productCategoryOptions.map(([value, label]) => (
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
                                    form.setData(
                                        'is_public',
                                        event.target.checked,
                                    )
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

                    <div className="xl:col-span-4">
                        <ProductContentEditor
                            name={form.data.name}
                            category={form.data.category}
                            summary={form.data.summary}
                            imagePath={form.data.image_path}
                            content={form.data.content}
                            generation={generation}
                            onContent={(content) =>
                                form.setData('content', content)
                            }
                            onImage={(path) => form.setData('image_path', path)}
                            onSuggestedName={(name) =>
                                form.setData((current) => ({
                                    ...current,
                                    name,
                                    content: {
                                        ...current.content,
                                        image_alt:
                                            current.content.image_alt ===
                                            current.name
                                                ? name
                                                : current.content.image_alt,
                                    },
                                }))
                            }
                            onDraft={(summary, content) =>
                                form.setData((current) => ({
                                    ...current,
                                    summary,
                                    content,
                                }))
                            }
                            onBusy={setStudioBusy}
                        />
                    </div>
                    <div className="flex flex-col gap-2">
                        <button
                            type="submit"
                            disabled={form.processing || studioBusy}
                            className="rounded-lg bg-red-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50"
                        >
                            Save
                        </button>
                        <div className="flex gap-1">
                            <button
                                type="button"
                                aria-label={`Move ${product.name} up`}
                                disabled={
                                    !allowReorder ||
                                    products[0]?.id === product.id
                                }
                                onClick={() => move(-1)}
                                className="rounded-lg border px-3 py-2 text-xs font-bold disabled:opacity-30"
                            >
                                ↑
                            </button>
                            <button
                                type="button"
                                aria-label={`Move ${product.name} down`}
                                disabled={
                                    !allowReorder ||
                                    products[products.length - 1]?.id ===
                                        product.id
                                }
                                onClick={() => move(1)}
                                className="rounded-lg border px-3 py-2 text-xs font-bold disabled:opacity-30"
                            >
                                ↓
                            </button>
                        </div>
                    </div>

                    {form.isDirty && !form.processing && (
                        <p
                            className="text-muted-foreground text-xs xl:col-span-4"
                            role="status"
                        >
                            Unsaved editor changes — review product details and
                            save before closing this entry.
                        </p>
                    )}
                    {Object.keys(form.errors).length > 0 && (
                        <div className="text-xs text-red-500 xl:col-span-4">
                            {Object.values(form.errors)[0]}
                        </div>
                    )}
                </div>
            )}
        </form>
    );
}

export function ProductManager({
    products,
    search = '',
    category = 'all',
    lifecycle = 'all',
    generation,
    activeProductId = null,
}: {
    products: ManagedProduct[];
    search?: string;
    category?: string;
    lifecycle?: string;
    generation?: GenerationConfiguration;
    activeProductId?: string | null;
}) {
    const [orderedProducts, setOrderedProducts] = useState(products);
    const [draggedId, setDraggedId] = useState<string | null>(null);
    const [reordering, setReordering] = useState(false);

    useEffect(() => {
        setOrderedProducts(products);
    }, [products]);

    const drop = (targetId: string) => {
        if (
            !allowReorder ||
            draggedId === null ||
            draggedId === targetId ||
            reordering
        ) {
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
    const allowReorder =
        search.trim() === '' && category === 'all' && lifecycle === 'all';
    const shown = orderedProducts.filter(
        (product) =>
            (category === 'all' || product.category === category) &&
            (lifecycle === 'all' || product.lifecycle === lifecycle) &&
            `${product.name} ${product.slug} ${product.summary ?? ''}`
                .toLowerCase()
                .includes(search.trim().toLowerCase()),
    );

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
                <div className="grid grid-cols-2 gap-2 text-[10px] font-black 2xl:grid-cols-5">
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
                        {licensingCount} licensing-enabled
                    </span>
                    {reordering ? (
                        <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-amber-600 dark:text-amber-400">
                            Saving order…
                        </span>
                    ) : null}
                </div>
            </div>
            <div className="relative mb-4 rounded-xl border border-white/[0.07] bg-white/[0.025] px-4 py-3 text-[11px] leading-5 text-white/50">
                {allowReorder
                    ? 'Drag or use arrows to reorder the entire catalog. '
                    : 'Clear all filters before changing the product order. '}
                Changes here are the governed source for public visibility,
                lifecycle, artwork and landing-page order. Purchase remains
                fail-closed unless the product is Available.
            </div>
            <div className="relative grid gap-3">
                {shown.map((product) => (
                    <ManagedProductEditor
                        key={product.id}
                        product={product}
                        initiallyEditing={product.id === activeProductId}
                        products={orderedProducts}
                        onDragStart={setDraggedId}
                        onDrop={drop}
                        allowReorder={allowReorder}
                        generation={generation}
                    />
                ))}
                {shown.length === 0 && (
                    <p
                        role="status"
                        className="rounded-xl border border-dashed border-white/20 p-8 text-center text-sm text-white/70"
                    >
                        No products match these filters. Try another category or
                        lifecycle.
                    </p>
                )}
            </div>
        </section>
    );
}
