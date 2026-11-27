import { Link, usePage } from '@inertiajs/react';
import { ArrowRight, CheckCircle2, ShieldCheck } from 'lucide-react';
import ProductBrandVisual from '@/components/public/product-visual';
import PublicSeo from '@/components/public-seo';
import ProductShare from '@/components/public/product-share';
import { priceLines, type ProductPrices } from '@/lib/price-labels';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';
import CalibrationDemo from '@/components/products/calibration-demo';
import CloudOSDemo from '@/components/products/cloudos-demo';

const productSocialImages: Record<string, string> = {
    'kmj-cloudos': '/assets/products/kmj-cloudos.webp',
    'kmj-calibration-pro': '/assets/products/kmj-calibration.webp',
    'kmj-forge': '/assets/products/kmj-forge.webp',
    'kmj-connect': '/assets/products/kmj-connect.webp',
    'kmj-cloud-nexus': '/assets/products/kmj-cloud-nexus.webp',
    'kmj-agent': '/assets/products/kmj-agent.webp',
    'kmj-creative-studio': '/assets/products/kmj-creative-studio.webp',
    'kmj-cinema-platform': '/assets/products/kmj-cinema-platform.webp',
    'kmj-360-dome': '/assets/products/kmj-360-dome.webp',
    'kmj-cinema-player': '/assets/products/kmj-cinema-player.webp',
    'kmj-licensing-hub': '/assets/products/kmj-licensing-hub.webp',
};

type Product = {
    image_path?: string | null;
    content?: {
        offering_type?: 'product' | 'service';
        description?: string;
        features?: string[];
        faqs?: { question: string; answer: string }[];
        banner_path?: string;
        image_alt?: string;
    };
    slug: string;
    name: string;
    lifecycle: string;
    lifecycle_label: string;
    purchase_enabled: boolean;
    eyebrow: string;
    headline: string;
    summary: string;
    category: string;
    family: string | null;
    variants?: string[];
    truth: {
        status: string;
        physical_capability_certified?: boolean;
    };
    proof: Array<{
        title: string;
        detail: string;
        state: string;
    }>;
    demo: {
        kind: 'cloudos' | 'calibration' | 'none';
        simulation: boolean;
        label: string;
        steps: Array<{
            key: string;
            label: string;
            detail: string;
        }>;
    };
};

type Access = 'trial' | 'request' | 'preregister';

type Answer = { question: string; answer: string };

// Only states a visitor can act on get a label.
const proofLabels: Record<string, string> = {
    'roadmap-verified': 'On the product roadmap',
    'fail-closed': 'Held back until verified',
    simulation: 'Demo with sample data',
};

const primaryButton =
    'inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-[#c1121f] px-6 text-sm font-black text-white shadow-[0_14px_40px_rgba(193,18,31,.35)] transition hover:bg-[#a50f1a]';
const secondaryButton =
    'inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/[0.03] px-6 text-sm font-bold text-white/85 transition hover:border-white/30 hover:text-white';
const container = 'mx-auto w-full max-w-[1280px] px-5 sm:px-8';
const eyebrow =
    'text-[11px] font-black tracking-[0.22em] text-[#ff6a72] uppercase';
const heading = 'mt-3 text-3xl font-black tracking-[-0.035em] sm:text-4xl';
const card = 'rounded-2xl border border-white/[0.09] bg-white/[0.025] p-6';

function ProductArtwork({ product }: { product: Product }) {
    return (
        <figure className="relative min-w-0">
            <div className="pointer-events-none absolute -inset-6 rounded-[3rem] bg-[#c1121f]/15 blur-[80px]" />
            <div className="relative overflow-hidden rounded-[1.75rem] border border-white/[0.12] bg-[#0a0d12] p-2 shadow-[0_40px_120px_rgba(0,0,0,.55)]">
                {product.image_path ? (
                    <img
                        src={product.image_path}
                        alt={product.content?.image_alt || product.name}
                        width={1280}
                        height={960}
                        fetchPriority="high"
                        className="aspect-[4/3] w-full rounded-[1.35rem] object-contain"
                    />
                ) : (
                    <ProductBrandVisual
                        slug={product.slug}
                        name={product.name}
                        kind={product.demo.kind}
                    />
                )}
            </div>
            <figcaption className="relative mt-4 text-center text-xs leading-5 text-white/65">
                Concept artwork. Any figures shown in the picture are
                illustrative, not measured results.
            </figcaption>
        </figure>
    );
}

function PlanCards({
    pricing,
    onSale,
    action,
}: {
    pricing: ProductPrices;
    onSale: boolean;
    action: { href: string; label: string };
}) {
    return (
        <ul className="mt-10 grid grid-cols-[repeat(auto-fit,minmax(min(100%,17rem),1fr))] gap-4">
            {pricing.plans.map((plan) => {
                const [price, ...notes] = priceLines(plan);
                // "₹499 + GST per user / month": the amount leads, terms follow.
                const [, amount, terms] =
                    price.match(/^(₹[\d,.]+)\s+(.+)$/) ?? [];

                return (
                    <li
                        key={plan.name}
                        className="flex flex-col rounded-3xl border border-white/[0.1] bg-gradient-to-b from-white/[0.055] to-white/[0.015] p-7"
                    >
                        <h3 className="text-sm font-black tracking-[0.12em] text-white/75 uppercase">
                            {plan.name}
                        </h3>
                        <p className="mt-4 text-2xl leading-snug font-black tracking-[-0.025em] text-white">
                            {amount ? (
                                <>
                                    <span className="text-5xl">{amount}</span>{' '}
                                    <span className="text-sm font-bold tracking-normal text-white/70">
                                        {terms}
                                    </span>
                                </>
                            ) : (
                                price
                            )}
                        </p>
                        {notes.map((note) => (
                            <p
                                key={note}
                                className="mt-2 text-sm text-white/70"
                            >
                                {note}
                            </p>
                        ))}
                        <div className="mt-auto pt-7">
                            {onSale ? (
                                <Link
                                    href={action.href}
                                    className={secondaryButton + ' w-full'}
                                    aria-label={`${action.label}: ${plan.name}`}
                                >
                                    {action.label}
                                </Link>
                            ) : (
                                <p className="rounded-xl border border-white/10 px-4 py-3 text-center text-xs font-bold text-white/70">
                                    Planned price. Not on sale yet.
                                </p>
                            )}
                        </div>
                    </li>
                );
            })}
        </ul>
    );
}

export default function ProductShow({
    product,
    pricing = null,
    access = 'preregister',
    answers = [],
}: {
    product: Product;
    pricing?: ProductPrices | null;
    access?: Access;
    answers?: Answer[];
}) {
    const { auth } = usePage<{ auth?: { user?: unknown } }>().props;
    const signedIn = Boolean(auth?.user);
    const Demo =
        product.demo.kind === 'cloudos'
            ? CloudOSDemo
            : product.demo.kind === 'calibration'
              ? CalibrationDemo
              : null;
    const onSale = product.purchase_enabled;
    const signupHref = signedIn
        ? '/dashboard'
        : `/register?product=${encodeURIComponent(product.slug)}`;
    const primary = {
        trial: {
            href: signupHref,
            label: signedIn ? 'Open My Services' : 'Start 30-day free trial',
        },
        request: { href: '/purchase', label: 'Request access' },
        preregister: {
            href: signupHref,
            label: signedIn ? 'Open My Services' : 'Pre-register',
        },
    }[access];
    const reassurance = {
        trial: 'Verify your email and the trial starts. Nothing is charged automatically.',
        request:
            'Access is activated after KMJ confirms your payment. Nothing is charged automatically.',
        preregister:
            'Free to pre-register. Access is not given until the product is released.',
    }[access];
    const steps = {
        trial: [
            ['Create your account', 'Sign up with your email.'],
            ['Verify your email', 'Your 30-day free trial starts.'],
            [
                'Choose a plan',
                'Request a paid plan when you are ready. Paid access starts after KMJ confirms payment.',
            ],
        ],
        request: [
            ['Create your account', 'Sign up and verify your email.'],
            ['Request access', 'Tell us which plan you need.'],
            ['Get activated', 'Access starts after KMJ confirms your payment.'],
        ],
        preregister: [
            ['Create your account', 'Sign up and verify your email.'],
            ['Pre-register', 'We record your interest in this product.'],
            [
                'Wait for release',
                'Nothing is charged, and access is not given before release.',
            ],
        ],
    }[access];
    const accountNote =
        onSale && !signedIn ? (
            <p className="mt-2 max-w-xl text-xs leading-5 text-white/65">
                Requesting access needs a KMJ account. No payment is taken at
                this step.
            </p>
        ) : null;
    const image = product.image_path || productSocialImages[product.slug];

    return (
        <>
            <PublicSeo
                title={
                    product.eyebrow &&
                    product.eyebrow !== 'KMJ TECHNO product catalog'
                        ? `${product.name}: ${product.eyebrow} — KMJ TECHNO`
                        : `${product.name} — KMJ TECHNO`
                }
                description={product.summary}
                path={'/products/' + product.slug}
                image={image}
                imageAlt={
                    product.content?.image_alt || product.name + ' — KMJ TECHNO'
                }
                structuredData={[
                    ...(answers.length
                        ? [
                              {
                                  '@context': 'https://schema.org',
                                  '@type': 'FAQPage',
                                  mainEntity: answers.map((faq) => ({
                                      '@type': 'Question',
                                      name: faq.question,
                                      acceptedAnswer: {
                                          '@type': 'Answer',
                                          text: faq.answer,
                                      },
                                  })),
                              },
                          ]
                        : []),
                    {
                        '@context': 'https://schema.org',
                        '@type':
                            product.content?.offering_type === 'service'
                                ? 'Service'
                                : 'SoftwareApplication',
                        name: product.name,
                        description: product.summary,
                        ...(product.content?.offering_type === 'service'
                            ? {
                                  provider: {
                                      '@type': 'Organization',
                                      name: 'KMJ TECHNO',
                                  },
                              }
                            : {
                                  brand: {
                                      '@type': 'Brand',
                                      name: 'KMJ TECHNO',
                                  },
                                  additionalProperty: {
                                      '@type': 'PropertyValue',
                                      name: 'Lifecycle',
                                      value: product.lifecycle_label,
                                  },
                              }),
                    },
                    {
                        '@context': 'https://schema.org',
                        '@type': 'BreadcrumbList',
                        itemListElement: [
                            {
                                '@type': 'ListItem',
                                position: 1,
                                name: 'Home',
                                item: 'https://kmjtechno.com/',
                            },
                            {
                                '@type': 'ListItem',
                                position: 2,
                                name: 'Products',
                                item: 'https://kmjtechno.com/products',
                            },
                            {
                                '@type': 'ListItem',
                                position: 3,
                                name: product.name,
                                item:
                                    'https://kmjtechno.com/products/' +
                                    product.slug,
                            },
                        ],
                    },
                ]}
            />

            <div className="min-h-screen overflow-x-clip bg-[#030b10] text-white selection:bg-[#ef2632] selection:text-white">
                <PublicSiteHeader />

                <main id="main-content">
                    <section className="relative isolate">
                        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_70%_60%_at_75%_20%,rgba(193,18,31,0.16),transparent_70%)]" />
                        <div className={container + ' pt-8 pb-16 lg:pb-24'}>
                            <nav aria-label="Breadcrumb">
                                <ol className="flex flex-wrap items-center gap-2 text-xs font-bold text-white/65">
                                    <li>
                                        <Link
                                            href="/products"
                                            className="hover:text-white"
                                        >
                                            Products
                                        </Link>
                                    </li>
                                    <li aria-hidden="true">/</li>
                                    <li aria-current="page">{product.name}</li>
                                </ol>
                            </nav>

                            <div className="mt-10 grid items-center gap-12 lg:grid-cols-[1fr_1.05fr] lg:gap-16">
                                <div className="min-w-0">
                                    <div className="flex flex-wrap items-center gap-3">
                                        <span className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/[0.04] px-3.5 py-1.5 text-[11px] font-black tracking-[0.12em] text-white/80 uppercase">
                                            <span
                                                aria-hidden="true"
                                                className={
                                                    'h-1.5 w-1.5 rounded-full ' +
                                                    (onSale
                                                        ? 'bg-emerald-400'
                                                        : 'bg-amber-300')
                                                }
                                            />
                                            {product.lifecycle_label}
                                        </span>
                                        <span className={eyebrow}>
                                            {product.eyebrow}
                                        </span>
                                    </div>

                                    <h1 className="mt-6 font-black text-balance">
                                        {product.name}
                                    </h1>
                                    <p className="mt-5 max-w-xl text-xl leading-8 font-bold text-balance text-white sm:text-2xl sm:leading-9">
                                        {product.headline}
                                    </p>
                                    <p className="mt-4 max-w-xl text-base leading-7 text-white/70">
                                        {product.summary}
                                    </p>

                                    {product.variants &&
                                        product.variants.length > 0 && (
                                            <ul
                                                aria-label="Platform configurations"
                                                className="mt-6 flex flex-wrap gap-2"
                                            >
                                                {product.variants.map(
                                                    (variant) => (
                                                        <li
                                                            key={variant}
                                                            className="rounded-full border border-[#ef3340]/30 bg-[#ef3340]/[0.08] px-3.5 py-1.5 text-xs font-black text-[#ff8087]"
                                                        >
                                                            {variant}
                                                        </li>
                                                    ),
                                                )}
                                            </ul>
                                        )}

                                    <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                                        <Link
                                            href={primary.href}
                                            className={primaryButton}
                                        >
                                            {primary.label}
                                            <ArrowRight
                                                aria-hidden="true"
                                                className="h-4 w-4"
                                            />
                                        </Link>
                                        {pricing ? (
                                            <a
                                                href="#pricing"
                                                className={secondaryButton}
                                            >
                                                See pricing
                                            </a>
                                        ) : Demo ? (
                                            <a
                                                href="#demo"
                                                className={secondaryButton}
                                            >
                                                Try the demo
                                            </a>
                                        ) : (
                                            <Link
                                                href="/products"
                                                className={secondaryButton}
                                            >
                                                All products
                                            </Link>
                                        )}
                                    </div>
                                    <p className="mt-4 max-w-xl text-sm leading-6 text-white/65">
                                        {reassurance}
                                    </p>
                                    {access === 'request' && !pricing
                                        ? accountNote
                                        : null}
                                </div>

                                <ProductArtwork product={product} />
                            </div>
                        </div>
                    </section>

                    {pricing && (
                        <section
                            id="pricing"
                            aria-labelledby="pricing-heading"
                            className="scroll-mt-24 border-t border-white/[0.07]"
                        >
                            <div className={container + ' py-16 lg:py-24'}>
                                <p className={eyebrow}>Pricing</p>
                                <h2 id="pricing-heading" className={heading}>
                                    {onSale
                                        ? 'Choose your plan'
                                        : 'Planned pricing'}
                                </h2>
                                <PlanCards
                                    pricing={pricing}
                                    onSale={onSale}
                                    action={{
                                        href: '/purchase',
                                        label: 'Request this plan',
                                    }}
                                />
                                <p className="mt-5 text-xs leading-5 text-white/65">
                                    GST is extra. Your own cloud, AI provider,
                                    hardware and onsite costs are not included.
                                    Nothing is charged automatically.
                                </p>
                                {accountNote}
                            </div>
                        </section>
                    )}

                    <section
                        aria-labelledby="start-heading"
                        className="border-t border-white/[0.07] bg-white/[0.015]"
                    >
                        <div className={container + ' py-16 lg:py-24'}>
                            <p className={eyebrow}>Getting access</p>
                            <h2 id="start-heading" className={heading}>
                                Three clear steps
                            </h2>
                            <ol className="mt-10 grid gap-4 md:grid-cols-3">
                                {steps.map(([title, detail], index) => (
                                    <li key={title} className={card}>
                                        <span className="grid h-10 w-10 place-items-center rounded-full bg-[#c1121f] text-sm font-black">
                                            {index + 1}
                                        </span>
                                        <h3 className="mt-5 text-lg font-black">
                                            {title}
                                        </h3>
                                        <p className="mt-2 text-sm leading-6 text-white/70">
                                            {detail}
                                        </p>
                                    </li>
                                ))}
                            </ol>
                        </div>
                    </section>

                    {product.content?.description ||
                    product.content?.features?.length ||
                    product.content?.banner_path ? (
                        <section
                            aria-label="Product details"
                            className="border-t border-white/[0.07]"
                        >
                            <div
                                className={
                                    container + ' grid gap-10 py-16 lg:py-24'
                                }
                            >
                                {product.content.banner_path && (
                                    <img
                                        src={product.content.banner_path}
                                        alt={
                                            product.content.image_alt ||
                                            product.name
                                        }
                                        loading="lazy"
                                        className="aspect-video w-full rounded-3xl object-cover"
                                    />
                                )}
                                {product.content.description && (
                                    <div>
                                        <h2 className={heading}>
                                            About {product.name}
                                        </h2>
                                        <p className="mt-5 max-w-3xl text-base leading-8 whitespace-pre-wrap text-white/75">
                                            {product.content.description}
                                        </p>
                                    </div>
                                )}
                                {product.content.features &&
                                    product.content.features.length > 0 && (
                                        <div>
                                            <h2 className={heading}>
                                                Product features
                                            </h2>
                                            <ul className="mt-6 grid gap-3 sm:grid-cols-2">
                                                {product.content.features.map(
                                                    (feature, index) => (
                                                        <li
                                                            key={index}
                                                            className="flex gap-3 rounded-2xl border border-white/[0.09] p-4 text-sm leading-6 text-white/80"
                                                        >
                                                            <CheckCircle2
                                                                aria-hidden="true"
                                                                className="mt-0.5 h-4 w-4 shrink-0 text-[#ff6a72]"
                                                            />
                                                            {feature}
                                                        </li>
                                                    ),
                                                )}
                                            </ul>
                                        </div>
                                    )}
                            </div>
                        </section>
                    ) : null}

                    {Demo ? (
                        <section
                            id="demo"
                            className="scroll-mt-24 border-t border-white/[0.07]"
                        >
                            <div className={container + ' py-16 lg:py-24'}>
                                <p className={eyebrow}>Interactive demo</p>
                                <h2 className={heading}>
                                    See how the workflow runs
                                </h2>
                                <p className="mt-4 max-w-2xl text-base leading-7 text-white/70">
                                    {product.truth.status} The demo runs in your
                                    browser and controls no live system.
                                </p>
                                <div className="mt-10 min-w-0">
                                    <Demo steps={product.demo.steps} />
                                </div>
                            </div>
                        </section>
                    ) : (
                        <section className="border-t border-white/[0.07]">
                            <div className={container + ' py-16'}>
                                <div className={card}>
                                    <p className={eyebrow}>Current status</p>
                                    <p className="mt-3 max-w-3xl text-base leading-7 text-white/75">
                                        {product.truth.status}
                                    </p>
                                </div>
                            </div>
                        </section>
                    )}

                    {product.proof.length > 0 && (
                        <section
                            aria-labelledby="trust-heading"
                            className="border-t border-white/[0.07] bg-white/[0.015]"
                        >
                            <div className={container + ' py-16 lg:py-24'}>
                                <p className={eyebrow}>Trust</p>
                                <h2 id="trust-heading" className={heading}>
                                    What you can rely on today
                                </h2>
                                <ul className="mt-10 grid grid-cols-[repeat(auto-fit,minmax(min(100%,17rem),1fr))] gap-4">
                                    {product.proof.map((item) => (
                                        <li key={item.title} className={card}>
                                            <ShieldCheck
                                                aria-hidden="true"
                                                className="h-6 w-6 text-[#ff6a72]"
                                            />
                                            <h3 className="mt-4 text-lg font-black">
                                                {item.title}
                                            </h3>
                                            <p className="mt-2 text-sm leading-6 text-white/70">
                                                {item.detail}
                                            </p>
                                            {proofLabels[item.state] && (
                                                <p className="mt-4 text-xs font-bold text-white/65">
                                                    {proofLabels[item.state]}
                                                </p>
                                            )}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </section>
                    )}

                    {answers.length > 0 && (
                        <section
                            aria-labelledby="faq-heading"
                            className="border-t border-white/[0.07]"
                        >
                            <div
                                className={
                                    container +
                                    ' grid gap-10 py-16 lg:grid-cols-[.7fr_1.3fr] lg:py-24'
                                }
                            >
                                <div>
                                    <p className={eyebrow}>FAQ</p>
                                    <h2 id="faq-heading" className={heading}>
                                        Common questions
                                    </h2>
                                </div>
                                <div className="min-w-0 border-t border-white/10">
                                    {answers.map((item, index) => (
                                        <details
                                            key={item.question}
                                            open={index === 0}
                                            className="group border-b border-white/10"
                                        >
                                            <summary className="flex min-h-16 cursor-pointer list-none items-center justify-between gap-4 py-4 text-base font-bold">
                                                {item.question}
                                                <span
                                                    aria-hidden="true"
                                                    className="text-2xl text-[#ff6a72] group-open:rotate-45"
                                                >
                                                    +
                                                </span>
                                            </summary>
                                            <p className="pb-5 text-sm leading-7 whitespace-pre-wrap text-white/75">
                                                {item.answer}
                                            </p>
                                        </details>
                                    ))}
                                </div>
                            </div>
                        </section>
                    )}

                    <section className="border-t border-white/[0.07]">
                        <div className={container + ' py-16 lg:py-20'}>
                            <div className="rounded-3xl border border-[#c1121f]/30 bg-gradient-to-br from-[#c1121f]/20 to-transparent p-8 sm:p-12">
                                <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
                                    <div className="max-w-xl">
                                        <h2 className="text-3xl font-black tracking-[-0.035em]">
                                            Get started with {product.name}
                                        </h2>
                                        <p className="mt-3 text-sm leading-6 text-white/75">
                                            {reassurance}
                                        </p>
                                    </div>
                                    <div className="flex flex-col gap-3 sm:flex-row">
                                        <Link
                                            href={primary.href}
                                            className={primaryButton}
                                        >
                                            {primary.label}
                                        </Link>
                                        <Link
                                            href="/products"
                                            className={secondaryButton}
                                        >
                                            All products
                                        </Link>
                                    </div>
                                </div>
                            </div>

                            <ProductShare
                                name={product.name}
                                slug={product.slug}
                            />

                            {product.slug === 'kmj-codebridge' && (
                                <div className="mt-6 flex flex-wrap gap-2 text-xs font-bold">
                                    {[
                                        ['terms', 'Terms of Service'],
                                        ['privacy', 'Privacy Policy'],
                                        ['support', 'Support'],
                                    ].map(([path, label]) => (
                                        <Link
                                            key={path}
                                            href={`/products/kmj-codebridge/${path}`}
                                            className="inline-flex min-h-10 items-center rounded-lg border border-white/10 px-3 text-white/75 hover:text-white"
                                        >
                                            {label}
                                        </Link>
                                    ))}
                                </div>
                            )}
                        </div>
                    </section>
                </main>

                <PublicSiteFooter />
            </div>
        </>
    );
}
