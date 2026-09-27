import { Link } from '@inertiajs/react';
import {
    Activity,
    ArrowRight,
    CheckCircle2,
    Code2,
    LockKeyhole,
    ServerCog,
    ShieldCheck,
    Sparkles,
} from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import ProductShare from '@/components/public/product-share';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';
import CalibrationDemo from '@/components/products/calibration-demo';
import CloudOSDemo from '@/components/products/cloudos-demo';

const productSocialImages: Record<string, string> = {
    'kmj-cloudos': '/assets/products/kmj-cloudos.webp',
    'kmj-calibration-pro': '/assets/products/kmj-calibration.webp',
    'kmj-forge': '/assets/products/kmj-forge.webp',
    'kmj-connect': '/assets/products/kmj-connect.webp',
    'kmj-cloud-nexus': '/assets/products/kmj-cloud-nexus.webp',
    'kmj-agent': '/assets/products/kmj-agent.webp',
    'kmj-creative-studio': '/assets/products/kmj-creative-studio.webp',
    'kmj-cinema-platform': '/assets/products/kmj-cinema-platform.webp',
    'kmj-360-dome': '/assets/products/kmj-360-dome.webp',
    'kmj-cinema-player': '/assets/products/kmj-cinema-player.webp',
    'kmj-licensing-hub': '/assets/products/kmj-licensing-hub.webp',
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
    truth: {
        status: string;
        physical_capability_certified?: boolean;
    };
    proof: Array<{
        title: string;
        detail: string;
        state: string;
    }>;
    demo: {
        kind: 'cloudos' | 'calibration' | 'none';
        simulation: boolean;
        label: string;
        steps: Array<{
            key: string;
            label: string;
            detail: string;
        }>;
    };
};

function ProductVisual({ product }: { product: Product }) {
    const steps = product.demo.steps.length
        ? product.demo.steps
        : [
              {
                  key: 'discover',
                  label: 'Discover',
                  detail: 'Product boundary',
              },
              { key: 'govern', label: 'Govern', detail: 'Access authority' },
              { key: 'verify', label: 'Verify', detail: 'Release evidence' },
          ];

    return (
        <div className="relative">
            <div className="absolute -inset-10 rounded-[3rem] bg-[#ed2632]/10 blur-[90px]" />
            <div className="relative overflow-hidden rounded-[2rem] border border-white/[0.11] bg-[#0a0d12]/96 shadow-[0_40px_120px_rgba(0,0,0,.55)]">
                <div className="flex h-12 items-center justify-between border-b border-white/[0.07] px-5">
                    <div className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-[#ef3340]" />
                        <span className="h-2 w-2 rounded-full bg-white/16" />
                        <span className="h-2 w-2 rounded-full bg-white/10" />
                    </div>
                    <div className="text-[10px] font-black tracking-[0.18em] text-white/30 uppercase">
                        Product experience
                    </div>
                </div>

                <div className="grid gap-4 p-5 sm:p-6">
                    <div className="flex items-start justify-between gap-6 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-5">
                        <div>
                            <div className="text-[10px] font-bold tracking-[0.16em] text-white/30 uppercase">
                                Operational boundary
                            </div>
                            <div className="mt-2 text-lg font-black tracking-[-0.025em] text-white">
                                {product.name}
                            </div>
                            <div className="mt-1 text-xs leading-5 text-white/40">
                                Governed by KMJ Main Platform authority
                            </div>
                        </div>
                        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-[#ef3340]/20 bg-[#ef3340]/10">
                            <ServerCog className="h-5 w-5 text-[#ff4a54]" />
                        </div>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-3">
                        <div className="rounded-2xl border border-white/[0.07] bg-[#080a0e] p-4">
                            <Activity className="h-4 w-4 text-emerald-300/80" />
                            <div className="mt-5 text-[10px] font-bold tracking-[0.16em] text-white/28 uppercase">
                                Lifecycle
                            </div>
                            <div className="mt-1 text-sm font-black text-white/86">
                                {product.lifecycle_label}
                            </div>
                        </div>
                        <div className="rounded-2xl border border-white/[0.07] bg-[#080a0e] p-4">
                            <LockKeyhole className="h-4 w-4 text-[#ff4a54]" />
                            <div className="mt-5 text-[10px] font-bold tracking-[0.16em] text-white/28 uppercase">
                                Access
                            </div>
                            <div className="mt-1 text-sm font-black text-white/86">
                                {product.purchase_enabled
                                    ? 'Governed'
                                    : 'Closed'}
                            </div>
                        </div>
                        <div className="rounded-2xl border border-white/[0.07] bg-[#080a0e] p-4">
                            <ShieldCheck className="h-4 w-4 text-sky-300/80" />
                            <div className="mt-5 text-[10px] font-bold tracking-[0.16em] text-white/28 uppercase">
                                Claims
                            </div>
                            <div className="mt-1 text-sm font-black text-white/86">
                                Evidence-led
                            </div>
                        </div>
                    </div>

                    <div className="rounded-2xl border border-white/[0.07] bg-[#080a0e] p-5">
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-[10px] font-bold tracking-[0.16em] text-white/28 uppercase">
                                    Workflow
                                </div>
                                <div className="mt-1 text-sm font-bold text-white/75">
                                    {product.demo.simulation
                                        ? 'Interactive browser simulation'
                                        : 'Verified product boundary'}
                                </div>
                            </div>
                            <span className="rounded-full border border-white/10 px-2.5 py-1 text-[9px] font-bold tracking-[0.12em] text-white/35 uppercase">
                                Safe preview
                            </span>
                        </div>
                        <div className="mt-5 grid gap-2">
                            {steps.slice(0, 4).map((step, index) => (
                                <div
                                    key={step.key}
                                    className="flex items-center gap-3 rounded-xl border border-white/[0.055] bg-white/[0.02] px-3 py-3"
                                >
                                    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-white/[0.05] text-[10px] font-black text-white/45">
                                        {String(index + 1).padStart(2, '0')}
                                    </span>
                                    <div className="min-w-0 flex-1">
                                        <div className="text-xs font-bold text-white/75">
                                            {step.label}
                                        </div>
                                        <div className="mt-0.5 truncate text-[10px] text-white/30">
                                            {step.detail}
                                        </div>
                                    </div>
                                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300/45" />
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default function ProductShow({ product }: { product: Product }) {
    const Demo =
        product.demo.kind === 'cloudos'
            ? CloudOSDemo
            : product.demo.kind === 'calibration'
              ? CalibrationDemo
              : null;

    return (
        <>
            <PublicSeo
                title={product.name + ' — KMJ TECHNO'}
                description={product.summary}
                path={'/products/' + product.slug}
                image={productSocialImages[product.slug]}
                imageAlt={product.name + ' — KMJ TECHNO'}
                structuredData={{
                    '@context': 'https://schema.org',
                    '@type': 'SoftwareApplication',
                    name: product.name,
                    description: product.summary,
                    brand: {
                        '@type': 'Brand',
                        name: 'KMJ TECHNO',
                    },
                    additionalProperty: {
                        '@type': 'PropertyValue',
                        name: 'Lifecycle',
                        value: product.lifecycle_label,
                    },
                }}
            />

            <div className="min-h-screen overflow-hidden bg-[#06080b] text-white selection:bg-[#ef2632] selection:text-white">
                <div className="pointer-events-none fixed inset-0">
                    <div className="absolute -top-72 left-[16%] h-[44rem] w-[44rem] rounded-full bg-[#a30f18]/15 blur-[150px]" />
                    <div className="absolute top-[35rem] right-[-18rem] h-[38rem] w-[38rem] rounded-full bg-[#ef2632]/8 blur-[140px]" />
                </div>

                <PublicSiteHeader />

                <main id="main-content" className="relative z-10">
                    <section className="mx-auto grid max-w-[1440px] gap-14 px-5 pt-16 pb-20 sm:px-8 lg:grid-cols-[1.02fr_.98fr] lg:items-center lg:px-12 lg:pt-24 lg:pb-28">
                        <div>
                            <Link
                                href="/products"
                                className="inline-flex items-center gap-2 text-xs font-bold tracking-[0.12em] text-white/38 uppercase transition hover:text-white/70"
                            >
                                Products
                                <span className="text-white/18">/</span>
                                <span className="text-white/62">
                                    {product.name}
                                </span>
                            </Link>

                            <div className="mt-8 flex flex-wrap items-center gap-3">
                                <span className="rounded-full border border-[#ef3340]/30 bg-[#ef3340]/10 px-3.5 py-1.5 text-[10px] font-black tracking-[0.16em] text-[#ff6a72] uppercase">
                                    {product.eyebrow}
                                </span>
                                <span className="rounded-full border border-white/10 bg-white/[0.035] px-3.5 py-1.5 text-[10px] font-bold tracking-[0.1em] text-white/48 uppercase">
                                    {product.lifecycle_label}
                                </span>
                            </div>

                            <h1 className="mt-7 max-w-3xl text-5xl leading-[0.94] font-black tracking-[-0.06em] sm:text-6xl lg:text-[5.1rem]">
                                {product.name}
                            </h1>
                            <p className="mt-7 max-w-2xl text-xl leading-9 font-medium tracking-[-0.015em] text-white/68 sm:text-2xl sm:leading-10">
                                {product.headline}
                            </p>
                            <p className="mt-5 max-w-2xl text-sm leading-7 text-white/42 sm:text-[15px]">
                                {product.summary}
                            </p>

                            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                                {Demo ? (
                                    <a
                                        href="#demo"
                                        className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-white px-6 text-sm font-black text-[#07090c] transition hover:-translate-y-0.5 hover:bg-white/90"
                                    >
                                        Explore the product
                                        <ArrowRight className="h-4 w-4" />
                                    </a>
                                ) : (
                                    <Link
                                        href="/products"
                                        className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-white px-6 text-sm font-black text-[#07090c] transition hover:-translate-y-0.5 hover:bg-white/90"
                                    >
                                        Explore portfolio
                                        <ArrowRight className="h-4 w-4" />
                                    </Link>
                                )}

                                {product.purchase_enabled ? (
                                    <Link
                                        href="/purchase"
                                        className="inline-flex h-12 items-center justify-center rounded-xl border border-white/12 bg-white/[0.035] px-6 text-sm font-bold text-white/78 transition hover:border-white/22 hover:bg-white/[0.07] hover:text-white"
                                    >
                                        Request commercial access
                                    </Link>
                                ) : (
                                    <span className="inline-flex h-12 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.02] px-6 text-sm font-bold text-white/36">
                                        {product.lifecycle_label}
                                    </span>
                                )}
                            </div>

                            <ProductShare
                                name={product.name}
                                slug={product.slug}
                            />

                            <div className="mt-10 grid max-w-2xl gap-px overflow-hidden rounded-2xl border border-white/[0.07] bg-white/[0.07] sm:grid-cols-3">
                                {[
                                    ['Authority', 'Canonical product'],
                                    ['Access', 'Entitlement governed'],
                                    ['Safety', 'Production isolated'],
                                ].map(([label, value]) => (
                                    <div
                                        key={label}
                                        className="bg-[#080b0f] px-5 py-4"
                                    >
                                        <div className="text-[9px] font-black tracking-[0.16em] text-white/25 uppercase">
                                            {label}
                                        </div>
                                        <div className="mt-1.5 text-xs font-bold text-white/62">
                                            {value}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <ProductVisual product={product} />
                    </section>

                    <section className="border-y border-white/[0.07] bg-[#090c10]/72">
                        <div className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 lg:px-12 lg:py-24">
                            <div className="grid gap-12 lg:grid-cols-[.8fr_1.2fr]">
                                <div className="max-w-lg">
                                    <div className="inline-flex items-center gap-2 text-[10px] font-black tracking-[0.2em] text-[#ff5962] uppercase">
                                        <Sparkles className="h-3.5 w-3.5" />
                                        Product foundation
                                    </div>
                                    <h2 className="mt-4 text-3xl font-black tracking-[-0.045em] sm:text-4xl">
                                        Built around verifiable authority, not
                                        marketing shortcuts.
                                    </h2>
                                    <p className="mt-5 text-sm leading-7 text-white/42">
                                        The public experience stays aligned with
                                        product lifecycle, access authority and
                                        release evidence. Internal engineering
                                        controls remain outside the customer
                                        surface.
                                    </p>
                                </div>

                                <div className="grid gap-4 md:grid-cols-3">
                                    {product.proof.map((item, index) => {
                                        const Icon =
                                            index === 0
                                                ? Code2
                                                : index === 1
                                                  ? ShieldCheck
                                                  : CheckCircle2;

                                        return (
                                            <article
                                                key={item.title}
                                                className="group rounded-[1.5rem] border border-white/[0.08] bg-[#07090d] p-6 transition hover:-translate-y-1 hover:border-white/[0.14]"
                                            >
                                                <div className="grid h-10 w-10 place-items-center rounded-xl border border-[#ef3340]/18 bg-[#ef3340]/8">
                                                    <Icon className="h-4.5 w-4.5 text-[#ff5962]" />
                                                </div>
                                                <div className="mt-6 text-base font-black tracking-[-0.02em] text-white/90">
                                                    {item.title}
                                                </div>
                                                <p className="mt-3 text-sm leading-6 text-white/38">
                                                    {item.detail}
                                                </p>
                                                <div className="mt-6 text-[9px] font-black tracking-[0.15em] text-white/24 uppercase">
                                                    {item.state.replaceAll(
                                                        '-',
                                                        ' ',
                                                    )}
                                                </div>
                                            </article>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    </section>

                    {Demo ? (
                        <section id="demo" className="scroll-mt-24">
                            <div className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 lg:px-12 lg:py-28">
                                <div className="grid gap-10 lg:grid-cols-[.78fr_1.22fr]">
                                    <div className="lg:pt-4">
                                        <div className="text-[10px] font-black tracking-[0.2em] text-[#ff5962] uppercase">
                                            Interactive product experience
                                        </div>
                                        <h2 className="mt-4 text-4xl font-black tracking-[-0.05em] sm:text-5xl">
                                            Understand the workflow by using it.
                                        </h2>
                                        <p className="mt-5 max-w-lg text-sm leading-7 text-white/42">
                                            This deterministic browser
                                            simulation explains the product flow
                                            without controlling production
                                            infrastructure or claiming
                                            unverified physical capability.
                                        </p>
                                        <div className="mt-7 rounded-2xl border border-white/[0.08] bg-white/[0.025] p-5">
                                            <div className="text-[9px] font-black tracking-[0.15em] text-white/25 uppercase">
                                                Current verified status
                                            </div>
                                            <p className="mt-2 text-sm leading-6 text-white/55">
                                                {product.truth.status}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="overflow-hidden rounded-[1.75rem] border border-white/[0.09] bg-[#090c10] shadow-[0_32px_90px_rgba(0,0,0,.38)]">
                                        <Demo steps={product.demo.steps} />
                                    </div>
                                </div>
                            </div>
                        </section>
                    ) : (
                        <section className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 lg:px-12 lg:py-24">
                            <div className="overflow-hidden rounded-[2rem] border border-white/[0.08] bg-gradient-to-br from-white/[0.045] to-transparent p-8 sm:p-10">
                                <div className="max-w-3xl">
                                    <div className="text-[10px] font-black tracking-[0.2em] text-amber-200/65 uppercase">
                                        Product lifecycle
                                    </div>
                                    <h2 className="mt-4 text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                                        Public demo stays closed until real
                                        evidence is ready.
                                    </h2>
                                    <p className="mt-5 text-sm leading-7 text-white/40">
                                        KMJ TECHNO publishes customer-facing
                                        screenshots, downloads and performance
                                        claims only after the corresponding
                                        product gates are verified.
                                    </p>
                                </div>
                            </div>
                        </section>
                    )}

                    <section className="border-t border-white/[0.07] bg-[#090b0f]">
                        <div className="mx-auto flex max-w-[1440px] flex-col gap-8 px-5 py-16 sm:px-8 lg:flex-row lg:items-center lg:justify-between lg:px-12 lg:py-20">
                            <div className="max-w-2xl">
                                <div className="text-[10px] font-black tracking-[0.2em] text-white/30 uppercase">
                                    KMJ TECHNO
                                </div>
                                <h2 className="mt-3 text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                                    One product ecosystem. Clear authority at
                                    every layer.
                                </h2>
                            </div>
                            <div className="flex flex-col gap-3 sm:flex-row">
                                <Link
                                    href="/products"
                                    className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-white/10 px-5 text-sm font-bold text-white/72 transition hover:border-white/20 hover:text-white"
                                >
                                    Explore all products
                                </Link>
                                {product.purchase_enabled && (
                                    <Link
                                        href="/purchase"
                                        className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-[#ef2632] px-6 text-sm font-black text-white transition hover:bg-[#ff3742]"
                                    >
                                        Request access
                                        <ArrowRight className="h-4 w-4" />
                                    </Link>
                                )}
                            </div>
                        </div>
                    </section>
                </main>

                <PublicSiteFooter />
            </div>
        </>
    );
}
