import { useEffect, useRef, useState } from 'react';
import { router } from '@inertiajs/react';
import { Sparkles } from 'lucide-react';
import {
    studioRequest,
    useCloudTextCooldown,
    type GenerationConfiguration,
} from '@/components/product-content-editor';
import { type ManagedProduct } from '@/components/operator-product-manager';

export default function QuickProductCreator({
    generation,
    onCreated,
    onBusy,
}: {
    generation?: GenerationConfiguration;
    onCreated?: (productId: string | null) => void;
    onBusy?: (busy: boolean) => void;
}) {
    const [brief, setBrief] = useState('');
    const [busy, setBusy] = useState(false);
    const retrySeconds = useCloudTextCooldown();
    const inFlight = useRef(false);
    const requestId = useRef<string | null>(null);
    const localRequestId = useRef<string | null>(null);
    const [notice, setNotice] = useState('');
    const [created, setCreated] = useState<ManagedProduct | null>(null);
    useEffect(() => {
        onBusy?.(busy);
    }, [busy, onBusy]);
    const create = async (localOnly: boolean) => {
        if (inFlight.current) return;
        inFlight.current = true;
        setBusy(true);
        setNotice('');
        try {
            // UUID generation can fail in restricted webviews. Never leave
            // the single-flight lock stuck outside the guaranteed finally.
            if (localOnly) localRequestId.current ??= crypto.randomUUID();
            else requestId.current ??= crypto.randomUUID();
            const result = await studioRequest(
                '/operator/products/from-brief',
                {
                    brief,
                    request_id: (localOnly
                        ? localRequestId.current
                        : requestId.current)!,
                    local_only: localOnly ? '1' : '0',
                },
            );
            setCreated(result.product);
            onCreated?.(result.product.id);
            setNotice(
                result.generation_mode === 'local-template'
                    ? 'Offline template saved as a PRIVATE planned draft. This is not AI-generated content. Verify every fact and artwork prompt before publishing.'
                    : 'Verified-free AI draft saved privately. Review every claim in the editor before publishing.',
            );
            router.reload({ only: ['products'] });
        } catch (error) {
            setNotice(
                error instanceof Error
                    ? error.message
                    : 'Generation failed. Your description is preserved.',
            );
        } finally {
            inFlight.current = false;
            setBusy(false);
        }
    };
    return (
        <section
            aria-label="One-click AI product or service"
            className="grid gap-4 rounded-xl border border-red-500/20 p-4 sm:p-5"
        >
            <div>
                <h3 className="flex items-center gap-2 text-lg font-bold">
                    <Sparkles className="size-5 text-red-500" /> Describe it.
                    Build your product page.
                </h3>
                <p className="text-muted-foreground mt-2 text-sm">
                    Enter a short public description. Verified-free AI can
                    prepare a reviewable product draft. If the provider is
                    unavailable, choose an explicit offline template instead.
                    Both stay private and require owner review.
                </p>
            </div>
            {!created && (
                <>
                    <label className="grid gap-2 text-sm font-semibold">
                        Describe your product or service
                        <textarea
                            aria-label="Product or service description"
                            className="bg-background w-full rounded-xl border px-4 py-3 text-sm leading-6"
                            rows={5}
                            maxLength={3000}
                            minLength={20}
                            disabled={busy}
                            value={brief}
                            onChange={(e) => {
                                setBrief(e.target.value);
                                requestId.current = null;
                                localRequestId.current = null;
                                setNotice('');
                            }}
                            placeholder="Example: KMJ Calibration Studio is proposed projector-calibration software for integrators. Its intended workflow uses a camera for alignment. Describe the actual features, audience and limitations you know."
                        />
                    </label>
                    <p className="text-muted-foreground text-xs">
                        Public facts only. The AI button sends your description
                        to the cloud; the offline button does not. Never enter
                        secrets or customer data. Unknown details stay
                        unverified.
                    </p>
                    <button
                        type="button"
                        onClick={() => create(false)}
                        disabled={
                            busy ||
                            retrySeconds > 0 ||
                            brief.trim().length < 20 ||
                            !generation?.text_configured
                        }
                        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-red-600 px-4 text-sm font-bold text-white disabled:opacity-50"
                    >
                        <Sparkles className="size-4" />
                        {busy
                            ? 'Preparing content & saving draft…'
                            : retrySeconds > 0
                              ? `Retry AI in ${retrySeconds}s`
                              : 'Generate & add from description'}
                    </button>
                    <button
                        type="button"
                        onClick={() => create(true)}
                        disabled={busy || brief.trim().length < 20}
                        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-white/20 px-4 text-sm font-bold hover:border-red-500/50 disabled:opacity-50"
                    >
                        {busy
                            ? 'Preparing draft…'
                            : 'Create offline review draft · no cloud AI'}
                    </button>
                </>
            )}
            {!generation?.text_configured && (
                <p role="status" className="text-sm">
                    Free cloud text is not configured. You can still create a
                    private offline review draft without contacting an AI
                    provider.
                </p>
            )}
            {notice && (
                <p
                    role="status"
                    className="rounded-lg border border-red-500/30 p-3 text-sm"
                >
                    {notice}
                </p>
            )}
            <p className="text-muted-foreground text-xs leading-5">
                Cloud generation keeps the zero-cost verification gate. The
                offline button uses a deterministic facts-only template, not AI,
                and sends no description to an AI provider. Existing KMJ artwork
                is a labeled fallback; AI images remain separately gated.
                Publishing, licensing and pricing remain owner-controlled.
            </p>
            {created && (
                <div className="grid min-w-0 gap-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <h4 className="font-bold">
                            Saved draft · Review all fields
                        </h4>
                        <button
                            type="button"
                            className="rounded-lg border px-3 py-2 text-xs font-semibold"
                            onClick={() => {
                                setCreated(null);
                                setBrief('');
                                requestId.current = null;
                                localRequestId.current = null;
                                setNotice('');
                                onCreated?.(null);
                            }}
                        >
                            Create another
                        </button>
                    </div>
                    <a
                        href={`#catalog-product-${created.id}`}
                        className="text-sm font-bold text-red-400 underline"
                    >
                        Review the populated product editor below
                    </a>
                </div>
            )}
        </section>
    );
}
