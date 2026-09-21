import { Head, Link } from '@inertiajs/react';
import { ArrowLeft, CheckCircle2, Code2, ShieldCheck } from 'lucide-react';
import CalibrationDemo from '@/components/products/calibration-demo';
import CloudOSDemo from '@/components/products/cloudos-demo';
import ProductEvidenceTable from '@/components/products/product-evidence-table';

type Product = {
    slug: string;
    name: string;
    lifecycle: string;
    lifecycle_label: string;
    purchase_enabled: boolean;
    eyebrow: string;
    headline: string;
    summary: string;
    truth: {
        status: string;
        physical_capability_certified?: boolean;
    };
    proof: Array<{
        title: string;
        detail: string;
        state: string;
    }>;
    evidence: Array<{
        criterion: string;
        value: string;
        state: string;
        evidence_ref: string;
    }>;
    trust: {
        purchase_boundary: string;
        demo_boundary: string;
        license_authority: string;
        production_signing: string;
    };
    demo: {
        kind: 'cloudos' | 'calibration';
        simulation: boolean;
        label: string;
        steps: Array<{
            key: string;
            label: string;
            detail: string;
        }>;
    };
};

export default function ProductShow({ product }: { product: Product }) {
    const Demo =
        product.demo.kind === 'cloudos' ? CloudOSDemo : CalibrationDemo;

    return (
        <>
            <Head title={product.name + ' — KMJ TECHNO'}>
                <meta name="description" content={product.summary} />
            </Head>

            <main className="min-h-screen bg-[#07090c] text-white">
                <header className="border-b border-white/[0.07] bg-[#07090c]/95">
                    <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 sm:px-8 lg:px-10">
                        <Link
                            href="/"
                            className="text-sm font-black tracking-[0.16em]"
                        >
                            KMJ TECHNO
                        </Link>
                        <Link
                            href="/products"
                            className="inline-flex items-center gap-2 text-sm font-semibold text-white/55 transition hover:text-white"
                        >
                            <ArrowLeft className="h-4 w-4" />
                            All products
                        </Link>
                    </div>
                </header>

                <section className="mx-auto grid max-w-7xl gap-12 px-5 pt-16 pb-12 sm:px-8 lg:grid-cols-[1.05fr_.95fr] lg:px-10 lg:pt-24">
                    <div>
                        <div className="flex flex-wrap gap-3">
                            <span className="rounded-full border border-[#ef3941]/30 bg-[#ef3941]/10 px-3 py-1 text-[11px] font-bold tracking-[0.14em] text-[#ff777c] uppercase">
                                {product.eyebrow}
                            </span>
                            <span
                                className={
                                    product.purchase_enabled
                                        ? 'rounded-full border border-emerald-300/20 bg-emerald-300/[0.06] px-3 py-1 text-[11px] font-semibold text-emerald-200/80'
                                        : 'rounded-full border border-amber-300/20 bg-amber-300/[0.05] px-3 py-1 text-[11px] font-semibold text-amber-200/80'
                                }
                            >
                                {product.lifecycle_label}
                            </span>
                        </div>

                        <h1 className="mt-7 text-4xl font-black tracking-[-0.05em] sm:text-6xl">
                            {product.name}
                        </h1>
                        <p className="mt-6 max-w-2xl text-xl leading-9 text-white/65">
                            {product.headline}
                        </p>
                        <p className="mt-5 max-w-2xl text-sm leading-7 text-white/43">
                            {product.summary}
                        </p>

                        <div className="mt-8 rounded-2xl border border-white/[0.09] bg-white/[0.025] p-5">
                            <div className="text-xs font-bold tracking-[0.14em] text-white/45 uppercase">
                                Current verified status
                            </div>
                            <p className="mt-2 text-sm leading-6 text-white/60">
                                {product.truth.status}
                            </p>
                        </div>
                    </div>

                    <div className="grid gap-3">
                        {product.proof.map((item, index) => {
                            const Icon =
                                index === 0
                                    ? Code2
                                    : index === 1
                                      ? ShieldCheck
                                      : CheckCircle2;

                            return (
                                <div
                                    key={item.title}
                                    className="rounded-2xl border border-white/[0.08] bg-white/[0.025] p-5"
                                >
                                    <div className="flex items-start gap-4">
                                        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#e21b23]/10">
                                            <Icon className="h-5 w-5 text-[#ef3941]" />
                                        </div>
                                        <div>
                                            <div className="font-bold">
                                                {item.title}
                                            </div>
                                            <div className="mt-2 text-sm leading-6 text-white/42">
                                                {item.detail}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </section>

                <section className="border-y border-white/[0.07] bg-white/[0.015]">
                    <div className="mx-auto max-w-7xl px-5 py-16 sm:px-8 lg:px-10 lg:py-20">
                        <div className="mb-8 max-w-3xl">
                            <div className="text-xs font-bold tracking-[0.2em] text-[#ef3941] uppercase">
                                Virtual demo
                            </div>
                            <h2 className="mt-4 text-3xl font-black tracking-[-0.035em] sm:text-4xl">
                                Learn the workflow by using it.
                            </h2>
                            <p className="mt-4 text-sm leading-7 text-white/45">
                                This deterministic browser simulation never
                                controls production infrastructure or claims
                                physical measurements.
                            </p>
                        </div>

                        <Demo steps={product.demo.steps} />
                    </div>
                </section>

                <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 lg:px-10">
                    <div className="mb-8 max-w-3xl">
                        <div className="text-xs font-bold tracking-[0.2em] text-[#ef3941] uppercase">
                            Evidence + trust
                        </div>
                        <h2 className="mt-4 text-3xl font-black tracking-[-0.035em] sm:text-4xl">
                            Verify the boundaries, not marketing claims.
                        </h2>
                        <p className="mt-4 text-sm leading-7 text-white/45">
                            Lifecycle, purchase, licensing and demo boundaries
                            are rendered from explicit product facts and
                            authority state.
                        </p>
                    </div>

                    <ProductEvidenceTable
                        evidence={product.evidence}
                        trust={product.trust}
                    />
                </section>

                <section className="mx-auto max-w-7xl px-5 pb-14 sm:px-8 lg:px-10">
                    {product.purchase_enabled ? (
                        <div className="flex flex-col items-start justify-between gap-6 rounded-2xl border border-emerald-300/15 bg-emerald-300/[0.035] p-6 sm:flex-row sm:items-center">
                            <div>
                                <div className="font-bold">
                                    Commercial access is governed by KMJ Main
                                    Platform.
                                </div>
                                <div className="mt-1 text-sm text-white/42">
                                    A purchase request does not grant access by
                                    itself; entitlement fulfillment remains
                                    authoritative.
                                </div>
                            </div>
                            <Link
                                href="/purchase"
                                className="rounded-xl bg-[#e21b23] px-5 py-3 text-sm font-bold transition hover:bg-[#f1252e]"
                            >
                                Request access
                            </Link>
                        </div>
                    ) : (
                        <div className="flex flex-col items-start justify-between gap-6 rounded-2xl border border-white/[0.08] bg-white/[0.025] p-6 sm:flex-row sm:items-center">
                            <div>
                                <div className="font-bold">
                                    Commercial licensing is not enabled yet.
                                </div>
                                <div className="mt-1 text-sm text-white/38">
                                    Purchase remains unavailable until product
                                    capability is verified and explicitly
                                    promoted.
                                </div>
                            </div>
                            <span className="rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-white/45">
                                Preview only
                            </span>
                        </div>
                    )}
                </section>
            </main>
        </>
    );
}
