import { Link } from '@inertiajs/react';
import {
    ArrowRight,
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

const capabilities = [
    {
        icon: ServerCog,
        title: 'Cloud & platform systems',
        text: 'Centralized product operations, customer authority, governed access and cloud-oriented workflows built around explicit system boundaries.',
    },
    {
        icon: Sparkles,
        title: 'AI & autonomous engineering',
        text: 'Policy-bound automation, verified AI routing and autonomous engineering workflows designed to accelerate delivery without removing control.',
    },
    {
        icon: FlaskConical,
        title: 'Immersive calibration systems',
        text: 'Projection mapping, alignment, warping, blending and geometry workflows for immersive display environments, developed with evidence-led capability status.',
    },
    {
        icon: ShieldCheck,
        title: 'Security & trust architecture',
        text: 'Tenant boundaries, auditability, fail-closed policy, release provenance and controlled access treated as core platform capabilities.',
    },
    {
        icon: KeyRound,
        title: 'Licensing & entitlement authority',
        text: 'Organization-aware entitlements, licensing and activation flows that keep payment state, access rights and device authority separate.',
    },
    {
        icon: Layers3,
        title: 'Connected digital products',
        text: 'A shared commercial and customer layer that lets independent KMJ products integrate without collapsing their engineering boundaries.',
    },
];

const deliveryModel = [
    'Public experience',
    'Customer & organization portal',
    'Product authority',
    'Automation & AI',
    'Trust & operations',
];

export default function Capabilities() {
    return (
        <>
            <PublicSeo
                title="Capabilities — KMJ TECHNO"
                description="Explore KMJ TECHNO focus areas across cloud platforms, AI automation, immersive calibration, security, licensing and connected digital products."
                path="/capabilities"
                structuredData={{
                    '@context': 'https://schema.org',
                    '@type': 'CollectionPage',
                    name: 'KMJ TECHNO Capabilities',
                }}
            />

            <div className="min-h-screen overflow-hidden bg-[#06080b] text-white selection:bg-[#e21b23] selection:text-white">
                <div className="pointer-events-none fixed inset-0">
                    <div className="absolute -top-56 right-[4%] h-[40rem] w-[40rem] rounded-full bg-[#e21b23]/10 blur-[150px]" />
                    <div className="absolute top-[66rem] -left-56 h-[34rem] w-[34rem] rounded-full bg-[#7f0d13]/9 blur-[130px]" />
                </div>

                <PublicSiteHeader />

                <main id="main-content" tabIndex={-1} className="relative z-10">
                    <section className="mx-auto max-w-[1440px] px-5 pt-20 pb-16 sm:px-8 lg:px-12 lg:pt-28 lg:pb-22">
                        <div className="max-w-5xl">
                            <div className="text-[10px] font-black tracking-[0.24em] text-[#ff5962] uppercase">
                                KMJ TECHNO · Capabilities
                            </div>
                            <h1 className="mt-6 text-5xl leading-[0.96] font-black tracking-[-0.06em] sm:text-6xl lg:text-[5.5rem]">
                                Engineering across
                                <span className="block bg-gradient-to-r from-[#ff4149] via-[#e21b23] to-[#921018] bg-clip-text text-transparent">
                                    software, cloud and intelligent systems.
                                </span>
                            </h1>
                            <p className="mt-8 max-w-3xl text-base leading-8 text-white/52 sm:text-lg">
                                KMJ TECHNO combines product engineering,
                                platform authority and governed automation
                                across several focus areas. Capability does not
                                imply every feature is commercially released;
                                product pages remain the source of lifecycle and
                                availability truth.
                            </p>
                        </div>
                    </section>

                    <section className="mx-auto max-w-[1440px] px-5 pb-24 sm:px-8 lg:px-12 lg:pb-28">
                        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                            {capabilities.map(({ icon: Icon, title, text }) => (
                                <article
                                    key={title}
                                    className="group min-h-[18rem] rounded-[1.75rem] border border-white/[0.08] bg-[#090c10] p-7 transition duration-300 hover:-translate-y-1 hover:border-white/[0.15]"
                                >
                                    <span className="grid h-12 w-12 place-items-center rounded-xl border border-[#e21b23]/18 bg-[#e21b23]/8 text-[#ff5962]">
                                        <Icon className="h-5 w-5" />
                                    </span>
                                    <h2 className="mt-7 text-2xl font-black tracking-[-0.035em]">
                                        {title}
                                    </h2>
                                    <p className="mt-4 text-sm leading-7 text-white/65">
                                        {text}
                                    </p>
                                </article>
                            ))}
                        </div>
                    </section>

                    <section className="border-y border-white/[0.07] bg-[#050608]">
                        <div className="mx-auto grid max-w-[1440px] gap-12 px-5 py-20 sm:px-8 lg:grid-cols-[.9fr_1.1fr] lg:px-12 lg:py-24">
                            <div>
                                <div className="text-[10px] font-black tracking-[0.2em] text-[#ff5962] uppercase">
                                    Delivery model
                                </div>
                                <h2 className="mt-4 text-3xl font-black tracking-[-0.045em] sm:text-5xl">
                                    A platform layer that connects the
                                    experience.
                                </h2>
                                <p className="mt-5 max-w-xl text-sm leading-7 text-white/65 sm:text-base">
                                    Shared authority belongs in the Main
                                    Platform. Product-specific engineering
                                    remains inside each independent product.
                                    That separation keeps the system easier to
                                    secure, test and evolve.
                                </p>
                            </div>

                            <div className="grid gap-3">
                                {deliveryModel.map((item, index) => (
                                    <div
                                        key={item}
                                        className="flex items-center gap-4 rounded-2xl border border-white/[0.07] bg-white/[0.025] px-5 py-4"
                                    >
                                        <span className="text-[10px] font-black tracking-[0.14em] text-[#ff5962]">
                                            {String(index + 1).padStart(2, '0')}
                                        </span>
                                        <span className="text-sm font-bold text-white/68">
                                            {item}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </section>

                    <section className="mx-auto grid max-w-[1440px] gap-8 px-5 py-20 sm:px-8 lg:grid-cols-[1fr_auto] lg:items-center lg:px-12 lg:py-24">
                        <div className="max-w-3xl">
                            <div className="text-[10px] font-black tracking-[0.18em] text-[#ff5962] uppercase">
                                Explore the portfolio
                            </div>
                            <h2 className="mt-4 text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                                See which capabilities are active, in preview or
                                on the roadmap.
                            </h2>
                            <p className="mt-4 text-sm leading-7 text-white/65">
                                Product pages expose lifecycle and access state
                                so presentation never substitutes for verified
                                availability.
                            </p>
                        </div>
                        <Link
                            href="/products"
                            className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-white px-5 text-sm font-black text-[#07090c] transition hover:bg-white/90"
                        >
                            Explore products
                            <ArrowRight className="h-4 w-4" />
                        </Link>
                    </section>
                </main>

                <PublicSiteFooter />
            </div>
        </>
    );
}
