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
import PublicLanguageSwitch from '@/components/public-language-switch';
import { dashboard, login, register } from '@/routes';

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
            <Head title="KMJ TECHNO — Software, Cloud & Intelligent Systems">
                <meta name="kmj-main-platform" content="native-home" />
                <meta
                    name="description"
                    content="Explore KMJ TECHNO products, product demos and governed software access from one customer-facing platform."
                />
            </Head>

            <div className="min-h-screen overflow-hidden bg-[#07090c] text-white selection:bg-[#e21b23] selection:text-white">
                <div className="pointer-events-none fixed inset-0">
                    <div className="absolute -top-52 left-1/2 h-[38rem] w-[58rem] -translate-x-1/2 rounded-full bg-[#e21b23]/10 blur-[130px]" />
                    <div className="absolute top-[48rem] -right-56 h-[34rem] w-[34rem] rounded-full bg-[#8f1016]/10 blur-[120px]" />
                </div>

                <header className="relative z-20 border-b border-white/[0.07] bg-[#07090c]/85 backdrop-blur-xl">
                    <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 sm:px-8 lg:px-10">
                        <Link href="/" className="flex items-center gap-3">
                            <span className="grid h-10 w-10 place-items-center rounded-xl border border-[#e21b23]/40 bg-[#e21b23]/10 text-lg font-black text-[#f1252e]">
                                K
                            </span>
                            <span>
                                <span className="block text-[15px] font-extrabold tracking-[0.16em]">
                                    KMJ TECHNO
                                </span>
                                <span className="mt-0.5 block text-[9px] font-medium tracking-[0.22em] text-white/35 uppercase">
                                    Technology ecosystem
                                </span>
                            </span>
                        </Link>

                        <nav className="flex items-center gap-2 sm:gap-3">
                            <Link
                                href="/products"
                                className="hidden h-10 items-center px-3 text-sm font-medium text-white/65 transition hover:text-white md:inline-flex"
                            >
                                Products
                            </Link>
                            <Link
                                href="/trust"
                                className="hidden h-10 items-center px-3 text-sm font-medium text-white/65 transition hover:text-white lg:inline-flex"
                            >
                                Trust
                            </Link>
                            <PublicLanguageSwitch className="hidden h-10 items-center px-3 text-sm font-medium text-white/65 transition hover:text-white sm:inline-flex" />
                            {auth.user ? (
                                <Link
                                    href={dashboard()}
                                    className="inline-flex h-10 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-4 text-sm font-semibold transition hover:border-white/20"
                                >
                                    Dashboard
                                    <ArrowRight className="h-4 w-4" />
                                </Link>
                            ) : (
                                <>
                                    <Link
                                        href={login()}
                                        className="hidden h-10 items-center px-3 text-sm font-medium text-white/65 transition hover:text-white sm:inline-flex"
                                    >
                                        Sign in
                                    </Link>
                                    <Link
                                        href={register()}
                                        className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#e21b23] px-4 text-sm font-bold transition hover:bg-[#f1252e]"
                                    >
                                        Create account
                                        <ArrowRight className="h-4 w-4" />
                                    </Link>
                                </>
                            )}
                        </nav>
                    </div>
                </header>

                <main className="relative z-10">
                    <section className="mx-auto max-w-7xl px-5 pt-20 pb-20 sm:px-8 sm:pt-28 lg:px-10 lg:pt-32 lg:pb-28">
                        <div className="max-w-5xl">
                            <div className="inline-flex items-center gap-2 rounded-full border border-[#e21b23]/25 bg-[#e21b23]/[0.07] px-3 py-1.5 text-xs font-semibold text-[#ff747a]">
                                <span className="h-1.5 w-1.5 rounded-full bg-[#e21b23]" />
                                KMJ TECHNO product ecosystem
                            </div>

                            <h1 className="mt-7 text-5xl leading-[0.96] font-black tracking-[-0.055em] sm:text-6xl lg:text-[5.6rem]">
                                Build. Operate.
                                <span className="block bg-gradient-to-r from-[#ff3b44] via-[#e21b23] to-[#941018] bg-clip-text text-transparent">
                                    Experience KMJ products.
                                </span>
                            </h1>

                            <p className="mt-7 max-w-3xl text-base leading-8 text-white/55 sm:text-lg">
                                One customer-facing destination for KMJ TECHNO
                                software products, product experiences, governed
                                access and licensing. Explore what is available
                                today and what is still in verified development.
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
                                        Products first. Internal engineering
                                        stays internal.
                                    </h2>
                                    <p className="mt-4 max-w-2xl text-sm leading-7 text-white/45 sm:text-base">
                                        Only products backed by the canonical
                                        public catalog appear here.
                                        Availability, preview state and purchase
                                        access remain explicit.
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
                                Platform foundation
                            </div>
                            <h2 className="mt-4 text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                                One KMJ ecosystem, clear product boundaries.
                            </h2>
                            <p className="mt-4 text-sm leading-7 text-white/45 sm:text-base">
                                The Main Platform provides the customer,
                                entitlement and licensing layer.
                                Product-specific engineering remains behind the
                                product experience, not on the public homepage.
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

                    <section className="border-t border-white/[0.07] bg-[#050608]">
                        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-8 px-5 py-16 sm:px-8 lg:flex-row lg:items-center lg:px-10">
                            <div>
                                <div className="text-2xl font-black tracking-[-0.03em]">
                                    KMJ TECHNO
                                </div>
                                <p className="mt-2 max-w-xl text-sm leading-6 text-white/40">
                                    Software products, governed customer access
                                    and product experiences from one evolving
                                    platform.
                                </p>
                            </div>
                            <div className="flex items-center gap-5 text-sm text-white/50">
                                <Link
                                    href="/products"
                                    className="hover:text-white"
                                >
                                    Products
                                </Link>
                                <Link
                                    href={login()}
                                    className="hover:text-white"
                                >
                                    Sign in
                                </Link>
                            </div>
                        </div>
                    </section>
                </main>
            </div>
        </>
    );
}
