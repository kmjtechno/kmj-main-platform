import { Link } from '@inertiajs/react';
import { Fragment } from 'react';
import { ArrowRight, CheckCircle2 } from 'lucide-react';
import ProductVisual from '@/components/public/product-visual';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';

const categoryOrder = [
    'Platform & Infrastructure',
    'Engineering & Automation',
    'Calibration & Vision Systems',
    'Secure Access & Connectivity',
    'Commerce & Licensing',
    'Media & Immersive Experience',
] as const;

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

type Product = {
    slug: string;
    name: string;
    lifecycle: string;
    lifecycle_label: string;
    purchase_enabled: boolean;
    eyebrow: string;
    headline: string;
    summary: string;
    category: string;
    family: string | null;
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
    const activeCount = products.filter(
        (product) => product.purchase_enabled,
    ).length;
    const categories = Array.from(
        new Set(products.map((product) => product.category)),
    );
    const categoryCount = categories.length;
    const orderedProducts = [...products].sort((left, right) => {
        const leftIndex = categoryOrder.indexOf(
            left.category as (typeof categoryOrder)[number],
        );
        const rightIndex = categoryOrder.indexOf(
            right.category as (typeof categoryOrder)[number],
        );

        if (leftIndex !== rightIndex) {
            return leftIndex - rightIndex;
        }

        if (
            left.slug === 'kmj-cloudos' ||
            left.slug === 'kmj-cinema-platform'
        ) {
            return -1;
        }

        if (
            right.slug === 'kmj-cloudos' ||
            right.slug === 'kmj-cinema-platform'
        ) {
            return 1;
        }

        return left.name.localeCompare(right.name);
    });

    return (
        <>
            <PublicSeo
                title="Products — KMJ TECHNO"
                description="Explore the KMJ TECHNO product portfolio with evidence-backed lifecycle, availability and product status."
                path="/products"
                structuredData={{
                    '@context': 'https://schema.org',
                    '@type': 'CollectionPage',
                    name: 'KMJ TECHNO Products',
                }}
            />

            <div className="min-h-screen overflow-hidden bg-[#06080b] text-white selection:bg-[#ef2632] selection:text-white">
                <div className="pointer-events-none fixed inset-0">
                    <div className="absolute -top-64 right-[4%] h-[42rem] w-[42rem] rounded-full bg-[#a30f18]/12 blur-[150px]" />
                    <div className="absolute top-[55rem] -left-64 h-[34rem] w-[34rem] rounded-full bg-[#ef2632]/7 blur-[140px]" />
                </div>

                <PublicSiteHeader />

                <main className="relative z-10">
                    <section className="mx-auto max-w-[1440px] px-5 pt-16 pb-12 sm:px-8 lg:px-12 lg:pt-24 lg:pb-16">
                        <div className="grid gap-10 lg:grid-cols-[1fr_auto] lg:items-end">
                            <div className="max-w-5xl">
                                <div className="text-[10px] font-black tracking-[0.22em] text-[#ff5962] uppercase">
                                    KMJ TECHNO product portfolio
                                </div>
                                <h1 className="mt-5 text-5xl leading-[0.96] font-black tracking-[-0.06em] sm:text-6xl lg:text-[5.4rem]">
                                    Products built to move
                                    <span className="block text-white/32">
                                        from idea to governed operation.
                                    </span>
                                </h1>
                                <p className="mt-7 max-w-3xl text-base leading-8 text-white/48 sm:text-lg">
                                    Explore the complete KMJ product ecosystem
                                    with lifecycle, access and public evidence
                                    kept explicit. Engineering progress never
                                    masquerades as commercial availability.
                                </p>
                            </div>

                            <div className="grid grid-cols-3 overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.025] lg:w-[390px]">
                                {[
                                    ['Portfolio', String(products.length)],
                                    ['Categories', String(categoryCount)],
                                    ['Commercial', String(activeCount)],
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
                        <div className="mb-7 flex flex-wrap gap-2">
                            {categories.map((category) => (
                                <span
                                    key={category}
                                    className="rounded-full border border-white/[0.08] bg-white/[0.025] px-3 py-2 text-[10px] font-black tracking-[0.12em] text-white/42 uppercase"
                                >
                                    {category}
                                </span>
                            ))}
                        </div>
                        <div className="grid gap-5 lg:grid-cols-2">
                            {orderedProducts.map((product, index) => {
                                const previous = orderedProducts[index - 1];
                                const startsCategory =
                                    previous?.category !== product.category;
                                const featured =
                                    product.slug === 'kmj-cloudos' ||
                                    product.slug === 'kmj-cinema-platform';

                                return (
                                    <Fragment key={product.slug}>
                                        {startsCategory && (
                                            <div className="mt-10 border-t border-white/[0.07] pt-10 first:mt-0 first:border-t-0 first:pt-0 lg:col-span-2">
                                                <div className="text-[10px] font-black tracking-[0.18em] text-[#ff5962] uppercase">
                                                    KMJ TECHNO · Product family
                                                </div>
                                                <div className="mt-3 grid gap-3 lg:grid-cols-[.8fr_1.2fr] lg:items-end">
                                                    <h2 className="text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                                                        {product.category}
                                                    </h2>
                                                    <p className="max-w-2xl text-sm leading-7 text-white/38 lg:justify-self-end">
                                                        {categoryDescriptions[
                                                            product.category
                                                        ] ??
                                                            'KMJ TECHNO product family.'}
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
                                            <div className="pointer-events-none absolute inset-0 opacity-0 transition duration-500 group-hover:opacity-100">
                                                <div className="absolute -top-36 right-[-5rem] h-80 w-80 rounded-full bg-[#ef2632]/10 blur-[100px]" />
                                            </div>

                                            <div className="relative p-4 pb-0 sm:p-5 sm:pb-0">
                                                <ProductVisual
                                                    slug={product.slug}
                                                    name={product.name}
                                                    kind={product.demo.kind}
                                                    compact={!featured}
                                                />
                                            </div>

                                            <div
                                                className={
                                                    'relative flex flex-1 flex-col p-7 sm:p-9 ' +
                                                    (featured
                                                        ? 'lg:grid lg:grid-cols-[1.05fr_.95fr] lg:gap-14 lg:p-11'
                                                        : '')
                                                }
                                            >
                                                <div className="flex flex-col">
                                                    <div className="flex items-start justify-between gap-4">
                                                        <div className="flex items-center gap-4">
                                                            <div className="grid h-11 w-11 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.035] text-[10px] font-black tracking-[.12em] text-white/46">
                                                                {String(
                                                                    index + 1,
                                                                ).padStart(
                                                                    2,
                                                                    '0',
                                                                )}
                                                            </div>
                                                            <div>
                                                                <div className="text-[9px] font-black tracking-[0.16em] text-white/25 uppercase">
                                                                    Product{' '}
                                                                    {String(
                                                                        index +
                                                                            1,
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
                                                                    Available
                                                                    configurations
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
                                                            Explore product
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
                                                        Evidence-led foundation
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
                                                                ? 'Interactive simulation available'
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
                                                                ? 'ACCESS OPEN'
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
                    </section>

                    <section className="border-y border-white/[0.07] bg-[#090b0f]">
                        <div className="mx-auto grid max-w-[1440px] gap-8 px-5 py-16 sm:px-8 lg:grid-cols-[1fr_auto] lg:items-center lg:px-12 lg:py-20">
                            <div className="max-w-3xl">
                                <div className="text-[10px] font-black tracking-[0.18em] text-[#ff5962] uppercase">
                                    One commercial authority
                                </div>
                                <h2 className="mt-3 text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                                    Products stay independent. Customer access
                                    stays governed.
                                </h2>
                                <p className="mt-4 max-w-2xl text-sm leading-7 text-white/38">
                                    KMJ Main Platform provides the shared
                                    customer, organization, entitlement and
                                    licensing authority while each product keeps
                                    its own engineering boundary.
                                </p>
                            </div>
                            <Link
                                href="/trust"
                                className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-white/10 px-5 text-sm font-bold text-white/70 transition hover:border-white/20 hover:text-white"
                            >
                                Open trust center
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
