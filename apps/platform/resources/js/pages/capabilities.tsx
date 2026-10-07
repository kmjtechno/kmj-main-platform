import { Link, usePage } from '@inertiajs/react';
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

const icons = [
    ServerCog,
    Sparkles,
    FlaskConical,
    ShieldCheck,
    KeyRound,
    Layers3,
];

const copy = {
    en: {
        title: 'Capabilities — KMJ TECHNO',
        description:
            'Explore KMJ TECHNO focus areas across cloud platforms, AI automation, immersive calibration, security, licensing and connected digital products.',
        eyebrow: 'KMJ TECHNO · Capabilities',
        heading: 'Engineering across',
        headingAccent: 'software, cloud and intelligent systems.',
        intro: 'KMJ TECHNO combines product engineering, platform authority and governed automation across several focus areas. Capability does not imply every feature is commercially released; product pages remain the source of lifecycle and availability truth.',
        capabilities: [
            [
                'Cloud & platform systems',
                'Centralized product operations, customer authority, governed access and cloud-oriented workflows built around explicit system boundaries.',
            ],
            [
                'AI & autonomous engineering',
                'Policy-bound automation, verified AI routing and autonomous engineering workflows designed to accelerate delivery without removing control.',
            ],
            [
                'Immersive calibration systems',
                'Projection mapping, alignment, warping, blending and geometry workflows for immersive display environments, developed with evidence-led capability status.',
            ],
            [
                'Security & trust architecture',
                'Tenant boundaries, auditability, fail-closed policy, release provenance and controlled access treated as core platform capabilities.',
            ],
            [
                'Licensing & entitlement authority',
                'Organization-aware entitlements, licensing and activation flows that keep payment state, access rights and device authority separate.',
            ],
            [
                'Connected digital products',
                'A shared commercial and customer layer that lets independent KMJ products integrate without collapsing their engineering boundaries.',
            ],
        ],
        deliveryEyebrow: 'Delivery model',
        deliveryHeading: 'A platform layer that connects the experience.',
        deliveryBody:
            'Shared authority belongs in the Main Platform. Product-specific engineering remains inside each independent product. That separation keeps the system easier to secure, test and evolve.',
        delivery: [
            'Public experience',
            'Customer & organization portal',
            'Product authority',
            'Automation & AI',
            'Trust & operations',
        ],
        exploreEyebrow: 'Explore the portfolio',
        exploreHeading:
            'See which capabilities are active, in preview or on the roadmap.',
        exploreBody:
            'Product pages expose lifecycle and access state so presentation never substitutes for verified availability.',
        explore: 'Explore products',
    },
    hi: {
        title: 'क्षमताएँ — KMJ TECHNO',
        description:
            'KMJ TECHNO की cloud platforms, AI automation, immersive calibration, security, licensing और connected digital products क्षमताएँ।',
        eyebrow: 'KMJ TECHNO · क्षमताएँ',
        heading: 'Engineering का विस्तार',
        headingAccent: 'software, cloud और intelligent systems तक।',
        intro: 'KMJ TECHNO कई focus areas में product engineering, platform authority और governed automation को जोड़ता है। Capability का अर्थ यह नहीं कि हर feature commercially released है; lifecycle और availability के लिए product pages authoritative हैं।',
        capabilities: [
            [
                'Cloud और platform systems',
                'स्पष्ट system boundaries के साथ centralized product operations, customer authority, governed access और cloud-oriented workflows।',
            ],
            [
                'AI और autonomous engineering',
                'Policy-bound automation, verified AI routing और autonomous workflows जो control हटाए बिना delivery तेज करते हैं।',
            ],
            [
                'Immersive calibration systems',
                'Immersive display environments के लिए projection mapping, alignment, warping, blending और geometry workflows, evidence-led status के साथ।',
            ],
            [
                'Security और trust architecture',
                'Tenant boundaries, auditability, fail-closed policy, release provenance और controlled access को core platform capability माना जाता है।',
            ],
            [
                'Licensing और entitlement authority',
                'Organization-aware entitlements, licensing और activation flows जो payment state, access rights और device authority को अलग रखते हैं।',
            ],
            [
                'Connected digital products',
                'Shared commercial और customer layer जिससे स्वतंत्र KMJ products अपनी engineering boundaries बनाए रखते हुए integrate कर सकें।',
            ],
        ],
        deliveryEyebrow: 'Delivery model',
        deliveryHeading: 'एक platform layer जो पूरे experience को जोड़ती है।',
        deliveryBody:
            'Shared authority Main Platform में रहती है। Product-specific engineering हर independent product के अंदर रहती है। यह separation system को secure, test और evolve करना आसान बनाता है।',
        delivery: [
            'Public experience',
            'Customer और organization portal',
            'Product authority',
            'Automation और AI',
            'Trust और operations',
        ],
        exploreEyebrow: 'Portfolio देखें',
        exploreHeading:
            'देखें कौन-सी capabilities active, preview या roadmap पर हैं।',
        exploreBody:
            'Product pages lifecycle और access state दिखाते हैं ताकि presentation कभी verified availability की जगह न ले।',
        explore: 'उत्पाद देखें',
    },
} as const;

export default function Capabilities() {
    const { localization } = usePage().props;
    const language = localization.locale === 'hi' ? 'hi' : 'en';
    const t = copy[language];

    return (
        <>
            <PublicSeo
                title={t.title}
                description={t.description}
                path="/capabilities"
                localized
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
                <main id="main-content" className="relative z-10">
                    <section className="mx-auto max-w-[1440px] px-5 pt-20 pb-16 sm:px-8 lg:px-12 lg:pt-28 lg:pb-22">
                        <div className="max-w-5xl">
                            <div className="text-[10px] font-black tracking-[0.24em] text-[#ff5962] uppercase">
                                {t.eyebrow}
                            </div>
                            <h1 className="mt-6 text-5xl leading-[0.96] font-black tracking-[-0.06em] sm:text-6xl lg:text-[5.5rem]">
                                {t.heading}
                                <span className="block bg-gradient-to-r from-[#ff4149] via-[#e21b23] to-[#921018] bg-clip-text text-transparent">
                                    {t.headingAccent}
                                </span>
                            </h1>
                            <p className="mt-8 max-w-3xl text-base leading-8 text-white/52 sm:text-lg">
                                {t.intro}
                            </p>
                        </div>
                    </section>

                    <section className="mx-auto max-w-[1440px] px-5 pb-24 sm:px-8 lg:px-12 lg:pb-28">
                        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                            {t.capabilities.map(([title, text], index) => {
                                const Icon = icons[index];
                                return (
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
                                        <p className="mt-4 text-sm leading-7 text-white/42">
                                            {text}
                                        </p>
                                    </article>
                                );
                            })}
                        </div>
                    </section>

                    <section className="border-y border-white/[0.07] bg-[#050608]">
                        <div className="mx-auto grid max-w-[1440px] gap-12 px-5 py-20 sm:px-8 lg:grid-cols-[.9fr_1.1fr] lg:px-12 lg:py-24">
                            <div>
                                <div className="text-[10px] font-black tracking-[0.2em] text-[#ff5962] uppercase">
                                    {t.deliveryEyebrow}
                                </div>
                                <h2 className="mt-4 text-3xl font-black tracking-[-0.045em] sm:text-5xl">
                                    {t.deliveryHeading}
                                </h2>
                                <p className="mt-5 max-w-xl text-sm leading-7 text-white/42 sm:text-base">
                                    {t.deliveryBody}
                                </p>
                            </div>
                            <div className="grid gap-3">
                                {t.delivery.map((item, index) => (
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
                                {t.exploreEyebrow}
                            </div>
                            <h2 className="mt-4 text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                                {t.exploreHeading}
                            </h2>
                            <p className="mt-4 text-sm leading-7 text-white/40">
                                {t.exploreBody}
                            </p>
                        </div>
                        <Link
                            href="/products"
                            className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-white px-5 text-sm font-black text-[#07090c] transition hover:bg-white/90"
                        >
                            {t.explore}
                            <ArrowRight className="h-4 w-4" />
                        </Link>
                    </section>
                </main>
                <PublicSiteFooter />
            </div>
        </>
    );
}
