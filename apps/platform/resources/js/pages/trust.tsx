import { Link, usePage } from '@inertiajs/react';
import { CheckCircle2, KeyRound, ShieldCheck } from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';

const copy = {
    en: {
        title: 'Trust Center — KMJ TECHNO',
        description:
            'KMJ TECHNO Trust Center: evidence-backed product lifecycle, governed access, licensing boundaries and release integrity.',
        eyebrow: 'KMJ TECHNO Trust Center',
        heading: 'Trust is a product contract.',
        headingMuted: 'Claims stay behind evidence.',
        intro: 'This page explains the public rules KMJ TECHNO uses for product status, commercial access, licensing and release evidence. It intentionally separates verified capability from roadmap intent.',
        principles: [
            [
                'Lifecycle truth',
                'Active, preview, development, planned and roadmap states are shown separately so public presentation does not outrun verified delivery.',
            ],
            [
                'Governed commercial access',
                'A purchase request is not product access. Confirmed commercial state must resolve through authoritative entitlement and licensing controls.',
            ],
            [
                'Fail-closed licensing',
                'Sandbox licenses are bound to organization, product and entitlement identity and are rejected when required claims or validation boundaries are not satisfied.',
            ],
            [
                'Evidence before imagery',
                'KMJ TECHNO publishes real product evidence and approved brand assets. Synthetic product UI screenshots and AI/CGI-looking product imagery are not used as release proof.',
            ],
        ],
        commercial: 'Commercial authority',
        commercialHeading: 'Request does not equal access.',
        commercialBody:
            'The current platform keeps order state, entitlement state and license state separate. External payment-gateway configuration is deliberately deferred and is not represented as active.',
        commercialSteps: [
            'Purchase request',
            'Confirmed order',
            'Entitlement',
            'Governed license',
        ],
        security: 'Security boundaries',
        securityHeading: 'Authority is explicit.',
        securityControls: [
            'Passkey-first authentication path with enrollment guidance.',
            'Tenant capability checks for organization-scoped authority.',
            'Step-up confirmation for sensitive license revocation.',
            'Session and device visibility with sign-out-other-sessions control.',
        ],
        evidence: 'Product evidence policy',
        evidenceHeading: 'Real evidence only.',
        evidenceBody:
            'Product screenshots, downloads, benchmarks and production-readiness claims are published only when the relevant product gate has evidence. Products stay visibly labelled as Available, Preview, Research or Planned until verified evidence supports a lifecycle change.',
        review: 'Review product status',
        main: 'Main Platform',
    },
    hi: {
        title: 'विश्वास केंद्र — KMJ TECHNO',
        description:
            'KMJ TECHNO Trust Center: evidence-backed product lifecycle, governed access, licensing boundaries और release integrity.',
        eyebrow: 'KMJ TECHNO विश्वास केंद्र',
        heading: 'Trust एक product contract है।',
        headingMuted: 'हर claim के पीछे evidence होना चाहिए।',
        intro: 'यह पेज product status, commercial access, licensing और release evidence के लिए KMJ TECHNO के public rules समझाता है। Verified capability और roadmap intent को जानबूझकर अलग रखा जाता है।',
        principles: [
            [
                'Lifecycle truth',
                'Active, preview, development, planned और roadmap states अलग दिखते हैं ताकि public presentation verified delivery से आगे न निकले।',
            ],
            [
                'Governed commercial access',
                'Purchase request अपने-आप product access नहीं है। Confirmed commercial state authoritative entitlement और licensing controls से तय होती है।',
            ],
            [
                'Fail-closed licensing',
                'Sandbox licenses organization, product और entitlement identity से bind होते हैं और required claims या validation boundaries पूरी न होने पर reject होते हैं।',
            ],
            [
                'Imagery से पहले evidence',
                'KMJ TECHNO real product evidence और approved brand assets प्रकाशित करता है। Synthetic product UI screenshots या AI/CGI-looking imagery को release proof नहीं माना जाता।',
            ],
        ],
        commercial: 'Commercial authority',
        commercialHeading: 'Request का अर्थ access नहीं है।',
        commercialBody:
            'Current platform order state, entitlement state और license state को अलग रखता है। External payment-gateway configuration जानबूझकर deferred है और उसे active नहीं दिखाया जाता।',
        commercialSteps: [
            'Purchase request',
            'Confirmed order',
            'Entitlement',
            'Governed license',
        ],
        security: 'Security boundaries',
        securityHeading: 'Authority स्पष्ट है।',
        securityControls: [
            'Enrollment guidance के साथ passkey-first authentication path.',
            'Organization-scoped authority के लिए tenant capability checks.',
            'Sensitive license revocation के लिए step-up confirmation.',
            'Sign-out-other-sessions control के साथ session और device visibility.',
        ],
        evidence: 'Product evidence policy',
        evidenceHeading: 'केवल वास्तविक evidence.',
        evidenceBody:
            'Product screenshots, downloads, benchmarks और production-readiness claims तभी publish होते हैं जब relevant product gate के पास evidence हो। Lifecycle change के verified evidence तक products Available, Preview, Research या Planned के रूप में स्पष्ट label रहते हैं।',
        review: 'Product status देखें',
        main: 'Main Platform',
    },
} as const;

export default function Trust() {
    const { localization } = usePage().props;
    const language = localization.locale === 'hi' ? 'hi' : 'en';
    const t = copy[language];

    return (
        <>
            <PublicSeo
                title={t.title}
                description={t.description}
                path="/trust"
                localized
                structuredData={{
                    '@context': 'https://schema.org',
                    '@type': 'WebPage',
                    name: 'KMJ TECHNO Trust Center',
                }}
            />
            <div className="min-h-screen overflow-hidden bg-[#06080b] text-white selection:bg-[#ef2632] selection:text-white">
                <PublicSiteHeader />
                <main id="main-content">
                    <section className="mx-auto max-w-[1440px] px-5 pt-16 pb-12 sm:px-8 lg:px-10 lg:pt-24">
                        <div className="max-w-4xl">
                            <div className="text-xs font-bold tracking-[0.22em] text-[#ef3941] uppercase">
                                {t.eyebrow}
                            </div>
                            <h1 className="mt-5 text-5xl leading-[0.96] font-black tracking-[-0.06em] sm:text-6xl lg:text-[5.1rem]">
                                {t.heading}
                                <span className="block text-white/38">
                                    {t.headingMuted}
                                </span>
                            </h1>
                            <p className="mt-6 max-w-3xl text-base leading-8 text-white/52 sm:text-lg">
                                {t.intro}
                            </p>
                        </div>
                    </section>

                    <section className="mx-auto grid max-w-[1440px] gap-4 px-5 pb-16 sm:px-8 md:grid-cols-2 lg:px-10">
                        {t.principles.map(([title, detail], index) => {
                            const Icon =
                                index === 1
                                    ? KeyRound
                                    : index === 2
                                      ? ShieldCheck
                                      : CheckCircle2;
                            return (
                                <article
                                    key={title}
                                    className="rounded-2xl border border-white/[0.08] bg-white/[0.025] p-6"
                                >
                                    <div className="grid h-11 w-11 place-items-center rounded-xl bg-[#e21b23]/10">
                                        <Icon className="h-5 w-5 text-[#ef3941]" />
                                    </div>
                                    <h2 className="mt-5 text-lg font-bold">
                                        {title}
                                    </h2>
                                    <p className="mt-3 text-sm leading-7 text-white/45">
                                        {detail}
                                    </p>
                                </article>
                            );
                        })}
                    </section>

                    <section className="border-y border-white/[0.07] bg-white/[0.015]">
                        <div className="mx-auto grid max-w-[1440px] gap-10 px-5 py-16 sm:px-8 lg:grid-cols-2 lg:px-10 lg:py-20">
                            <div>
                                <div className="text-xs font-bold tracking-[0.2em] text-[#ef3941] uppercase">
                                    {t.commercial}
                                </div>
                                <h2 className="mt-4 text-3xl font-black tracking-[-0.035em]">
                                    {t.commercialHeading}
                                </h2>
                                <p className="mt-4 text-sm leading-7 text-white/45">
                                    {t.commercialBody}
                                </p>
                                <div className="mt-7 flex flex-wrap gap-2 text-xs font-semibold text-white/60">
                                    {t.commercialSteps.map((step) => (
                                        <span
                                            key={step}
                                            className="rounded-full border border-white/10 bg-white/[0.025] px-3 py-2"
                                        >
                                            {step}
                                        </span>
                                    ))}
                                </div>
                            </div>
                            <div>
                                <div className="text-xs font-bold tracking-[0.2em] text-[#ef3941] uppercase">
                                    {t.security}
                                </div>
                                <h2 className="mt-4 text-3xl font-black tracking-[-0.035em]">
                                    {t.securityHeading}
                                </h2>
                                <div className="mt-6 grid gap-3">
                                    {t.securityControls.map((control) => (
                                        <div
                                            key={control}
                                            className="flex items-start gap-3 rounded-xl border border-white/[0.08] bg-white/[0.02] p-4"
                                        >
                                            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300/80" />
                                            <p className="text-sm leading-6 text-white/48">
                                                {control}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </section>

                    <section className="mx-auto max-w-[1440px] px-5 py-16 sm:px-8 lg:px-10">
                        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.025] p-6 sm:p-8">
                            <div className="text-xs font-bold tracking-[0.2em] text-[#ef3941] uppercase">
                                {t.evidence}
                            </div>
                            <h2 className="mt-4 text-2xl font-black tracking-[-0.03em] sm:text-3xl">
                                {t.evidenceHeading}
                            </h2>
                            <p className="mt-4 max-w-3xl text-sm leading-7 text-white/45">
                                {t.evidenceBody}
                            </p>
                            <div className="mt-7 flex flex-wrap gap-3">
                                <Link
                                    href="/products"
                                    className="rounded-xl bg-[#e21b23] px-5 py-3 text-sm font-bold transition hover:bg-[#f1252e]"
                                >
                                    {t.review}
                                </Link>
                                <Link
                                    href="/"
                                    className="rounded-xl border border-white/10 px-5 py-3 text-sm font-semibold text-white/70 transition hover:border-white/20 hover:text-white"
                                >
                                    {t.main}
                                </Link>
                            </div>
                        </div>
                    </section>
                </main>
                <PublicSiteFooter />
            </div>
        </>
    );
}
