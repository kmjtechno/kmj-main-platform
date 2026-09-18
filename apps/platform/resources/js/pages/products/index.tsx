import { Head, Link } from '@inertiajs/react';
import {
    ArrowRight,
    CheckCircle2,
    Cpu,
    FlaskConical,
    ShieldCheck,
    Sparkles,
} from 'lucide-react';

type Product = {
    slug: string;
    name: string;
    lifecycle: string;
    lifecycle_label: string;
    purchase_enabled: boolean;
    eyebrow: string;
    headline: string;
    summary: string;
    proof: Array<{
        title: string;
        detail: string;
        state: string;
    }>;
    demo: {
        kind: string;
        simulation: boolean;
        label: string;
    };
};

export default function ProductsIndex({ products }: { products: Product[] }) {
    const calibration = products[0];

    return (
        <>
            <Head title="Products — KMJ TECHNO">
                <meta
                    name="description"
                    content="Explore KMJ TECHNO products through concise, evidence-backed product pages and interactive virtual demos."
                />
            </Head>

            <main className="min-h-screen bg-[#07090c] text-white">
                <header className="border-b border-white/[0.07] bg-[#07090c]/95">
                    <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 sm:px-8 lg:px-10">
                        <Link href="/" className="text-sm font-black tracking-[0.16em]">
                            KMJ TECHNO
                        </Link>
                        <div className="flex items-center gap-4 text-sm text-white/55">
                            <span className="hidden sm:inline">Products</span>
                            <Link
                                href="/"
                                className="rounded-lg border border-white/10 px-4 py-2 font-semibold text-white/80 transition hover:border-white/20 hover:text-white"
                            >
                                Main Platform
                            </Link>
                        </div>
                    </div>
                </header>

                <section className="mx-auto max-w-7xl px-5 pt-16 pb-10 sm:px-8 lg:px-10 lg:pt-24">
                    <div className="max-w-4xl">
                        <div className="text-xs font-bold tracking-[0.22em] text-[#ef3941] uppercase">
                            KMJ product portfolio
                        </div>
                        <h1 className="mt-5 text-4xl font-black tracking-[-0.045em] sm:text-6xl">
                            Understand the product in seconds.
                            <span className="block text-white/38">
                                Explore the workflow before you decide.
                            </span>
                        </h1>
                        <p className="mt-6 max-w-2xl text-base leading-7 text-white/50 sm:text-lg">
                            Every KMJ product page is outcome-first, demo-led and explicit about
                            what is verified today versus what is still in development.
                        </p>
                    </div>
                </section>

                {calibration && (
                    <section className="mx-auto max-w-7xl px-5 pb-24 sm:px-8 lg:px-10">
                        <div className="overflow-hidden rounded-[2rem] border border-white/[0.09] bg-gradient-to-br from-white/[0.055] to-white/[0.015] shadow-2xl">
                            <div className="grid lg:grid-cols-[1.05fr_.95fr]">
                                <div className="p-7 sm:p-10 lg:p-12">
                                    <div className="flex flex-wrap items-center gap-3">
                                        <span className="rounded-full border border-[#ef3941]/30 bg-[#ef3941]/10 px-3 py-1 text-[11px] font-bold tracking-[0.14em] text-[#ff777c] uppercase">
                                            Flagship preview
                                        </span>
                                        <span className="rounded-full border border-amber-300/20 bg-amber-300/5 px-3 py-1 text-[11px] font-semibold text-amber-200/80">
                                            {calibration.lifecycle_label}
                                        </span>
                                    </div>

                                    <div className="mt-8 text-sm font-bold text-white/45">
                                        {calibration.eyebrow}
                                    </div>
                                    <h2 className="mt-3 max-w-2xl text-3xl font-black tracking-[-0.035em] sm:text-5xl">
                                        {calibration.name}
                                    </h2>
                                    <p className="mt-5 max-w-2xl text-lg leading-8 text-white/62">
                                        {calibration.headline}
                                    </p>
                                    <p className="mt-4 max-w-2xl text-sm leading-7 text-white/42">
                                        {calibration.summary}
                                    </p>

                                    <div className="mt-8 grid gap-3 sm:grid-cols-3">
                                        {calibration.proof.map((item, index) => {
                                            const Icon =
                                                index === 0
                                                    ? Cpu
                                                    : index === 1
                                                      ? ShieldCheck
                                                      : FlaskConical;

                                            return (
                                                <div
                                                    key={item.title}
                                                    className="rounded-2xl border border-white/[0.075] bg-black/20 p-4"
                                                >
                                                    <Icon className="h-5 w-5 text-[#ef3941]" />
                                                    <div className="mt-4 text-sm font-bold">
                                                        {item.title}
                                                    </div>
                                                    <div className="mt-2 text-xs leading-5 text-white/40">
                                                        {item.detail}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>

                                    <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                                        <Link
                                            href="/products/kmj-calibration-pro"
                                            className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-[#e21b23] px-6 text-sm font-bold shadow-[0_12px_40px_rgba(226,27,35,0.2)] transition hover:bg-[#f1252e]"
                                        >
                                            Explore virtual demo
                                            <ArrowRight className="h-4 w-4" />
                                        </Link>
                                        <span className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-white/10 px-5 text-sm text-white/48">
                                            <CheckCircle2 className="h-4 w-4 text-emerald-300/70" />
                                            Evidence-backed product status
                                        </span>
                                    </div>
                                </div>

                                <div className="relative min-h-[420px] border-t border-white/[0.07] bg-[#050608] p-6 lg:border-t-0 lg:border-l lg:p-8">
                                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(226,27,35,0.14),transparent_38%)]" />
                                    <div className="relative flex h-full flex-col rounded-[1.5rem] border border-white/[0.08] bg-[#090b0f] p-5">
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <div className="text-xs font-bold tracking-[0.14em] text-white/35 uppercase">
                                                    Virtual workflow
                                                </div>
                                                <div className="mt-1 font-bold">
                                                    Setup → Capture → Analyze → Results
                                                </div>
                                            </div>
                                            <Sparkles className="h-5 w-5 text-[#ef3941]" />
                                        </div>

                                        <div className="mt-8 grid flex-1 grid-cols-4 gap-2">
                                            {['Setup', 'Capture', 'Analyze', 'Results'].map(
                                                (step, index) => (
                                                    <div
                                                        key={step}
                                                        className="flex flex-col justify-between rounded-xl border border-white/[0.07] bg-white/[0.025] p-3"
                                                    >
                                                        <span className="text-[10px] font-bold text-[#ff6a70]">
                                                            {'0' + (index + 1)}
                                                        </span>
                                                        <span className="text-xs font-semibold text-white/70">
                                                            {step}
                                                        </span>
                                                    </div>
                                                ),
                                            )}
                                        </div>

                                        <div className="mt-4 rounded-xl border border-amber-300/15 bg-amber-300/[0.035] px-4 py-3 text-xs leading-5 text-amber-100/65">
                                            Interactive simulation only. No physical calibration
                                            result is presented as certified.
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>
                )}
            </main>
        </>
    );
}
