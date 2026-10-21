import { Link, usePage } from '@inertiajs/react';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
    Activity,
    ArrowRight,
    Bell,
    Boxes,
    ChartNoAxesCombined,
    ChevronRight,
    Cloud,
    Code2,
    CreditCard,
    Crown,
    Database,
    FileText,
    Gauge,
    Globe2,
    Home,
    KeyRound,
    Mail,
    Menu,
    Package,
    Plus,
    Search,
    Settings,
    ShieldCheck,
    ShoppingCart,
    Users,
    Zap,
} from 'lucide-react';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogTitle,
} from '@/components/ui/dialog';
import LockedBrand from '@/components/locked-brand';
import ProductArtwork from '@/components/product-artwork';
import KristiOwnerAssistant from '@/components/kristi-owner-assistant';
import '../../css/owner-lock.css';

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
type Order = {
    id: string;
    status: string;
    fulfillment_state: string;
    currency?: string | null;
    amount_minor?: number | null;
    created_at?: string | null;
    product_id?: string;
};
type Props = {
    metrics: {
        users: number;
        organizations: number;
        entitlements: number;
        orders: number;
        confirmed_orders: number;
        confirmed_inr_revenue_minor: number;
    };
    catalogProducts: Product[];
    recentOrders: Order[];
    missingCanonicalSlugs: string[];
};
const art: Record<string, string> = {
    'kmj-cloudos': 'cloudos',
    'kmj-codebridge': 'codebridge',
    'kmj-omnidesk': 'omnidesk',
    'kmj-calibration-pro': 'calibration',
    'kmj-cinema-platform': 'cinema',
    'kmj-motiondirector': 'motion',
    'kmj-cloud-nexus': 'nexus',
    'kmj-forge': 'forge',
    'kmj-agent': 'agent',
    'kmj-creative-studio': 'studio',
    'kmj-licensing-hub': 'licensing',
};
const groups = [
    {
        title: 'BUSINESS',
        items: [
            ['Products & Catalog', '/operator/products', Package],
            ['Customers & Orgs', '/operator/directory', Users],
            ['Orders & Payments', '/super-admin#commercial-orders', ShoppingCart],
            ['Licensing & Entitlements', '/operator/kslp', KeyRound],
            ['Subscriptions & Plans', '/operator/kslp', FileText],
            ['Revenue & Analytics', '#owner-revenue', ChartNoAxesCombined],
        ],
    },
    {
        title: 'PLATFORM',
        items: [
            ['Developer Apps & Keys', '/developer/apps', Code2],
            ['CodeBridge & Devices', '/operator/codebridge/owner-plan', Boxes],
            ['ModelFabric & AI', '/operator/ops', Gauge],
            ['CloudOS & Infrastructure', '/operator/ops', Cloud],
            ['OmniDesk Remote Access', '/operator/products', Globe2],
            ['CineCore & Calibration', '/operator/products', Gauge],
            ['Content & Website', '/operator/products', FileText],
            ['Communication (Mail/SMS)', '/operator/ops', Mail],
        ],
    },
    {
        title: 'OPERATIONS',
        items: [
            ['System Health', '/operator/ops', Activity],
            ['Backups & Restore', '/operator/ops', Database],
            ['Security & Access', '/settings/security', ShieldCheck],
            ['Audit Logs', '/operator/ops', FileText],
            ['Monitoring & Alerts', '/operator/ops', Bell],
            ['Task Automation', '/operator/ops', Zap],
            ['Settings & Configuration', '/operator/ops', Settings],
        ],
    },
];
const quick = [
    ['Add Product', '/operator/products', Plus],
    ['Add Customer', '/operator/directory', Users],
    ['Manage Orders', '#commercial-orders', ShoppingCart],
    ['Issue License', '/operator/kslp', KeyRound],
    ['Payment Settings', '/operator/payments', CreditCard],
    ['View Analytics', '#owner-revenue', ChartNoAxesCombined],
    ['Manage Content', '/operator/products', FileText],
    ['Contact Support', '/products/kmj-codebridge/support', Mail],
    ['System Settings', '/operator/ops', Settings],
    ['Backup Status', '/operator/ops', Database],
];
function PanelTitle({
    title,
    href,
    label = 'View All',
}: {
    title: string;
    href?: string;
    label?: string;
}) {
    return (
        <div className="owner-panel-title">
            <h2>
                <Activity size={17} />
                {title}
            </h2>
            {href && (
                <Link href={href}>
                    {label}
                    <ChevronRight size={13} />
                </Link>
            )}
        </div>
    );
}
export default function OperatorCommandOs({
    metrics,
    catalogProducts,
    recentOrders,
    missingCanonicalSlugs,
}: Props) {
    const { auth } = usePage().props;
    const name = auth.user?.name?.trim() || 'Platform Owner';
    const nameParts = name.split(/\s+/);
    const initials = (
        (nameParts[0]?.[0] ?? '') + (nameParts.at(-1)?.[0] ?? '')
    ).toLocaleUpperCase();
    const [searchOpen, setSearchOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [navOpen, setNavOpen] = useState(false);
    const track = useRef<HTMLDivElement>(null);
    useEffect(() => {
        const listener = (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                setSearchOpen((v) => !v);
            }
            if (e.key === 'Escape') {
                setSearchOpen(false);
                setNavOpen(false);
            }
        };
        window.addEventListener('keydown', listener);
        return () => window.removeEventListener('keydown', listener);
    }, []);
    function scrollProducts(distance: number) {
        track.current?.scrollBy({
            left: distance,
            behavior: window.matchMedia('(prefers-reduced-motion: reduce)')
                .matches
                ? 'auto'
                : 'smooth',
        });
    }
    const results = useMemo(() => {
        const needle = query.toLowerCase();
        const workspaces = groups
            .flatMap((g) => g.items)
            .filter(([label]) => String(label).toLowerCase().includes(needle))
            .map(([label, href]) => ({
                label: String(label),
                href: String(href),
                category: 'Workspace',
            }));
        const products = catalogProducts
            .filter((product) =>
                (product.name + ' ' + product.slug)
                    .toLowerCase()
                    .includes(needle),
            )
            .map((product) => ({
                label: product.name,
                href: '/operator/products',
                category: 'Catalog product',
            }));
        return [...workspaces, ...products].slice(0, 20);
    }, [query, catalogProducts]);
    const confirmed = recentOrders.filter(
        (o) =>
            o.status === 'confirmed' &&
            o.currency === 'INR' &&
            typeof o.amount_minor === 'number',
    );
    // The KPI uses the backend's complete confirmed-INR aggregate; the
    // 20-row recentOrders collection below is only a chart preview.
    const revenue = metrics.confirmed_inr_revenue_minor / 100;
    const revenueByDay = useMemo(() => {
        const map = new Map<string, number>();
        for (const o of confirmed) {
            if (!o.created_at) continue;
            const d = o.created_at.slice(0, 10);
            map.set(d, (map.get(d) || 0) + (o.amount_minor || 0) / 100);
        }
        return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
    }, [confirmed]);
    const max = Math.max(1, ...revenueByDay.map(([, v]) => v));
    const points = revenueByDay
        .map(
            ([, v], i) =>
                `${25 + (i * 365) / Math.max(1, revenueByDay.length - 1)},${145 - (v / max) * 120}`,
        )
        .join(' ');
    return (
        <div className="owner-lock">
            <a className="owner-skip" href="#owner-main">
                Skip to dashboard
            </a>
            <header className="owner-header">
                <Link href="/" className="owner-brand">
                    <LockedBrand compact />
                </Link>
                <button
                    className="owner-mobile-nav"
                    aria-label="Toggle owner navigation"
                    aria-expanded={navOpen}
                    onClick={() => setNavOpen(!navOpen)}
                >
                    <Menu />
                </button>
                <button
                    className="owner-search"
                    onClick={() => setSearchOpen(true)}
                >
                    <Search size={17} />
                    <span>Search anything… (Ctrl + K)</span>
                </button>
                <Link href="/operator/ops" className="owner-status">
                    <span />
                    System Status
                </Link>
                <div className="owner-identity">
                    <span className="owner-initials">{initials}</span>
                    <div>
                        <strong>{name}</strong>
                        <small>Platform Owner / Super Admin</small>
                    </div>
                    <ChevronRight size={13} />
                </div>
            </header>
            <aside
                className={'owner-sidebar ' + (navOpen ? 'is-open' : '')}
                aria-label="Owner navigation"
            >
                <Link href="/super-admin" className="owner-nav-active">
                    <Home size={17} />
                    Dashboard
                </Link>
                <button onClick={() => setSearchOpen(true)}>
                    <Gauge size={17} />
                    Command Center
                    <ChevronRight size={12} />
                </button>
                {groups.map((group) => (
                    <nav key={group.title} aria-label={group.title}>
                        <h2>{group.title}</h2>
                        {group.items.map(([label, href, Icon]) => {
                            const I = Icon as typeof Home;
                            return (
                                <Link
                                    key={String(label)}
                                    href={String(href)}
                                    onClick={() => setNavOpen(false)}
                                >
                                    <I size={17} />
                                    {String(label)}
                                </Link>
                            );
                        })}
                    </nav>
                ))}
                <a href="#owner-kristi" className="owner-sidebar-kristi">
                    <img src="/assets/locked/kristi-owner.webp" alt="" />
                    <div>
                        <strong>Kristi AI Assistant</strong>
                        <small>Your Intelligent Copilot</small>
                        <em>Guided mode</em>
                    </div>
                </a>
            </aside>
            <div className="owner-body">
                <main id="owner-main" className="owner-main">
                    <section className="owner-hero">
                        <img src="/assets/locked/owner-earth.webp" alt="" />
                        <div>
                            <p>Good Evening,</p>
                            <h1>
                                {name} <Crown size={25} />
                            </h1>
                            <h2>
                                Super Admin • KMJ TECHNO Enterprise Command OS
                            </h2>
                            <p className="owner-hero-description">
                                Manage your products, customers, licensing,
                                payments, infrastructure and everything
                                <br /> from a single intelligent platform.
                            </p>
                            <div className="owner-hero-actions">
                                <a
                                    href="#owner-quick"
                                    className="owner-primary"
                                >
                                    <Zap size={16} />
                                    Quick Actions
                                    <ChevronRight size={16} />
                                </a>
                                <button onClick={() => setSearchOpen(true)}>
                                    <Boxes size={16} />
                                    Explore Workspaces
                                </button>
                            </div>
                        </div>
                        <aside>
                            <strong>
                                <b>KMJ</b> TECHNO
                            </strong>
                            <p>
                                Global Innovation Platform
                                <br />
                                for a Smarter Tomorrow
                            </p>
                            <div>
                                <span>
                                    <b>{catalogProducts.length}</b>Products
                                </span>
                                <span>
                                    <b>Global</b>Platform
                                </span>
                                <span>
                                    <b>AI Powered</b>Vision
                                </span>
                            </div>
                        </aside>
                    </section>
                    <section
                        className="owner-stats"
                        aria-label="Authoritative platform snapshot"
                    >
                        {[
                            [
                                CreditCard,
                                'Recorded Revenue',
                                metrics.confirmed_orders
                                    ? '₹ ' + revenue.toLocaleString('en-IN')
                                    : '—',
                                'All confirmed INR orders',
                                'cyan',
                            ],
                            [
                                Users,
                                'Total Customers',
                                metrics.users.toLocaleString('en-IN'),
                                'Platform user records',
                                'purple',
                            ],
                            [
                                KeyRound,
                                'Entitlements',
                                metrics.entitlements.toLocaleString('en-IN'),
                                'Granted access rights',
                                'amber',
                            ],
                            [
                                Package,
                                'Public Products',
                                catalogProducts.filter((p) => p.is_public)
                                    .length +
                                    ' / ' +
                                    catalogProducts.length,
                                'Public catalog visibility',
                                'green',
                            ],
                            [
                                ShieldCheck,
                                'System Health',
                                'Not verified',
                                'Open system checks',
                                'green',
                            ],
                        ].map(([Icon, label, value, caption, tone]) => {
                            const I = Icon as typeof Home;
                            return (
                                <article
                                    key={String(label)}
                                    className={'owner-stat ' + tone}
                                >
                                    <span>
                                        <I size={22} />
                                    </span>
                                    <div>
                                        <h2>{String(label)}</h2>
                                        <strong>{String(value)}</strong>
                                        <p>{String(caption)}</p>
                                    </div>
                                </article>
                            );
                        })}
                    </section>
                    <section className="owner-panel owner-suite">
                        <PanelTitle
                            title="Product Suite Overview"
                            href="/operator/products"
                            label="View All Products"
                        />
                        <p className="owner-panel-subtitle">
                            Manage all KMJ products and services
                        </p>
                        <div className="owner-product-track" ref={track}>
                            {catalogProducts.map((p) => (
                                <article key={p.id} className="owner-product">
                                    <h3>
                                        <Package size={16} />
                                        {p.name}
                                    </h3>
                                    <p>
                                        {p.slug
                                            .replace('kmj-', '')
                                            .replaceAll('-', ' ')}
                                    </p>
                                    <Link href="/operator/products">
                                        <ProductArtwork
                                            src={
                                                art[p.slug]
                                                    ? '/assets/locked/' +
                                                      art[p.slug] +
                                                      '.webp'
                                                    : null
                                            }
                                            name={p.name}
                                            fallbackClassName="owner-product-art-unavailable"
                                            fallbackText="Artwork pending"
                                        />
                                    </Link>
                                    <div className="owner-product-state">
                                        <span>
                                            {p.is_public
                                                ? '● Public'
                                                : 'Private'}
                                        </span>
                                        <small>{p.lifecycle || p.status}</small>
                                    </div>
                                    <div className="owner-product-actions">
                                        <Link href="/operator/kslp">
                                            <KeyRound size={14} />
                                            Licensing
                                        </Link>
                                        <Link href="/operator/products">
                                            <ChartNoAxesCombined size={14} />
                                            Catalog
                                        </Link>
                                        <Link href="/operator/products">
                                            <Settings size={14} />
                                            Settings
                                        </Link>
                                    </div>
                                </article>
                            ))}
                        </div>
                        <button
                            className="owner-track-next"
                            aria-label="Next products"
                            onClick={() => scrollProducts(260)}
                        >
                            <ChevronRight size={18} />
                        </button>
                        <button
                            className="owner-track-previous"
                            aria-label="Previous products"
                            onClick={() => scrollProducts(-260)}
                        >
                            <ChevronRight size={18} />
                        </button>
                        {!catalogProducts.length && (
                            <p className="owner-empty">
                                No products in this catalog snapshot.
                            </p>
                        )}
                    </section>
                    <div className="owner-middle">
                        <section id="owner-revenue" className="owner-panel">
                            <PanelTitle title="Revenue & Growth" />
                            <p className="owner-panel-subtitle">
                                Last 20 orders, confirmed INR only
                            </p>
                            <div className="owner-chart">
                                <svg
                                    viewBox="0 0 420 180"
                                    role="img"
                                    aria-label={
                                        confirmed.length
                                            ? 'Recent confirmed INR order revenue by date'
                                            : 'No confirmed INR revenue to chart'
                                    }
                                >
                                    <defs>
                                        <linearGradient
                                            id="revenueFill"
                                            x2="0"
                                            y2="1"
                                        >
                                            <stop
                                                stopColor="#ec1238"
                                                stopOpacity=".45"
                                            />
                                            <stop
                                                offset="1"
                                                stopColor="#ec1238"
                                                stopOpacity="0"
                                            />
                                        </linearGradient>
                                    </defs>
                                    {[25, 65, 105, 145].map((y) => (
                                        <line
                                            key={y}
                                            x1="25"
                                            x2="400"
                                            y1={y}
                                            y2={y}
                                            stroke="#29323b"
                                        />
                                    ))}
                                    {[25, 100, 175, 250, 325, 400].map((x) => (
                                        <line
                                            key={x}
                                            x1={x}
                                            x2={x}
                                            y1="25"
                                            y2="145"
                                            stroke="#202930"
                                        />
                                    ))}
                                    {revenueByDay.length > 1 && (
                                        <>
                                            <polygon
                                                points={
                                                    '25,145 ' +
                                                    points +
                                                    ' 390,145'
                                                }
                                                fill="url(#revenueFill)"
                                            />
                                            <polyline
                                                points={points}
                                                stroke="#ff123e"
                                                strokeWidth="2"
                                                fill="none"
                                            />
                                        </>
                                    )}
                                    {revenueByDay.map(([day, v], i) => (
                                        <circle
                                            key={day}
                                            cx={
                                                25 +
                                                (i * 365) /
                                                    Math.max(
                                                        1,
                                                        revenueByDay.length - 1,
                                                    )
                                            }
                                            cy={145 - (v / max) * 120}
                                            r="3"
                                            fill="#ff3154"
                                        />
                                    ))}
                                    <text
                                        x="25"
                                        y="170"
                                        fill="#aab6c6"
                                        fontSize="10"
                                    >
                                        {revenueByDay[0]?.[0] ||
                                            'No confirmed orders'}
                                    </text>
                                    <text
                                        x="400"
                                        y="170"
                                        fill="#aab6c6"
                                        fontSize="10"
                                        textAnchor="end"
                                    >
                                        {revenueByDay.at(-1)?.[0] || ''}
                                    </text>
                                </svg>
                            </div>
                        </section>
                        <section className="owner-panel">
                            <PanelTitle
                                title="Recent Orders"
                                href="#commercial-orders"
                            />
                            {recentOrders.slice(0, 4).map((o) => (
                                <Link
                                    className="owner-order"
                                    key={o.id}
                                    href="#commercial-orders"
                                >
                                    <ShoppingCart size={19} />
                                    <span>
                                        <strong>{o.id}</strong>
                                        <small>
                                            {catalogProducts.find(
                                                (p) => p.id === o.product_id,
                                            )?.name || 'Commercial order'}
                                        </small>
                                    </span>
                                    <div>
                                        <strong>
                                            {o.amount_minor != null &&
                                            o.currency
                                                ? o.currency +
                                                  ' ' +
                                                  (
                                                      o.amount_minor / 100
                                                  ).toLocaleString('en-IN')
                                                : '—'}
                                        </strong>
                                        <small>
                                            {o.created_at?.slice(0, 10) ||
                                                'Date unavailable'}
                                        </small>
                                    </div>
                                    <em
                                        className={
                                            o.status === 'confirmed'
                                                ? 'confirmed'
                                                : ''
                                        }
                                    >
                                        {o.status}
                                    </em>
                                </Link>
                            ))}
                            {!recentOrders.length && (
                                <p className="owner-empty">
                                    No commercial orders yet.
                                </p>
                            )}
                        </section>
                        <section className="owner-panel">
                            <PanelTitle
                                title="System Health"
                                href="/operator/ops"
                                label="Details"
                            />
                            <p className="owner-panel-subtitle">
                                Live checks require operational evidence
                            </p>
                            {[
                                'Website & API',
                                'Database (PostgreSQL)',
                                'Queue Workers',
                                'CodeBridge Gateway',
                                'Mail Service',
                                'Payment Gateways',
                                'Backup System',
                            ].map((label) => (
                                <Link
                                    href="/operator/ops"
                                    className="owner-health"
                                    key={label}
                                >
                                    <span />
                                    {label}
                                    <small>Not verified</small>
                                </Link>
                            ))}
                        </section>
                    </div>
                    <div className="owner-bottom">
                        <section className="owner-panel">
                            <PanelTitle
                                title="Recent Platform Activity"
                                href="/operator/ops"
                                label="View All Activity"
                            />
                            <div className="owner-activity">
                                <Link href="#commercial-orders">
                                    <ShoppingCart />
                                    <span>
                                        <strong>
                                            {metrics.orders} commercial orders
                                        </strong>
                                        <small>
                                            {metrics.confirmed_orders} confirmed
                                            orders
                                        </small>
                                    </span>
                                </Link>
                                <Link href="/operator/products">
                                    <Package />
                                    <span>
                                        <strong>
                                            {catalogProducts.length} catalog
                                            products
                                        </strong>
                                        <small>
                                            {missingCanonicalSlugs.length
                                                ? missingCanonicalSlugs.length +
                                                  ' catalog entries need review'
                                                : 'Catalog snapshot loaded'}
                                        </small>
                                    </span>
                                </Link>
                                <Link href="/operator/directory">
                                    <Users />
                                    <span>
                                        <strong>
                                            {metrics.users} registered users
                                        </strong>
                                        <small>
                                            {metrics.organizations}{' '}
                                            organizations
                                        </small>
                                    </span>
                                </Link>
                                <Link href="/operator/kslp">
                                    <KeyRound />
                                    <span>
                                        <strong>
                                            {metrics.entitlements} entitlements
                                        </strong>
                                        <small>Governed platform access</small>
                                    </span>
                                </Link>
                            </div>
                        </section>
                        <section id="owner-quick" className="owner-panel">
                            <PanelTitle title="Quick Tools & Actions" />
                            <div className="owner-quick">
                                {quick.map(([label, href, Icon]) => {
                                    const I = Icon as typeof Home;
                                    return (
                                        <Link
                                            href={String(href)}
                                            key={String(label)}
                                        >
                                            <I size={19} />
                                            {String(label)}
                                        </Link>
                                    );
                                })}
                            </div>
                        </section>
                    </div>
                </main>
                <div id="owner-kristi" className="owner-assistant">
                    <KristiOwnerAssistant
                        counts={{
                            orders: metrics.orders,
                            customers: metrics.users,
                            products: catalogProducts.length,
                        }}
                    />
                </div>
            </div>
            <Dialog open={searchOpen} onOpenChange={setSearchOpen}>
                <DialogContent className="border-red-900 bg-[#0b1119] text-white">
                    <DialogTitle>Find a workspace or product</DialogTitle>
                    <DialogDescription>
                        Search your platform workspaces. Escape closes this
                        window.
                    </DialogDescription>
                    <input
                        autoFocus
                        aria-label="Search owner workspaces and catalog products"
                        className="rounded-lg border border-white/20 p-3"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Search anything…"
                    />
                    <nav className="grid max-h-80 overflow-auto">
                        {results.map(({ label, href, category }) => (
                            <Link
                                key={String(label)}
                                href={String(href)}
                                className="rounded p-3 hover:bg-white/10"
                                onClick={() => setSearchOpen(false)}
                            >
                                {String(label)} <small>{category}</small>
                                <ArrowRight className="float-right" size={14} />
                            </Link>
                        ))}
                        {!results.length && <p>No matching workspaces.</p>}
                    </nav>
                </DialogContent>
            </Dialog>
        </div>
    );
}
