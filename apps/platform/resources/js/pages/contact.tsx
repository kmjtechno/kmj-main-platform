import { Link } from '@inertiajs/react';
import { ArrowUpRight, Mail, ShieldCheck } from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';

export default function Contact() {
    return (
        <>
            <PublicSeo
                title="Contact KMJ TECHNO — Sales, Support & Billing"
                description="Contact KMJ TECHNO for business enquiries, software support, billing, refunds and payment questions."
                path="/contact"
                structuredData={{
                    '@context': 'https://schema.org',
                    '@type': 'ContactPage',
                    name: 'Contact KMJ TECHNO',
                }}
            />
            <div className="min-h-screen bg-[#06080b] text-white">
                <PublicSiteHeader />
                <main
                    id="main-content"
                    tabIndex={-1}
                    className="mx-auto w-full max-w-[1120px] px-5 py-20 sm:px-8 lg:px-12 lg:py-28"
                >
                    <p className="text-xs font-black tracking-[0.2em] text-[#ff5962] uppercase">
                        KMJ TECHNO · Contact
                    </p>
                    <h1 className="mt-6 max-w-3xl text-4xl font-black tracking-tight sm:text-6xl">
                        Contact our team
                    </h1>
                    <p className="mt-6 max-w-3xl text-base leading-8 text-white/70">
                        For software licensing, sales, international business enquiries,
                        technical support, payments, invoices, cancellations or refund requests,
                        reach KMJ TECHNO using the contact details below.
                    </p>
                    <section className="mt-12 grid gap-5 md:grid-cols-2" aria-label="Contact channels">
                        <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-7">
                            <Mail className="h-6 w-6 text-[#ff5962]" aria-hidden="true" />
                            <h2 className="mt-4 text-lg font-bold">Email support &amp; billing</h2>
                            <a
                                href="mailto:kmjtechno.net@gmail.com"
                                className="mt-3 inline-block break-all text-base font-semibold text-white underline decoration-[#e21b23] underline-offset-4"
                            >
                                kmjtechno.net@gmail.com
                            </a>
                            <p className="mt-4 text-sm leading-7 text-white/60">
                                For an existing order, include the order reference and product.
                                Never email card numbers, passwords, OTPs or API secrets.
                            </p>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-7">
                            <ShieldCheck className="h-6 w-6 text-[#ff5962]" aria-hidden="true" />
                            <h2 className="mt-4 text-lg font-bold">Orders, cancellations &amp; remedies</h2>
                            <p className="mt-3 text-sm leading-7 text-white/65">
                                Read the published policy for digital-product refunds,
                                subscription cancellations, delivery issues and disputes.
                            </p>
                            <Link
                                href="/refund-policy"
                                className="mt-4 inline-flex items-center gap-2 text-sm font-bold text-white underline decoration-[#e21b23] underline-offset-4"
                            >
                                Refund &amp; Cancellation Policy
                                <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
                            </Link>
                        </div>
                    </section>
                    <p className="mt-10 text-sm leading-7 text-white/60">
                        For legal information, see our{' '}
                        <Link href="/terms" className="underline underline-offset-4">
                            Terms &amp; Conditions
                        </Link>{' '}
                        and{' '}
                        <Link href="/privacy" className="underline underline-offset-4">
                            Privacy Policy
                        </Link>
                        . Our checkout is activated only when the relevant payment provider
                        has been verified and enabled.
                    </p>
                </main>
                <PublicSiteFooter />
            </div>
        </>
    );
}
