import { useRef, useState } from 'react';
import { Link, router } from '@inertiajs/react';
import { Sparkles } from 'lucide-react';
import {
    studioRequest,
    type GenerationConfiguration,
} from '@/components/product-content-editor';
import {
    productCategoryOptions,
    type ManagedProduct,
} from '@/components/operator-product-manager';

export default function QuickProductCreator({
    generation,
}: {
    generation?: GenerationConfiguration;
}) {
    const [name, setName] = useState('');
    const [kind, setKind] = useState('product');
    const [category, setCategory] = useState('other');
    const [facts, setFacts] = useState('');
    const [busy, setBusy] = useState(false);
    const inFlight = useRef(false);
    const [notice, setNotice] = useState('');
    const [created, setCreated] = useState<ManagedProduct | null>(null);
    const field = 'bg-background w-full rounded-lg border px-3 py-2 text-sm';
    const create = async () => {
        if (inFlight.current) return;
        inFlight.current = true;
        setBusy(true);
        setNotice('');
        setCreated(null);
        try {
            const result = await studioRequest('/operator/products/ai-create', {
                name,
                category,
                offering_type: kind,
                context: facts,
            });
            setCreated(result.product);
            setNotice(
                'Added as a private planned draft. All generated text fields are saved; review before publishing.',
            );
            router.reload({ only: ['products'] });
        } catch (error) {
            setNotice(
                error instanceof Error
                    ? error.message
                    : 'Creation failed. Your inputs remain here.',
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
                    <Sparkles className="size-5 text-red-500" /> AI fill & add
                </h3>
                <p className="text-muted-foreground mt-2 text-sm">
                    Enter a title and verified public facts. One click prepares
                    and saves the content, URL slug, FAQs, artwork prompts and
                    image alt text. Existing GEO/SEO metadata follows the saved
                    content.
                </p>
            </div>
            <fieldset
                disabled={busy}
                className="grid gap-4 disabled:opacity-70"
            >
                <label className="grid gap-2 text-xs font-semibold">
                    Product or service title
                    <input
                        className={field}
                        value={name}
                        minLength={2}
                        maxLength={160}
                        onChange={(e) => {
                            setName(e.target.value);
                            setCreated(null);
                        }}
                        placeholder="KMJ Calibration Pro"
                    />
                </label>
                <div className="grid gap-4 sm:grid-cols-2">
                    <label className="grid gap-2 text-xs font-semibold">
                        Offering type
                        <select
                            className={field}
                            aria-label="Offering type"
                            value={kind}
                            onChange={(e) => {
                                setKind(e.target.value);
                                setCreated(null);
                            }}
                        >
                            <option value="product">Product</option>
                            <option value="service">Service</option>
                        </select>
                    </label>
                    <label className="grid gap-2 text-xs font-semibold">
                        Category
                        <select
                            className={field}
                            value={category}
                            onChange={(e) => {
                                setCategory(e.target.value);
                                setCreated(null);
                            }}
                        >
                            {productCategoryOptions.map(([value, label]) => (
                                <option value={value} key={value}>
                                    {label}
                                </option>
                            ))}
                        </select>
                    </label>
                </div>
                <label className="grid gap-2 text-xs font-semibold">
                    Verified public facts (optional)
                    <textarea
                        className={field}
                        rows={4}
                        maxLength={7900}
                        value={facts}
                        onChange={(e) => {
                            setFacts(e.target.value);
                            setCreated(null);
                        }}
                        placeholder="Actual features, intended users, platforms and limitations. Sent to the free cloud provider; do not enter secrets or customer data. Without facts, AI describes proposed scope only."
                    />
                </label>
                <button
                    type="button"
                    onClick={create}
                    disabled={
                        busy ||
                        !!created ||
                        name.trim().length < 2 ||
                        !generation?.text_configured
                    }
                    className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-red-600 px-4 text-sm font-bold text-white disabled:opacity-50"
                >
                    <Sparkles className="size-4" />
                    {busy
                        ? 'Generating & adding…'
                        : 'AI fill & add private draft'}
                </button>
            </fieldset>
            <p className="text-muted-foreground text-xs leading-5">
                Verified-free cloud text only. Existing KMJ brand artwork is
                used as a fallback; upload original photo/banner in the full
                editor. AI images are not configured. Publishing, availability,
                pricing and licensing remain owner-controlled.
            </p>
            {!generation?.text_configured && (
                <p role="status" className="text-sm">
                    Free cloud text is not configured. Use the manual form
                    below.
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
            {created && (
                <div className="grid gap-4 rounded-lg border p-4">
                    <h4 className="text-lg font-bold">{created.name}</h4>
                    <p className="text-sm">{created.summary}</p>
                    <dl className="grid gap-3 text-sm sm:grid-cols-2">
                        <div>
                            <dt className="text-muted-foreground">
                                Public URL after publishing
                            </dt>
                            <dd className="break-all">
                                /products/{created.slug}
                            </dd>
                        </div>
                        <div>
                            <dt className="text-muted-foreground">State</dt>
                            <dd>Private · Planned · Purchasing off</dd>
                        </div>
                    </dl>
                    <details className="rounded-lg border p-3">
                        <summary className="cursor-pointer text-sm font-semibold">
                            View generated fields
                        </summary>
                        <div className="mt-4 grid gap-3 text-sm">
                            <strong>{created.content?.headline}</strong>
                            <p className="whitespace-pre-wrap">
                                {created.content?.description}
                            </p>
                            <ul className="list-disc pl-5">
                                {created.content?.features?.map(
                                    (feature, i) => (
                                        <li key={i}>{feature}</li>
                                    ),
                                )}
                            </ul>
                            {created.content?.faqs?.map((faq, i) => (
                                <div key={i}>
                                    <strong>{faq.question}</strong>
                                    <p>{faq.answer}</p>
                                </div>
                            ))}
                            <p>Photo prompt: {created.content?.photo_prompt}</p>
                            <p>
                                Banner prompt: {created.content?.banner_prompt}
                            </p>
                            <p>Artwork alt: {created.content?.image_alt}</p>
                        </div>
                    </details>
                    <Link
                        href={`/operator/products?edit=${created.id}`}
                        className="text-sm font-bold text-red-400 underline"
                    >
                        Open full editor to review & publish
                    </Link>
                </div>
            )}
        </section>
    );
}
