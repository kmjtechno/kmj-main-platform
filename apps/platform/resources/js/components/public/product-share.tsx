import { Check, Copy, MessageCircle, Share2 } from 'lucide-react';
import { usePage } from '@inertiajs/react';
import { useState } from 'react';

type ProductShareProps = {
    name: string;
    slug: string;
};

export default function ProductShare({ name, slug }: ProductShareProps) {
    const { localization } = usePage().props;
    const hi = localization.locale === 'hi';
    const [copied, setCopied] = useState(false);
    const url = `https://kmjtechno.com/products/${slug}`;
    const text = `${name} — KMJ TECHNO`;
    const encodedUrl = encodeURIComponent(url);
    const encodedText = encodeURIComponent(`${text} ${url}`);

    async function share() {
        if (navigator.share) {
            await navigator.share({ title: text, text, url });
            return;
        }

        await navigator.clipboard.writeText(url);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1800);
    }

    async function copy() {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1800);
    }
    return (
        <div className="mt-7">
            <div className="text-[9px] font-black tracking-[0.16em] text-white/28 uppercase">
                {hi ? 'इस product को share करें' : 'Share this product'}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
                <button
                    type="button"
                    onClick={share}
                    className="inline-flex h-10 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.035] px-3.5 text-xs font-bold text-white/68 transition hover:border-white/20 hover:bg-white/[0.07] hover:text-white"
                >
                    <Share2 className="h-3.5 w-3.5" />
                    {hi ? 'Share करें' : 'Share'}
                </button>
                <a
                    href={`https://wa.me/?text=${encodedText}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-10 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.035] px-3.5 text-xs font-bold text-white/68 transition hover:border-white/20 hover:bg-white/[0.07] hover:text-white"
                >
                    <MessageCircle className="h-3.5 w-3.5" />
                    WhatsApp
                </a>
                <a
                    href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-10 items-center rounded-lg border border-white/10 bg-white/[0.035] px-3.5 text-xs font-bold text-white/68 transition hover:border-white/20 hover:bg-white/[0.07] hover:text-white"
                >
                    LinkedIn
                </a>
                <a
                    href={`https://twitter.com/intent/tweet?text=${encodedText}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-10 items-center rounded-lg border border-white/10 bg-white/[0.035] px-3.5 text-xs font-bold text-white/68 transition hover:border-white/20 hover:bg-white/[0.07] hover:text-white"
                >
                    X
                </a>
                <a
                    href={`https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-10 items-center rounded-lg border border-white/10 bg-white/[0.035] px-3.5 text-xs font-bold text-white/68 transition hover:border-white/20 hover:bg-white/[0.07] hover:text-white"
                >
                    Facebook
                </a>
                <button
                    type="button"
                    onClick={copy}
                    className="inline-flex h-10 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.035] px-3.5 text-xs font-bold text-white/68 transition hover:border-white/20 hover:bg-white/[0.07] hover:text-white"
                >
                    {copied ? (
                        <Check className="h-3.5 w-3.5" />
                    ) : (
                        <Copy className="h-3.5 w-3.5" />
                    )}
                    {copied
                        ? hi
                            ? 'कॉपी हो गया'
                            : 'Copied'
                        : hi
                          ? 'लिंक कॉपी करें'
                          : 'Copy link'}
                </button>
            </div>
        </div>
    );
}
