import { Link } from '@inertiajs/react';
import {
    ArrowRight,
    KeyRound,
    Layers3,
    ServerCog,
    ShieldCheck,
    Sparkles,
} from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';

const operatingPrinciples = [
    {
        icon: Layers3,
        title: 'Platform thinking',
        text: 'KMJ TECHNO builds connected product systems rather than isolated pages, with shared customer, access and commercial authority where it belongs.',
    },
    {
        icon: ShieldCheck,
        title: 'Governed by design',
        text: 'Security, entitlement boundaries, auditability and truthful lifecycle status are treated as product requirements, not finishing touches.',
    },
    {
        icon: ServerCog,
        title: 'Independent product engineering',
        text: 'Each product keeps a clear engineering boundary while the Main Platform provides a consistent customer and business layer.',
    },
    {
        icon: Sparkles,
        title: 'Automation with verification',
        text: 'Automation is useful only when its actions remain policy-bound, observable and independently verifiable.',
    },
];

const companyCommitments = [
    'Keep public product claims aligned with verified delivery state.',
    'Separate customer authority from individual product implementation.',
    'Prefer secure, maintainable architecture over unnecessary complexity.',
    'Build for international product quality without hiding development status.',
];

export default function Company() {
    return (
        <>
            <PublicSeo
                title="Company — KMJ TECHNO"
                description="Learn how KMJ TECHNO approaches software, cloud systems, intelligent automation, immersive technology and governed digital products."
                path="/company"
                structuredData={{
                    '@context': 'https://schema.org',
                    '@type': 'AboutPage',
                    name: 'About KMJ TECHNO',
                }}
            />

            <div className="min-h-screen overflow-hidden bg-[#06080b] text-white selection:bg-[#e21b23] selection:text-white">
                <div className="pointer-events-none fixed inset-0">
                    <div className="absolute -top-64 left-[8%] h-[38rem] w-[38rem] rounded-full bg-[#e21b23]/10 blur-[140px]" />
                    <div className="absolute top-[54rem] -right-52 h-[32rem] w-[32rem] rounded-full bg-[#8f1016]/9 blur-[130px]" />
                </div>

                <PublicSiteHeader />

                <main id="main-content" tabIndex={-1} className="relative z-10">
                    <section className="mx-auto max-w-[1440px] px-5 pt-20 pb-18 sm:px-8 lg:px-12 lg:pt-28 lg:pb-24">
                        <div className="max-w-5xl">
                            <div className="text-[10px] font-black tracking-[0.24em] text-[#ff5962] uppercase">
                                KMJ TECHNO · Company
                            </div>
                            <h1 className="mt-6 text-5xl leading-[0.96] font-black tracking-[-0.06em] sm:text-6xl lg:text-[5.6rem]">
                                Innovate.
                                <span className="text-white/65"> Build.</span>
                                <span className="block bg-gradient-to-r from-[#ff4149] via-[#e21b23] to-[#921018] bg-clip-text text-transparent">
                                    Scale with discipline.
                                </span>
                            </h1>
                            <p className="mt-8 max-w-3xl text-base leading-8 text-white/52 sm:text-lg">
                                KMJ TECHNO is building a portfolio across
                                software, cloud systems, intelligent automation,
                                secure digital access and immersive technology.
                                The goal is not to look large before the work is
                                ready; it is to build products and operating
                                systems that can earn trust as they scale.
                            </p>
                            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                                <Link
                                    href="/products"
                                    className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-[#e21b23] px-6 text-sm font-black shadow-[0_12px_40px_rgba(226,27,35,0.22)] transition hover:-translate-y-0.5 hover:bg-[#f1252e]"
                                >
                                    Explore products
                                    <ArrowRight className="h-4 w-4" />
                                </Link>
                                <Link
                                    href="/capabilities"
                                    className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.035] px-6 text-sm font-bold text-white/78 transition hover:border-white/20 hover:bg-white/[0.07]"
                                >
                                    View capabilities
                                    <ArrowRight className="h-4 w-4" />
                                </Link>
                            </div>
                        </div>
                    </section>

                    <section className="border-y border-white/[0.07] bg-[#050608]">
                        <div className="mx-auto grid max-w-[1440px] gap-6 px-5 py-20 sm:px-8 md:grid-cols-2 lg:px-12 lg:py-24">
                            {operatingPrinciples.map(
                                ({ icon: Icon, title, text }) => (
                                    <article
                                        key={title}
                                        className="rounded-[1.75rem] border border-white/[0.08] bg-gradient-to-br from-white/[0.05] to-white/[0.015] p-7 sm:p-8"
                                    >
                                        <span className="grid h-11 w-11 place-items-center rounded-xl border border-[#e21b23]/18 bg-[#e21b23]/8 text-[#ff5962]">
                                            <Icon className="h-5 w-5" />
                                        </span>
                                        <h2 className="mt-6 text-2xl font-black tracking-[-0.035em]">
                                            {title}
                                        </h2>
                                        <p className="mt-3 text-sm leading-7 text-white/65">
                                            {text}
                                        </p>
                                    </article>
                                ),
                            )}
                        </div>
                    </section>

                    <section className="mx-auto grid max-w-[1440px] gap-10 px-5 py-20 sm:px-8 lg:grid-cols-[.9fr_1.1fr] lg:px-12 lg:py-28">
                        <div>
                            <div className="text-[10px] font-black tracking-[0.22em] text-[#ff5962] uppercase">
                                How we operate
                            </div>
                            <h2 className="mt-4 text-3xl font-black tracking-[-0.045em] sm:text-5xl">
                                One company identity.
                                <span className="block text-white/65">
                                    Clear system boundaries.
                                </span>
                            </h2>
                            <p className="mt-5 max-w-xl text-sm leading-7 text-white/65 sm:text-base">
                                The Main Platform is the central customer,
                                product, entitlement, licensing and operational
                                authority. Independent KMJ products remain
                                separate engineering systems and integrate
                                through governed contracts.
                            </p>
                        </div>

                        <div className="grid gap-3">
                            {companyCommitments.map((commitment, index) => (
                                <div
                                    key={commitment}
                                    className="flex items-start gap-4 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-5"
                                >
                                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[#e21b23]/10 text-xs font-black text-[#ff5962]">
                                        {String(index + 1).padStart(2, '0')}
                                    </span>
                                    <p className="pt-1 text-sm leading-6 font-semibold text-white/64">
                                        {commitment}
                                    </p>
                                </div>
                            ))}
                        </div>
                    </section>

                    <section className="border-y border-white/[0.07] bg-[#090b0f]">
                        <div className="mx-auto grid max-w-[1440px] gap-8 px-5 py-16 sm:px-8 lg:grid-cols-[1fr_auto] lg:items-center lg:px-12 lg:py-20">
                            <div className="max-w-3xl">
                                <div className="flex items-center gap-2 text-[10px] font-black tracking-[0.18em] text-[#ff5962] uppercase">
                                    <KeyRound className="h-4 w-4" />
                                    Trust through explicit authority
                                </div>
                                <h2 className="mt-4 text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                                    Product ambition without false certainty.
                                </h2>
                                <p className="mt-4 text-sm leading-7 text-white/65">
                                    Availability, access and product status
                                    remain explicit. Public presentation does
                                    not override verified technical or
                                    commercial state.
                                </p>
                            </div>
                            <Link
                                href="/trust"
                                className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-white/10 px-5 text-sm font-bold text-white/72 transition hover:border-white/20 hover:text-white"
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
