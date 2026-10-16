import { Link } from '@inertiajs/react';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
    Activity,
    ArrowRight,
    Boxes,
    CheckCircle2,
    ChevronLeft,
    ChevronRight,
    Command,
    KeyRound,
    Package,
    Search,
    ShieldCheck,
    ShoppingCart,
    Users,
} from 'lucide-react';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogTitle,
} from '@/components/ui/dialog';
import KristiOwnerAssistant from '@/components/kristi-owner-assistant';
import OperatorWorkspaceMap from '@/components/operator-workspace-map';

type Metrics = {
    users: number;
    organizations: number;
    entitlements: number;
    orders: number;
    confirmed_orders: number;
};
type Product = {
    id: string;
    slug: string;
    name: string;
    status: string;
    lifecycle: string;
    is_public: boolean;
    purchase_enabled: boolean;
    licensing_enabled: boolean;
};
type Order = { id: string; status: string; fulfillment_state: string };
type Props = {
    metrics: Metrics;
    catalogProducts: Product[];
    recentOrders: Order[];
    missingCanonicalSlugs: string[];
};

const images: Record<string, string> = {
    'kmj-cloudos': '/assets/products/kmj-cloudos.webp',
    'kmj-calibration-pro': '/assets/products/kmj-calibration.webp',
    'kmj-cinema-platform': '/assets/products/kmj-cinema-platform.webp',
    'kmj-360-dome': '/assets/products/kmj-360-dome.webp',
    'kmj-cinema-player': '/assets/products/kmj-cinema-player.webp',
    'kmj-cloud-nexus': '/assets/products/kmj-cloud-nexus.webp',
    'kmj-forge': '/assets/products/kmj-forge.webp',
    'kmj-connect': '/assets/products/kmj-connect.webp',
    'kmj-agent': '/assets/products/kmj-agent.webp',
    'kmj-creative-studio': '/assets/products/kmj-creative-studio.webp',
    'kmj-licensing-hub': '/assets/products/kmj-licensing-hub.webp',
};
const destinations = [
    { label: 'Command Center', href: '/operator' },
    { label: 'Products & Catalog', href: '/operator/products' },
    { label: 'Customers & Organizations', href: '/operator/directory' },
    { label: 'Commercial Orders', href: '/operator#commercial-orders' },
    { label: 'Payment Gateways', href: '/operator/payments' },
    { label: 'Entitlements & Licensing', href: '/operator/kslp' },
    { label: 'Operations & Audit', href: '/operator/ops' },
    { label: 'CodeBridge Controls', href: '/operator/codebridge/owner-plan' },
    { label: 'Developer Apps & Keys', href: '/developer/apps' },
] as const;

function Stat({
    name,
    value,
    caption,
    icon: Icon,
    tone,
}: {
    name: string;
    value: number;
    caption: string;
    icon: typeof Users;
    tone: string;
}) {
    return (
        <div className="kmj-os-stat">
            <span className={'kmj-os-stat-icon ' + tone}>
                <Icon className="size-5" aria-hidden="true" />
            </span>
            <div className="min-w-0">
                <p className="text-xs font-semibold text-slate-300">{name}</p>
                <p className="mt-1 text-2xl font-extrabold text-white tabular-nums">
                    {value.toLocaleString('en-IN')}
                </p>
                <p className="mt-1 text-[11px] leading-4 text-slate-400">
                    {caption}
                </p>
            </div>
        </div>
    );
}

export default function OperatorCommandOs({
    metrics,
    catalogProducts,
    recentOrders,
    missingCanonicalSlugs,
}: Props) {
    const [searchOpen, setSearchOpen] = useState(false);
    const [query, setQuery] = useState('');
    const input = useRef<HTMLInputElement | null>(null);
    const carousel = useRef<HTMLDivElement | null>(null);
    const results = useMemo(() => {
        const term = query.trim().toLocaleLowerCase();
        const workspaces = destinations.map((item) => ({
            key: item.href,
            label: item.label,
            href: item.href,
            category: 'Workspace',
        }));
        if (!term) return workspaces;
        const matchingWorkspaces = workspaces.filter((item) =>
            item.label.toLocaleLowerCase().includes(term),
        );
        const matchingProducts = catalogProducts
            .filter((product) =>
                (product.name + ' ' + product.slug)
                    .toLocaleLowerCase()
                    .includes(term),
            )
            .slice(0, 12)
            .map((product) => ({
                key: 'product:' + product.id,
                label: product.name,
                href: '/operator/products',
                category: 'Catalog product',
            }));
        return [...matchingWorkspaces, ...matchingProducts].slice(0, 20);
    }, [catalogProducts, query]);
    const needsReview = [
        {
            name: 'Payment evidence',
            count: recentOrders.filter((order) => order.status === 'requested')
                .length,
            href: '/operator#commercial-orders',
            note: 'From the bounded order snapshot',
        },
        {
            name: 'Entitlement fulfillment',
            count: recentOrders.filter(
                (order) => order.fulfillment_state === 'ready',
            ).length,
            href: '/operator#commercial-orders',
            note: 'Explicit owner confirmation required',
        },
        {
            name: 'Catalog reconciliation',
            count: missingCanonicalSlugs.length,
            href: '/operator/products',
            note: 'Missing canonical catalog registrations',
        },
    ].filter((item) => item.count > 0);

    function scrollProducts(distance: number) {
        carousel.current?.scrollBy({
            left: distance,
            behavior: window.matchMedia('(prefers-reduced-motion: reduce)')
                .matches
                ? 'auto'
                : 'smooth',
        });
    }

    useEffect(() => {
        const shortcut = (event: KeyboardEvent) => {
            if (
                (event.ctrlKey || event.metaKey) &&
                event.key.toLowerCase() === 'k'
            ) {
                event.preventDefault();
                setSearchOpen((opened) => !opened);
            }
            if (event.key === 'Escape') setSearchOpen(false);
        };
        window.addEventListener('keydown', shortcut);
        return () => window.removeEventListener('keydown', shortcut);
    }, []);
    useEffect(() => {
        if (searchOpen) input.current?.focus();
    }, [searchOpen]);

    return (
        <div className="kmj-command-os">
            <div className="kmj-os-layout">
                <main
                    className="kmj-os-main"
                    aria-label="Enterprise owner command center"
                >
                    <div className="kmj-os-toolbar">
                        <button
                            type="button"
                            onClick={() => setSearchOpen(true)}
                            className="kmj-os-search"
                            aria-haspopup="dialog"
                            aria-expanded={searchOpen}
                        >
                            <Search
                                className="size-4 shrink-0"
                                aria-hidden="true"
                            />
                            <span className="min-w-0 flex-1 truncate text-left">
                                Find workspaces and catalog products…
                            </span>
                            <kbd>Ctrl K</kbd>
                        </button>
                        <Link
                            href="/operator/ops"
                            className="kmj-os-toolbar-link"
                        >
                            <Activity className="size-4" /> Check system status
                        </Link>
                        <span className="kmj-os-owner">
                            <ShieldCheck className="size-4" /> Platform owner
                        </span>
                    </div>
                    <header className="kmj-os-hero">
                        <img
                            className="kmj-os-hero-image"
                            src="/assets/admin/earth-orbit.svg"
                            alt=""
                            aria-hidden="true"
                            decoding="async"
                        />
                        <div className="kmj-os-hero-text">
                            <span className="kmj-os-eyebrow">
                                KMJ TECHNO · ENTERPRISE CONTROL
                            </span>
                            <h1>
                                Super Admin <span>Command Center</span>
                            </h1>
                            <p>
                                Your complete platform. People, products,
                                commerce, licensing and operations—together in
                                one secure workspace.
                            </p>
                            <div className="mt-5 flex flex-wrap gap-2.5">
                                <a
                                    href="#kmj-os-workspace"
                                    className="kmj-os-primary"
                                >
                                    <Command className="size-4" /> Explore
                                    workspaces <ArrowRight className="size-4" />
                                </a>
                                <Link
                                    href="/operator/products"
                                    className="kmj-os-secondary"
                                >
                                    <Package className="size-4" /> Manage
                                    products
                                </Link>
                            </div>
                        </div>
                        <span className="kmj-os-hero-mark">
                            INNOVATE | BUILD | SCALE
                        </span>
                    </header>
                    <div
                        className="kmj-os-stats"
                        aria-label="Authoritative platform snapshot"
                    >
                        <Stat
                            name="Users"
                            value={metrics.users}
                            caption="Platform records"
                            icon={Users}
                            tone="blue"
                        />
                        <Stat
                            name="Organizations"
                            value={metrics.organizations}
                            caption="Registered organizations"
                            icon={Boxes}
                            tone="cyan"
                        />
                        <Stat
                            name="Orders"
                            value={metrics.orders}
                            caption="Commercial orders"
                            icon={ShoppingCart}
                            tone="red"
                        />
                        <Stat
                            name="Entitlements"
                            value={metrics.entitlements}
                            caption="Granted rights"
                            icon={KeyRound}
                            tone="amber"
                        />
                        <Stat
                            name="Public products"
                            value={
                                catalogProducts.filter((p) => p.is_public)
                                    .length
                            }
                            caption="Catalog visibility"
                            icon={Package}
                            tone="violet"
                        />
                        <Stat
                            name="Confirmed orders"
                            value={metrics.confirmed_orders}
                            caption="Not revenue"
                            icon={CheckCircle2}
                            tone="green"
                        />
                    </div>
                    <section
                        className="kmj-os-section"
                        aria-labelledby="kmj-products-title"
                    >
                        <div className="kmj-os-heading">
                            <div>
                                <h2 id="kmj-products-title">
                                    Product Suite Overview
                                </h2>
                                <p>Real governed KMJ product catalog</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    type="button"
                                    aria-label="Previous products"
                                    onClick={() => scrollProducts(-260)}
                                    className="kmj-os-icon"
                                >
                                    <ChevronLeft className="size-4" />
                                </button>
                                <button
                                    type="button"
                                    aria-label="Next products"
                                    onClick={() => scrollProducts(260)}
                                    className="kmj-os-icon"
                                >
                                    <ChevronRight className="size-4" />
                                </button>
                                <Link
                                    href="/operator/products"
                                    className="kmj-os-link"
                                >
                                    View products{' '}
                                    <ArrowRight className="size-4" />
                                </Link>
                            </div>
                        </div>
                        <div className="kmj-os-product-track" ref={carousel}>
                            {catalogProducts.length === 0 && (
                                <p
                                    role="status"
                                    className="p-5 text-sm text-slate-300"
                                >
                                    No registered products in this catalog
                                    snapshot.
                                </p>
                            )}
                            {catalogProducts.map((product) => (
                                <Link
                                    key={product.id}
                                    href="/operator/products"
                                    className="kmj-os-product"
                                    aria-label={'Manage ' + product.name}
                                >
                                    <div className="kmj-os-product-title">
                                        <Package className="size-4 text-red-400" />
                                        <strong className="truncate">
                                            {product.name}
                                        </strong>
                                    </div>
                                    <div className="kmj-os-product-image">
                                        {images[product.slug] ? (
                                            <img
                                                loading="lazy"
                                                src={images[product.slug]}
                                                alt={
                                                    product.name +
                                                    ' product visual'
                                                }
                                                onError={(event) => {
                                                    event.currentTarget.hidden = true;
                                                }}
                                            />
                                        ) : (
                                            <Boxes className="size-12 text-slate-500" />
                                        )}
                                    </div>
                                    <p className="kmj-os-product-status">
                                        <span>
                                            {product.is_public
                                                ? 'Public listing'
                                                : 'Private listing'}
                                        </span>
                                        <span>
                                            {product.lifecycle ||
                                                product.status}
                                        </span>
                                    </p>
                                    <div className="kmj-os-product-link">
                                        Catalog · Licensing · Settings{' '}
                                        <ArrowRight className="size-3.5" />
                                    </div>
                                </Link>
                            ))}
                        </div>
                    </section>
                    <div id="kmj-os-workspace" className="kmj-os-workspace">
                        <OperatorWorkspaceMap />
                    </div>
                    <div className="kmj-os-insights">
                        <section
                            className="kmj-os-section"
                            aria-labelledby="kmj-review-title"
                        >
                            <div className="kmj-os-heading">
                                <div>
                                    <h2 id="kmj-review-title">
                                        Attention & Review
                                    </h2>
                                    <p>From currently available records</p>
                                </div>
                                <a
                                    href="#commercial-orders"
                                    className="kmj-os-link"
                                >
                                    View orders{' '}
                                    <ArrowRight className="size-4" />
                                </a>
                            </div>
                            {needsReview.length ? (
                                needsReview.map((item) => (
                                    <Link
                                        key={item.name}
                                        href={item.href}
                                        className="kmj-os-attention"
                                    >
                                        <span className="kmj-os-attention-number">
                                            {item.count}
                                        </span>
                                        <span className="min-w-0 flex-1">
                                            <strong>{item.name}</strong>
                                            <small>{item.note}</small>
                                        </span>
                                        <ArrowRight className="size-4 text-slate-400" />
                                    </Link>
                                ))
                            ) : (
                                <p className="p-4 text-sm text-slate-300">
                                    No flagged items in this snapshot; this does
                                    not prove everything is healthy.
                                </p>
                            )}
                        </section>
                        <section
                            className="kmj-os-section"
                            aria-labelledby="kmj-growth-title"
                        >
                            <div className="kmj-os-heading">
                                <div>
                                    <h2 id="kmj-growth-title">
                                        Revenue & Growth
                                    </h2>
                                    <p>Verified reporting only</p>
                                </div>
                            </div>
                            <div className="kmj-os-no-data">
                                <Activity className="size-8 text-slate-500" />
                                <strong>Analytics not connected</strong>
                                <p>
                                    No invented revenue, trends, or growth
                                    percentages.
                                </p>
                                <Link
                                    href="/operator/payments"
                                    className="kmj-os-link"
                                >
                                    Payment settings{' '}
                                    <ArrowRight className="size-4" />
                                </Link>
                            </div>
                        </section>
                        <section
                            className="kmj-os-section"
                            aria-labelledby="kmj-health-title"
                        >
                            <div className="kmj-os-heading">
                                <div>
                                    <h2 id="kmj-health-title">System Health</h2>
                                    <p>Evidence from Operations</p>
                                </div>
                                <Link
                                    href="/operator/ops"
                                    className="kmj-os-link"
                                >
                                    Details <ArrowRight className="size-4" />
                                </Link>
                            </div>
                            {[
                                'Application & deployment',
                                'Database & queues',
                                'Backups',
                                'Security & audit',
                            ].map((label) => (
                                <Link
                                    key={label}
                                    href="/operator/ops"
                                    className="kmj-os-health"
                                >
                                    <ShieldCheck className="size-4 text-slate-400" />
                                    <span>{label}</span>
                                    <span className="text-amber-200">
                                        Check
                                    </span>
                                </Link>
                            ))}
                        </section>
                    </div>
                    <p className="kmj-os-footnote">
                        All figures above are backend records or clearly marked
                        unavailable—not estimated revenue, live device
                        heartbeats or uptime.
                    </p>
                </main>
                <KristiOwnerAssistant
                    counts={{
                        orders: metrics.orders,
                        customers: metrics.users,
                        products: catalogProducts.length,
                    }}
                />
            </div>
            <Dialog open={searchOpen} onOpenChange={setSearchOpen}>
                <DialogContent className="kmj-os-modal max-w-[min(550px,calc(100vw-32px))] gap-0 overflow-hidden border-[#466078] bg-[#101725] p-0 text-white">
                    <div className="border-b border-white/10 px-5 py-4">
                        <DialogTitle className="text-base font-bold">
                            Find a workspace or product
                        </DialogTitle>
                        <DialogDescription className="mt-1 text-xs text-slate-400">
                            Search workspaces and loaded catalog products. Press
                            Escape to close.
                        </DialogDescription>
                    </div>
                    <label className="flex items-center gap-3 px-4 py-3">
                        <Search
                            className="size-4 shrink-0 text-slate-400"
                            aria-hidden="true"
                        />
                        <input
                            ref={input}
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                            aria-label="Search owner workspaces and catalog products"
                            placeholder="Workspaces or catalog products…"
                            className="w-full bg-transparent py-2 text-sm text-white outline-none"
                        />
                    </label>
                    <nav
                        className="max-h-72 overflow-y-auto border-t border-white/10 p-2"
                        aria-label="Search results"
                    >
                        {results.map((result) => (
                            <Link
                                key={result.key}
                                href={result.href}
                                onClick={() => setSearchOpen(false)}
                                className="flex min-h-11 items-center justify-between rounded-lg px-3 text-sm hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500"
                            >
                                <span className="min-w-0 flex-1">
                                    <span className="block truncate">
                                        {result.label}
                                    </span>
                                    <span className="block text-[11px] text-slate-400">
                                        {result.category}
                                    </span>
                                </span>
                                <ArrowRight
                                    className="size-4"
                                    aria-hidden="true"
                                />
                            </Link>
                        ))}
                        {!results.length && (
                            <p
                                role="status"
                                className="p-4 text-sm text-slate-400"
                            >
                                No matching workspace or loaded catalog product
                            </p>
                        )}
                    </nav>
                </DialogContent>
            </Dialog>
        </div>
    );
}
