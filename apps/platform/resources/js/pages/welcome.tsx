import { Head, Link, usePage } from '@inertiajs/react';
import {
    ArrowRight,
    Boxes,
    CheckCircle2,
    Cpu,
    Fingerprint,
    Globe2,
    KeyRound,
    Layers3,
    LockKeyhole,
    RadioTower,
    ShieldCheck,
    Sparkles,
    Workflow,
} from 'lucide-react';
import { dashboard, login, register } from '@/routes';

const capabilities = [
    {
        icon: Layers3,
        title: 'Unified control plane',
        text: 'Identity, organizations, products, entitlements, licensing, releases, support and operations built around one authority model.',
        status: 'Foundation active',
    },
    {
        icon: KeyRound,
        title: 'Entitlements & licensing',
        text: 'Commercial rights are modeled separately from payments, device activation and product validation for safer product integrations.',
        status: 'Validation active',
    },
    {
        icon: ShieldCheck,
        title: 'Trusted releases',
        text: 'Release metadata, verification and revocation are designed as first-class platform capabilities instead of file-download shortcuts.',
        status: 'Release track queued',
    },
    {
        icon: Sparkles,
        title: 'Governed automation',
        text: 'Kristi operations are designed around scoped tools, policy gates, independent verification, audit and human approval for high-risk actions.',
        status: 'Automation track active',
    },
];

const principles = [
    'Cloud-first generative AI with verified-zero routing policy',
    'No paid AI fallback unless policy is explicitly changed',
    'Versioned APIs and events between products and platform',
    'Security, auditability, recovery and rollback by design',
];

const authority = [
    'Account',
    'Organization',
    'Subscription',
    'Entitlement',
    'License',
    'Device',
];

export default function Welcome() {
    const stagingSyncBadge = (
        <div className="fixed right-4 bottom-4 z-50 rounded-full border border-emerald-400/20 bg-[#08110d]/95 px-3 py-2 text-[10px] font-bold tracking-[0.12em] text-emerald-300 uppercase shadow-2xl backdrop-blur">
            Live staging · frontend sync
        </div>
    );
    const { auth } = usePage().props;

    return (
        <>
            {stagingSyncBadge}
            <Head title="KMJ TECHNO — Main Platform">
                <meta
                    name="description"
                    content="KMJ TECHNO Main Platform — a secure operating platform for software products, licensing, releases, customer operations and governed automation."
                />
            </Head>

            <div className="min-h-screen overflow-hidden bg-[#07090c] text-white selection:bg-[#e21b23] selection:text-white">
                <div className="pointer-events-none fixed inset-0 opacity-70">
                    <div className="absolute -top-48 left-1/2 h-[36rem] w-[52rem] -translate-x-1/2 rounded-full bg-[#e21b23]/10 blur-[120px]" />
                    <div className="absolute top-[42rem] -right-52 h-[32rem] w-[32rem] rounded-full bg-[#b90f17]/10 blur-[120px]" />
                </div>

                <header className="relative z-20 border-b border-white/[0.07] bg-[#07090c]/80 backdrop-blur-xl">
                    <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 sm:px-8 lg:px-10">
                        <Link
                            href="/"
                            className="group flex items-center gap-3"
                        >
                            <span className="relative grid h-10 w-10 place-items-center overflow-hidden rounded-xl border border-[#e21b23]/45 bg-[#e21b23]/10 shadow-[0_0_30px_rgba(226,27,35,0.08)]">
                                <span className="text-[17px] font-black tracking-[-0.12em] text-[#f1252e]">
                                    K
                                </span>
                                <span className="absolute right-1.5 bottom-1.5 h-1.5 w-1.5 rounded-full bg-[#e21b23] shadow-[0_0_12px_#e21b23]" />
                            </span>
                            <span>
                                <span className="block text-[15px] font-extrabold tracking-[0.16em]">
                                    KMJ TECHNO
                                </span>
                                <span className="mt-0.5 block text-[9px] font-medium tracking-[0.25em] text-white/35 uppercase">
                                    Main Platform
                                </span>
                            </span>
                        </Link>

                        <nav className="flex items-center gap-2 sm:gap-3">
                            {auth.user ? (
                                <Link
                                    href={dashboard()}
                                    className="inline-flex h-10 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-4 text-sm font-semibold text-white transition hover:border-white/20 hover:bg-white/[0.08]"
                                >
                                    Dashboard
                                    <ArrowRight className="h-4 w-4" />
                                </Link>
                            ) : (
                                <>
                                    <Link
                                        href={login()}
                                        className="hidden h-10 items-center px-3 text-sm font-medium text-white/65 transition hover:text-white sm:inline-flex"
                                    >
                                        Sign in
                                    </Link>
                                    <Link
                                        href={register()}
                                        className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#e21b23] px-4 text-sm font-bold text-white shadow-[0_8px_28px_rgba(226,27,35,0.2)] transition hover:bg-[#f1252e]"
                                    >
                                        Create account
                                        <ArrowRight className="h-4 w-4" />
                                    </Link>
                                </>
                            )}
                        </nav>
                    </div>
                </header>

                <main className="relative z-10">
                    <section className="mx-auto grid max-w-7xl items-center gap-14 px-5 pt-20 pb-20 sm:px-8 sm:pt-28 lg:grid-cols-[1.08fr_.92fr] lg:px-10 lg:pt-32 lg:pb-28">
                        <div>
                            <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-[#e21b23]/25 bg-[#e21b23]/[0.07] px-3 py-1.5 text-xs font-semibold tracking-wide text-[#ff747a]">
                                <span className="h-1.5 w-1.5 rounded-full bg-[#e21b23] shadow-[0_0_10px_#e21b23]" />
                                Staging live · foundation + licensing validation
                                in motion
                            </div>

                            <h1 className="max-w-4xl text-5xl leading-[0.98] font-black tracking-[-0.055em] sm:text-6xl lg:text-[5.4rem]">
                                The operating layer for
                                <span className="block bg-gradient-to-r from-[#ff3039] via-[#e21b23] to-[#8b1117] bg-clip-text text-transparent">
                                    KMJ software.
                                </span>
                            </h1>

                            <p className="mt-7 max-w-2xl text-base leading-7 text-white/55 sm:text-lg sm:leading-8">
                                A secure central platform for software products,
                                customer access, entitlements, licensing,
                                releases and governed automation — built as an
                                enterprise foundation instead of a collection of
                                disconnected tools. The current staging track
                                now includes the authority foundation, sandbox
                                licensing validation and deployment verification
                                in parallel.
                            </p>

                            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                                {auth.user ? (
                                    <Link
                                        href={dashboard()}
                                        className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-[#e21b23] px-6 text-sm font-bold shadow-[0_12px_40px_rgba(226,27,35,0.22)] transition hover:-translate-y-0.5 hover:bg-[#f1252e]"
                                    >
                                        Open control center
                                        <ArrowRight className="h-4 w-4" />
                                    </Link>
                                ) : (
                                    <Link
                                        href={register()}
                                        className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-[#e21b23] px-6 text-sm font-bold shadow-[0_12px_40px_rgba(226,27,35,0.22)] transition hover:-translate-y-0.5 hover:bg-[#f1252e]"
                                    >
                                        Get started
                                        <ArrowRight className="h-4 w-4" />
                                    </Link>
                                )}
                                <a
                                    href="#platform"
                                    className="inline-flex h-12 items-center justify-center rounded-xl border border-white/10 bg-white/[0.035] px-6 text-sm font-semibold text-white/80 transition hover:border-white/20 hover:bg-white/[0.07] hover:text-white"
                                >
                                    Explore the platform
                                </a>
                            </div>

                            <div className="mt-10 grid max-w-2xl grid-cols-2 gap-x-6 gap-y-4 border-t border-white/[0.08] pt-6 sm:grid-cols-4">
                                {[
                                    ['Laravel 13', 'Control plane'],
                                    ['PostgreSQL 18', 'Authority data'],
                                    ['React 19', 'Product UX'],
                                    ['Rust', 'License core'],
                                ].map(([value, label]) => (
                                    <div key={value}>
                                        <div className="text-sm font-bold text-white/90">
                                            {value}
                                        </div>
                                        <div className="mt-1 text-[11px] text-white/35">
                                            {label}
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className="mt-6 grid max-w-2xl gap-3 sm:grid-cols-3">
                                {[
                                    [
                                        'Authority core',
                                        'Active',
                                        'Identity → entitlement → license chain',
                                    ],
                                    [
                                        'License validation',
                                        'Running',
                                        'Sandbox verification + audit evidence',
                                    ],
                                    [
                                        'Staging delivery',
                                        'Auto',
                                        'CI → promotion → deploy → health',
                                    ],
                                ].map(([title, status, detail]) => (
                                    <div
                                        key={title}
                                        className="rounded-xl border border-[#e21b23]/15 bg-[#e21b23]/[0.045] p-4"
                                    >
                                        <div className="flex items-center justify-between gap-3">
                                            <span className="text-xs font-bold text-white/85">
                                                {title}
                                            </span>
                                            <span className="rounded-full border border-emerald-400/15 bg-emerald-400/[0.06] px-2 py-1 text-[9px] font-bold tracking-wide text-emerald-300 uppercase">
                                                {status}
                                            </span>
                                        </div>
                                        <p className="mt-2 text-[11px] leading-5 text-white/40">
                                            {detail}
                                        </p>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="relative mx-auto w-full max-w-xl lg:max-w-none">
                            <div className="absolute -inset-10 rounded-full bg-[#e21b23]/10 blur-[90px]" />
                            <div className="relative overflow-hidden rounded-[1.75rem] border border-white/10 bg-[#0d1117]/90 shadow-2xl shadow-black/50">
                                <div className="flex items-center justify-between border-b border-white/[0.08] px-5 py-4">
                                    <div className="flex items-center gap-2.5">
                                        <div className="grid h-8 w-8 place-items-center rounded-lg bg-[#e21b23]/10 text-[#f33a42]">
                                            <Workflow className="h-4 w-4" />
                                        </div>
                                        <div>
                                            <div className="text-xs font-bold">
                                                Commercial authority
                                            </div>
                                            <div className="text-[10px] text-white/35">
                                                Canonical rights chain
                                            </div>
                                        </div>
                                    </div>
                                    <span className="rounded-full border border-emerald-400/15 bg-emerald-400/[0.06] px-2.5 py-1 text-[10px] font-semibold text-emerald-300">
                                        Foundation
                                    </span>
                                </div>

                                <div className="p-5 sm:p-7">
                                    <div className="space-y-2.5">
                                        {authority.map((item, index) => (
                                            <div
                                                key={item}
                                                className="relative flex items-center gap-3"
                                            >
                                                {index <
                                                    authority.length - 1 && (
                                                    <span className="absolute top-9 left-[15px] h-4 w-px bg-gradient-to-b from-[#e21b23]/50 to-white/10" />
                                                )}
                                                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-white/[0.08] bg-white/[0.035] text-[10px] font-black text-[#f34a51]">
                                                    {String(index + 1).padStart(
                                                        2,
                                                        '0',
                                                    )}
                                                </span>
                                                <div className="flex h-10 flex-1 items-center justify-between rounded-lg border border-white/[0.07] bg-white/[0.025] px-4">
                                                    <span className="text-xs font-semibold text-white/80">
                                                        {item}
                                                    </span>
                                                    {index === 3 && (
                                                        <span className="text-[9px] font-bold tracking-wide text-[#ff5b62] uppercase">
                                                            capability
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>

                                    <div className="mt-7 grid grid-cols-3 gap-2.5">
                                        {[
                                            [LockKeyhole, 'Policy'],
                                            [Fingerprint, 'Proof'],
                                            [RadioTower, 'Audit'],
                                        ].map(([Icon, label]) => {
                                            const Component =
                                                Icon as typeof LockKeyhole;
                                            return (
                                                <div
                                                    key={label as string}
                                                    className="rounded-xl border border-white/[0.07] bg-[#080b0f] px-3 py-4 text-center"
                                                >
                                                    <Component className="mx-auto h-4 w-4 text-[#e21b23]" />
                                                    <div className="mt-2 text-[10px] font-semibold text-white/50">
                                                        {label as string}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>

                    <section
                        id="platform"
                        className="border-y border-white/[0.07] bg-white/[0.018]"
                    >
                        <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:px-10 lg:py-24">
                            <div className="max-w-3xl">
                                <div className="text-xs font-bold tracking-[0.2em] text-[#e21b23] uppercase">
                                    Platform foundation
                                </div>
                                <h2 className="mt-4 text-3xl font-black tracking-[-0.035em] sm:text-4xl">
                                    One source of truth. Clear boundaries.
                                </h2>
                                <p className="mt-4 text-sm leading-7 text-white/45 sm:text-base">
                                    The Main Platform is being built as a
                                    modular business control plane. Products
                                    remain independent and consume versioned
                                    identity, entitlement, licensing, release
                                    and support contracts.
                                </p>
                            </div>

                            <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                                {capabilities.map(
                                    ({ icon: Icon, title, text, status }) => (
                                        <article
                                            key={title}
                                            className="group rounded-2xl border border-white/[0.08] bg-[#0b0e12] p-5 transition hover:-translate-y-1 hover:border-[#e21b23]/25 hover:bg-[#0d1015]"
                                        >
                                            <div className="flex items-start justify-between gap-4">
                                                <span className="grid h-10 w-10 place-items-center rounded-xl border border-[#e21b23]/15 bg-[#e21b23]/[0.07] text-[#ee343c]">
                                                    <Icon className="h-4.5 w-4.5" />
                                                </span>
                                                <span className="rounded-full border border-white/[0.07] px-2 py-1 text-[9px] font-semibold text-white/35">
                                                    {status}
                                                </span>
                                            </div>
                                            <h3 className="mt-5 text-base font-bold">
                                                {title}
                                            </h3>
                                            <p className="mt-2 text-[13px] leading-6 text-white/42">
                                                {text}
                                            </p>
                                        </article>
                                    ),
                                )}
                            </div>
                        </div>
                    </section>

                    <section className="mx-auto grid max-w-7xl gap-12 px-5 py-20 sm:px-8 lg:grid-cols-2 lg:px-10 lg:py-28">
                        <div className="rounded-[1.5rem] border border-white/[0.08] bg-gradient-to-br from-white/[0.045] to-transparent p-7 sm:p-9">
                            <div className="flex items-center gap-3">
                                <span className="grid h-10 w-10 place-items-center rounded-xl bg-[#e21b23]/10 text-[#ef3a42]">
                                    <Cpu className="h-5 w-5" />
                                </span>
                                <div>
                                    <div className="text-sm font-bold">
                                        Engineering policy
                                    </div>
                                    <div className="text-[11px] text-white/35">
                                        Built for controlled autonomy
                                    </div>
                                </div>
                            </div>
                            <div className="mt-7 space-y-4">
                                {principles.map((principle) => (
                                    <div
                                        key={principle}
                                        className="flex gap-3 text-sm leading-6 text-white/55"
                                    >
                                        <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-[#e21b23]" />
                                        <span>{principle}</span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="flex flex-col justify-center lg:pl-10">
                            <div className="text-xs font-bold tracking-[0.2em] text-[#e21b23] uppercase">
                                Built to evolve
                            </div>
                            <h2 className="mt-4 max-w-xl text-3xl font-black tracking-[-0.035em] sm:text-4xl">
                                Infrastructure is working. Product capabilities
                                come next.
                            </h2>
                            <p className="mt-5 max-w-xl text-sm leading-7 text-white/45 sm:text-base">
                                The current staging environment is the active
                                engineering preview. Core authority, licensing,
                                trusted releases and product integrations will
                                be exposed here only after they pass their
                                implementation and verification gates.
                            </p>
                            <div className="mt-7 flex flex-wrap gap-3 text-[11px] font-semibold text-white/45">
                                <span className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] px-3 py-1.5">
                                    <Boxes className="h-3.5 w-3.5 text-[#e21b23]" />{' '}
                                    Modular domains
                                </span>
                                <span className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] px-3 py-1.5">
                                    <Globe2 className="h-3.5 w-3.5 text-[#e21b23]" />{' '}
                                    Versioned interfaces
                                </span>
                                <span className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] px-3 py-1.5">
                                    <ShieldCheck className="h-3.5 w-3.5 text-[#e21b23]" />{' '}
                                    Verification gates
                                </span>
                            </div>
                        </div>
                    </section>

                    <section className="border-t border-white/[0.07]">
                        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-6 px-5 py-12 sm:px-8 md:flex-row md:items-center lg:px-10">
                            <div>
                                <div className="text-lg font-black tracking-[0.08em]">
                                    KMJ TECHNO
                                </div>
                                <div className="mt-1 text-xs text-white/30">
                                    Innovation · Technology · Global Solutions
                                </div>
                            </div>
                            <div className="flex items-center gap-5 text-xs text-white/35">
                                <span>Main Platform</span>
                                <span className="h-1 w-1 rounded-full bg-white/20" />
                                <span>Staging Preview</span>
                            </div>
                        </div>
                    </section>
                </main>
            </div>
        </>
    );
}
