import * as DialogPrimitive from '@radix-ui/react-dialog';
import { Head, Link } from '@inertiajs/react';
import { useState } from 'react';
import {
    ArrowRight,
    BrainCircuit,
    Building2,
    Clapperboard,
    Code2,
    Factory,
    Globe2,
    Layers3,
    Monitor,
    ShieldCheck,
    Smartphone,
    Cloud,
    FileCheck,
    Star,
    PlayCircle,
    Menu,
    X,
    Search,
    Send,
    ChevronRight,
} from 'lucide-react';
import LockedBrand from '@/components/locked-brand';
import PublicSeo from '@/components/public-seo';
import '../../css/locked-landing.css';

type Product = {
    slug: string;
    name: string;
    lifecycle: string;
    lifecycle_label: string;
    purchase_enabled: boolean;
    eyebrow: string;
    headline: string;
    summary: string;
    image_path?: string | null;
    variants?: string[];
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

const whatWeBuild = [
    {
        icon: Code2,
        title: 'Software applications',
        text: 'Purpose-built business software, integrations and developer tools.',
    },
    {
        icon: Smartphone,
        title: 'Mobile applications',
        text: 'Native and cross-platform experiences for Android and iOS.',
    },
    {
        icon: Globe2,
        title: 'Web platforms',
        text: 'Accessible websites, customer portals and scalable web applications.',
    },
    {
        icon: Monitor,
        title: 'Desktop applications',
        text: 'Focused, high-performance tools for modern workstations.',
    },
    {
        icon: BrainCircuit,
        title: 'AI & automation',
        text: 'Assisted workflows, intelligent agents and governed AI systems.',
    },
    {
        icon: Building2,
        title: 'Enterprise systems',
        text: 'Secure operations, licensing, identity and business platforms.',
    },
    {
        icon: Factory,
        title: 'Industrial technology',
        text: 'Calibration, monitoring, visualization and control tooling.',
    },
    {
        icon: Clapperboard,
        title: 'Immersive experiences',
        text: 'Cinema, simulation, projection and spatial experiences.',
    },
];

const artwork: Record<string, string> = {
    'kmj-cloudos': 'cloudos',
    'kmj-codebridge': 'codebridge',
    'kmj-omnidesk': 'omnidesk',
    'kmj-calibration-pro': 'calibration',
    'kmj-cinema-platform': 'cinema',
    'kmj-cinecore': 'cinema',
    'kmj-forge': 'forge',
    'kmj-agent': 'agent',
    'kmj-cloud-nexus': 'nexus',
    'kmj-licensing-hub': 'licensing',
    'kmj-creative-studio': 'studio',
    'kmj-motiondirector': 'motion',
};
const industries = [
    ['entertainment', 'Entertainment & Theme Parks'],
    ['education', 'Education & Training'],
    ['museums', 'Museums & Exhibitions'],
    ['industry', 'Industrial & Manufacturing'],
    ['research', 'Research & Simulation'],
    ['architecture', 'Architecture & Visualization'],
    ['healthcare', 'Healthcare & Life Sciences'],
    ['corporate', 'Corporate Enterprises'],
];
const publicNav = [
    ['Home', '/'],
    ['Company', '/company'],
    ['Products', '/products'],
    ['Solutions', '/capabilities'],
    ['Industries', '#industries'],
    ['Resources', '/products'],
    ['Support', '#contact'],
];
const guidance = [
    [
        'Product information',
        'Explore the product catalog for features and current availability.',
        '/products',
    ],
    [
        'Licensing & pricing',
        'Open the Licensing Hub for product access and licensing information.',
        '/products/kmj-licensing-hub',
    ],
    [
        'Software solutions',
        'Explore our software, cloud, mobile and AI capabilities.',
        '/capabilities',
    ],
    [
        'Mobile apps & development',
        'Tell us about your Android or iOS application through our contact page.',
        '#contact',
    ],
    [
        'Technical support',
        'Visit support to get help with your KMJ product.',
        '#contact',
    ],
    [
        'General inquiries',
        'Contact KMJ TECHNO to discuss your project.',
        '#contact',
    ],
];
function SectionHeading({
    title,
    subtitle,
    href,
    label = 'Explore more',
}: {
    title: string;
    subtitle: string;
    href?: string;
    label?: string;
}) {
    return (
        <div className="lock-heading">
            <div>
                <h2>{title}</h2>
                <p>{subtitle}</p>
            </div>
            {href && (
                <Link className="lock-outline" href={href}>
                    {label}
                    <ArrowRight size={13} />
                </Link>
            )}
        </div>
    );
}
function PublicKristi() {
    const [open, setOpen] = useState(true);
    const [answer, setAnswer] = useState<number | null>(null);
    const [query, setQuery] = useState('');
    return (
        <aside
            className={'lock-kristi ' + (open ? 'is-open' : '')}
            aria-label="Kristi product guidance"
        >
            {open ? (
                <>
                    <img
                        src="/assets/locked/kristi-public.webp"
                        className="lock-kristi-person"
                        alt="Kristi, KMJ product guide"
                    />
                    <div className="lock-kristi-box">
                        <button
                            className="lock-close"
                            aria-label="Close Kristi"
                            onClick={() => setOpen(false)}
                        >
                            <X size={14} />
                        </button>
                        <h3>
                            Hi, I'm Kristi <span>✦</span>
                        </h3>
                        <p>
                            Your product guide.
                            <br />
                            How can I help you today?
                        </p>
                        {guidance.map(([label], i) => (
                            <button
                                className="lock-kristi-option"
                                key={label}
                                onClick={() => setAnswer(i)}
                            >
                                {label}
                                <ChevronRight size={11} />
                            </button>
                        ))}
                        {answer !== null && (
                            <div className="lock-kristi-answer" role="status">
                                {guidance[answer][1]}{' '}
                                <Link href={guidance[answer][2]}>
                                    Open <ArrowRight size={12} />
                                </Link>
                            </div>
                        )}
                        <form
                            onSubmit={(e) => {
                                e.preventDefault();
                                setAnswer(
                                    /licens|price/i.test(query)
                                        ? 1
                                        : /support|help/i.test(query)
                                          ? 4
                                          : 0,
                                );
                                setQuery('');
                            }}
                        >
                            <input
                                aria-label="Ask Kristi"
                                placeholder="Type your message…"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                            />
                            <button aria-label="Send message">
                                <Send size={14} />
                            </button>
                        </form>
                    </div>
                </>
            ) : (
                <button className="lock-primary" onClick={() => setOpen(true)}>
                    Hi, I'm Kristi
                </button>
            )}
        </aside>
    );
}
export default function Welcome({
    products,
}: {
    products: Product[];
    portfolioCount: number;
}) {
    const [menu, setMenu] = useState(false);
    const [tour, setTour] = useState(false);
    // Catalog ordering and visibility remain controlled by the backend.
    const ecosystemProducts = products.filter(
        (p) => p.slug !== 'kmj-immersive-cinema-suite',
    );
    return (
        <>
            <PublicSeo
                title="KMJ TECHNO — Software, Mobile Apps, Cloud & AI Engineering"
                description="KMJ TECHNO builds software platforms, cloud systems, AI and immersive experiences."
                path="/"
                structuredData={[
                    {
                        '@context': 'https://schema.org',
                        '@type': 'Organization',
                        name: 'KMJ TECHNO',
                        slogan: 'INNOVATE | BUILD | SCALE',
                        logo: 'https://kmjtechno.com/assets/brand/kmj-logo-horizontal.webp',
                        image: 'https://kmjtechno.com/assets/brand/kmj-social-card.webp',
                        description:
                            'KMJ TECHNO develops software, cloud platforms, AI engineering systems, immersive calibration, secure connectivity and cinema technology.',
                    },
                    {
                        '@context': 'https://schema.org',
                        '@type': 'WebSite',
                        name: 'KMJ TECHNO',
                    },
                ]}
            />
            <Head>
                <meta name="kmj-main-platform" content="native-home" />
                <link
                    rel="preload"
                    as="image"
                    href="/assets/locked/landing-hero.webp"
                />
            </Head>
            <div className="locked-landing">
                <a className="lock-skip" href="#main-content">
                    Skip to main content
                </a>
                <header className="lock-header">
                    <Link href="/" aria-label="KMJ TECHNO home">
                        <LockedBrand compact />
                    </Link>
                    <nav
                        aria-label="Primary navigation"
                        className={menu ? 'is-open' : ''}
                    >
                        {publicNav.map(([label, href]) => (
                            <Link
                                key={label}
                                href={href}
                                className={label === 'Home' ? 'active' : ''}
                                onClick={() => setMenu(false)}
                            >
                                {label}
                            </Link>
                        ))}
                    </nav>
                    <Link
                        className="lock-search"
                        href="/products#product-search"
                    >
                        <Search size={15} />
                        <span>Search products, solutions…</span>
                    </Link>
                    <span className="lock-language">
                        <Globe2 size={16} /> EN
                    </span>
                    <Link href="#contact" className="lock-primary lock-contact">
                        Contact Us <ArrowRight size={13} />
                    </Link>
                    <button
                        className="lock-menu"
                        aria-label="Toggle navigation"
                        aria-expanded={menu}
                        onClick={() => setMenu(!menu)}
                    >
                        {menu ? <X /> : <Menu />}
                    </button>
                </header>
                <main id="main-content">
                    <section className="lock-hero">
                        <img
                            src="/assets/locked/landing-hero.webp"
                            alt="Engineers overlooking a connected futuristic city"
                            width="2176"
                            height="724"
                            fetchPriority="high"
                        />
                        <div className="lock-hero-copy">
                            <p className="lock-eyebrow">
                                AI-POWERED PLATFORMS <b>|</b> IMMERSIVE
                                EXPERIENCES <b>|</b> REAL-WORLD SOLUTIONS
                            </p>
                            <h1>
                                Build Any Software.
                                <br />
                                <span>
                                    Power Every
                                    <br />
                                    Experience.
                                </span>
                            </h1>
                            <p>
                                KMJ TECHNO builds next-generation software
                                platforms, mobile apps, web applications,
                                desktop systems, cloud infrastructure, AI
                                solutions, remote access products, industrial
                                systems, calibration technologies and immersive
                                experiences — to connect people, technology and
                                real-world possibilities.
                            </p>
                            <div className="lock-hero-actions">
                                <Link href="/products" className="lock-primary">
                                    Explore Our Products{' '}
                                    <ArrowRight size={16} />
                                </Link>
                                <DialogPrimitive.Root
                                    open={tour}
                                    onOpenChange={setTour}
                                >
                                    <DialogPrimitive.Trigger asChild>
                                        <button className="lock-outline">
                                            <PlayCircle size={22} /> Watch
                                            Company Video
                                        </button>
                                    </DialogPrimitive.Trigger>
                                    <DialogPrimitive.Portal>
                                        <DialogPrimitive.Overlay className="lock-dialog-backdrop" />
                                        <DialogPrimitive.Content
                                            className="lock-dialog"
                                            aria-label="Company overview"
                                        >
                                            <DialogPrimitive.Close asChild>
                                                <button aria-label="Close company overview">
                                                    <X />
                                                </button>
                                            </DialogPrimitive.Close>
                                            <DialogPrimitive.Title
                                                className="sr-only"
                                            >
                                                Company overview
                                            </DialogPrimitive.Title>
                                            <h2>Build. Connect. Scale.</h2>
                                            <DialogPrimitive.Description
                                                asChild
                                            >
                                                <p>
                                                    Explore KMJ TECHNO's
                                                    software, cloud, AI and
                                                    immersive technology
                                                    capabilities. A company
                                                    video is not available yet.
                                                </p>
                                            </DialogPrimitive.Description>
                                            <Link
                                                href="/company"
                                                className="lock-primary"
                                                onClick={() => setTour(false)}
                                            >
                                                Explore our company{' '}
                                                <ArrowRight size={16} />
                                            </Link>
                                        </DialogPrimitive.Content>
                                    </DialogPrimitive.Portal>
                                </DialogPrimitive.Root>
                            </div>
                        </div>
                        <div className="lock-hero-words">
                            SOFTWARE
                            <br />
                            APPS
                            <br />
                            CLOUD
                            <br />
                            AI SYSTEMS
                            <br />
                            IMMERSIVE
                            <br />
                            INDUSTRIAL
                            <br />
                            AND BEYOND
                        </div>
                    </section>
                    <div className="lock-trust">
                        {[
                            [
                                ShieldCheck,
                                'Security by Design',
                                'Enterprise Focus',
                            ],
                            [Cloud, 'Cloud-Ready', 'Global Deployment'],
                            [
                                Layers3,
                                'Scalable Architecture',
                                'From Startup to Enterprise',
                            ],
                            [
                                Globe2,
                                'Multi-Language Support',
                                'Connected Experiences',
                            ],
                            [
                                FileCheck,
                                'Flexible Licensing',
                                'Commercial & Enterprise',
                            ],
                            [
                                Star,
                                'Built for Global Clients',
                                'Real-World Solutions',
                            ],
                        ].map(([Icon, title, detail]) => {
                            const I = Icon as typeof Cloud;
                            return (
                                <div key={String(title)}>
                                    <I />
                                    <span>
                                        <strong>{String(title)}</strong>
                                        <small>{String(detail)}</small>
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                    <section className="lock-section" id="flagship">
                        <SectionHeading
                            title="Our Flagship Products"
                            subtitle="Powerful solutions for immersive experiences, intelligent operations and real-world impact."
                            href="/products"
                            label="View All Products"
                        />
                        <div className="lock-products">
                            {ecosystemProducts.map((p) => (
                                <article className="lock-product" key={p.slug}>
                                    <Link href={'/products/' + p.slug}>
                                        {artwork[p.slug] || p.image_path ? (
                                            <img
                                                src={
                                                    artwork[p.slug]
                                                        ? '/assets/locked/' +
                                                          artwork[p.slug] +
                                                          '.webp'
                                                        : (p.image_path ?? '')
                                                }
                                                alt={
                                                    p.name + ' product artwork'
                                                }
                                                loading="lazy"
                                                width="480"
                                                height="270"
                                            />
                                        ) : (
                                            <span
                                                className="lock-product-art-unavailable"
                                                role="img"
                                                aria-label={
                                                    p.name +
                                                    ' artwork not available'
                                                }
                                            >
                                                Artwork coming soon
                                            </span>
                                        )}
                                        <span className="lock-product-category">
                                            {p.eyebrow || p.lifecycle_label}
                                        </span>
                                        <div>
                                            <h3>{p.name}</h3>
                                            <p>{p.summary}</p>
                                            <span className="lock-product-cta">
                                                Explore{' '}
                                                {p.name.replace('KMJ ', '')}{' '}
                                                <ArrowRight size={12} />
                                            </span>
                                        </div>
                                    </Link>
                                </article>
                            ))}
                        </div>
                        <p className="lock-catalog-note">
                            Product availability and access remain governed by
                            verified lifecycle and release states.
                        </p>
                    </section>
                    <section
                        className="lock-section"
                        aria-labelledby="what-we-build-heading"
                    >
                        <SectionHeading
                            title="What We Build"
                            subtitle="From idea to global deployment — we build any kind of software, system or immersive experience."
                            href="/capabilities"
                        />
                        <h2 id="what-we-build-heading" className="sr-only">
                            Software capabilities
                        </h2>
                        <div className="lock-capabilities">
                            {whatWeBuild.map(({ icon: Icon, title, text }) => (
                                <Link href="/capabilities" key={title}>
                                    <Icon />
                                    <h3>{title}</h3>
                                    <p>{text}</p>
                                </Link>
                            ))}
                        </div>
                    </section>
                    <section className="lock-ecosystem">
                        <SectionHeading
                            title="A Complete and Connected Ecosystem"
                            subtitle="Our products work together to create a unified platform for creation, control, deployment and growth."
                            href="/products"
                            label="Explore Full Ecosystem"
                        />
                        <div className="lock-ecosystem-scene">
                            <img
                                src="/assets/locked/ecosystem.webp"
                                alt="Connected KMJ technology ecosystem"
                                loading="lazy"
                                width="2176"
                                height="724"
                            />
                            <div className="lock-ecosystem-brand">
                                <LockedBrand />
                            </div>
                            <div className="lock-orbit">
                                {[
                                    [
                                        'CloudOS',
                                        'Core Platform',
                                        '/products/kmj-cloudos',
                                    ],
                                    [
                                        'CodeBridge',
                                        'Build Apps',
                                        '/products/kmj-codebridge',
                                    ],
                                    [
                                        'Cloud Nexus',
                                        'Global Cloud',
                                        '/products/kmj-cloud-nexus',
                                    ],
                                    [
                                        'Agent',
                                        'AI Automation',
                                        '/products/kmj-agent',
                                    ],
                                    [
                                        'Calibration Pro',
                                        'Precision Tools',
                                        '/products/kmj-calibration-pro',
                                    ],
                                    [
                                        'Cinema Platform',
                                        'Immersive Media',
                                        '/products/kmj-cinema-platform',
                                    ],
                                    [
                                        'Forge',
                                        'Engineering Systems',
                                        '/products/kmj-forge',
                                    ],
                                    [
                                        'Licensing Hub',
                                        'Access & Control',
                                        '/products/kmj-licensing-hub',
                                    ],
                                    [
                                        'OmniDesk',
                                        'Remote Access',
                                        '/products/kmj-omnidesk',
                                    ],
                                    [
                                        'Creative Studio',
                                        'Content & Media',
                                        '/products/kmj-creative-studio',
                                    ],
                                ].map(([name, detail, href], i) => (
                                    <Link
                                        key={name}
                                        href={href}
                                        style={
                                            {
                                                '--orbit-index': i,
                                            } as React.CSSProperties
                                        }
                                    >
                                        <Layers3 />
                                        <span>
                                            <strong>{name}</strong>
                                            <small>{detail}</small>
                                        </span>
                                    </Link>
                                ))}
                            </div>
                            <p className="lock-ecosystem-left">
                                ONE
                                <br />
                                ECOSYSTEM
                                <br />
                                ENDLESS
                                <br />
                                POSSIBILITIES
                            </p>
                            <p className="lock-ecosystem-right">
                                CREATE
                                <br />
                                CONNECT
                                <br />
                                DEPLOY
                                <br />
                                SCALE
                                <br />
                                INNOVATE
                                <br />
                                TOGETHER
                            </p>
                        </div>
                    </section>
                    <section className="lock-section" id="industries">
                        <SectionHeading
                            title="Industries We Serve"
                            subtitle="Real solutions for real-world challenges."
                            href="/capabilities"
                            label="View All Industries"
                        />
                        <div className="lock-industries">
                            {industries.map(([key, label]) => (
                                <Link href="/capabilities" key={key}>
                                    <img
                                        src={
                                            '/assets/locked/industry-' +
                                            key +
                                            '.webp'
                                        }
                                        alt=""
                                        loading="lazy"
                                        width="320"
                                        height="180"
                                    />
                                    <h3>{label}</h3>
                                </Link>
                            ))}
                        </div>
                    </section>
                    <section className="lock-roadmap">
                        <SectionHeading
                            title="Our Roadmap"
                            subtitle="Building a future-ready ecosystem."
                            href="/products"
                            label="View Full Roadmap"
                        />
                        <div className="lock-roadmap-steps">
                            {[
                                [
                                    'Now',
                                    'Available Products',
                                    'Review platform and product availability.',
                                ],
                                [
                                    'Next',
                                    'Enhanced Features',
                                    'Advanced capabilities and new integrations.',
                                ],
                                [
                                    'In Development',
                                    'New Products',
                                    'Ongoing development and testing.',
                                ],
                                [
                                    'Future',
                                    'Ecosystem Expansion',
                                    'More industries, more tools and global reach.',
                                ],
                            ].map(([title, sub, text], i) => (
                                <div key={title}>
                                    <span>0{i + 1}</span>
                                    <section>
                                        <h3>{title}</h3>
                                        <strong>{sub}</strong>
                                        <p>{text}</p>
                                    </section>
                                </div>
                            ))}
                        </div>
                    </section>
                </main>
                <footer className="lock-footer">
                    <div className="lock-footer-main">
                        <div>
                            <LockedBrand compact />
                            <p>
                                AI-powered platforms, immersive systems and
                                intelligent solutions for a connected world.
                            </p>
                            <Link href="#contact">
                                Connect with KMJ TECHNO <ArrowRight size={12} />
                            </Link>
                        </div>
                        {[
                            [
                                'Products',
                                ...ecosystemProducts
                                    .slice(0, 10)
                                    .map((p) => p.name.replace('KMJ ', '')),
                            ],
                            [
                                'Company',
                                'About Us',
                                'Our Capabilities',
                                'Industries',
                                'Trust & Security',
                                'Careers',
                            ],
                            [
                                'Resources',
                                'Documentation',
                                'Product Tutorials',
                                'Roadmap',
                                'News & Updates',
                                'Support',
                            ],
                            [
                                'Legal',
                                'Terms & Conditions',
                                'Privacy Policy',
                                'Refund Policy',
                                'Acceptable Use',
                                'Cookie Policy',
                            ],
                        ].map((group, i) => (
                            <div key={group[0]}>
                                <h3>{group[0]}</h3>
                                {group.slice(1).map((label, j) => (
                                    <Link
                                        key={label}
                                        href={
                                            i === 0
                                                ? '/products/' +
                                                  ecosystemProducts[j].slug
                                                : i === 1
                                                  ? '/company'
                                                  : i === 2
                                                    ? '/products'
                                                    : [
                                                          '/terms',
                                                          '/privacy',
                                                          '/refund-policy',
                                                          '/acceptable-use',
                                                          '/cookie-policy',
                                                      ][j]
                                        }
                                    >
                                        {label}
                                    </Link>
                                ))}
                            </div>
                        ))}
                        <div>
                            <h3 id="contact">Stay Connected</h3>
                            <p>Get product updates and news.</p>
                            <a
                                href="mailto:kmjtechnonet@gmail.com"
                                className="lock-outline"
                            >
                                Contact our team <ArrowRight size={14} />
                            </a>
                            <a
                                href="https://www.linkedin.com/company/kmj-techno/"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                Connect on LinkedIn <ArrowRight size={14} />
                            </a>
                        </div>
                    </div>
                    <div className="lock-copyright">
                        <span>
                            © {new Date().getFullYear()} KMJ TECHNO. All rights
                            reserved.
                        </span>
                        <span>Engineered for a connected world.</span>
                    </div>
                </footer>
                <PublicKristi />
            </div>
        </>
    );
}
