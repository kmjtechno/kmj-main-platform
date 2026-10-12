import { Head, Link, usePage } from '@inertiajs/react';
import {
    ArrowRight,
    BrainCircuit,
    Building2,
    Clapperboard,
    Code2,
    Factory,
    Globe2,
    KeyRound,
    Layers3,
    Monitor,
    ShieldCheck,
    Smartphone,
    Sparkles,
} from 'lucide-react';
import LandingJourney from '@/components/public/landing-journey';
import ProductVisual from '@/components/public/product-visual';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';
import { register } from '@/routes';

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

const flagshipSlugs = [
    'kmj-cloudos',
    'kmj-calibration-pro',
    'kmj-cinema-platform',
    'kmj-360-dome',
];

const whatWeBuild = [
    {
        icon: Code2,
        title: 'Software applications',
        text: 'Purpose-built business software, integrations and developer tools.',
    },
    {
        icon: Smartphone,
        title: 'Mobile applications',
        text: 'Native and cross-platform experiences for Android and iOS.',
    },
    {
        icon: Globe2,
        title: 'Web platforms',
        text: 'Accessible websites, customer portals and scalable web applications.',
    },
    {
        icon: Monitor,
        title: 'Desktop applications',
        text: 'Focused, high-performance tools for modern workstations.',
    },
    {
        icon: BrainCircuit,
        title: 'AI & automation',
        text: 'Assisted workflows, intelligent agents and governed AI systems.',
    },
    {
        icon: Building2,
        title: 'Enterprise systems',
        text: 'Secure operations, licensing, identity and business platforms.',
    },
    {
        icon: Factory,
        title: 'Industrial technology',
        text: 'Calibration, monitoring, visualization and control tooling.',
    },
    {
        icon: Clapperboard,
        title: 'Immersive experiences',
        text: 'Cinema, simulation, projection and spatial experiences.',
    },
];

const platformCapabilities = [
    {
        icon: Layers3,
        title: 'One product ecosystem',
        text: 'A single KMJ customer layer connects independent products without collapsing their engineering boundaries.',
    },
    {
        icon: KeyRound,
        title: 'Governed access',
        text: 'Identity, organizations, entitlements and product access stay behind explicit platform authority.',
    },
    {
        icon: ShieldCheck,
        title: 'Evidence before claims',
        text: 'Availability, release state and public product claims remain tied to verified repository evidence.',
    },
    {
        icon: Sparkles,
        title: 'Built for automation',
        text: 'Operational workflows are designed for governed automation while production-sensitive actions remain protected.',
    },
];

export default function Welcome({
    products,
}: {
    products: Product[];
    portfolioCount: number;
}) {
    const { auth } = usePage().props;
    const immersiveCinemaSuite = products.find(
        (product) => product.slug === 'kmj-immersive-cinema-suite',
    );
    const ecosystemProducts = products.filter(
        (product) => product.slug !== 'kmj-immersive-cinema-suite',
    );

    return (
        <>
            <PublicSeo
                title="KMJ TECHNO — Software, Mobile Apps, Cloud & AI Engineering"
                description="KMJ TECHNO engineers custom software, Android and iOS apps, desktop and web platforms, AI automation, secure cloud systems and immersive experiences."
                path="/"
                structuredData={[
                    {
                        '@context': 'https://schema.org',
                        '@type': 'Organization',
                        name: 'KMJ TECHNO',
                        slogan: 'INNOVATE | BUILD | SCALE',
                        logo: 'https://kmjtechno.com/assets/brand/kmj-logo-horizontal.webp',
                        image: 'https://kmjtechno.com/assets/brand/kmj-social-card.webp',
                        description:
                            'KMJ TECHNO develops software, cloud platforms, AI engineering systems, immersive calibration, secure connectivity and cinema technology.',
                    },
                    {
                        '@context': 'https://schema.org',
                        '@type': 'WebSite',
                        name: 'KMJ TECHNO',
                    },
                ]}
            />
            <Head>
                <meta name="kmj-main-platform" content="native-home" />
                <link
                    rel="preload"
                    as="image"
                    href="/assets/products/kmj-cloudos.webp"
                    fetchPriority="high"
                />
            </Head>

            <div className="min-h-screen overflow-hidden bg-[#05070a] text-white selection:bg-[#e21b23] selection:text-white">
                <div className="pointer-events-none fixed inset-0">
                    <div className="absolute -top-64 left-[54%] h-[42rem] w-[52rem] rounded-full bg-[#e21b23]/[0.09] blur-[150px]" />
                    <div className="absolute top-[58rem] -left-56 h-[36rem] w-[36rem] rounded-full bg-[#e21b23]/[0.045] blur-[150px]" />
                </div>

                <PublicSiteHeader />

                <main id="main-content" className="relative z-10">
                    <section className="mx-auto max-w-[1440px] px-5 pt-14 pb-20 sm:px-8 sm:pt-20 lg:px-12 lg:pt-24 lg:pb-28">
                        <div className="grid items-center gap-12 lg:grid-cols-[.95fr_1.05fr] lg:gap-16">
                            <div>
                                <div className="inline-flex items-center gap-2 rounded-full border border-[#e21b23]/20 bg-[#e21b23]/[0.06] px-3 py-1.5 text-[10px] font-black tracking-[0.16em] text-[#ff6d75] uppercase">
                                    <span className="h-1.5 w-1.5 rounded-full bg-[#e21b23]" />
                                    KMJ TECHNO · SOFTWARE · MOBILE · CLOUD · AI
                                </div>

                                <h1 className="mt-7 max-w-[780px] text-5xl leading-[0.94] font-black tracking-[-0.058em] sm:text-6xl lg:text-[5.15rem]">
                                    Build any software.
                                    <span className="block text-[#ff3d47]">
                                        Power every experience.
                                    </span>
                                </h1>

                                <p className="mt-7 max-w-2xl text-base leading-8 text-white/68 sm:text-lg">
                                    From web, desktop and mobile applications to
                                    AI systems, secure cloud infrastructure,
                                    professional calibration and immersive
                                    experiences, KMJ TECHNO engineers practical
                                    solutions for real-world challenges. Product
                                    availability and access remain governed by
                                    verified lifecycle and release states.
                                </p>

                                <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                                    <Link
                                        href="/products"
                                        className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-[#e21b23] px-6 text-sm font-black shadow-[0_14px_42px_rgba(226,27,35,.2)] transition hover:-translate-y-0.5 hover:bg-[#f22b34]"
                                    >
                                        Explore KMJ products
                                        <ArrowRight className="h-4 w-4" />
                                    </Link>
                                    {!auth.user && (
                                        <Link
                                            href={register()}
                                            className="inline-flex h-12 items-center justify-center rounded-xl border border-white/10 bg-white/[0.035] px-6 text-sm font-bold text-white/78 transition hover:border-white/20 hover:bg-white/[0.065]"
                                        >
                                            Create customer account
                                        </Link>
                                    )}
                                </div>
                                <a
                                    href="https://www.linkedin.com/company/kmj-techno/"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="mt-5 inline-flex items-center gap-2 text-sm font-bold text-white/75 underline decoration-[#e21b23]/60 underline-offset-4 transition hover:text-white"
                                >
                                    Discuss an international B2B project
                                    <ArrowRight className="h-4 w-4" />
                                </a>
                                <Link
                                    href="/contact"
                                    className="ml-4 inline-flex items-center gap-2 text-sm font-bold text-white/75 underline decoration-[#e21b23]/60 underline-offset-4 transition hover:text-white"
                                >
                                    Email a project brief
                                    <ArrowRight className="h-4 w-4" />
                                </Link>

                                <div className="mt-10 max-w-2xl border-t border-white/[0.08] pt-6">
                                    <div className="mb-5 grid max-w-lg grid-cols-3 gap-2">
                                        <div className="rounded-xl border border-white/[0.07] bg-white/[0.025] px-3 py-3">
                                            <div className="text-xl font-black">
                                                {products.length}
                                            </div>
                                            <div className="mt-1 text-[9px] font-black tracking-[.13em] text-white/65 uppercase">
                                                Products
                                            </div>
                                        </div>
                                        <div className="rounded-xl border border-white/[0.07] bg-white/[0.025] px-3 py-3">
                                            <div className="text-xl font-black">
                                                {
                                                    products.filter(
                                                        (product) =>
                                                            product.lifecycle ===
                                                            'available',
                                                    ).length
                                                }
                                            </div>
                                            <div className="mt-1 text-[9px] font-black tracking-[.13em] text-white/65 uppercase">
                                                Available
                                            </div>
                                        </div>
                                        <div className="rounded-xl border border-red-500/15 bg-red-500/[0.04] px-3 py-3">
                                            <div className="text-xl font-black text-[#ff4b54]">
                                                {
                                                    products.filter(
                                                        (product) =>
                                                            product.purchase_enabled,
                                                    ).length
                                                }
                                            </div>
                                            <div className="mt-1 text-[9px] font-black tracking-[.13em] text-white/65 uppercase">
                                                Purchasable
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex flex-wrap gap-x-6 gap-y-3 text-[10px] font-black tracking-[0.13em] text-white/58 uppercase">
                                        <span>Central Licensing</span>
                                        <span>Secure Access</span>
                                        <span>Product Entitlements</span>
                                        <span>Clear Lifecycle Status</span>
                                    </div>
                                    <p className="mt-4 text-xs leading-5 text-white/65">
                                        Product availability, access and
                                        lifecycle status reflect the current
                                        verified platform state.
                                    </p>
                                </div>
                            </div>

                            <div className="relative grid min-h-[430px] grid-cols-[1.18fr_.82fr] grid-rows-2 gap-3 overflow-hidden rounded-[2rem] border border-white/[0.08] bg-[#090c12] p-3 shadow-[0_35px_100px_rgba(0,0,0,.35)] sm:min-h-[500px]">
                                <Link
                                    href="/products/kmj-cloudos"
                                    className="group relative row-span-2 overflow-hidden rounded-[1.45rem] border border-white/[0.07]"
                                >
                                    <img
                                        src="/assets/products/kmj-cloudos.webp"
                                        alt="KMJ CloudOS platform"
                                        width={1280}
                                        height={960}
                                        fetchPriority="high"
                                        decoding="async"
                                        className="absolute inset-0 h-full w-full object-cover transition duration-700 group-hover:scale-[1.025]"
                                    />
                                    <div className="absolute inset-0 bg-gradient-to-t from-black/65 via-black/5 to-transparent" />
                                    <div className="absolute right-5 bottom-5 left-5">
                                        <div className="text-[10px] font-black tracking-[.15em] text-white/50 uppercase">
                                            Cloud platform
                                        </div>
                                        <div className="mt-1 text-lg font-black">
                                            KMJ CloudOS
                                        </div>
                                    </div>
                                </Link>
                                <Link
                                    href="/products/kmj-calibration-pro"
                                    className="group relative overflow-hidden rounded-[1.45rem] border border-white/[0.07]"
                                >
                                    <img
                                        src="/assets/products/kmj-calibration.webp"
                                        alt="KMJ Calibration Pro"
                                        width={1280}
                                        height={960}
                                        loading="eager"
                                        decoding="async"
                                        className="absolute inset-0 h-full w-full object-cover transition duration-700 group-hover:scale-[1.03]"
                                    />
                                    <div className="absolute inset-0 bg-gradient-to-t from-black/65 via-transparent to-transparent" />
                                    <div className="absolute right-4 bottom-4 left-4 text-sm font-black">
                                        Calibration Pro
                                    </div>
                                </Link>
                                <Link
                                    href="/products/kmj-cinema-platform"
                                    className="group relative overflow-hidden rounded-[1.45rem] border border-white/[0.07]"
                                >
                                    <img
                                        src="/assets/products/kmj-cinema-platform.webp"
                                        alt="KMJ Cinema Platform"
                                        width={1280}
                                        height={960}
                                        loading="eager"
                                        decoding="async"
                                        className="absolute inset-0 h-full w-full object-cover transition duration-700 group-hover:scale-[1.03]"
                                    />
                                    <div className="absolute inset-0 bg-gradient-to-t from-black/65 via-transparent to-transparent" />
                                    <div className="absolute right-4 bottom-4 left-4 text-sm font-black">
                                        Cinema Platform
                                    </div>
                                </Link>
                            </div>
                        </div>
                    </section>

                    <section
                        aria-labelledby="what-we-build-heading"
                        className="mx-auto max-w-[1440px] px-5 py-16 sm:px-8 lg:px-12 lg:py-20"
                    >
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                            <div className="max-w-3xl">
                                <div className="text-[10px] font-black tracking-[0.2em] text-[#ee3942] uppercase">
                                    Engineering capabilities
                                </div>
                                <h2
                                    id="what-we-build-heading"
                                    className="mt-4 text-4xl font-black tracking-[-0.045em] sm:text-5xl"
                                >
                                    What we build.
                                    <span className="block text-white/65">
                                        Software for real-world possibilities.
                                    </span>
                                </h2>
                                <p className="mt-5 max-w-2xl text-sm leading-7 text-white/65 sm:text-base">
                                    From your first idea to a secure, scalable
                                    product, KMJ designs and engineers custom
                                    applications and connected technology.
                                </p>
                            </div>
                            <Link
                                href="/capabilities"
                                className="inline-flex h-11 items-center gap-2 text-sm font-black text-white/75 transition hover:text-white"
                            >
                                Explore capabilities
                                <ArrowRight className="h-4 w-4" />
                            </Link>
                        </div>
                        <div className="mt-9 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                            {whatWeBuild.map(({ icon: Icon, title, text }) => (
                                <article
                                    key={title}
                                    className="group rounded-[1.3rem] border border-white/[0.08] bg-gradient-to-br from-white/[0.04] to-transparent p-5 transition duration-300 hover:-translate-y-1 hover:border-[#e21b23]/30"
                                >
                                    <span className="grid h-11 w-11 place-items-center rounded-xl border border-[#e21b23]/25 bg-[#e21b23]/[0.08] text-[#ff5962]">
                                        <Icon
                                            aria-hidden="true"
                                            className="h-5 w-5"
                                        />
                                    </span>
                                    <h3 className="mt-5 text-base font-black tracking-[-0.02em]">
                                        {title}
                                    </h3>
                                    <p className="mt-2 text-[13px] leading-6 text-white/60">
                                        {text}
                                    </p>
                                </article>
                            ))}
                        </div>
                    </section>

                    <section className="border-y border-white/[0.065] bg-[#07090d]">
                        <div className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 lg:px-12 lg:py-24">
                            <div className="flex flex-col justify-between gap-7 lg:flex-row lg:items-end">
                                <div className="max-w-3xl">
                                    <div className="text-[10px] font-black tracking-[0.2em] text-[#ee3942] uppercase">
                                        KMJ TECHNO product ecosystem
                                    </div>
                                    <h2 className="mt-4 text-4xl font-black tracking-[-0.045em] sm:text-5xl">
                                        See the products.
                                        <span className="block text-white/65">
                                            Know exactly where each one stands.
                                        </span>
                                    </h2>
                                    <p className="mt-5 max-w-2xl text-sm leading-7 text-white/65 sm:text-base">
                                        Explore real product visuals, current
                                        lifecycle state and available
                                        configurations before opening the full
                                        product detail.
                                    </p>
                                </div>
                                <Link
                                    href="/products"
                                    className="inline-flex h-11 items-center gap-2 text-sm font-black text-white/74 transition hover:text-white"
                                >
                                    View full portfolio
                                    <ArrowRight className="h-4 w-4" />
                                </Link>
                            </div>

                            <div className="mt-10 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                                {ecosystemProducts.map((product) => (
                                    <Link
                                        key={product.slug}
                                        href={'/products/' + product.slug}
                                        className={
                                            'group overflow-hidden rounded-[1.35rem] border border-white/[0.08] bg-[#0a0d12] transition duration-300 hover:-translate-y-1 hover:border-white/[0.16] ' +
                                            (flagshipSlugs.includes(
                                                product.slug,
                                            )
                                                ? 'xl:col-span-2'
                                                : '')
                                        }
                                    >
                                        <div
                                            className={
                                                'relative overflow-hidden ' +
                                                (flagshipSlugs.includes(
                                                    product.slug,
                                                )
                                                    ? 'h-56 sm:h-64'
                                                    : 'h-44')
                                            }
                                        >
                                            <ProductVisual
                                                slug={product.slug}
                                                name={product.name}
                                                kind={product.demo.kind}
                                                imagePath={product.image_path}
                                                compact
                                            />
                                            <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-[#080b10] via-transparent to-transparent" />
                                        </div>
                                        <div className="p-5">
                                            <div className="flex items-center justify-between gap-3">
                                                <div className="min-w-0">
                                                    <div className="text-[9px] font-black tracking-[.14em] text-[#ee3942] uppercase">
                                                        {product.eyebrow}
                                                    </div>
                                                    <h3 className="mt-2 truncate text-xl font-black tracking-[-0.03em]">
                                                        {product.name}
                                                    </h3>
                                                </div>
                                                <ArrowRight className="h-4 w-4 shrink-0 text-white/65 transition group-hover:translate-x-0.5 group-hover:text-white" />
                                            </div>
                                            {flagshipSlugs.includes(
                                                product.slug,
                                            ) && (
                                                <p className="mt-3 max-w-xl text-sm leading-6 text-white/65">
                                                    {product.summary}
                                                </p>
                                            )}
                                            {product.variants &&
                                                product.variants.length > 0 && (
                                                    <div className="mt-4 flex flex-wrap gap-1.5">
                                                        {product.variants.map(
                                                            (variant) => (
                                                                <span
                                                                    key={
                                                                        variant
                                                                    }
                                                                    className="rounded-full border border-white/[0.08] bg-white/[0.025] px-2 py-1 text-[9px] font-bold text-white/65"
                                                                >
                                                                    {variant}
                                                                </span>
                                                            ),
                                                        )}
                                                    </div>
                                                )}
                                            <div className="mt-4 text-[10px] font-bold text-white/65">
                                                {product.lifecycle_label}
                                            </div>
                                        </div>
                                    </Link>
                                ))}
                            </div>
                        </div>
                    </section>

                    {immersiveCinemaSuite && (
                        <section className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 lg:px-12 lg:py-24">
                            <div className="relative overflow-hidden rounded-[2rem] border border-[#e21b23]/20 bg-[#080a0e] p-6 sm:p-8 lg:p-10">
                                <div className="pointer-events-none absolute -top-24 -right-24 h-80 w-80 rounded-full bg-[#e21b23]/12 blur-[100px]" />
                                <div className="relative grid gap-8 lg:grid-cols-[.9fr_1.1fr] lg:items-center">
                                    <div>
                                        <div className="text-[10px] font-black tracking-[0.2em] text-[#ee3942] uppercase">
                                            KMJ immersive cinema suite
                                        </div>
                                        <h2 className="mt-4 text-4xl font-black tracking-[-0.05em] sm:text-5xl">
                                            One product family.
                                            <span className="block text-white/65">
                                                Multiple immersive formats.
                                            </span>
                                        </h2>
                                        <p className="mt-5 max-w-2xl text-sm leading-7 text-white/56 sm:text-base">
                                            {immersiveCinemaSuite.summary}
                                        </p>
                                        <div className="mt-6 flex flex-wrap gap-2">
                                            {immersiveCinemaSuite.variants?.map(
                                                (variant) => (
                                                    <span
                                                        key={variant}
                                                        className="rounded-full border border-[#e21b23]/25 bg-[#e21b23]/[0.07] px-3 py-1.5 text-xs font-black text-white/78"
                                                    >
                                                        {variant}
                                                    </span>
                                                ),
                                            )}
                                        </div>
                                        <div className="mt-7 flex flex-wrap items-center gap-4">
                                            <Link
                                                href={
                                                    '/products/' +
                                                    immersiveCinemaSuite.slug
                                                }
                                                className="inline-flex h-12 items-center gap-2 rounded-xl bg-[#e21b23] px-6 text-sm font-black transition hover:-translate-y-0.5 hover:bg-[#f22b34]"
                                            >
                                                Explore Cinema Suite
                                                <ArrowRight className="h-4 w-4" />
                                            </Link>
                                            <span className="text-xs font-bold text-white/65">
                                                {
                                                    immersiveCinemaSuite.lifecycle_label
                                                }
                                            </span>
                                        </div>
                                    </div>
                                    <div className="overflow-hidden rounded-[1.5rem] border border-white/[0.08] bg-[#0a0d12] p-4">
                                        <div className="grid min-h-[320px] grid-cols-2 gap-3 sm:grid-cols-4">
                                            {(
                                                immersiveCinemaSuite.variants ??
                                                []
                                            ).map((variant, index) => (
                                                <div
                                                    key={variant}
                                                    className={
                                                        'relative overflow-hidden rounded-xl border border-white/[0.08] bg-gradient-to-br from-[#151820] to-[#07090d] p-4 ' +
                                                        (index === 6
                                                            ? 'sm:col-span-2'
                                                            : '')
                                                    }
                                                >
                                                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_20%,rgba(226,27,35,.18),transparent_45%)]" />
                                                    <div className="relative flex h-full min-h-28 flex-col justify-between">
                                                        <span className="text-[10px] font-bold tracking-[.14em] text-white/65 uppercase">
                                                            Immersive format
                                                        </span>
                                                        <span className="text-3xl font-black tracking-[-0.04em] text-white">
                                                            {variant}
                                                        </span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </section>
                    )}

                    <section className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 lg:px-12 lg:py-24">
                        <div className="grid gap-10 lg:grid-cols-[.72fr_1.28fr] lg:items-end">
                            <div>
                                <div className="text-[10px] font-black tracking-[0.2em] text-[#ee3942] uppercase">
                                    Why KMJ Main Platform
                                </div>
                                <h2 className="mt-4 text-4xl font-black tracking-[-0.045em]">
                                    One customer layer.
                                    <span className="block text-white/65">
                                        Product boundaries stay clear.
                                    </span>
                                </h2>
                            </div>
                            <p className="max-w-2xl text-sm leading-7 text-white/65 sm:text-base">
                                Customer identity, commercial access and product
                                entitlements stay unified while each KMJ product
                                keeps its own engineering and release boundary.
                            </p>
                        </div>

                        <div className="mt-10 grid gap-6 lg:grid-cols-[1.1fr_.9fr] lg:items-stretch">
                            <div className="overflow-hidden rounded-[1.6rem] border border-white/[0.075] bg-[#0a0d12]">
                                <img
                                    src="/assets/products/kmj-licensing-hub.webp"
                                    alt="KMJ Licensing and entitlement control system"
                                    loading="lazy"
                                    decoding="async"
                                    className="h-full min-h-[320px] w-full object-cover"
                                />
                            </div>
                            <div className="grid gap-4 sm:grid-cols-2">
                                {platformCapabilities.map(
                                    ({ icon: Icon, title, text }) => (
                                        <article
                                            key={title}
                                            className="rounded-[1.4rem] border border-white/[0.075] bg-[#0a0d12] p-5"
                                        >
                                            <span className="grid h-10 w-10 place-items-center rounded-xl border border-[#e21b23]/15 bg-[#e21b23]/[0.07] text-[#ee3942]">
                                                <Icon className="h-4.5 w-4.5" />
                                            </span>
                                            <h3 className="mt-5 text-base font-black">
                                                {title}
                                            </h3>
                                            <p className="mt-2 text-[13px] leading-6 text-white/65">
                                                {text}
                                            </p>
                                        </article>
                                    ),
                                )}
                            </div>
                        </div>
                    </section>

                    <LandingJourney showCreateAccount={!auth.user} />
                </main>

                <PublicSiteFooter />
            </div>
        </>
    );
}
