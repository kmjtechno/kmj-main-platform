import { Link } from '@inertiajs/react';
import { ArrowRight, CheckCircle2 } from 'lucide-react';

const journeySteps = [
    [
        '01',
        'Discover',
        'Explore KMJ products and understand their current lifecycle state.',
    ],
    [
        '02',
        'Choose',
        'Select an available plan, configuration or approved access path.',
    ],
    [
        '03',
        'Purchase or request',
        'Buy when commercial access is enabled, or request preview access when it is not.',
    ],
    [
        '04',
        'Receive governed access',
        'Eligible access is delivered through the KMJ Main Platform and its entitlement rules.',
    ],
];

const lifecycleStates = [
    [
        'Available',
        'Ready for customer access where commercial requirements are active.',
    ],
    ['Preview', 'Controlled evaluation access while validation continues.'],
    [
        'Research',
        'Active engineering or validation work; customer-ready availability is not implied.',
    ],
    [
        'Planned',
        'Planned product direction that has not yet reached a customer-ready release.',
    ],
];

export default function LandingJourney({
    showCreateAccount,
}: {
    showCreateAccount: boolean;
}) {
    return (
        <>
            <section className="border-y border-white/[0.07] bg-[#07090d]">
                <div className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 lg:px-12 lg:py-24">
                    <div className="max-w-3xl">
                        <div className="text-[10px] font-black tracking-[0.2em] text-[#ee3942] uppercase">
                            From discovery to access
                        </div>
                        <h2 className="mt-4 text-4xl font-black tracking-[-0.045em] sm:text-5xl">
                            A clear path from product discovery
                            <span className="block text-white/48">
                                to governed access.
                            </span>
                        </h2>
                        <p className="mt-5 max-w-2xl text-sm leading-7 text-white/55 sm:text-base">
                            Product availability and access follow the verified
                            lifecycle and commercial rules of each KMJ product.
                        </p>
                    </div>

                    <div className="mt-10 grid gap-px overflow-hidden rounded-[1.5rem] border border-white/[0.08] bg-white/[0.08] md:grid-cols-2 xl:grid-cols-4">
                        {journeySteps.map(([number, title, text]) => (
                            <article key={number} className="bg-[#090c11] p-6">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-black text-[#ff4c55]">
                                        {number}
                                    </span>
                                    <ArrowRight className="h-4 w-4 text-white/20" />
                                </div>
                                <h3 className="mt-8 text-lg font-black tracking-[-0.02em]">
                                    {title}
                                </h3>
                                <p className="mt-3 text-sm leading-6 text-white/46">
                                    {text}
                                </p>
                            </article>
                        ))}
                    </div>
                </div>
            </section>

            <section className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 lg:px-12 lg:py-24">
                <div className="grid gap-10 lg:grid-cols-[.72fr_1.28fr]">
                    <div>
                        <div className="text-[10px] font-black tracking-[0.2em] text-[#ee3942] uppercase">
                            Product lifecycle
                        </div>
                        <h2 className="mt-4 text-4xl font-black tracking-[-0.045em] sm:text-5xl">
                            Know where every
                            <span className="block text-white/48">
                                product stands.
                            </span>
                        </h2>
                        <p className="mt-5 max-w-lg text-sm leading-7 text-white/52">
                            KMJ separates released capability from previews,
                            active development and future roadmap work.
                        </p>
                        <Link
                            href="/products"
                            className="mt-7 inline-flex items-center gap-2 text-sm font-black text-white/74 transition hover:text-white"
                        >
                            View product status
                            <ArrowRight className="h-4 w-4" />
                        </Link>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                        {lifecycleStates.map(([title, text]) => (
                            <article
                                key={title}
                                className="rounded-[1.4rem] border border-white/[0.075] bg-[#0a0d12] p-5"
                            >
                                <div className="flex items-center gap-3">
                                    <span className="grid h-9 w-9 place-items-center rounded-xl border border-[#e21b23]/16 bg-[#e21b23]/[0.07]">
                                        <CheckCircle2 className="h-4 w-4 text-[#ff4c55]" />
                                    </span>
                                    <h3 className="text-base font-black">
                                        {title}
                                    </h3>
                                </div>
                                <p className="mt-4 text-sm leading-6 text-white/46">
                                    {text}
                                </p>
                            </article>
                        ))}
                    </div>
                </div>
            </section>

            <section className="mx-auto max-w-[1440px] px-5 pb-20 sm:px-8 lg:px-12 lg:pb-28">
                <div className="relative overflow-hidden rounded-[2rem] border border-white/[0.09] bg-[#0a0d12] px-6 py-12 sm:px-10 lg:px-14 lg:py-16">
                    <div className="pointer-events-none absolute -top-32 -right-24 h-80 w-80 rounded-full bg-[#e21b23]/12 blur-[100px]" />
                    <div className="relative grid gap-8 lg:grid-cols-[1fr_auto] lg:items-end">
                        <div className="max-w-3xl">
                            <div className="text-[10px] font-black tracking-[0.2em] text-[#ee3942] uppercase">
                                Build with KMJ
                            </div>
                            <h2 className="mt-4 text-4xl font-black tracking-[-0.05em] sm:text-5xl">
                                Explore the technology behind the next
                                generation of KMJ systems.
                            </h2>
                            <p className="mt-5 max-w-2xl text-sm leading-7 text-white/55 sm:text-base">
                                From cloud infrastructure and engineering
                                software to calibration and immersive cinema,
                                KMJ products are connected through one governed
                                customer experience.
                            </p>
                        </div>
                        <div className="flex flex-col gap-3 sm:flex-row lg:flex-col">
                            <Link
                                href="/products"
                                className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-[#e21b23] px-6 text-sm font-black transition hover:-translate-y-0.5 hover:bg-[#f22b34]"
                            >
                                Explore KMJ Products
                                <ArrowRight className="h-4 w-4" />
                            </Link>
                            {showCreateAccount && (
                                <Link
                                    href="/register"
                                    className="inline-flex h-12 items-center justify-center rounded-xl border border-white/12 bg-white/[0.035] px-6 text-sm font-bold text-white/78 transition hover:border-white/22 hover:bg-white/[0.07] hover:text-white"
                                >
                                    Create Customer Account
                                </Link>
                            )}
                        </div>
                    </div>
                </div>
            </section>
        </>
    );
}
