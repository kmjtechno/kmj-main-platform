import { Link, usePage } from '@inertiajs/react';
import { ArrowRight, BookOpenCheck, Scale, ShieldCheck } from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';

const copy = {
    en: {
        eyebrow: 'KMJ TECHNO · Insights',
        title: 'Engineering principles',
        titleMuted: 'behind the public platform.',
        intro: 'Short public notes on how KMJ TECHNO keeps product claims, automation and customer authority aligned with evidence.',
        notes: [
            [
                'Lifecycle truth before launch language',
                'A polished interface is not release evidence. Product lifecycle, access and proof should stay independently verifiable.',
                BookOpenCheck,
            ],
            [
                'Automation stays inside authority',
                'Autonomous work is useful when task scope, retries, artifacts and promotion boundaries are explicit and observable.',
                ShieldCheck,
            ],
            [
                'Commercial state is not inferred',
                'A request, payment event, entitlement and license are separate states. Customer access should resolve from authoritative controls.',
                Scale,
            ],
        ],
        trust: 'Review the trust center',
    },
    hi: {
        eyebrow: 'KMJ TECHNO · इनसाइट्स',
        title: 'सार्वजनिक प्लेटफ़ॉर्म के पीछे',
        titleMuted: 'इंजीनियरिंग सिद्धांत।',
        intro: 'KMJ TECHNO उत्पाद दावों, automation और customer authority को प्रमाण के साथ कैसे जोड़कर रखता है—इस पर छोटे सार्वजनिक नोट्स।',
        notes: [
            [
                'Launch language से पहले lifecycle truth',
                'सिर्फ polished interface release evidence नहीं है। Product lifecycle, access और proof अलग-अलग सत्यापित होने चाहिए।',
                BookOpenCheck,
            ],
            [
                'Automation authority के अंदर रहे',
                'Autonomous work तभी उपयोगी है जब task scope, retries, artifacts और promotion boundaries स्पष्ट और observable हों।',
                ShieldCheck,
            ],
            [
                'Commercial state अनुमान से नहीं',
                'Request, payment event, entitlement और license अलग अवस्थाएँ हैं। Customer access authoritative controls से तय होना चाहिए।',
                Scale,
            ],
        ],
        trust: 'Trust center देखें',
    },
} as const;

export default function Insights() {
    const { localization } = usePage().props;
    const language = localization.locale === 'hi' ? 'hi' : 'en';
    const t = copy[language];

    return (
        <>
            <PublicSeo
                title={
                    language === 'hi'
                        ? 'इनसाइट्स — KMJ TECHNO'
                        : 'Insights — KMJ TECHNO'
                }
                description={
                    language === 'hi'
                        ? 'KMJ TECHNO के evidence-led product, automation और authority engineering principles।'
                        : 'KMJ TECHNO notes on evidence-led product, automation and authority engineering.'
                }
                path="/insights"
                localized
                type="article"
                structuredData={{
                    '@context': 'https://schema.org',
                    '@type': 'CollectionPage',
                    name: 'KMJ TECHNO Insights',
                }}
            />
            <div className="min-h-screen bg-[#06080b] text-white selection:bg-[#e21b23] selection:text-white">
                <PublicSiteHeader />
                <main>
                    <section className="mx-auto max-w-[1280px] px-5 pt-18 pb-14 sm:px-8 lg:px-10 lg:pt-24">
                        <div className="max-w-4xl">
                            <div className="text-[10px] font-black tracking-[0.22em] text-[#ff5962] uppercase">
                                {t.eyebrow}
                            </div>
                            <h1 className="mt-5 text-5xl leading-[0.98] font-black tracking-[-0.055em] sm:text-6xl">
                                {t.title}
                                <span className="block text-white/34">
                                    {t.titleMuted}
                                </span>
                            </h1>
                            <p className="mt-6 max-w-3xl text-base leading-8 text-white/50">
                                {t.intro}
                            </p>
                        </div>
                    </section>

                    <section className="mx-auto grid max-w-[1280px] gap-4 px-5 pb-18 sm:px-8 lg:grid-cols-3 lg:px-10">
                        {t.notes.map(([title, detail, Icon], index) => (
                            <article
                                key={title}
                                className="rounded-2xl border border-white/[0.08] bg-white/[0.025] p-6"
                            >
                                <div className="flex items-center justify-between">
                                    <span className="grid h-11 w-11 place-items-center rounded-xl bg-[#e21b23]/10 text-[#ff5962]">
                                        <Icon className="h-5 w-5" />
                                    </span>
                                    <span className="text-[10px] font-black tracking-[0.16em] text-white/22">
                                        0{index + 1}
                                    </span>
                                </div>
                                <h2 className="mt-6 text-xl font-black tracking-[-0.025em]">
                                    {title}
                                </h2>
                                <p className="mt-3 text-sm leading-7 text-white/44">
                                    {detail}
                                </p>
                            </article>
                        ))}
                    </section>

                    <section className="border-y border-white/[0.07] bg-white/[0.018]">
                        <div className="mx-auto max-w-[1280px] px-5 py-14 sm:px-8 lg:px-10">
                            <Link
                                href="/trust"
                                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.025] px-5 py-3 text-sm font-black text-white/76 transition hover:border-white/20 hover:text-white"
                            >
                                {t.trust}
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
