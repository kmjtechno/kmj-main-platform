import { useRef, useState } from 'react';
import { router } from '@inertiajs/react';
import { Sparkles } from 'lucide-react';
import {
    studioRequest,
    type GenerationConfiguration,
} from '@/components/product-content-editor';
import {
    ManagedProductEditor,
    type ManagedProduct,
} from '@/components/operator-product-manager';

export default function QuickProductCreator({
    generation,
    onCreated,
}: {
    generation?: GenerationConfiguration;
    onCreated?: (productId: string | null) => void;
}) {
    const [brief, setBrief] = useState('');
    const [busy, setBusy] = useState(false);
    const [editorBusy, setEditorBusy] = useState(false);
    const inFlight = useRef(false);
    const requestId = useRef<string | null>(null);
    const [notice, setNotice] = useState('');
    const [created, setCreated] = useState<ManagedProduct | null>(null);
    const create = async () => {
        if (inFlight.current) return;
        inFlight.current = true;
        requestId.current ??= crypto.randomUUID();
        setBusy(true);
        setNotice('');
        try {
            const result = await studioRequest(
                '/operator/products/from-brief',
                { brief, request_id: requestId.current },
            );
            setCreated(result.product);
            onCreated?.(result.product.id);
            setNotice(
                'Your description has become a saved catalog draft. The real editor below is populated; review it before publishing.',
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
                    Give a short public description. AI prepares the name,
                    category, product/service type, summary, full description,
                    features, FAQs and photo/banner prompts. Slug, image alt and
                    existing GEO/SEO metadata follow automatically.
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
                                setNotice('');
                            }}
                            placeholder="Example: KMJ Calibration Studio is proposed projector-calibration software for integrators. Its intended workflow uses a camera for alignment. Describe the actual features, audience and limitations you know."
                        />
                    </label>
                    <p className="text-muted-foreground text-xs">
                        Public facts only; this description is sent to the cloud
                        provider. Do not enter secrets or customer data. Unknown
                        capabilities and availability stay unverified.
                    </p>
                    <button
                        type="button"
                        onClick={create}
                        disabled={
                            busy ||
                            brief.trim().length < 20 ||
                            !generation?.text_configured
                        }
                        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-red-600 px-4 text-sm font-bold text-white disabled:opacity-50"
                    >
                        <Sparkles className="size-4" />
                        {busy
                            ? 'Preparing content & saving draft…'
                            : 'Generate & add from description'}
                    </button>
                </>
            )}
            {!generation?.text_configured && (
                <p role="status" className="text-sm">
                    Free cloud text is not configured. Manual editing is
                    available.
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
                Text generation uses the verified-free cloud route. Actual AI
                image generation is not configured: existing KMJ brand artwork
                is a labeled fallback, and original photo/banner upload is
                available in the editor. Pricing, public visibility, licensing
                and release readiness remain owner-controlled.
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
                            disabled={editorBusy}
                            onClick={() => {
                                setCreated(null);
                                setBrief('');
                                requestId.current = null;
                                setNotice('');
                                onCreated?.(null);
                            }}
                        >
                            Create another
                        </button>
                    </div>
                    <ManagedProductEditor
                        key={created.id}
                        product={created}
                        products={[created]}
                        onDragStart={() => {}}
                        onDrop={() => {}}
                        allowReorder={false}
                        initiallyEditing
                        onActivityChange={setEditorBusy}
                        generation={generation}
                    />
                </div>
            )}
        </section>
    );
}
