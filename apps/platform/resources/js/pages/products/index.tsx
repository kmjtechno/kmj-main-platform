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

const flagshipSlugs = [
    'kmj-cloudos',
    'kmj-calibration-pro',
    'kmj-cinema-platform',
    'kmj-360-dome',
];

/* Fill every row on wide screens, so a category never ends in an empty gap. */
function cardSpan(index: number, total: number) {
    if (total === 1) {
        return 'md:col-span-2 lg:col-span-6 lg:flex-row';
    }

    const halves = total === 4 || total % 3 === 1 ? 4 : total % 3 === 2 ? 2 : 0;
    const oddLast = total % 2 === 1 && index === total - 1;

    return (
        (index >= total - halves ? 'lg:col-span-3' : 'lg:col-span-2') +
        (oddLast ? ' md:col-span-2' : '')
    );
}

function ProductCard({
    product,
    pricing,
    span = '',
    wide = false,
}: {
    product: Product;
    pricing?: ProductPrices | null;
    span?: string;
    wide?: boolean;
}) {
    const price = priceTeaser(product, pricing);

    return (
        <li
            className={
                'kmj-card group relative flex min-w-0 flex-col overflow-hidden rounded-[1.75rem] ' +
                span
            }
        >
            <div
                className={
                    'overflow-hidden ' +
                    (wide ? 'lg:w-[56%] lg:shrink-0' : 'w-full')
                }
            >
                <ProductVisual
                    slug={product.slug}
                    name={product.name}
                    imagePath={product.image_path}
                    compact
                    className="aspect-[4/3] w-full rounded-none border-0"
                />
            </div>
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
                <h3 className="mt-3 text-2xl font-black tracking-[-0.03em] sm:text-[1.75rem]">
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
    const browsing = query.trim() === '' && lifecycle === 'all';
    const flagships = flagshipSlugs.flatMap((slug) =>
        products.filter((product) => product.slug === slug),
    );
    const areaCount = new Set(products.map((product) => product.category)).size;
    const categories = useMemo(() => {
        const normalizedQuery = query.trim().toLowerCase();
        const matches = products
            .filter(
                (product) =>
                    !(browsing && flagshipSlugs.includes(product.slug)) &&
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
    }, [browsing, lifecycle, products, query]);
    const noMatches = !browsing && categories.length === 0;

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
                    <section className="kmj-hero relative isolate">
                        <div
                            aria-hidden="true"
                            className="kmj-hero-glow pointer-events-none absolute inset-0 -z-10"
                        />
                        <div className="kmj-rise mx-auto w-full max-w-[1440px] px-5 pt-16 pb-12 text-center sm:px-8 sm:pt-24">
                            <p className="text-[11px] font-black tracking-[0.34em] text-[#ff6a72] uppercase">
                                KMJ TECHNO products
                            </p>
                            <h1 className="mx-auto mt-6 max-w-6xl font-black text-balance">
                                Technology for modern{' '}
                                <span className="kmj-shine">
                                    business and engineering.
                                </span>
                            </h1>
                            <p className="mx-auto mt-6 max-w-2xl text-base leading-7 text-white/75 sm:text-lg sm:leading-8">
                                Cloud, software engineering, secure access,
                                calibration and immersive cinema. Every product
                                shows its current status.
                            </p>
                            <dl className="mx-auto mt-10 grid max-w-2xl grid-cols-3 divide-x divide-white/10 rounded-2xl border border-white/10 bg-white/[0.03]">
                                {[
                                    ['Products', products.length],
                                    ['Technology areas', areaCount],
                                    ['Available now', availableCount],
                                ].map(([label, value]) => (
                                    <div
                                        key={label}
                                        className="flex flex-col-reverse gap-1 px-2 py-5"
                                    >
                                        <dt className="text-[11px] font-bold text-white/65 sm:text-xs">
                                            {label}
                                        </dt>
                                        <dd className="text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                                            {value}
                                        </dd>
                                    </div>
                                ))}
                            </dl>

                            <div
                                id="product-search"
                                role="search"
                                className="mt-10 flex scroll-mt-28 flex-col items-center gap-5"
                            >
                                <label className="relative block w-full max-w-xl">
                                    <span className="sr-only">
                                        Search KMJ products
                                    </span>
                                    <Search
                                        aria-hidden="true"
                                        className="pointer-events-none absolute top-1/2 left-5 h-5 w-5 -translate-y-1/2 text-white/65"
                                    />
                                    <input
                                        type="search"
                                        value={query}
                                        onChange={(event) =>
                                            setQuery(event.target.value)
                                        }
                                        placeholder="Search products"
                                        className="h-14 w-full rounded-2xl border border-white/15 bg-black/40 pr-4 pl-14 text-base text-white placeholder:text-white/60 focus:border-[#ef3340]"
                                    />
                                </label>
                                <div className="flex flex-wrap justify-center gap-2">
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
                                                    'min-h-11 rounded-full border px-5 text-xs font-bold transition-colors ' +
                                                    (lifecycle === option
                                                        ? 'border-[#c1121f] bg-[#c1121f] text-white'
                                                        : 'border-white/15 bg-white/[0.03] text-white/75 hover:border-white/30 hover:text-white')
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

                    {browsing && flagships.length > 0 && (
                        <section>
                            <div className="mx-auto w-full max-w-[1440px] px-5 pt-6 pb-16 sm:px-8">
                                <h2 className="text-3xl font-black tracking-[-0.035em] sm:text-5xl">
                                    Flagship products
                                </h2>
                                <ul className="mt-9 grid gap-6 md:grid-cols-2">
                                    {flagships.map((product) => (
                                        <ProductCard
                                            key={product.slug}
                                            product={product}
                                            pricing={pricing[product.slug]}
                                        />
                                    ))}
                                </ul>
                            </div>
                        </section>
                    )}

                    {categories.map((category) => (
                        <section
                            key={category.name}
                            className="border-t border-white/[0.07]"
                        >
                            <div className="mx-auto w-full max-w-[1440px] px-5 py-16 sm:px-8">
                                <h2 className="text-3xl font-black tracking-[-0.035em] sm:text-4xl">
                                    {category.name}
                                </h2>
                                {categoryDescriptions[category.name] && (
                                    <p className="mt-3 text-base leading-7 text-white/72">
                                        {categoryDescriptions[category.name]}
                                    </p>
                                )}
                                <ul className="mt-9 grid gap-6 md:grid-cols-2 lg:grid-cols-6">
                                    {category.products.map((product, index) => (
                                        <ProductCard
                                            key={product.slug}
                                            product={product}
                                            pricing={pricing[product.slug]}
                                            span={cardSpan(
                                                index,
                                                category.products.length,
                                            )}
                                            wide={
                                                category.products.length === 1
                                            }
                                        />
                                    ))}
                                </ul>
                            </div>
                        </section>
                    ))}

                    <p
                        role="status"
                        className={
                            noMatches
                                ? 'px-5 py-16 text-center text-white/72'
                                : 'sr-only'
                        }
                    >
                        {noMatches
                            ? 'No matching product found. Clear the search or choose another status.'
                            : ''}
                    </p>

                    <section className="border-t border-white/[0.07]">
                        <div className="mx-auto w-full max-w-[1440px] px-5 py-16 sm:px-8">
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
