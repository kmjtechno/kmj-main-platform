import { usePage } from '@inertiajs/react';
import { KeyRound, LifeBuoy, Mail, ShieldAlert } from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';

const copy = {
    en: {
        eyebrow: 'KMJ TECHNO · Support',
        title: 'Get help without',
        titleMuted: 'guessing the authority path.',
        intro: 'Use the category that matches your issue. Support guidance does not create an entitlement, activate a license or change a product lifecycle state.',
        cards: [
            [
                'Account access',
                'Sign-in, registration, passkey and account-access questions.',
                KeyRound,
            ],
            [
                'Licensing & entitlement',
                'Questions about governed access, entitlement state or license validation.',
                LifeBuoy,
            ],
            [
                'Security concern',
                'Report a security or trust concern with enough context to investigate safely.',
                ShieldAlert,
            ],
        ],
        contact: 'Primary support contact',
        contactText:
            'Include the affected product, account or organization context, the observed error, and the time it occurred. Do not email passwords, private keys or authentication secrets.',
        response:
            'Support replies are evidence-bound: a request or acknowledgement is not proof that a product, order, entitlement or license is active.',
    },
    hi: {
        eyebrow: 'KMJ TECHNO · सहायता',
        title: 'सही authority path से',
        titleMuted: 'सीधी सहायता पाएँ।',
        intro: 'अपनी समस्या से मेल खाने वाली श्रेणी चुनें। सपोर्ट मार्गदर्शन अपने-आप entitlement नहीं बनाता, license सक्रिय नहीं करता और product lifecycle स्थिति नहीं बदलता।',
        cards: [
            [
                'अकाउंट पहुँच',
                'Sign-in, registration, passkey और account-access से जुड़े प्रश्न।',
                KeyRound,
            ],
            [
                'लाइसेंसिंग और entitlement',
                'नियंत्रित पहुँच, entitlement स्थिति या license validation से जुड़े प्रश्न।',
                LifeBuoy,
            ],
            [
                'सुरक्षा चिंता',
                'सुरक्षित जाँच के लिए पर्याप्त संदर्भ के साथ security या trust concern रिपोर्ट करें।',
                ShieldAlert,
            ],
        ],
        contact: 'मुख्य सपोर्ट संपर्क',
        contactText:
            'प्रभावित उत्पाद, अकाउंट या organization का संदर्भ, दिखी हुई error और उसका समय शामिल करें। Password, private key या authentication secret ईमेल न करें।',
        response:
            'सपोर्ट जवाब evidence-bound हैं: request या acknowledgement इस बात का प्रमाण नहीं है कि product, order, entitlement या license सक्रिय है।',
    },
} as const;

export default function Support() {
    const { localization } = usePage().props;
    const language = localization.locale === 'hi' ? 'hi' : 'en';
    const t = copy[language];

    return (
        <>
            <PublicSeo
                title={
                    language === 'hi'
                        ? 'सहायता — KMJ TECHNO'
                        : 'Support — KMJ TECHNO'
                }
                description={
                    language === 'hi'
                        ? 'KMJ TECHNO अकाउंट, लाइसेंसिंग, entitlement और security सहायता।'
                        : 'KMJ TECHNO support for account access, licensing, entitlements and security concerns.'
                }
                path="/support"
                localized
                structuredData={{
                    '@context': 'https://schema.org',
                    '@type': 'ContactPage',
                    name: 'KMJ TECHNO Support',
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

                    <section className="mx-auto grid max-w-[1280px] gap-4 px-5 pb-16 sm:px-8 md:grid-cols-3 lg:px-10">
                        {t.cards.map(([title, detail, Icon]) => (
                            <article
                                key={title}
                                className="rounded-2xl border border-white/[0.08] bg-white/[0.025] p-6"
                            >
                                <span className="grid h-11 w-11 place-items-center rounded-xl bg-[#e21b23]/10 text-[#ff5962]">
                                    <Icon className="h-5 w-5" />
                                </span>
                                <h2 className="mt-5 text-lg font-black">
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
                            <div className="grid gap-8 rounded-2xl border border-white/[0.08] bg-[#090b0f] p-6 sm:p-8 lg:grid-cols-[.7fr_1.3fr]">
                                <div>
                                    <div className="text-[10px] font-black tracking-[0.2em] text-[#ff5962] uppercase">
                                        {t.contact}
                                    </div>
                                    <a
                                        href="mailto:kmjtechno.net@gmail.com"
                                        className="mt-4 inline-flex items-center gap-2 text-lg font-black text-white/88 transition hover:text-white"
                                    >
                                        <Mail className="h-5 w-5" />{' '}
                                        kmjtechno.net@gmail.com
                                    </a>
                                </div>
                                <div className="space-y-4 text-sm leading-7 text-white/46">
                                    <p>{t.contactText}</p>
                                    <p>{t.response}</p>
                                </div>
                            </div>
                        </div>
                    </section>
                </main>
                <PublicSiteFooter />
            </div>
        </>
    );
}
