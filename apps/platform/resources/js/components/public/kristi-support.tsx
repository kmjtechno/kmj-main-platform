import { Link } from '@inertiajs/react';
import { Bot, ChevronRight, MessageCircle, X } from 'lucide-react';
import { useState } from 'react';

const options = [
    {
        label: 'Recommend a product',
        message:
            'Start with the product portfolio, then open the product that best matches your use case. Lifecycle labels show whether a product is available, in preview, development or roadmap.',
        href: '/products',
        cta: 'Explore products',
    },
    {
        label: 'Licensing help',
        message:
            'KMJ Main Platform governs product access, entitlements and licensing. Product-specific purchase and licensing availability stays tied to the verified lifecycle state.',
        href: '/products/kmj-licensing-hub',
        cta: 'Open Licensing Hub',
    },
    {
        label: 'Immersive cinema',
        message:
            'KMJ Immersive Cinema Suite groups 5D, 7D, 9D, 12D, 14D, 16D and 5DX as one product family. KMJ 360 Dome remains a separate immersive product.',
        href: '/products/kmj-immersive-cinema-suite',
        cta: 'Explore Cinema Suite',
    },
    {
        label: 'Early access',
        message:
            'Development and roadmap products do not pretend to be generally available. Open the product page to review its current verified status and available access path.',
        href: '/products',
        cta: 'View product status',
    },
];

export default function KristiSupport() {
    const [open, setOpen] = useState(false);
    const [active, setActive] = useState(0);
    const option = options[active];

    return (
        <div className="fixed right-4 bottom-4 z-[60] sm:right-6 sm:bottom-6">
            {open && (
                <section
                    aria-label="Kristi support"
                    className="mb-3 w-[calc(100vw-2rem)] max-w-sm overflow-hidden rounded-[1.35rem] border border-white/10 bg-[#090c11]/95 shadow-2xl shadow-black/60 backdrop-blur-2xl"
                >
                    <div className="flex items-center justify-between border-b border-white/[0.08] px-4 py-3.5">
                        <div className="flex items-center gap-3">
                            <span className="grid h-9 w-9 place-items-center rounded-xl border border-[#e21b23]/20 bg-[#e21b23]/10 text-[#ff4c55]">
                                <Bot className="h-4 w-4" />
                            </span>
                            <div>
                                <div className="text-sm font-black">
                                    Kristi Support
                                </div>
                                <div className="mt-0.5 text-[10px] font-bold tracking-[0.12em] text-white/36 uppercase">
                                    Verified product guidance
                                </div>
                            </div>
                        </div>
                        <button
                            type="button"
                            onClick={() => setOpen(false)}
                            aria-label="Close Kristi support"
                            className="grid h-9 w-9 place-items-center rounded-lg border border-white/10 text-white/50 transition hover:bg-white/[0.06] hover:text-white"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </div>

                    <div className="p-4">
                        <p className="text-sm leading-6 text-white/62">
                            Hi, I’m Kristi. I can guide you using the current
                            verified KMJ product information.
                        </p>

                        <div className="mt-4 grid gap-2">
                            {options.map((item, index) => (
                                <button
                                    type="button"
                                    key={item.label}
                                    onClick={() => setActive(index)}
                                    className={
                                        'flex items-center justify-between rounded-xl border px-3.5 py-3 text-left text-sm font-bold transition ' +
                                        (active === index
                                            ? 'border-[#e21b23]/35 bg-[#e21b23]/10 text-white'
                                            : 'border-white/[0.08] bg-white/[0.025] text-white/58 hover:border-white/15 hover:text-white')
                                    }
                                >
                                    {item.label}
                                    <ChevronRight className="h-4 w-4" />
                                </button>
                            ))}
                        </div>

                        <div className="mt-4 rounded-xl border border-white/[0.08] bg-black/20 p-4">
                            <p className="text-sm leading-6 text-white/58">
                                {option.message}
                            </p>
                            <Link
                                href={option.href}
                                className="mt-4 inline-flex items-center gap-2 text-sm font-black text-[#ff5962] transition hover:text-[#ff858b]"
                            >
                                {option.cta}
                                <ChevronRight className="h-4 w-4" />
                            </Link>
                        </div>

                        <p className="mt-3 text-[10px] leading-5 text-white/28">
                            Kristi does not invent pricing, availability or
                            release claims. Live generative assistance can be
                            enabled only after its production backend is
                            verified.
                        </p>
                    </div>
                </section>
            )}

            <button
                type="button"
                onClick={() => setOpen((value) => !value)}
                aria-expanded={open}
                aria-label={
                    open ? 'Close Kristi support' : 'Open Kristi support'
                }
                className="ml-auto flex h-12 items-center gap-2 rounded-full border border-[#e21b23]/35 bg-[#e21b23] px-4 text-sm font-black text-white shadow-xl shadow-[#e21b23]/20 transition hover:-translate-y-0.5 hover:bg-[#f22b34]"
            >
                <MessageCircle className="h-4 w-4" />
                Kristi Support
            </button>
        </div>
    );
}
