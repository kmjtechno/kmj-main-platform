import { Link } from '@inertiajs/react';
import { CheckCircle2, KeyRound, ShieldCheck } from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';

const trustPrinciples = [
    {
        title: 'Lifecycle truth',
        detail: 'Active, preview, development, planned and roadmap states are shown separately so public presentation does not outrun verified delivery.',
    },
    {
        title: 'Governed commercial access',
        detail: 'A purchase request is not product access. Confirmed commercial state must resolve through authoritative entitlement and licensing controls.',
    },
    {
        title: 'Fail-closed licensing',
        detail: 'Sandbox licenses are bound to organization, product and entitlement identity and are rejected when required claims or validation boundaries are not satisfied.',
    },
    {
        title: 'Evidence before imagery',
        detail: 'KMJ TECHNO publishes real product evidence and approved brand assets. Synthetic product UI screenshots and AI/CGI-looking product imagery are not used as release proof.',
    },
];

const securityControls = [
    'Passkey-first authentication path with enrollment guidance.',
    'Tenant capability checks for organization-scoped authority.',
    'Step-up confirmation for sensitive license revocation.',
    'Session and device visibility with sign-out-other-sessions control.',
];

export default function Trust() {
    return (
        <>
            <PublicSeo
                title="Trust Center — KMJ TECHNO"
                description="KMJ TECHNO Trust Center: evidence-backed product lifecycle, governed access, licensing boundaries and release integrity."
                path="/trust"
                structuredData={{
                    '@context': 'https://schema.org',
                    '@type': 'WebPage',
                    name: 'KMJ TECHNO Trust Center',
                }}
            />

            <div className="min-h-screen overflow-hidden bg-[#06080b] text-white selection:bg-[#ef2632] selection:text-white">
                <PublicSiteHeader />
                <main>


                <section className="mx-auto max-w-[1440px] px-5 pt-16 pb-12 sm:px-8 lg:px-10 lg:pt-24">
                    <div className="max-w-4xl">
                        <div className="text-xs font-bold tracking-[0.22em] text-[#ef3941] uppercase">
                            KMJ TECHNO Trust Center
                        </div>
                        <h1 className="mt-5 text-5xl leading-[0.96] font-black tracking-[-0.06em] sm:text-6xl lg:text-[5.1rem]">
                            Trust is a product contract.
                            <span className="block text-white/38">
                                Claims stay behind evidence.
                            </span>
                        </h1>
                        <p className="mt-6 max-w-3xl text-base leading-8 text-white/52 sm:text-lg">
                            This page explains the public rules KMJ TECHNO uses
                            for product status, commercial access, licensing and
                            release evidence. It intentionally separates
                            verified capability from roadmap intent.
                        </p>
                    </div>
                </section>

                <section className="mx-auto grid max-w-[1440px] gap-4 px-5 pb-16 sm:px-8 md:grid-cols-2 lg:px-10">
                    {trustPrinciples.map((item, index) => {
                        const Icon =
                            index === 1
                                ? KeyRound
                                : index === 2
                                  ? ShieldCheck
                                  : CheckCircle2;

                        return (
                            <article
                                key={item.title}
                                className="rounded-2xl border border-white/[0.08] bg-white/[0.025] p-6"
                            >
                                <div className="grid h-11 w-11 place-items-center rounded-xl bg-[#e21b23]/10">
                                    <Icon className="h-5 w-5 text-[#ef3941]" />
                                </div>
                                <h2 className="mt-5 text-lg font-bold">
                                    {item.title}
                                </h2>
                                <p className="mt-3 text-sm leading-7 text-white/45">
                                    {item.detail}
                                </p>
                            </article>
                        );
                    })}
                </section>

                <section className="border-y border-white/[0.07] bg-white/[0.015]">
                    <div className="mx-auto grid max-w-[1440px] gap-10 px-5 py-16 sm:px-8 lg:grid-cols-2 lg:px-10 lg:py-20">
                        <div>
                            <div className="text-xs font-bold tracking-[0.2em] text-[#ef3941] uppercase">
                                Commercial authority
                            </div>
                            <h2 className="mt-4 text-3xl font-black tracking-[-0.035em]">
                                Request does not equal access.
                            </h2>
                            <p className="mt-4 text-sm leading-7 text-white/45">
                                The current platform keeps order state,
                                entitlement state and license state separate.
                                External payment-gateway configuration is
                                deliberately deferred and is not represented as
                                active.
                            </p>
                            <div className="mt-7 flex flex-wrap gap-2 text-xs font-semibold text-white/60">
                                {[
                                    'Purchase request',
                                    'Confirmed order',
                                    'Entitlement',
                                    'Governed license',
                                ].map((step) => (
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
                                Security boundaries
                            </div>
                            <h2 className="mt-4 text-3xl font-black tracking-[-0.035em]">
                                Authority is explicit.
                            </h2>
                            <div className="mt-6 grid gap-3">
                                {securityControls.map((control) => (
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
                            Product evidence policy
                        </div>
                        <h2 className="mt-4 text-2xl font-black tracking-[-0.03em] sm:text-3xl">
                            Real evidence only.
                        </h2>
                        <p className="mt-4 max-w-3xl text-sm leading-7 text-white/45">
                            Product screenshots, downloads, benchmarks and
                            production-readiness claims are published only when
                            the relevant product gate has evidence. Roadmap
                            products stay visibly labelled as roadmap,
                            development or preview until that changes.
                        </p>
                        <div className="mt-7 flex flex-wrap gap-3">
                            <Link
                                href="/products"
                                className="rounded-xl bg-[#e21b23] px-5 py-3 text-sm font-bold transition hover:bg-[#f1252e]"
                            >
                                Review product status
                            </Link>
                            <Link
                                href="/"
                                className="rounded-xl border border-white/10 px-5 py-3 text-sm font-semibold text-white/70 transition hover:border-white/20 hover:text-white"
                            >
                                Main Platform
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
