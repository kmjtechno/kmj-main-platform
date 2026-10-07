import { Link, usePage } from '@inertiajs/react';
import {
    ArrowRight,
    BookOpen,
    KeyRound,
    Layers3,
    ShieldCheck,
} from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';

const copy = {
    en: {
        eyebrow: 'KMJ TECHNO · Documentation',
        title: 'Public documentation with',
        titleMuted: 'clear authority boundaries.',
        intro: 'Start with the public sources that describe KMJ product status, customer access, licensing, security and platform boundaries. Documentation never upgrades a roadmap item into a released product.',
        cards: [
            [
                '/products',
                'Product lifecycle',
                'Check canonical product status, public evidence and commercial availability.',
                Layers3,
            ],
            [
                '/trust',
                'Trust & security',
                'Review lifecycle truth, governed access, licensing boundaries and release evidence.',
                ShieldCheck,
            ],
            [
                '/legal',
                'Legal & policy',
                'Read the public terms, privacy, refund, acceptable-use and cookie policies.',
                BookOpen,
            ],
            [
                '/support',
                'Access & licensing help',
                'Use the support center for account, entitlement, licensing or security questions.',
                KeyRound,
            ],
        ],
        ruleTitle: 'Documentation rule',
        rule: 'Git and verified platform state remain authoritative for engineering and release status. Public documentation explains that state; it does not replace it.',
        products: 'Browse products',
    },
    hi: {
        eyebrow: 'KMJ TECHNO · दस्तावेज़',
        title: 'सार्वजनिक दस्तावेज़,',
        titleMuted: 'स्पष्ट अधिकार सीमाओं के साथ।',
        intro: 'KMJ उत्पाद स्थिति, ग्राहक पहुँच, लाइसेंसिंग, सुरक्षा और प्लेटफ़ॉर्म सीमाओं के लिए इन सार्वजनिक स्रोतों से शुरुआत करें। दस्तावेज़ किसी रोडमैप आइटम को रिलीज़ हुआ उत्पाद घोषित नहीं करते।',
        cards: [
            [
                '/products',
                'उत्पाद जीवनचक्र',
                'कैनोनिकल उत्पाद स्थिति, सार्वजनिक प्रमाण और व्यावसायिक उपलब्धता देखें।',
                Layers3,
            ],
            [
                '/trust',
                'विश्वास और सुरक्षा',
                'जीवनचक्र सत्य, नियंत्रित पहुँच, लाइसेंसिंग सीमाएँ और रिलीज़ प्रमाण देखें।',
                ShieldCheck,
            ],
            [
                '/legal',
                'कानूनी और नीति',
                'सार्वजनिक शर्तें, गोपनीयता, रिफंड, स्वीकार्य उपयोग और कुकी नीतियाँ पढ़ें।',
                BookOpen,
            ],
            [
                '/support',
                'पहुँच और लाइसेंसिंग सहायता',
                'अकाउंट, एंटाइटलमेंट, लाइसेंसिंग या सुरक्षा प्रश्नों के लिए सपोर्ट सेंटर उपयोग करें।',
                KeyRound,
            ],
        ],
        ruleTitle: 'दस्तावेज़ नियम',
        rule: 'इंजीनियरिंग और रिलीज़ स्थिति के लिए Git और सत्यापित प्लेटफ़ॉर्म स्थिति ही authoritative हैं। सार्वजनिक दस्तावेज़ उस स्थिति को समझाते हैं; उसे बदलते नहीं हैं।',
        products: 'उत्पाद देखें',
    },
} as const;

export default function Docs() {
    const { localization } = usePage().props;
    const language = localization.locale === 'hi' ? 'hi' : 'en';
    const t = copy[language];

    return (
        <>
            <PublicSeo
                title={
                    language === 'hi'
                        ? 'दस्तावेज़ — KMJ TECHNO'
                        : 'Documentation — KMJ TECHNO'
                }
                description={
                    language === 'hi'
                        ? 'KMJ TECHNO के उत्पाद, सुरक्षा, लाइसेंसिंग और प्लेटफ़ॉर्म सीमाओं के सार्वजनिक दस्तावेज़।'
                        : 'Public KMJ TECHNO documentation for products, security, licensing and platform boundaries.'
                }
                path="/docs"
                localized
                structuredData={{
                    '@context': 'https://schema.org',
                    '@type': 'CollectionPage',
                    name: 'KMJ TECHNO Documentation',
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

                    <section className="mx-auto grid max-w-[1280px] gap-4 px-5 pb-18 sm:px-8 md:grid-cols-2 lg:px-10">
                        {t.cards.map(([href, title, detail, Icon]) => (
                            <Link
                                key={href}
                                href={href}
                                className="group rounded-2xl border border-white/[0.08] bg-white/[0.025] p-6 transition hover:-translate-y-0.5 hover:border-white/[0.16]"
                            >
                                <div className="flex items-start justify-between gap-4">
                                    <span className="grid h-11 w-11 place-items-center rounded-xl bg-[#e21b23]/10 text-[#ff5962]">
                                        <Icon className="h-5 w-5" />
                                    </span>
                                    <ArrowRight className="h-4 w-4 text-white/25 transition group-hover:text-white/70" />
                                </div>
                                <h2 className="mt-5 text-xl font-black">
                                    {title}
                                </h2>
                                <p className="mt-3 text-sm leading-7 text-white/44">
                                    {detail}
                                </p>
                            </Link>
                        ))}
                    </section>

                    <section className="border-y border-white/[0.07] bg-white/[0.018]">
                        <div className="mx-auto max-w-[1280px] px-5 py-14 sm:px-8 lg:px-10">
                            <div className="rounded-2xl border border-white/[0.08] bg-[#090b0f] p-6 sm:p-8">
                                <div className="text-[10px] font-black tracking-[0.2em] text-[#ff5962] uppercase">
                                    {t.ruleTitle}
                                </div>
                                <p className="mt-4 max-w-4xl text-sm leading-7 text-white/48">
                                    {t.rule}
                                </p>
                                <Link
                                    href="/products"
                                    className="mt-6 inline-flex items-center gap-2 text-sm font-black text-white/80 transition hover:text-white"
                                >
                                    {t.products}
                                    <ArrowRight className="h-4 w-4" />
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
