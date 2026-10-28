import { Check, Copy, MessageCircle, Share2 } from 'lucide-react';
import { useRef, useState } from 'react';
import {
    deliverProductLink,
    type ProductShareOutcome,
} from '@/lib/product-share-actions.mjs';

type ProductShareProps = {
    name: string;
    slug: string;
};

export default function ProductShare({ name, slug }: ProductShareProps) {
    const [status, setStatus] = useState<ProductShareOutcome | 'idle'>('idle');
    const [busy, setBusy] = useState(false);
    const inFlight = useRef(false);
    const url = `https://kmjtechno.com/products/${slug}`;
    const text = `${name} — KMJ TECHNO`;
    const encodedUrl = encodeURIComponent(url);
    const encodedText = encodeURIComponent(`${text} ${url}`);

    async function act(mode: 'share' | 'copy') {
        if (inFlight.current) return;
        inFlight.current = true;
        setBusy(true);
        setStatus('idle');
        try {
            const result = await deliverProductLink({
                mode,
                title: text,
                url,
                nativeShare: navigator.share?.bind(navigator),
                copyText: navigator.clipboard?.writeText?.bind(
                    navigator.clipboard,
                ),
            });
            setStatus(result);
        } catch {
            setStatus('unavailable');
        } finally {
            inFlight.current = false;
            setBusy(false);
        }
    }

    return (
        <div className="mt-7">
            <div className="text-xs font-black tracking-[0.16em] text-white/70 uppercase">
                Share this product
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
                <button
                    type="button"
                    onClick={() => void act('share')}
                    disabled={busy}
                    className="inline-flex h-10 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.035] px-3.5 text-xs font-bold text-white/68 transition hover:border-white/20 hover:bg-white/[0.07] hover:text-white"
                >
                    <Share2 className="h-3.5 w-3.5" />
                    Share
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
                    onClick={() => void act('copy')}
                    disabled={busy}
                    className="inline-flex h-10 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.035] px-3.5 text-xs font-bold text-white/68 transition hover:border-white/20 hover:bg-white/[0.07] hover:text-white"
                >
                    {status === 'copied' ? (
                        <Check className="h-3.5 w-3.5" />
                    ) : (
                        <Copy className="h-3.5 w-3.5" />
                    )}
                    {status === 'copied' ? 'Copied' : 'Copy link'}
                </button>
            </div>
            <p
                role="status"
                aria-live="polite"
                className={
                    status === 'unavailable'
                        ? 'mt-2 text-xs text-white/75'
                        : 'sr-only'
                }
            >
                {status === 'copied'
                    ? 'Product link copied to clipboard.'
                    : status === 'shared'
                      ? 'Product link shared.'
                      : status === 'unavailable'
                        ? 'Share or copy is unavailable in this browser. Use a share link above or copy the address from your browser.'
                        : ''}
            </p>
        </div>
    );
}
