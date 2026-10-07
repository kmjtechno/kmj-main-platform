import { Link, usePage } from '@inertiajs/react';
import { Fragment, useMemo, useState } from 'react';
import {
    ArrowRight,
    CheckCircle2,
    FlaskConical,
    Search,
    ServerCog,
    ShieldCheck,
} from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';
import ProductVisual from '@/components/public/product-visual';

const categoryOrder = [
    'Platform & Infrastructure',
    'Engineering & Automation',
    'Calibration & Vision Systems',
    'Secure Access & Connectivity',
    'Commerce & Licensing',
    'Media & Immersive Experience',
] as const;

const categoryRank = new Map<string, number>(
    categoryOrder.map((category, index) => [category, index]),
);

const categoryDescriptions: Record<string, string> = {
    'Platform & Infrastructure':
        'Governed cloud and platform foundations for KMJ products and operations.',
    'Engineering & Automation':
        'Autonomous engineering systems for building, testing and operating software.',
    'Calibration & Vision Systems':
        'Projection, camera and spatial-calibration technology for immersive environments.',
    'Secure Access & Connectivity':
        'Governed remote access and secure product connectivity.',
    'Commerce & Licensing':
        'Software licensing, subscriptions, entitlements and governed digital-product access.',
    'Media & Immersive Experience':
        'Cinema, dome, playback and creative systems for immersive venues and media workflows.',
};

const categoryDescriptionsHi: Record<string, string> = {
    'Platform & Infrastructure':
        'KMJ products और operations के लिए governed cloud और platform foundations.',
    'Engineering & Automation':
        'Software build, test और operate करने के लिए autonomous engineering systems.',
    'Calibration & Vision Systems':
        'Immersive environments के लिए projection, camera और spatial-calibration technology.',
    'Secure Access & Connectivity':
        'Governed remote access और secure product connectivity.',
    'Commerce & Licensing':
        'Software licensing, subscriptions, entitlements और governed digital-product access.',
    'Media & Immersive Experience':
        'Immersive venues और media workflows के लिए cinema, dome, playback और creative systems.',
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
    proof: Array<{
        title: string;
        detail: string;
        state: string;
    }>;
    demo: {
        kind: string;
        simulation: boolean;
        label: string;
    };
};

export default function ProductsIndex({ products }: { products: Product[] }) {
    const { localization } = usePage().props;
    const hi = localization.locale === 'hi';
    const descriptions = hi ? categoryDescriptionsHi : categoryDescriptions;
    const [query, setQuery] = useState('');
    const [lifecycle, setLifecycle] = useState('all');
    const activeCount = products.filter(
        (product) => product.purchase_enabled,
    ).length;
    const categoryCount = new Set(products.map((product) => product.category))
        .size;
    const lifecycleOptions = ['Available', 'Preview', 'Research', 'Planned'];
    const filteredProducts = useMemo(() => {
        const normalizedQuery = query.trim().toLowerCase();

        return products
            .filter((product) => {
                const matchesLifecycle =
                    lifecycle === 'all' ||
                    product.lifecycle_label === lifecycle;
                const haystack = [
                    product.name,
                    product.eyebrow,
                    product.headline,
                    product.summary,
                ]
                    .join(' ')
                    .toLowerCase();

                return (
                    matchesLifecycle &&
                    (normalizedQuery === '' ||
                        haystack.includes(normalizedQuery))
                );
            })
            .sort(
                (left, right) =>
                    (categoryRank.get(left.category) ??
                        Number.MAX_SAFE_INTEGER) -
                    (categoryRank.get(right.category) ??
                        Number.MAX_SAFE_INTEGER),
            );
    }, [lifecycle, products, query]);

    return (
        <>
            <PublicSeo
                title={hi ? 'उत्पाद — KMJ TECHNO' : 'Products — KMJ TECHNO'}
                description={
                    hi
                        ? 'Evidence-backed lifecycle, availability और product status के साथ KMJ TECHNO product portfolio देखें।'
                        : 'Explore the KMJ TECHNO product portfolio with evidence-backed lifecycle, availability and product status.'
                }
                path="/products"
                structuredData={[
                    {
                        '@context': 'https://schema.org',
                        '@type': 'CollectionPage',
                        name: 'KMJ TECHNO Products',
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

            <div className="min-h-screen overflow-hidden bg-[#06080b] text-white selection:bg-[#ef2632] selection:text-white">
                <div className="pointer-events-none fixed inset-0">
                    <div className="absolute -top-64 right-[4%] h-[42rem] w-[42rem] rounded-full bg-[#a30f18]/12 blur-[150px]" />
                    <div className="absolute top-[55rem] -left-64 h-[34rem] w-[34rem] rounded-full bg-[#ef2632]/7 blur-[140px]" />
                </div>

                <PublicSiteHeader />

                <main id="main-content" className="relative z-10">
                    <section className="mx-auto max-w-[1440px] px-5 pt-16 pb-12 sm:px-8 lg:px-12 lg:pt-24 lg:pb-16">
                        <div className="grid gap-10 lg:grid-cols-[1fr_auto] lg:items-end">
                            <div className="max-w-5xl">
                                <div className="text-[10px] font-black tracking-[0.22em] text-[#ff5962] uppercase">
                                    {hi
                                        ? 'KMJ TECHNO उत्पाद पोर्टफोलियो'
                                        : 'KMJ TECHNO product portfolio'}
                                </div>
                                <h1 className="mt-5 text-5xl leading-[0.96] font-black tracking-[-0.06em] sm:text-6xl lg:text-[5.4rem]">
                                    {hi
                                        ? 'ऐसे products जो आगे बढ़ें'
                                        : 'Products built to move'}
                                    <span className="block text-white/32">
                                        {hi
                                            ? 'idea से governed operation तक।'
                                            : 'from idea to governed operation.'}
                                    </span>
                                </h1>
                                <p className="mt-7 max-w-3xl text-base leading-8 text-white/48 sm:text-lg">
                                    {hi
                                        ? 'पूरे KMJ product ecosystem को lifecycle, access और public evidence की स्पष्ट स्थिति के साथ देखें। Engineering progress को commercial availability की तरह प्रस्तुत नहीं किया जाता।'
                                        : 'Explore the complete KMJ product ecosystem with lifecycle, access and public evidence kept explicit. Engineering progress never masquerades as commercial availability.'}
                                </p>
                            </div>

                            <div className="grid grid-cols-3 overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.025] lg:w-[390px]">
                                {[
                                    [
                                        hi ? 'पोर्टफोलियो' : 'Portfolio',
                                        String(products.length),
                                    ],
                                    [
                                        hi ? 'श्रेणियाँ' : 'Categories',
                                        String(categoryCount),
                                    ],
                                    [
                                        hi ? 'Commercial' : 'Commercial',
                                        String(activeCount),
                                    ],
                                ].map(([label, value], index) => (
                                    <div
                                        key={label}
                                        className={
                                            'px-4 py-5 text-center ' +
                                            (index > 0
                                                ? 'border-l border-white/[0.07]'
                                                : '')
                                        }
                                    >
                                        <div className="text-2xl font-black tracking-[-0.04em]">
                                            {value}
                                        </div>
                                        <div className="mt-1 text-[9px] font-black tracking-[0.12em] text-white/28 uppercase">
                                            {label}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </section>

                    <section className="mx-auto max-w-[1440px] px-5 pb-24 sm:px-8 lg:px-12 lg:pb-28">
                        <div
                            id="product-search"
                            role="search"
                            className="mb-8 grid scroll-mt-28 gap-4 rounded-[1.4rem] border border-white/[0.08] bg-white/[0.025] p-4 sm:p-5 lg:grid-cols-[1fr_auto] lg:items-center"
                        >
                            <label className="relative block">
                                <span className="sr-only">
                                    {hi
                                        ? 'KMJ उत्पाद खोजें'
                                        : 'Search KMJ products'}
                                </span>
                                <Search className="pointer-events-none absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2 text-white/28" />
                                <input
                                    value={query}
                                    onChange={(event) =>
                                        setQuery(event.target.value)
                                    }
                                    placeholder={
                                        hi
                                            ? 'Products, capabilities या use cases खोजें'
                                            : 'Search products, capabilities or use cases'
                                    }
                                    className="h-12 w-full rounded-xl border border-white/[0.08] bg-[#07090c] pr-4 pl-11 text-sm text-white outline-none placeholder:text-white/24 focus:border-[#e21b23]/45"
                                />
                            </label>
                            <div className="flex flex-wrap gap-2">
                                {['all', ...lifecycleOptions].map((option) => (
                                    <button
                                        key={option}
                                        type="button"
                                        aria-pressed={lifecycle === option}
                                        onClick={() => setLifecycle(option)}
                                        className={
                                            'rounded-full border px-3 py-2 text-[10px] font-black tracking-[0.08em] uppercase transition ' +
                                            (lifecycle === option
                                                ? 'border-[#e21b23]/35 bg-[#e21b23]/10 text-white'
                                                : 'border-white/[0.08] bg-white/[0.025] text-white/38 hover:border-white/15 hover:text-white/68')
                                        }
                                    >
                                        {option === 'all'
                                            ? hi
                                                ? 'सभी उत्पाद'
                                                : 'All products'
                                            : option}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="grid gap-5 lg:grid-cols-2">
                            {filteredProducts.map((product, index) => {
                                const ProductIcon =
                                    product.demo.kind === 'cloudos'
                                        ? ServerCog
                                        : product.demo.kind === 'calibration'
                                          ? FlaskConical
                                          : ShieldCheck;
                                const featured = index === 0;
                                const startsCategory =
                                    index === 0 ||
                                    filteredProducts[index - 1]?.category !==
                                        product.category;

                                return (
                                    <Fragment key={product.slug}>
                                        {startsCategory && (
                                            <div className="mt-10 border-t border-white/[0.07] pt-10 first:mt-0 first:border-t-0 first:pt-0 lg:col-span-2">
                                                <div className="text-[10px] font-black tracking-[0.18em] text-[#ff5962] uppercase">
                                                    {hi
                                                        ? 'KMJ TECHNO · उत्पाद परिवार'
                                                        : 'KMJ TECHNO · Product family'}
                                                </div>
                                                <div className="mt-3 grid gap-3 lg:grid-cols-[.8fr_1.2fr] lg:items-end">
                                                    <h2 className="text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                                                        {product.category}
                                                    </h2>
                                                    <p className="max-w-2xl text-sm leading-7 text-white/38 lg:justify-self-end">
                                                        {descriptions[
                                                            product.category
                                                        ] ??
                                                            (hi
                                                                ? 'KMJ TECHNO उत्पाद परिवार।'
                                                                : 'KMJ TECHNO product family.')}
                                                    </p>
                                                </div>
                                            </div>
                                        )}
                                        <article
                                            className={
                                                'group relative flex min-h-[31rem] flex-col overflow-hidden rounded-[2rem] border border-white/[0.09] bg-[#090c10] transition duration-300 hover:-translate-y-1 hover:border-white/[0.16] ' +
                                                (featured
                                                    ? 'lg:col-span-2 lg:min-h-[28rem]'
                                                    : '')
                                            }
                                        >
                                            <div className="flex flex-col">
                                                <div className="mb-7 overflow-hidden rounded-2xl border border-white/[0.08] bg-black/30">
                                                    <ProductVisual
                                                        slug={product.slug}
                                                        name={product.name}
                                                        imagePath={
                                                            product.image_path
                                                        }
                                                        className="aspect-[4/3] w-full object-cover"
                                                    />
                                                </div>
                                                <div className="flex items-start justify-between gap-4">
                                                    <div className="flex items-center gap-4">
                                                        <div className="grid h-11 w-11 place-items-center rounded-xl border border-[#ef3340]/18 bg-[#ef3340]/8">
                                                            <ProductIcon className="h-5 w-5 text-[#ff5962]" />
                                                        </div>
                                                        <div>
                                                            <div className="text-[9px] font-black tracking-[0.16em] text-white/25 uppercase">
                                                                {hi
                                                                    ? 'उत्पाद'
                                                                    : 'Product'}{' '}
                                                                {String(
                                                                    index + 1,
                                                                ).padStart(
                                                                    2,
                                                                    '0',
                                                                )}
                                                            </div>
                                                            <div className="mt-1 text-xs font-bold text-white/45">
                                                                {
                                                                    product.category
                                                                }
                                                            </div>
                                                            <div className="mt-1 text-[10px] font-semibold text-white/28">
                                                                {
                                                                    product.eyebrow
                                                                }
                                                            </div>
                                                        </div>

                                                        <span
                                                            className={
                                                                'rounded-full border px-3 py-1.5 text-[9px] font-black tracking-[0.1em] uppercase ' +
                                                                (product.purchase_enabled
                                                                    ? 'border-emerald-300/20 bg-emerald-300/[0.06] text-emerald-200/75'
                                                                    : 'border-white/10 bg-white/[0.03] text-white/38')
                                                            }
                                                        >
                                                            {
                                                                product.lifecycle_label
                                                            }
                                                        </span>
                                                    </div>

                                                    <h2
                                                        className={
                                                            'mt-8 font-black tracking-[-0.05em] ' +
                                                            (featured
                                                                ? 'text-4xl sm:text-5xl lg:text-6xl'
                                                                : 'text-3xl sm:text-4xl')
                                                        }
                                                    >
                                                        {product.name}
                                                    </h2>
                                                    <p className="mt-5 max-w-2xl text-base leading-7 font-medium text-white/62">
                                                        {product.headline}
                                                    </p>
                                                    <p className="mt-3 max-w-2xl text-sm leading-7 text-white/37">
                                                        {product.summary}
                                                    </p>

                                                    {product.variants &&
                                                        product.variants
                                                            .length > 0 && (
                                                            <div className="mt-5">
                                                                <div className="text-[9px] font-black tracking-[0.14em] text-white/25 uppercase">
                                                                    {hi
                                                                        ? 'उपलब्ध configurations'
                                                                        : 'Available configurations'}
                                                                </div>
                                                                <div className="mt-2 flex flex-wrap gap-2">
                                                                    {product.variants.map(
                                                                        (
                                                                            variant,
                                                                        ) => (
                                                                            <span
                                                                                key={
                                                                                    variant
                                                                                }
                                                                                className="rounded-full border border-[#ef2632]/20 bg-[#ef2632]/[0.06] px-3 py-1.5 text-[10px] font-black tracking-[0.08em] text-[#ff737b]"
                                                                            >
                                                                                {
                                                                                    variant
                                                                                }
                                                                            </span>
                                                                        ),
                                                                    )}
                                                                </div>
                                                            </div>
                                                        )}

                                                    <div className="mt-auto pt-8">
                                                        <Link
                                                            href={
                                                                '/products/' +
                                                                product.slug
                                                            }
                                                            className="inline-flex h-11 items-center gap-2 rounded-xl bg-white px-5 text-sm font-black text-[#07090c] transition hover:bg-white/90"
                                                        >
                                                            {hi
                                                                ? 'उत्पाद देखें'
                                                                : 'Explore product'}
                                                            <ArrowRight className="h-4 w-4" />
                                                        </Link>
                                                    </div>
                                                </div>

                                                <div
                                                    className={
                                                        'mt-8 grid gap-3 border-t border-white/[0.07] pt-7 ' +
                                                        (featured
                                                            ? 'lg:mt-0 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-10'
                                                            : '')
                                                    }
                                                >
                                                    <div className="text-[9px] font-black tracking-[0.16em] text-white/24 uppercase">
                                                        {hi
                                                            ? 'Evidence-led foundation'
                                                            : 'Evidence-led foundation'}
                                                    </div>
                                                    {product.proof
                                                        .slice(0, 3)
                                                        .map((item) => (
                                                            <div
                                                                key={item.title}
                                                                className="rounded-2xl border border-white/[0.065] bg-white/[0.022] p-4"
                                                            >
                                                                <div className="flex items-start gap-3">
                                                                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300/55" />
                                                                    <div>
                                                                        <div className="text-sm font-black text-white/78">
                                                                            {
                                                                                item.title
                                                                            }
                                                                        </div>
                                                                        <p className="mt-1.5 text-xs leading-5 text-white/32">
                                                                            {
                                                                                item.detail
                                                                            }
                                                                        </p>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        ))}
                                                    <div className="mt-1 flex items-center justify-between rounded-xl border border-white/[0.055] bg-black/20 px-4 py-3 text-[10px] font-bold text-white/32">
                                                        <span>
                                                            {product.demo
                                                                .simulation
                                                                ? hi
                                                                    ? 'Interactive simulation उपलब्ध'
                                                                    : 'Interactive simulation available'
                                                                : product.demo
                                                                      .label}
                                                        </span>
                                                        <span
                                                            className={
                                                                product.purchase_enabled
                                                                    ? 'text-emerald-300/60'
                                                                    : 'text-white/25'
                                                            }
                                                        >
                                                            {product.purchase_enabled
                                                                ? hi
                                                                    ? 'ACCESS OPEN'
                                                                    : 'ACCESS OPEN'
                                                                : hi
                                                                  ? 'GATED'
                                                                  : 'GATED'}
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        </article>
                                    </Fragment>
                                );
                            })}
                        </div>

                        {filteredProducts.length === 0 && (
                            <div className="mt-6 rounded-[1.35rem] border border-white/[0.08] bg-white/[0.025] px-6 py-10 text-center">
                                <div className="text-lg font-black">
                                    {hi
                                        ? 'कोई matching KMJ product नहीं मिला।'
                                        : 'No matching KMJ product found.'}
                                </div>
                                <p className="mt-2 text-sm text-white/38">
                                    {hi
                                        ? 'Search साफ करें या दूसरी lifecycle state चुनें।'
                                        : 'Clear the search or select another lifecycle state.'}
                                </p>
                            </div>
                        )}
                    </section>

                    <section className="border-y border-white/[0.07] bg-[#090b0f]">
                        <div className="mx-auto grid max-w-[1440px] gap-8 px-5 py-16 sm:px-8 lg:grid-cols-[1fr_auto] lg:items-center lg:px-12 lg:py-20">
                            <div className="max-w-3xl">
                                <div className="text-[10px] font-black tracking-[0.18em] text-[#ff5962] uppercase">
                                    {hi
                                        ? 'एक commercial authority'
                                        : 'One commercial authority'}
                                </div>
                                <h2 className="mt-3 text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                                    {hi
                                        ? 'Products स्वतंत्र रहते हैं। Customer access governed रहता है।'
                                        : 'Products stay independent. Customer access stays governed.'}
                                </h2>
                                <p className="mt-4 max-w-2xl text-sm leading-7 text-white/38">
                                    {hi
                                        ? 'KMJ Main Platform shared customer, organization, entitlement और licensing authority देता है, जबकि हर product अपनी engineering boundary बनाए रखता है।'
                                        : 'KMJ Main Platform provides the shared customer, organization, entitlement and licensing authority while each product keeps its own engineering boundary.'}
                                </p>
                            </div>
                            <Link
                                href="/trust"
                                className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-white/10 px-5 text-sm font-bold text-white/70 transition hover:border-white/20 hover:text-white"
                            >
                                {hi ? 'विश्वास केंद्र खोलें' : 'Open trust center'}
                                <ArrowRight className="h-4 w-4" />
                            </Link>
                        </div>
                    </section>
                </main>

                <PublicSiteFooter />
            </div>
        </>
    );
}
