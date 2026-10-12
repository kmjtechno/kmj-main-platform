import { Link } from '@inertiajs/react';
import {
    ArrowRight,
    Globe2,
    Mail,
    MessageCircle,
    ShieldCheck,
} from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';

const projectBrief = [
    'Your company, country and preferred contact details',
    'The business challenge, intended users and current systems',
    'Required integrations, constraints and approximate timeline',
    'Whether you need discovery, development or modernization',
];

export default function Contact() {
    return (
        <>
            <PublicSeo
                title="Contact KMJ TECHNO — International B2B Software Projects"
                description="Contact KMJ TECHNO about custom software, web and mobile applications, API integrations and cloud engineering. Send a project brief by email or LinkedIn."
                path="/contact"
                structuredData={{
                    '@context': 'https://schema.org',
                    '@type': 'ContactPage',
                    name: 'Contact KMJ TECHNO',
                    description:
                        'Business enquiries for custom software, application development and engineering services.',
                }}
            />

            <div className="min-h-screen overflow-hidden bg-[#06080b] text-white selection:bg-[#e21b23] selection:text-white">
                <div className="pointer-events-none fixed inset-0">
                    <div className="absolute -top-56 right-0 h-[36rem] w-[36rem] rounded-full bg-[#e21b23]/10 blur-[140px]" />
                </div>
                <PublicSiteHeader />

                <main id="main-content" tabIndex={-1} className="relative z-10">
                    <section className="mx-auto max-w-[1440px] px-5 pt-20 pb-20 sm:px-8 lg:px-12 lg:pt-28 lg:pb-28">
                        <div className="max-w-4xl">
                            <div className="text-[10px] font-black tracking-[0.24em] text-[#ff5962] uppercase">
                                KMJ TECHNO · Business enquiries
                            </div>
                            <h1 className="mt-6 text-5xl leading-[1.02] font-black tracking-[-0.055em] sm:text-6xl lg:text-7xl">
                                Tell us what you
                                <span className="block bg-gradient-to-r from-[#ff4149] via-[#e21b23] to-[#b21922] bg-clip-text text-transparent">
                                    want to build.
                                </span>
                            </h1>
                            <p className="mt-7 max-w-3xl text-base leading-8 text-white/65 sm:text-lg">
                                KMJ TECHNO welcomes international business
                                enquiries for custom applications, web and
                                mobile platforms, API integrations, cloud
                                workflows and modernization. Start with your
                                business goal and the scope you have in mind.
                            </p>
                            <div className="mt-8 flex flex-wrap items-center gap-2 text-xs font-semibold text-white/55">
                                <Globe2
                                    className="h-4 w-4 text-[#ff5962]"
                                    aria-hidden="true"
                                />
                                Remote B2B enquiries worldwide · Gwalior, India
                            </div>
                        </div>

                        <div className="mt-12 grid gap-5 lg:grid-cols-2">
                            <article className="rounded-[1.75rem] border border-white/[0.1] bg-white/[0.035] p-7 sm:p-9">
                                <span className="grid h-12 w-12 place-items-center rounded-xl bg-[#e21b23]/12 text-[#ff5962]">
                                    <Mail
                                        className="h-5 w-5"
                                        aria-hidden="true"
                                    />
                                </span>
                                <h2 className="mt-7 text-2xl font-black tracking-[-0.035em]">
                                    Email your project brief
                                </h2>
                                <p className="mt-3 text-sm leading-7 text-white/65">
                                    Send your requirements directly. No account
                                    or subscription is needed to enquire.
                                </p>
                                <a
                                    href="mailto:kmjtechnonet@gmail.com?subject=KMJ%20TECHNO%20B2B%20Project%20Enquiry"
                                    className="mt-7 inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-[#e21b23] px-5 text-sm font-black text-white transition hover:bg-[#f22b34]"
                                >
                                    Email KMJ TECHNO
                                    <ArrowRight
                                        className="h-4 w-4"
                                        aria-hidden="true"
                                    />
                                </a>
                                <p className="mt-4 text-sm break-all text-white/60">
                                    kmjtechnonet@gmail.com
                                </p>
                            </article>

                            <article className="rounded-[1.75rem] border border-white/[0.1] bg-white/[0.025] p-7 sm:p-9">
                                <span className="grid h-12 w-12 place-items-center rounded-xl bg-white/[0.06] text-white/80">
                                    <MessageCircle
                                        className="h-5 w-5"
                                        aria-hidden="true"
                                    />
                                </span>
                                <h2 className="mt-7 text-2xl font-black tracking-[-0.035em]">
                                    Connect on LinkedIn
                                </h2>
                                <p className="mt-3 text-sm leading-7 text-white/65">
                                    Open the verified KMJ TECHNO Company Page
                                    for business enquiries and public company
                                    updates.
                                </p>
                                <a
                                    href="https://www.linkedin.com/company/kmj-techno/"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="mt-7 inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-white/20 px-5 text-sm font-black text-white transition hover:bg-white/[0.07]"
                                >
                                    Visit Company Page
                                    <ArrowRight
                                        className="h-4 w-4"
                                        aria-hidden="true"
                                    />
                                </a>
                            </article>
                        </div>
                    </section>

                    <section className="border-y border-white/[0.07] bg-[#050608]">
                        <div className="mx-auto grid max-w-[1440px] gap-10 px-5 py-16 sm:px-8 lg:grid-cols-2 lg:items-start lg:px-12 lg:py-20">
                            <div>
                                <h2 className="text-3xl font-black tracking-[-0.045em] sm:text-4xl">
                                    What to include in your enquiry
                                </h2>
                                <p className="mt-5 max-w-lg text-sm leading-7 text-white/65">
                                    A concise outline helps assess fit and
                                    define a realistic next step. No
                                    confidential passwords, API keys or customer
                                    records should be included in an initial
                                    message.
                                </p>
                                <div className="mt-7 flex items-center gap-2 text-sm text-white/65">
                                    <ShieldCheck
                                        className="h-5 w-5 text-[#ff5962]"
                                        aria-hidden="true"
                                    />
                                    Scoping and availability are confirmed
                                    individually.
                                </div>
                            </div>
                            <ol className="grid gap-3">
                                {projectBrief.map((item, index) => (
                                    <li
                                        key={item}
                                        className="flex items-start gap-4 rounded-xl border border-white/[0.08] bg-white/[0.025] px-5 py-4"
                                    >
                                        <span className="text-xs font-black text-[#ff5962]">
                                            {String(index + 1).padStart(2, '0')}
                                        </span>
                                        <span className="text-sm leading-6 font-semibold text-white/75">
                                            {item}
                                        </span>
                                    </li>
                                ))}
                            </ol>
                        </div>
                    </section>

                    <section className="mx-auto flex max-w-[1440px] flex-col gap-5 px-5 py-16 sm:px-8 lg:flex-row lg:items-center lg:justify-between lg:px-12">
                        <div>
                            <h2 className="text-2xl font-black">
                                Explore our engineering capabilities first.
                            </h2>
                            <p className="mt-2 text-sm text-white/60">
                                Public product availability is described on
                                individual product pages.
                            </p>
                        </div>
                        <Link
                            href="/capabilities"
                            className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-white/20 px-5 text-sm font-black text-white transition hover:bg-white/[0.06]"
                        >
                            View capabilities
                            <ArrowRight
                                className="h-4 w-4"
                                aria-hidden="true"
                            />
                        </Link>
                    </section>
                </main>
                <PublicSiteFooter />
            </div>
        </>
    );
}
