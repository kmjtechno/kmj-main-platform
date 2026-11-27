import { Link } from '@inertiajs/react';
import { useMemo, useState } from 'react';
import { ArrowRight, Search } from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';
import ProductVisual from '@/components/public/product-visual';
import { priceLines, type ProductPrices } from '@/lib/price-labels';
import { compareProductCategories } from '@/lib/product-category-order.mjs';

const categoryDescriptions: Record<string, string> = {
    'Cloud & Infrastructure': 'Cloud platforms and connected infrastructure.',
    'Industrial & Calibration':
        'Calibration and visualisation tools for immersive environments.',
    'Cinema & Immersive': 'Cinema, playback and immersive experience systems.',
    'Business & Platform':
        'Secure access, licensing and connected business products.',
    'Developer & AI': 'Tools for software development with AI.',
    'Platform & Infrastructure': 'Cloud and engineering platforms.',
    'Engineering & Automation':
        'Tools for building, testing and running software.',
    'Calibration & Vision Systems':
        'Projector and camera calibration for immersive spaces.',
    'Secure Access & Connectivity': 'Remote access and secure connections.',
    'Commerce & Licensing': 'Software licences, plans and product access.',
    'Media & Immersive Experience':
        'Cinema, dome, playback and creative products.',
};

type Product = {
    slug: string;
    name: string;
    lifecycle: string;
    lifecycle_label: string;
    purchase_enabled: boolean;
    eyebrow: string;
    headline: string;
    summary: string;
    image_path?: string | null;
    category: string;
    variants?: string[];
};

function priceTeaser(product: Product, pricing?: ProductPrices | null) {
    const plan = pricing?.plans[0];

    if (!plan) {
        return null;
    }

    const label = product.purchase_enabled ? '' : 'Planned price: ';

    return `${label}${plan.name} · ${priceLines(plan)[0]}`;
}

function ProductCard({
    product,
    pricing,
}: {
    product: Product;
    pricing?: ProductPrices | null;
}) {
    const price = priceTeaser(product, pricing);

    return (
        <li className="relative flex min-w-0 flex-col overflow-hidden rounded-3xl border border-white/[0.1] bg-gradient-to-b from-white/[0.05] to-white/[0.012] transition hover:border-[#ef3340]/50">
            <ProductVisual
                slug={product.slug}
                name={product.name}
                imagePath={product.image_path}
                compact
                className="aspect-[4/3] w-full rounded-none border-x-0 border-t-0"
            />
            <div className="flex flex-1 flex-col p-6 sm:p-8">
                <p className="inline-flex items-center gap-2 text-[11px] font-black tracking-[0.14em] text-white/72 uppercase">
                    <span
                        aria-hidden="true"
                        className={
                            'h-1.5 w-1.5 rounded-full ' +
                            (product.purchase_enabled
                                ? 'bg-emerald-400'
                                : 'bg-amber-300')
                        }
                    />
                    {product.lifecycle_label}
                </p>
                <h3 className="mt-3 text-2xl font-black tracking-[-0.03em]">
                    {product.name}
                </h3>
                <p className="mt-3 text-sm leading-6 text-white/72">
                    {product.headline}
                </p>
                {product.variants && product.variants.length > 0 && (
                    <p className="mt-3 text-xs font-bold text-[#ff8087]">
                        {product.variants.join(' · ')}
                    </p>
                )}
                <div className="mt-auto pt-6">
                    {price && (
                        <p className="mb-4 border-t border-white/[0.09] pt-4 text-xs font-bold text-white/72">
                            {price}
                        </p>
                    )}
                    {/* The stretched link makes the whole card clickable. */}
                    <Link
                        href={'/products/' + product.slug}
                        className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-[#c1121f] px-5 text-sm font-black text-white after:absolute after:inset-0 hover:bg-[#a50f1a]"
                    >
                        View product
                        <span className="sr-only">: {product.name}</span>
                        <ArrowRight aria-hidden="true" className="h-4 w-4" />
                    </Link>
                </div>
            </div>
        </li>
    );
}

export default function ProductsIndex({
    products,
    pricing = {},
}: {
    products: Product[];
    pricing?: Record<string, ProductPrices | null>;
}) {
    const [query, setQuery] = useState('');
    const [lifecycle, setLifecycle] = useState('all');
    const availableCount = products.filter(
        (product) => product.purchase_enabled,
    ).length;
    const lifecycleOptions = [
        ...new Set(products.map((product) => product.lifecycle_label)),
    ];
    const categories = useMemo(() => {
        const normalizedQuery = query.trim().toLowerCase();
        const matches = products
            .filter(
                (product) =>
                    (lifecycle === 'all' ||
                        product.lifecycle_label === lifecycle) &&
                    [
                        product.name,
                        product.eyebrow,
                        product.headline,
                        product.summary,
                    ]
                        .join(' ')
                        .toLowerCase()
                        .includes(normalizedQuery),
            )
            .sort((left, right) =>
                compareProductCategories(left.category, right.category),
            );

        return [...new Set(matches.map((product) => product.category))].map(
            (name) => ({
                name,
                products: matches.filter(
                    (product) => product.category === name,
                ),
            }),
        );
    }, [lifecycle, products, query]);

    return (
        <>
            <PublicSeo
                title="Software, Cloud & Immersive Products — KMJ TECHNO"
                description="KMJ TECHNO products: cloud platform, developer tools, remote access, projector calibration and cinema systems, with current status and prices."
                path="/products"
                structuredData={[
                    {
                        '@context': 'https://schema.org',
                        '@type': 'CollectionPage',
                        name: 'KMJ TECHNO Products',
                    },
                    {
                        '@context': 'https://schema.org',
                        '@type': 'ItemList',
                        itemListElement: products.map((product, index) => ({
                            '@type': 'ListItem',
                            position: index + 1,
                            name: product.name,
                            url:
                                'https://kmjtechno.com/products/' +
                                product.slug,
                        })),
                    },
                    {
                        '@context': 'https://schema.org',
                        '@type': 'BreadcrumbList',
                        itemListElement: [
                            {
                                '@type': 'ListItem',
                                position: 1,
                                name: 'Home',
                                item: 'https://kmjtechno.com/',
                            },
                            {
                                '@type': 'ListItem',
                                position: 2,
                                name: 'Products',
                                item: 'https://kmjtechno.com/products',
                            },
                        ],
                    },
                ]}
            />

            <div className="kmj-public-page kmj-catalog min-h-screen overflow-x-clip bg-[#030b10] text-white selection:bg-[#c8102e] selection:text-white">
                <PublicSiteHeader />

                <main id="main-content">
                    <section className="relative isolate">
                        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_70%_80%_at_80%_0%,rgba(193,18,31,0.18),transparent_70%)]" />
                        <div className="mx-auto w-full max-w-[1280px] px-5 pt-8 pb-8 sm:px-8">
                            <p className="text-[11px] font-black tracking-[0.22em] text-[#ff6a72] uppercase">
                                KMJ TECHNO products
                            </p>
                            <h1 className="mt-4 max-w-4xl font-black text-balance">
                                Technology for modern{' '}
                                <span className="text-white/72">
                                    business and engineering.
                                </span>
                            </h1>
                            <p className="mt-5 max-w-2xl text-base leading-7 text-white/72">
                                {products.length} products across cloud,
                                software engineering, secure access, calibration
                                and immersive cinema. {availableCount} available
                                now; every page shows its current status.
                            </p>

                            <div
                                id="product-search"
                                role="search"
                                className="mt-10 grid scroll-mt-28 gap-4 lg:grid-cols-[minmax(0,26rem)_1fr] lg:items-center"
                            >
                                <label className="relative block">
                                    <span className="sr-only">
                                        Search KMJ products
                                    </span>
                                    <Search
                                        aria-hidden="true"
                                        className="pointer-events-none absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2 text-white/65"
                                    />
                                    <input
                                        type="search"
                                        value={query}
                                        onChange={(event) =>
                                            setQuery(event.target.value)
                                        }
                                        placeholder="Search products"
                                        className="h-12 w-full rounded-xl border border-white/15 bg-white/[0.04] pr-4 pl-11 text-sm text-white placeholder:text-white/60 focus:border-[#ef3340]"
                                    />
                                </label>
                                <div className="flex flex-wrap gap-2 lg:justify-end">
                                    {['all', ...lifecycleOptions].map(
                                        (option) => (
                                            <button
                                                key={option}
                                                type="button"
                                                aria-pressed={
                                                    lifecycle === option
                                                }
                                                onClick={() =>
                                                    setLifecycle(option)
                                                }
                                                className={
                                                    'min-h-11 rounded-full border px-4 text-xs font-bold ' +
                                                    (lifecycle === option
                                                        ? 'border-[#c1121f] bg-[#c1121f] text-white'
                                                        : 'border-white/15 bg-white/[0.03] text-white/72 hover:border-white/30 hover:text-white')
                                                }
                                            >
                                                {option === 'all'
                                                    ? 'All products'
                                                    : option}
                                            </button>
                                        ),
                                    )}
                                </div>
                            </div>
                        </div>
                    </section>

                    {categories.map((category) => (
                        <section
                            key={category.name}
                            className="border-t border-white/[0.07]"
                        >
                            <div className="mx-auto w-full max-w-[1280px] px-5 py-12 sm:px-8">
                                <h2 className="text-2xl font-black tracking-[-0.03em] sm:text-3xl">
                                    {category.name}
                                </h2>
                                {categoryDescriptions[category.name] && (
                                    <p className="mt-2 text-sm leading-6 text-white/72">
                                        {categoryDescriptions[category.name]}
                                    </p>
                                )}
                                <ul className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
                                    {category.products.map((product) => (
                                        <ProductCard
                                            key={product.slug}
                                            product={product}
                                            pricing={pricing[product.slug]}
                                        />
                                    ))}
                                </ul>
                            </div>
                        </section>
                    ))}

                    <p
                        role="status"
                        className={
                            categories.length === 0
                                ? 'px-5 py-16 text-center text-white/72'
                                : 'sr-only'
                        }
                    >
                        {categories.length === 0
                            ? 'No matching product found. Clear the search or choose another status.'
                            : ''}
                    </p>

                    <section className="border-t border-white/[0.07]">
                        <div className="mx-auto w-full max-w-[1280px] px-5 py-16 sm:px-8">
                            <p className="mb-6 text-xs leading-5 text-white/65">
                                Prices exclude GST. Nothing is charged
                                automatically. Product pictures are concept
                                artwork; any figures in them are illustrative,
                                not measured results.
                            </p>
                            <div className="flex flex-col gap-8 rounded-3xl border border-[#c1121f]/30 bg-gradient-to-br from-[#c1121f]/20 to-transparent p-8 sm:p-12 lg:flex-row lg:items-center lg:justify-between">
                                <div className="max-w-xl">
                                    <h2 className="text-3xl font-black tracking-[-0.035em]">
                                        One KMJ account for every product
                                    </h2>
                                    <p className="mt-3 text-sm leading-6 text-white/75">
                                        See your access, plans and licences in
                                        one place.
                                    </p>
                                </div>
                                <Link
                                    href="/trust"
                                    className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-white/20 px-6 text-sm font-bold text-white hover:border-white/40"
                                >
                                    How we protect your access
                                    <ArrowRight
                                        aria-hidden="true"
                                        className="h-4 w-4"
                                    />
                                </Link>
                            </div>
                        </div>
                    </section>
                </main>

                <PublicSiteFooter />
            </div>
        </>
    );
}
