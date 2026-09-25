import { Link } from '@inertiajs/react';
import {
    ArrowRight,
    CheckCircle2,
    FlaskConical,
    ServerCog,
    ShieldCheck,
} from 'lucide-react';
import PublicLanguageSwitch from '@/components/public-language-switch';
import PublicSeo from '@/components/public-seo';

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
    return (
        <>
            <PublicSeo
                title="Products — KMJ TECHNO"
                description="Explore the KMJ TECHNO product portfolio with evidence-backed lifecycle, availability and product status."
                path="/products"
                structuredData={{
                    '@context': 'https://schema.org',
                    '@type': 'CollectionPage',
                    name: 'KMJ TECHNO Products',
                }}
            />

            <main className="min-h-screen bg-[#07090c] text-white">
                <header className="border-b border-white/[0.07] bg-[#07090c]/95">
                    <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 sm:px-8 lg:px-10">
                        <Link
                            href="/"
                            className="text-sm font-black tracking-[0.16em]"
                        >
                            KMJ TECHNO
                        </Link>
                        <div className="flex items-center gap-4 text-sm text-white/55">
                            <span className="hidden sm:inline">Products</span>
                            <Link
                                href="/trust"
                                className="hidden font-semibold transition hover:text-white sm:inline"
                            >
                                Trust
                            </Link>
                            <PublicLanguageSwitch className="font-semibold transition hover:text-white" />
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
                            Product lifecycle, purchase availability and demo
                            state are shown separately so presentation never
                            outruns verified authority.
                        </p>
                    </div>
                </section>

                <section className="mx-auto grid max-w-7xl gap-5 px-5 pb-24 sm:px-8 lg:grid-cols-2 lg:px-10">
                    {products.map((product) => {
                        const ProductIcon =
                            product.demo.kind === 'cloudos'
                                ? ServerCog
                                : product.demo.kind === 'calibration'
                                  ? FlaskConical
                                  : ShieldCheck;

                        return (
                            <article
                                key={product.slug}
                                className="flex flex-col overflow-hidden rounded-[2rem] border border-white/[0.09] bg-gradient-to-br from-white/[0.055] to-white/[0.015]"
                            >
                                <div className="p-7 sm:p-9">
                                    <div className="flex flex-wrap items-center justify-between gap-3">
                                        <div className="grid h-11 w-11 place-items-center rounded-xl border border-[#ef3941]/20 bg-[#ef3941]/10">
                                            <ProductIcon className="h-5 w-5 text-[#ef3941]" />
                                        </div>
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

                                    <div className="mt-7 text-sm font-bold text-white/45">
                                        {product.eyebrow}
                                    </div>
                                    <h2 className="mt-2 text-3xl font-black tracking-[-0.035em]">
                                        {product.name}
                                    </h2>
                                    <p className="mt-4 text-base leading-7 text-white/62">
                                        {product.headline}
                                    </p>
                                    <p className="mt-3 text-sm leading-7 text-white/42">
                                        {product.summary}
                                    </p>

                                    <div className="mt-7 space-y-3">
                                        {product.proof
                                            .slice(0, 2)
                                            .map((item) => (
                                                <div
                                                    key={item.title}
                                                    className="flex gap-3 rounded-xl border border-white/[0.07] bg-black/20 p-4"
                                                >
                                                    <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[#ef3941]" />
                                                    <div>
                                                        <div className="text-sm font-bold">
                                                            {item.title}
                                                        </div>
                                                        <div className="mt-1 text-xs leading-5 text-white/40">
                                                            {item.detail}
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                    </div>
                                </div>

                                <div className="mt-auto border-t border-white/[0.07] bg-black/20 p-6">
                                    <div className="mb-4 flex items-center gap-2 text-xs text-white/42">
                                        {product.demo.simulation ? (
                                            <>
                                                <CheckCircle2 className="h-4 w-4 text-emerald-300/70" />
                                                Interactive simulation only
                                            </>
                                        ) : (
                                            <>
                                                <ShieldCheck className="h-4 w-4 text-amber-200/70" />
                                                {product.demo.label}
                                            </>
                                        )}
                                    </div>
                                    <div className="flex flex-col gap-3 sm:flex-row">
                                        <Link
                                            href={'/products/' + product.slug}
                                            className="inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-xl bg-[#e21b23] px-5 text-sm font-bold transition hover:bg-[#f1252e]"
                                        >
                                            {product.demo.simulation
                                                ? 'Open virtual demo'
                                                : 'View product status'}
                                            <ArrowRight className="h-4 w-4" />
                                        </Link>
                                        {product.purchase_enabled && (
                                            <Link
                                                href="/purchase"
                                                className="inline-flex h-11 items-center justify-center rounded-xl border border-white/10 px-5 text-sm font-semibold text-white/65 transition hover:border-white/20 hover:text-white"
                                            >
                                                Request access
                                            </Link>
                                        )}
                                    </div>
                                </div>
                            </article>
                        );
                    })}
                </section>
            </main>
        </>
    );
}
