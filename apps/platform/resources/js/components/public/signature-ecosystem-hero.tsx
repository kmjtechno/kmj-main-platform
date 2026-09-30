import { Link } from '@inertiajs/react';
import {
    ArrowRight,
    Bot,
    Cloud,
    Projector,
    RadioTower,
} from 'lucide-react';
import { useState } from 'react';

type ProductState = { slug: string; lifecycle_label: string };

const domains = [
    {
        id: 'cloud',
        title: 'Cloud',
        product: 'KMJ CloudOS',
        slug: 'kmj-cloudos',
        href: '/products/kmj-cloudos',
        summary: 'Cloud infrastructure and governed service control.',
        accent: '#25b4ff',
        Icon: Cloud,
    },
    {
        id: 'calibration',
        title: 'Calibration',
        product: 'KMJ Calibration Pro',
        slug: 'kmj-calibration-pro',
        href: '/products/kmj-calibration-pro',
        summary: 'Precision calibration, mapping and validation workflows.',
        accent: '#ff9a3d',
        Icon: Projector,
    },
    {
        id: 'immersive',
        title: 'Immersive',
        product: 'KMJ Cinema Platform',
        slug: 'kmj-cinema-platform',
        href: '/products/kmj-cinema-platform',
        summary: 'Immersive cinema, dome and playback technology.',
        accent: '#a87cff',
        Icon: RadioTower,
    },
    {
        id: 'engineering',
        title: 'AI + Remote',
        product: 'KMJ engineering systems',
        slug: 'kmj-desktop-commander',
        href: '/products/kmj-desktop-commander',
        summary:
            'Secure remote control and intelligent engineering workflows.',
        accent: '#27d3a2',
        Icon: Bot,
    },
] as const;

export default function SignatureEcosystemHero({
    products,
}: {
    products: ProductState[];
}) {
    const [selected, setSelected] = useState<string | null>(null);

    return (
        <div
            className="relative isolate min-h-[430px] overflow-hidden rounded-[2rem] border border-white/[0.09] bg-[#080b11] p-3 shadow-[0_35px_100px_rgba(0,0,0,.35)] sm:min-h-[500px] sm:p-5"
            aria-label="KMJ connected product ecosystem"
        >
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_42%,rgba(37,180,255,.10),transparent_26%),radial-gradient(circle_at_76%_72%,rgba(168,124,255,.09),transparent_28%),radial-gradient(circle_at_20%_78%,rgba(39,211,162,.07),transparent_28%)]" />
            <div className="pointer-events-none absolute inset-0 opacity-[.12] [background-image:linear-gradient(rgba(255,255,255,.12)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.12)_1px,transparent_1px)] [background-size:32px_32px] [mask-image:radial-gradient(circle_at_center,black,transparent_78%)]" />

            <div className="relative flex h-full min-h-[404px] flex-col sm:min-h-[458px]">
                <div className="flex items-center justify-between px-2 pt-2">
                    <div className="text-[9px] font-black tracking-[.18em] text-white/42 uppercase">
                        Connected KMJ ecosystem
                    </div>
                    <div className="rounded-full border border-white/[.08] bg-white/[.035] px-2.5 py-1 text-[8px] font-black tracking-[.13em] text-white/40 uppercase">
                        Governed platform
                    </div>
                </div>

                <div className="relative my-5 hidden flex-1 sm:block">
                    <div className="pointer-events-none absolute top-1/2 left-1/2 h-40 w-40 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/[.08] motion-safe:animate-[pulse_5s_ease-in-out_infinite]">
                        <div className="absolute inset-5 rounded-full border border-[#e21b23]/20 bg-[#0b0e14]/90 shadow-[0_0_70px_rgba(226,27,35,.08)]" />
                    </div>
                    <div className="pointer-events-none absolute top-1/2 left-1/2 z-10 -translate-x-1/2 -translate-y-1/2 text-center">
                        <div className="text-[9px] font-black tracking-[.16em] text-[#ff5962] uppercase">KMJ</div>
                        <div className="mt-1 text-sm font-black">One governed layer</div>
                        <div className="mt-1 text-[9px] text-white/38">Access · Licensing · Delivery</div>
                    </div>

                    <div className="absolute inset-0 grid grid-cols-2 grid-rows-2 gap-x-32 gap-y-16">
                        {domains.map(
                            ({
                                id,
                                title,
                                product,
                                slug,
                                href,
                                summary,
                                accent,
                                Icon,
                            }) => {
                                const active = selected === id;
                                const lifecycle = products.find(
                                    (item) => item.slug === slug,
                                )?.lifecycle_label;
                                return (
                                    <article
                                    key={id}
                                    onMouseEnter={() => setSelected(id)}
                                    onMouseLeave={() => setSelected(null)}
                                    onFocus={() => setSelected(id)}
                                    className="group relative flex min-h-32 flex-col justify-between rounded-[1.35rem] border bg-black/25 p-4 transition duration-200 motion-reduce:transform-none"
                                    style={{
                                        borderColor: active
                                            ? accent + '66'
                                            : 'rgba(255,255,255,.08)',
                                    }}
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <span
                                            className="grid h-10 w-10 place-items-center rounded-xl border border-white/[.08] bg-white/[.035]"
                                            style={{ color: accent }}
                                        >
                                            <Icon className="h-4 w-4" />
                                        </span>
                                        {lifecycle && (
                                            <span className="text-[8px] font-black tracking-[.12em] text-white/38 uppercase">
                                                {lifecycle}
                                            </span>
                                        )}
                                    </div>
                                    <div>
                                        <div
                                            className="text-[9px] font-black tracking-[.14em] uppercase"
                                            style={{ color }}
                                        >
                                            {title}
                                        </div>
                                        <h2 className="mt-1 text-sm font-black">
                                            {product}
                                        </h2>
                                        <p
                                            className={
                                                'mt-1 text-[10px] leading-4 text-white/45 transition-opacity duration-200 motion-reduce:transition-none ' +
                                                (active
                                                    ? 'opacity-100'
                                                    : 'opacity-70')
                                            }
                                        >
                                            {summary}
                                        </p>
                                        <Link
                                            href={href}
                                            className="mt-2 inline-flex items-center gap-1 text-[10px] font-bold text-white/70 outline-none transition hover:text-white focus-visible:ring-2 focus-visible:ring-white/70"
                                        >
                                            Explore
                                            <ArrowRight className="h-3 w-3" />
                                        </Link>
                                    </div>
                                    </article>
                                );
                            },
                        )}
                    </div>
                </div>

                <div className="mt-5 grid flex-1 gap-2 sm:hidden">
                    {domains.map(
                        ({
                            id,
                            title,
                            product,
                            slug,
                            href,
                            summary,
                            accent,
                            Icon,
                        }) => {
                            const active = selected === id;
                            const lifecycle = products.find(
                                (item) => item.slug === slug,
                            )?.lifecycle_label;

                            return (
                                <article
                                    key={id}
                                    className="rounded-2xl border bg-black/25"
                                    style={{
                                        borderColor: active
                                            ? accent + '66'
                                            : 'rgba(255,255,255,.08)',
                                    }}
                                >
                                    <button
                                        type="button"
                                        aria-expanded={active}
                                        aria-controls={'kmj-domain-' + id}
                                        onClick={() =>
                                            setSelected(active ? null : id)
                                        }
                                        className="flex min-h-14 w-full items-center gap-3 rounded-2xl px-3 py-2 text-left outline-none focus-visible:ring-2 focus-visible:ring-white/70"
                                    >
                                        <span
                                            className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-white/[.08] bg-white/[.035]"
                                            style={{ color: accent }}
                                        >
                                            <Icon className="h-4 w-4" />
                                        </span>
                                        <span className="min-w-0 flex-1">
                                            <span
                                                className="block text-[9px] font-black tracking-[.13em] uppercase"
                                                style={{ color: accent }}
                                            >
                                                {title}
                                            </span>
                                            <span className="block text-sm font-black">
                                                {product}
                                            </span>
                                        </span>
                                        {lifecycle && (
                                            <span className="text-[8px] font-black tracking-[.1em] text-white/38 uppercase">
                                                {lifecycle}
                                            </span>
                                        )}
                                    </button>
                                    {active && (
                                        <div
                                            id={'kmj-domain-' + id}
                                            className="px-3 pb-3 motion-reduce:transition-none"
                                        >
                                            <p className="text-xs leading-5 text-white/52">
                                                {summary}
                                            </p>
                                            <Link
                                                href={href}
                                                className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-xl border border-white/[.09] bg-white/[.04] px-4 text-xs font-black text-white/80 outline-none focus-visible:ring-2 focus-visible:ring-white/70"
                                            >
                                                Explore {title}
                                                <ArrowRight className="h-3.5 w-3.5" />
                                            </Link>
                                        </div>
                                    )}
                                </article>
                            );
                        },
                    )}
                </div>
            </div>
        </div>
    );
}
