import { Head, Link, usePage } from '@inertiajs/react';
import {
    ArrowRight,
    CheckCircle2,
    FlaskConical,
    KeyRound,
    Layers3,
    ServerCog,
    ShieldCheck,
    Sparkles,
} from 'lucide-react';
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

const platformCapabilities = [
    {
        icon: Layers3,
        title: 'Product ecosystem',
        text: 'A shared commercial and customer layer for KMJ software products while each product keeps its own engineering boundary.',
    },
    {
        icon: KeyRound,
        title: 'Governed access',
        text: 'Organizations, entitlements and product access are managed through explicit authority instead of browser-only state.',
    },
    {
        icon: ShieldCheck,
        title: 'Evidence-led delivery',
        text: 'Public product claims stay aligned with verified lifecycle and repository evidence.',
    },
    {
        icon: Sparkles,
        title: 'Automation-ready',
        text: 'The platform is designed for governed automation, operations and customer workflows without exposing internal control surfaces.',
    },
];

export default function Welcome({ products }: { products: Product[] }) {
    const { auth } = usePage().props;

    return (
        <>
            <PublicSeo
                title="KMJ TECHNO — Software, Cloud & Intelligent Systems"
                description="Explore Product portfolio, product demos and governed software access from one customer-facing platform."
                path="/"
                structuredData={[
                    {
                        '@context': 'https://schema.org',
                        '@type': 'Organization',
                        name: 'KMJ TECHNO',
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
            </Head>

            <div className="min-h-screen overflow-hidden bg-[#07090c] text-white selection:bg-[#e21b23] selection:text-white">
                <div className="pointer-events-none fixed inset-0">
                    <div className="absolute -top-52 left-1/2 h-[38rem] w-[58rem] -translate-x-1/2 rounded-full bg-[#e21b23]/10 blur-[130px]" />
                    <div className="absolute top-[48rem] -right-56 h-[34rem] w-[34rem] rounded-full bg-[#8f1016]/10 blur-[120px]" />
                </div>

                <PublicSiteHeader />

                <main className="relative z-10">
                    <section className="mx-auto max-w-7xl px-5 pt-20 pb-20 sm:px-8 sm:pt-28 lg:px-10 lg:pt-32 lg:pb-28">
                        <div className="max-w-5xl">
                            <div className="inline-flex items-center gap-2 rounded-full border border-[#e21b23]/25 bg-[#e21b23]/[0.07] px-3 py-1.5 text-xs font-semibold text-[#ff747a]">
                                <span className="h-1.5 w-1.5 rounded-full bg-[#e21b23]" />
                                KMJ TECHNO · INNOVATE | BUILD | SCALE
                            </div>

                            <h1 className="mt-7 text-5xl leading-[0.96] font-black tracking-[-0.055em] sm:text-6xl lg:text-[5.6rem]">
                                Technology built for ambitious operations.
                                <span className="block bg-gradient-to-r from-[#ff3b44] via-[#e21b23] to-[#941018] bg-clip-text text-transparent">
                                    Software. Cloud. Intelligent systems.
                                </span>
                            </h1>

                            <p className="mt-7 max-w-3xl text-base leading-8 text-white/55 sm:text-lg">
                                Explore KMJ TECHNO’s growing portfolio across
                                cloud infrastructure, immersive calibration,
                                autonomous engineering and secure digital
                                products—with clear availability and verified
                                product status.
                            </p>

                            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                                <Link
                                    href="/products"
                                    className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-[#e21b23] px-6 text-sm font-bold shadow-[0_12px_40px_rgba(226,27,35,0.22)] transition hover:-translate-y-0.5 hover:bg-[#f1252e]"
                                >
                                    Explore all products
                                    <ArrowRight className="h-4 w-4" />
                                </Link>
                                {!auth.user && (
                                    <Link
                                        href={register()}
                                        className="inline-flex h-12 items-center justify-center rounded-xl border border-white/10 bg-white/[0.035] px-6 text-sm font-semibold text-white/80 transition hover:border-white/20 hover:bg-white/[0.07]"
                                    >
                                        Create customer account
                                    </Link>
                                )}
                            </div>
                        </div>
                    </section>

                    <section className="border-y border-white/[0.07] bg-[#050608]">
                        <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:px-10 lg:py-24">
                            <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
                                <div className="max-w-3xl">
                                    <div className="text-xs font-bold tracking-[0.2em] text-[#e21b23] uppercase">
                                        KMJ TECHNO products
                                    </div>
                                    <h2 className="mt-4 text-3xl font-black tracking-[-0.04em] sm:text-5xl">
                                        A focused portfolio. One trusted KMJ
                                        experience.
                                    </h2>
                                    <p className="mt-4 max-w-2xl text-sm leading-7 text-white/45 sm:text-base">
                                        Discover products spanning cloud operations,
                                        immersive systems, autonomous engineering
                                        and secure access. Every product shows its
                                        lifecycle and access state clearly.
                                    </p>
                                </div>
                                <Link
                                    href="/products"
                                    className="inline-flex h-11 items-center gap-2 text-sm font-bold text-white/75 transition hover:text-white"
                                >
                                    Open product hub
                                    <ArrowRight className="h-4 w-4" />
                                </Link>
                            </div>

                            <div className="mt-10 grid gap-5 lg:grid-cols-2">
                                {products.map((product) => {
                                    const ProductIcon =
                                        product.demo.kind === 'cloudos'
                                            ? ServerCog
                                            : product.demo.kind ===
                                                'calibration'
                                              ? FlaskConical
                                              : ShieldCheck;

                                    return (
                                        <article
                                            key={product.slug}
                                            className="flex flex-col rounded-[1.75rem] border border-white/[0.09] bg-gradient-to-br from-white/[0.055] to-white/[0.015] p-7 sm:p-8"
                                        >
                                            <div className="flex items-start justify-between gap-4">
                                                <span className="grid h-12 w-12 place-items-center rounded-xl border border-[#e21b23]/20 bg-[#e21b23]/10 text-[#ef3941]">
                                                    <ProductIcon className="h-5 w-5" />
                                                </span>
                                                <span
                                                    className={
                                                        product.purchase_enabled
                                                            ? 'rounded-full border border-emerald-300/20 bg-emerald-300/[0.06] px-3 py-1 text-[11px] font-semibold text-emerald-200/80'
                                                            : 'rounded-full border border-amber-300/20 bg-amber-300/[0.05] px-3 py-1 text-[11px] font-semibold text-amber-200/80'
                                                    }
                                                >
                                                    {product.lifecycle_label}
                                                </span>
                                            </div>

                                            <div className="mt-7 text-sm font-bold text-white/42">
                                                {product.eyebrow}
                                            </div>
                                            <h3 className="mt-2 text-3xl font-black tracking-[-0.035em]">
                                                {product.name}
                                            </h3>
                                            <p className="mt-4 text-base leading-7 text-white/62">
                                                {product.headline}
                                            </p>
                                            <p className="mt-3 text-sm leading-7 text-white/40">
                                                {product.summary}
                                            </p>

                                            <div className="mt-6 space-y-2">
                                                {product.proof
                                                    .slice(0, 2)
                                                    .map((item) => (
                                                        <div
                                                            key={item.title}
                                                            className="flex items-start gap-3 rounded-xl border border-white/[0.06] bg-black/20 px-4 py-3"
                                                        >
                                                            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300/75" />
                                                            <div>
                                                                <div className="text-sm font-bold text-white/80">
                                                                    {item.title}
                                                                </div>
                                                                <div className="mt-1 text-xs leading-5 text-white/35">
                                                                    {
                                                                        item.detail
                                                                    }
                                                                </div>
                                                            </div>
                                                        </div>
                                                    ))}
                                            </div>

                                            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
                                                <Link
                                                    href={
                                                        '/products/' +
                                                        product.slug
                                                    }
                                                    className="inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-xl bg-[#e21b23] px-5 text-sm font-bold transition hover:bg-[#f1252e]"
                                                >
                                                    View product
                                                    <ArrowRight className="h-4 w-4" />
                                                </Link>
                                                {product.purchase_enabled && (
                                                    <Link
                                                        href="/purchase"
                                                        className="inline-flex h-11 items-center justify-center rounded-xl border border-white/10 px-5 text-sm font-semibold text-white/65 transition hover:border-white/20 hover:text-white"
                                                    >
                                                        Request access
                                                    </Link>
                                                )}
                                            </div>
                                        </article>
                                    );
                                })}
                            </div>
                        </div>
                    </section>

                    <section className="mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:px-10 lg:py-24">
                        <div className="max-w-3xl">
                            <div className="text-xs font-bold tracking-[0.2em] text-[#e21b23] uppercase">
                                Unified platform
                            </div>
                            <h2 className="mt-4 text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                                One identity, governed access, clear product boundaries.
                            </h2>
                            <p className="mt-4 text-sm leading-7 text-white/45 sm:text-base">
                                KMJ Main Platform unifies customer accounts,
                                product access, entitlements and licensing while
                                each product remains independently engineered.
                            </p>
                        </div>

                        <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                            {platformCapabilities.map(
                                ({ icon: Icon, title, text }) => (
                                    <article
                                        key={title}
                                        className="rounded-2xl border border-white/[0.08] bg-[#0b0e12] p-5"
                                    >
                                        <span className="grid h-10 w-10 place-items-center rounded-xl border border-[#e21b23]/15 bg-[#e21b23]/[0.07] text-[#ee343c]">
                                            <Icon className="h-4.5 w-4.5" />
                                        </span>
                                        <h3 className="mt-5 text-base font-bold">
                                            {title}
                                        </h3>
                                        <p className="mt-2 text-[13px] leading-6 text-white/42">
                                            {text}
                                        </p>
                                    </article>
                                ),
                            )}
                        </div>
                    </section>
                </main>
                <PublicSiteFooter />
            </div>
        </>
    );
}
