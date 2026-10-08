import { Link } from '@inertiajs/react';
import { ArrowRight, FileText, RotateCcw, ShieldCheck } from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';

const documents = [
    [
        '/terms',
        'Terms & Conditions',
        'Commercial, account, licensing and service terms.',
        FileText,
    ],
    [
        '/privacy',
        'Privacy Policy',
        'How personal data is collected, used, protected and shared.',
        ShieldCheck,
    ],
    [
        '/refund-policy',
        'Refund & Cancellation',
        'Digital products, subscriptions, services and remedies.',
        RotateCcw,
    ],
    [
        '/acceptable-use',
        'Acceptable Use',
        'Security, abuse, automation and responsible-use rules.',
        ShieldCheck,
    ],
    [
        '/cookie-policy',
        'Cookie Policy',
        'Device storage, necessary cookies and optional analytics.',
        FileText,
    ],
] as const;

export default function LegalCenter() {
    return (
        <>
            <PublicSeo
                title="Legal Center — KMJ TECHNO"
                description="KMJ TECHNO legal terms, privacy, refunds, acceptable use and cookie policies for international software and cloud services."
                path="/legal"
                structuredData={{
                    '@context': 'https://schema.org',
                    '@type': 'CollectionPage',
                    name: 'KMJ TECHNO Legal Center',
                }}
            />
            <div className="min-h-screen bg-[#05070a] text-white">
                <PublicSiteHeader />
                <main
                    id="main-content"
                    tabIndex={-1}
                    className="mx-auto max-w-[1180px] px-5 py-16 sm:px-8 lg:px-10 lg:py-24"
                >
                    <div className="max-w-4xl">
                        <div className="text-[10px] font-black tracking-[0.2em] text-[#ef3941] uppercase">
                            KMJ TECHNO · Legal Center
                        </div>
                        <h1 className="mt-5 text-5xl font-black tracking-[-0.055em] sm:text-6xl">
                            Clear terms for a global technology business.
                        </h1>
                        <p className="mt-6 max-w-3xl text-base leading-8 text-white/52">
                            These documents govern KMJ websites, accounts,
                            software, cloud services, previews, subscriptions,
                            licenses and digital products. Mandatory local
                            consumer and privacy rights always remain protected.
                        </p>
                    </div>
                    <div className="mt-12 grid gap-4 md:grid-cols-2">
                        {documents.map(([href, title, description, Icon]) => (
                            <Link
                                key={href}
                                href={href}
                                className="group rounded-2xl border border-white/[0.08] bg-[#0a0d12] p-6 transition hover:-translate-y-0.5 hover:border-white/[0.16]"
                            >
                                <div className="flex items-start justify-between gap-5">
                                    <div className="grid h-11 w-11 place-items-center rounded-xl bg-[#e21b23]/10 text-[#ef3941]">
                                        <Icon className="h-5 w-5" />
                                    </div>
                                    <ArrowRight className="h-4 w-4 text-white/65 transition group-hover:text-white/70" />
                                </div>
                                <h2 className="mt-5 text-xl font-black">
                                    {title}
                                </h2>
                                <p className="mt-2 text-sm leading-7 text-white/65">
                                    {description}
                                </p>
                            </Link>
                        ))}
                    </div>
                    <div className="mt-12 rounded-2xl border border-white/[0.08] bg-white/[0.025] p-6 text-sm leading-7 text-white/65">
                        Legal, privacy, billing or grievance enquiries may be
                        sent to{' '}
                        <span className="font-bold text-white/70">
                            kmjtechno.net@gmail.com
                        </span>
                        . Product-specific enterprise agreements or signed order
                        forms may supplement these public terms.
                    </div>
                </main>
                <PublicSiteFooter />
            </div>
        </>
    );
}
