import { Link, usePage } from '@inertiajs/react';
import { ArrowRight, Building2, ShieldCheck, Workflow } from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';

const copy = {
    en: {
        title: 'Company — KMJ TECHNO',
        description:
            'KMJ TECHNO company profile, operating model and product authority.',
        eyebrow: 'Company',
        heading:
            'Built to turn ambitious software ideas into governed products.',
        intro: 'KMJ TECHNO designs software, cloud systems and intelligent product infrastructure with one operating principle: product claims, customer access and release state should resolve from authoritative systems.',
        metrics: [
            ['Operating model', 'Product + platform'],
            ['Authority', 'KMJ Main Platform'],
            ['Source of truth', 'Git'],
            ['Product policy', 'Evidence-led'],
        ],
        principles: [
            [
                'Clear boundaries',
                'Each product has a defined lifecycle, authority boundary and customer-access state.',
                Building2,
            ],
            [
                'Governed delivery',
                'Entitlements, licenses and release evidence remain explicit rather than inferred.',
                ShieldCheck,
            ],
            [
                'Automation with control',
                'Automation accelerates work without silently overriding production or commercial authority.',
                Workflow,
            ],
        ],
        platformEyebrow: 'Operating model',
        platformHeading: 'The Main Platform is the business authority.',
        platformBody:
            'KMJ Main Platform owns organization, customer, product, licensing, release and automation authority. Engineering systems can integrate with it, but they do not silently become the customer or commercial source of truth.',
        products: 'Explore products',
        trust: 'Trust center',
        boundary: 'Boundary',
        boundaryText:
            'KMJ Cloud Nexus remains a separate engineering IDE and is not a Main Platform runtime dependency.',
    },
    hi: {
        title: 'कंपनी — KMJ TECHNO',
        description:
            'KMJ TECHNO का company profile, operating model और product authority.',
        eyebrow: 'कंपनी',
        heading:
            'महत्वाकांक्षी software ideas को governed products में बदलने के लिए बनाया गया।',
        intro: 'KMJ TECHNO software, cloud systems और intelligent product infrastructure बनाता है। हमारा मूल सिद्धांत है कि product claims, customer access और release state authoritative systems से तय हों।',
        metrics: [
            ['Operating model', 'Product + platform'],
            ['Authority', 'KMJ Main Platform'],
            ['Source of truth', 'Git'],
            ['Product policy', 'Evidence-led'],
        ],
        principles: [
            [
                'स्पष्ट सीमाएँ',
                'हर product की lifecycle, authority boundary और customer-access state स्पष्ट होती है।',
                Building2,
            ],
            [
                'Governed delivery',
                'Entitlements, licenses और release evidence अनुमान से नहीं, स्पष्ट authority से तय होते हैं।',
                ShieldCheck,
            ],
            [
                'Control के साथ automation',
                'Automation काम तेज करता है, लेकिन production या commercial authority को चुपचाप override नहीं करता।',
                Workflow,
            ],
        ],
        platformEyebrow: 'Operating model',
        platformHeading: 'Main Platform business authority है।',
        platformBody:
            'KMJ Main Platform organization, customer, product, licensing, release और automation authority का मालिक है। Engineering systems इससे integrate कर सकते हैं, लेकिन वे customer या commercial source of truth अपने-आप नहीं बनते।',
        products: 'उत्पाद देखें',
        trust: 'विश्वास केंद्र',
        boundary: 'सीमा',
        boundaryText:
            'KMJ Cloud Nexus एक अलग engineering IDE है और Main Platform की runtime dependency नहीं है।',
    },
} as const;

export default function Company() {
    const { localization } = usePage().props;
    const language = localization.locale === 'hi' ? 'hi' : 'en';
    const t = copy[language];

    return (
        <>
            <PublicSeo
                title={t.title}
                description={t.description}
                path="/company"
                localized
            />
            <div className="min-h-screen bg-[#06080b] text-white selection:bg-[#e21b23] selection:text-white">
                <PublicSiteHeader />
                <main id="main-content">
                    <section className="mx-auto max-w-[1440px] px-5 pt-20 pb-16 sm:px-8 lg:px-12 lg:pt-28">
                        <div className="max-w-4xl">
                            <div className="text-[10px] font-black tracking-[0.22em] text-[#ff5962] uppercase">
                                {t.eyebrow}
                            </div>
                            <h1 className="mt-5 text-5xl leading-[0.98] font-black tracking-[-0.055em] sm:text-6xl lg:text-7xl">
                                {t.heading}
                            </h1>
                            <p className="mt-7 max-w-3xl text-base leading-8 text-white/50 sm:text-lg">
                                {t.intro}
                            </p>
                        </div>
                        <div className="mt-14 grid overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.06] sm:grid-cols-2 lg:grid-cols-4">
                            {t.metrics.map(([label, value]) => (
                                <div
                                    key={label}
                                    className="bg-[#080a0e] px-6 py-6"
                                >
                                    <div className="text-[9px] font-black tracking-[0.16em] text-white/28 uppercase">
                                        {label}
                                    </div>
                                    <div className="mt-2 text-base font-black text-white/82">
                                        {value}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </section>

                    <section className="border-y border-white/[0.07] bg-[#090c10]/70">
                        <div className="mx-auto grid max-w-[1440px] gap-4 px-5 py-20 sm:px-8 lg:grid-cols-3 lg:px-12">
                            {t.principles.map(([title, detail, Icon]) => (
                                <article
                                    key={title}
                                    className="rounded-2xl border border-white/[0.08] bg-[#07090d] p-7"
                                >
                                    <div className="grid h-11 w-11 place-items-center rounded-xl border border-[#e21b23]/20 bg-[#e21b23]/10">
                                        <Icon className="h-5 w-5 text-[#ff5962]" />
                                    </div>
                                    <h2 className="mt-6 text-xl font-black">
                                        {title}
                                    </h2>
                                    <p className="mt-3 text-sm leading-7 text-white/42">
                                        {detail}
                                    </p>
                                </article>
                            ))}
                        </div>
                    </section>

                    <section className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 lg:px-12 lg:py-24">
                        <div className="grid gap-10 rounded-[2rem] border border-white/[0.08] bg-gradient-to-br from-white/[0.04] to-transparent p-8 sm:p-10 lg:grid-cols-[1.2fr_.8fr]">
                            <div>
                                <div className="text-[10px] font-black tracking-[0.2em] text-[#ff5962] uppercase">
                                    {t.platformEyebrow}
                                </div>
                                <h2 className="mt-4 max-w-2xl text-3xl font-black tracking-[-0.04em] sm:text-4xl">
                                    {t.platformHeading}
                                </h2>
                                <p className="mt-5 max-w-2xl text-sm leading-7 text-white/44">
                                    {t.platformBody}
                                </p>
                                <div className="mt-7 flex flex-wrap gap-3">
                                    <Link
                                        href="/products"
                                        className="inline-flex h-11 items-center gap-2 rounded-xl bg-white px-5 text-sm font-black text-black"
                                    >
                                        {t.products}
                                        <ArrowRight className="h-4 w-4" />
                                    </Link>
                                    <Link
                                        href="/trust"
                                        className="inline-flex h-11 items-center rounded-xl border border-white/10 px-5 text-sm font-bold text-white/68"
                                    >
                                        {t.trust}
                                    </Link>
                                </div>
                            </div>
                            <div className="rounded-2xl border border-white/[0.08] bg-[#07090d] p-6">
                                <div className="text-[9px] font-black tracking-[0.16em] text-white/28 uppercase">
                                    {t.boundary}
                                </div>
                                <p className="mt-4 text-sm leading-7 text-white/48">
                                    {t.boundaryText}
                                </p>
                            </div>
                        </div>
                    </section>
                </main>
                <PublicSiteFooter />
            </div>
        </>
    );
}
