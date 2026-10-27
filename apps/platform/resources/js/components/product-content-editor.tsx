import { useRef, useState } from 'react';
import { ImagePlus, Sparkles, Upload } from 'lucide-react';

export type ProductContent = {
    offering_type?: 'product' | 'service';
    headline: string;
    description: string;
    features: string[];
    faqs: { question: string; answer: string }[];
    photo_prompt: string;
    banner_prompt: string;
    banner_path: string;
    image_alt: string;
};
export type GenerationConfiguration = {
    text_configured: boolean;
    image_configured: boolean;
};
export const emptyProductContent = (): ProductContent => ({
    headline: '',
    description: '',
    features: [],
    faqs: [],
    photo_prompt: '',
    banner_prompt: '',
    banner_path: '',
    image_alt: '',
});

type Draft = Pick<
    ProductContent,
    | 'headline'
    | 'description'
    | 'features'
    | 'faqs'
    | 'photo_prompt'
    | 'banner_prompt'
> & { summary: string; suggested_name: string };

export async function studioRequest(
    path: string,
    body: FormData | Record<string, string>,
) {
    const csrf = document.cookie
        .split('; ')
        .find((item) => item.startsWith('XSRF-TOKEN='))
        ?.split('=')
        .slice(1)
        .join('=');
    const headers: Record<string, string> = {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
    };
    if (csrf) headers['X-XSRF-TOKEN'] = decodeURIComponent(csrf);
    if (!(body instanceof FormData))
        headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {
        method: 'POST',
        credentials: 'same-origin',
        headers,
        body: body instanceof FormData ? body : JSON.stringify(body),
        redirect: 'error',
    });
    const result = await response.json().catch(() => null);
    if (!response.ok) {
        if (response.status === 423)
            throw new Error(
                'Confirm your password again, then retry. Your draft is still here.',
            );
        if (response.status === 419 || response.status === 401)
            throw new Error(
                'Your session expired. Save your draft locally before signing in again.',
            );
        throw new Error(
            result?.message ||
                'The request failed. Your current product has not changed.',
        );
    }
    return result;
}

export default function ProductContentEditor({
    name,
    category,
    summary,
    imagePath,
    content,
    generation,
    onContent,
    onImage,
    onDraft,
    onSuggestedName,
    onBusy,
}: {
    name: string;
    category: string;
    summary: string;
    imagePath: string;
    content: ProductContent;
    generation?: GenerationConfiguration;
    onContent: (content: ProductContent) => void;
    onImage: (path: string) => void;
    onDraft: (summary: string, content: ProductContent) => void;
    onSuggestedName?: (name: string) => void;
    onBusy: (busy: boolean) => void;
}) {
    const identity = useRef({ name, category });
    identity.current = { name, category };
    const latestContent = useRef(content);
    latestContent.current = content;
    const [facts, setFacts] = useState('');
    const [busy, setBusy] = useState(false);
    const [notice, setNotice] = useState('');
    const [suggestedName, setSuggestedName] = useState('');
    const field = 'bg-background w-full rounded-lg border px-3 py-2 text-sm';
    const set = <K extends keyof ProductContent>(
        key: K,
        value: ProductContent[K],
    ) => onContent({ ...latestContent.current, [key]: value });
    const run = async (action: () => Promise<void>) => {
        if (busy) return;
        setBusy(true);
        onBusy(true);
        setNotice('');
        try {
            await action();
        } catch (error) {
            setNotice(
                error instanceof Error ? error.message : 'Request failed.',
            );
        } finally {
            setBusy(false);
            onBusy(false);
        }
    };
    const generate = () =>
        run(async () => {
            const requested = { name, category };
            const result = await studioRequest('/operator/products/draft', {
                name,
                category,
                context: facts || summary,
            });
            if (
                identity.current.name !== requested.name ||
                identity.current.category !== requested.category
            )
                throw new Error(
                    'The title or category changed. Generate again for the current item.',
                );
            const {
                summary: nextSummary,
                suggested_name: candidate,
                ...next
            } = result.draft as Draft;
            setSuggestedName(
                candidate.trim() !== name.trim() ? candidate.trim() : '',
            );
            onDraft(nextSummary, {
                ...latestContent.current,
                ...next,
                image_alt: latestContent.current.image_alt || name,
            });
            setNotice(
                'AI content filled into the form. Review any suggested name separately; nothing is saved yet.',
            );
        });
    const media = (variant: 'photo' | 'banner', file?: File) =>
        run(async () => {
            const data = new FormData();
            data.append('variant', variant);
            if (file) data.append('image', file);
            else
                data.append(
                    'prompt',
                    variant === 'photo'
                        ? content.photo_prompt
                        : content.banner_prompt,
                );
            const result = await studioRequest(
                '/operator/products/media',
                data,
            );
            if (variant === 'photo') onImage(result.path);
            else set('banner_path', result.path);
            setNotice(
                `${file ? 'Uploaded artwork' : 'Cloud AI artwork'} is ready to preview. Save the product to attach it.`,
            );
        });

    return (
        <section
            aria-label="Product content and artwork"
            className="grid min-w-0 gap-5 rounded-xl border border-white/10 bg-black/10 p-4"
        >
            <div>
                <h3 className="flex items-center gap-2 text-base font-bold">
                    <Sparkles className="size-4 text-red-500" /> Product content
                    studio
                </h3>
                <p className="text-muted-foreground mt-1 text-xs leading-5">
                    Write and upload manually, or use a configured verified-free
                    cloud AI route. Generated content stays unsaved until you
                    review and save it.
                </p>
            </div>
            <label className="grid gap-2 text-xs font-semibold">
                Public product facts for cloud drafting
                <textarea
                    className={field}
                    rows={3}
                    maxLength={8000}
                    value={facts}
                    onChange={(event) => setFacts(event.target.value)}
                    placeholder="Intended users, actual features, supported platforms and limitations. These facts are sent to the cloud provider. Do not enter secrets or private customer data."
                />
            </label>
            <div className="flex flex-wrap items-center gap-3">
                <button
                    type="button"
                    onClick={generate}
                    disabled={
                        busy ||
                        name.trim().length < 2 ||
                        !generation?.text_configured
                    }
                    className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-red-600 px-4 text-xs font-bold text-white disabled:opacity-50"
                >
                    <Sparkles className="size-4" />
                    {busy ? 'Preparing…' : 'AI fill all content fields'}
                </button>
                <span className="text-muted-foreground text-xs">
                    {generation?.text_configured
                        ? 'Free cloud configured; live zero-price evidence is checked on each request.'
                        : 'Free cloud key not configured. Manual editing remains available.'}
                </span>
            </div>
            {notice && (
                <p
                    role="status"
                    className="rounded-lg border border-red-500/30 p-3 text-sm"
                >
                    {notice}
                </p>
            )}
            {suggestedName && (
                <div className="flex flex-wrap items-center gap-3 rounded-lg border border-red-500/30 p-3 text-xs">
                    <span>
                        Suggested product name: <strong>{suggestedName}</strong>
                    </span>
                    <button
                        type="button"
                        className="rounded-lg border border-red-500/40 px-3 py-2 font-bold"
                        onClick={() => {
                            onSuggestedName?.(suggestedName);
                            setSuggestedName('');
                            setNotice(
                                'Suggested name applied to your form. Review the catalog URL before saving.',
                            );
                        }}
                        disabled={!onSuggestedName || busy}
                    >
                        Use suggested name
                    </button>
                    <button
                        type="button"
                        className="text-muted-foreground underline"
                        onClick={() => setSuggestedName('')}
                    >
                        Keep current name
                    </button>
                </div>
            )}
            <label className="grid gap-2 text-xs font-semibold">
                Product headline
                <input
                    className={field}
                    maxLength={200}
                    value={content.headline}
                    onChange={(event) => set('headline', event.target.value)}
                />
            </label>
            <label className="grid gap-2 text-xs font-semibold">
                Full product description
                <textarea
                    className={field}
                    rows={7}
                    maxLength={20000}
                    value={content.description}
                    onChange={(event) => set('description', event.target.value)}
                />
            </label>
            <label className="grid gap-2 text-xs font-semibold">
                Features — one per line, up to 12
                <textarea
                    className={field}
                    rows={5}
                    value={content.features.join('\n')}
                    onChange={(event) =>
                        set('features', event.target.value.split('\n'))
                    }
                />
            </label>
            <div className="grid gap-3">
                <h4 className="text-sm font-bold">Product FAQs</h4>
                {content.faqs.map((faq, index) => (
                    <div
                        key={index}
                        className="grid gap-2 rounded-lg border p-3"
                    >
                        <label className="grid gap-1 text-xs">
                            Question {index + 1}
                            <input
                                className={field}
                                maxLength={300}
                                value={faq.question}
                                onChange={(event) =>
                                    set(
                                        'faqs',
                                        content.faqs.map((item, i) =>
                                            i === index
                                                ? {
                                                      ...item,
                                                      question:
                                                          event.target.value,
                                                  }
                                                : item,
                                        ),
                                    )
                                }
                            />
                        </label>
                        <label className="grid gap-1 text-xs">
                            Answer {index + 1}
                            <textarea
                                className={field}
                                maxLength={2000}
                                value={faq.answer}
                                onChange={(event) =>
                                    set(
                                        'faqs',
                                        content.faqs.map((item, i) =>
                                            i === index
                                                ? {
                                                      ...item,
                                                      answer: event.target
                                                          .value,
                                                  }
                                                : item,
                                        ),
                                    )
                                }
                            />
                        </label>
                        <button
                            type="button"
                            className="justify-self-start text-xs text-red-400"
                            onClick={() =>
                                set(
                                    'faqs',
                                    content.faqs.filter((_, i) => i !== index),
                                )
                            }
                        >
                            Remove question {index + 1}
                        </button>
                    </div>
                ))}
                <button
                    type="button"
                    className="min-h-10 justify-self-start rounded-lg border px-3 text-xs"
                    disabled={content.faqs.length >= 8}
                    onClick={() =>
                        set('faqs', [
                            ...content.faqs,
                            { question: '', answer: '' },
                        ])
                    }
                >
                    Add FAQ
                </button>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
                {(['photo', 'banner'] as const).map((variant) => {
                    const path =
                        variant === 'photo' ? imagePath : content.banner_path;
                    const prompt =
                        variant === 'photo'
                            ? content.photo_prompt
                            : content.banner_prompt;
                    const usingBrandFallback =
                        path?.startsWith('/assets/brand/');
                    return (
                        <section
                            key={variant}
                            aria-label={`Product ${variant}`}
                            className="grid content-start gap-3 rounded-xl border p-3"
                        >
                            <h4 className="flex items-center gap-2 text-sm font-bold">
                                <ImagePlus className="size-4" />
                                {variant === 'photo'
                                    ? 'Product photo'
                                    : 'Wide banner'}
                            </h4>
                            {path && (
                                <img
                                    src={path}
                                    alt={
                                        content.image_alt ||
                                        `${name} ${variant} preview`
                                    }
                                    className="aspect-video w-full rounded-lg border object-contain"
                                />
                            )}
                            {usingBrandFallback && (
                                <p className="text-muted-foreground text-xs">
                                    KMJ brand fallback — not generated product
                                    artwork. Use an original upload or a
                                    verified-free image route.
                                </p>
                            )}
                            <label className="grid gap-1 text-xs">
                                {variant} prompt
                                <textarea
                                    className={field}
                                    maxLength={2000}
                                    rows={3}
                                    value={prompt}
                                    onChange={(event) =>
                                        set(
                                            variant === 'photo'
                                                ? 'photo_prompt'
                                                : 'banner_prompt',
                                            event.target.value,
                                        )
                                    }
                                />
                            </label>
                            <label className="flex min-h-11 min-w-0 cursor-pointer flex-wrap items-center gap-2 rounded-lg border px-3 text-xs">
                                <Upload className="size-4" />
                                Upload PNG, JPEG or WebP
                                <input
                                    type="file"
                                    className="max-w-full min-w-0 text-xs"
                                    accept="image/png,image/jpeg,image/webp"
                                    disabled={busy}
                                    onChange={(event) => {
                                        const file = event.target.files?.[0];
                                        if (file) {
                                            if (file.size > 8 * 1024 * 1024)
                                                setNotice(
                                                    'Choose an image of 8 MB or smaller.',
                                                );
                                            else void media(variant, file);
                                        }
                                        event.target.value = '';
                                    }}
                                />
                            </label>
                            <button
                                type="button"
                                className="min-h-11 rounded-lg border border-red-500/40 px-3 text-xs font-bold disabled:opacity-50"
                                disabled={
                                    busy ||
                                    !generation?.image_configured ||
                                    prompt.trim().length < 8
                                }
                                onClick={() => media(variant)}
                            >
                                Generate {variant} with cloud AI
                            </button>
                            {path && (
                                <button
                                    type="button"
                                    className="justify-self-start text-xs text-red-400"
                                    onClick={() =>
                                        variant === 'photo'
                                            ? onImage('')
                                            : set('banner_path', '')
                                    }
                                >
                                    Remove {variant} from form
                                </button>
                            )}
                        </section>
                    );
                })}
            </div>
            {!generation?.image_configured && (
                <p className="text-muted-foreground text-xs">
                    Cloud image generation requires an independently verified
                    Workers Free account and spare quota. It stays off until
                    then; original image upload is available without paid calls.
                </p>
            )}
            <label className="grid gap-2 text-xs font-semibold">
                Artwork alt text
                <input
                    className={field}
                    maxLength={300}
                    value={content.image_alt}
                    onChange={(event) => set('image_alt', event.target.value)}
                />
            </label>
            <p className="text-muted-foreground text-xs leading-5">
                GEO/SEO uses the existing Main Platform pipeline: reviewed
                title, summary, canonical product URL and artwork feed public
                metadata automatically. Hidden products stay out of the public
                catalog; staging stays noindex.
            </p>
        </section>
    );
}
