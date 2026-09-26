import { Head, Link, usePage } from '@inertiajs/react';
import {
    ArrowRight,
    CheckCircle2,
    KeyRound,
    Layers3,
    ShieldCheck,
    Sparkles,
} from 'lucide-react';
import HeroVisual from '@/components/public/hero-visual';
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

export default function Welcome({ products }: { products: Product[] }) {
    const { auth } = usePage().props;

    return (
        <>
            <PublicSeo
                title="KMJ TECHNO — Software, Cloud & Intelligent Systems"
                description="Explore the KMJ TECHNO product portfolio, governed software access and enterprise technology systems."
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

            <div className="min-h-screen overflow-hidden bg-[#05070a] text-white selection:bg-[#e21b23] selection:text-white">
                <div className="pointer-events-none fixed inset-0">
                    <div className="absolute -top-64 left-[54%] h-[42rem] w-[52rem] rounded-full bg-[#e21b23]/[0.09] blur-[150px]" />
                    <div className="absolute top-[58rem] -left-56 h-[36rem] w-[36rem] rounded-full bg-indigo-600/[0.06] blur-[150px]" />
                </div>

                <PublicSiteHeader />

                <main className="relative z-10">
                    <section className="mx-auto max-w-[1440px] px-5 pt-14 pb-20 sm:px-8 sm:pt-20 lg:px-12 lg:pt-24 lg:pb-28">
                        <div className="grid items-center gap-12 lg:grid-cols-[.95fr_1.05fr] lg:gap-16">
                            <div>
                                <div className="inline-flex items-center gap-2 rounded-full border border-[#e21b23]/20 bg-[#e21b23]/[0.06] px-3 py-1.5 text-[10px] font-black tracking-[0.16em] text-[#ff6d75] uppercase">
                                    <span className="h-1.5 w-1.5 rounded-full bg-[#e21b23]" />
                                    KMJ TECHNO · Innovate · Build · Scale
                                </div>

                                <h1 className="mt-7 max-w-[760px] text-5xl leading-[0.94] font-black tracking-[-0.058em] sm:text-6xl lg:text-[5.35rem]">
                                    Building the systems
                                    <span className="block text-white/32">
                                        behind the next generation.
                                    </span>
                                </h1>

                                <p className="mt-7 max-w-2xl text-base leading-8 text-white/55 sm:text-lg">
                                    KMJ TECHNO develops cloud platforms,
                                    immersive calibration, autonomous
                                    engineering systems and secure digital
                                    products from one governed technology
                                    ecosystem.
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

                                <div className="mt-10 grid max-w-xl grid-cols-3 gap-5 border-t border-white/[0.07] pt-6">
                                    <div>
                                        <div className="text-2xl font-black">
                                            8
                                        </div>
                                        <div className="mt-1 text-[10px] font-bold tracking-[.12em] text-white/30 uppercase">
                                            Product lines
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-2xl font-black">
                                            1
                                        </div>
                                        <div className="mt-1 text-[10px] font-bold tracking-[.12em] text-white/30 uppercase">
                                            KMJ platform
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-2xl font-black">
                                            100%
                                        </div>
                                        <div className="mt-1 text-[10px] font-bold tracking-[.12em] text-white/30 uppercase">
                                            Evidence-led
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <HeroVisual />
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
                                        Products that look and operate like
                                        <span className="block text-white/35">
                                            parts of one serious technology
                                            company.
                                        </span>
                                    </h2>
                                    <p className="mt-5 max-w-2xl text-sm leading-7 text-white/46 sm:text-base">
                                        Each product has its own visual
                                        identity, lifecycle and engineering
                                        boundary while sharing the same KMJ
                                        customer experience.
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

                            <div className="mt-12 grid gap-6 lg:grid-cols-2">
                                {products.map((product) => (
                                    <article
                                        key={product.slug}
                                        className="group overflow-hidden rounded-[2rem] border border-white/[0.08] bg-[#0a0d12] transition duration-300 hover:-translate-y-1 hover:border-white/[0.15]"
                                    >
                                        <ProductVisual
                                            slug={product.slug}
                                            name={product.name}
                                            kind={product.demo.kind}
                                            compact
                                        />

                                        <div className="p-6 sm:p-7">
                                            <div className="flex items-start justify-between gap-4">
                                                <div>
                                                    <div className="text-[10px] font-black tracking-[.16em] text-[#ee3942] uppercase">
                                                        {product.eyebrow}
                                                    </div>
                                                    <h3 className="mt-2 text-3xl font-black tracking-[-0.04em]">
                                                        {product.name}
                                                    </h3>
                                                </div>
                                                <span
                                                    className={
                                                        product.purchase_enabled
                                                            ? 'shrink-0 rounded-full border border-emerald-300/15 bg-emerald-300/[0.05] px-3 py-1 text-[10px] font-bold text-emerald-200/72'
                                                            : 'shrink-0 rounded-full border border-white/[0.08] bg-white/[0.035] px-3 py-1 text-[10px] font-bold text-white/42'
                                                    }
                                                >
                                                    {product.lifecycle_label}
                                                </span>
                                            </div>

                                            <p className="mt-4 text-base leading-7 font-semibold text-white/64">
                                                {product.headline}
                                            </p>
                                            <p className="mt-3 text-sm leading-7 text-white/38">
                                                {product.summary}
                                            </p>

                                            <div className="mt-5 grid gap-2 sm:grid-cols-2">
                                                {product.proof
                                                    .slice(0, 2)
                                                    .map((item) => (
                                                        <div
                                                            key={item.title}
                                                            className="flex items-start gap-2.5 rounded-xl border border-white/[0.055] bg-white/[0.02] px-3 py-3"
                                                        >
                                                            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300/65" />
                                                            <div className="text-xs leading-5 font-semibold text-white/48">
                                                                {item.title}
                                                            </div>
                                                        </div>
                                                    ))}
                                            </div>

                                            <div className="mt-6 flex items-center justify-between border-t border-white/[0.06] pt-5">
                                                <span className="text-[10px] font-bold tracking-[.14em] text-white/24 uppercase">
                                                    KMJ verified product profile
                                                </span>
                                                <Link
                                                    href={
                                                        '/products/' +
                                                        product.slug
                                                    }
                                                    className="inline-flex items-center gap-2 text-sm font-black text-white/78 transition group-hover:text-white"
                                                >
                                                    Explore
                                                    <ArrowRight className="h-4 w-4" />
                                                </Link>
                                            </div>
                                        </div>
                                    </article>
                                ))}
                            </div>
                        </div>
                    </section>

                    <section className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 lg:px-12 lg:py-24">
                        <div className="grid gap-10 lg:grid-cols-[.72fr_1.28fr] lg:items-end">
                            <div>
                                <div className="text-[10px] font-black tracking-[0.2em] text-[#ee3942] uppercase">
                                    Why KMJ Main Platform
                                </div>
                                <h2 className="mt-4 text-4xl font-black tracking-[-0.045em]">
                                    One brand.
                                    <span className="block text-white/32">
                                        Clear authority at every layer.
                                    </span>
                                </h2>
                            </div>
                            <p className="max-w-2xl text-sm leading-7 text-white/42 sm:text-base">
                                Customer identity, commercial access, product
                                entitlements and evidence stay unified without
                                turning every KMJ product into one monolithic
                                application.
                            </p>
                        </div>

                        <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
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
                                        <p className="mt-2 text-[13px] leading-6 text-white/38">
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
