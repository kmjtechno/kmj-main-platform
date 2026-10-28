import { Link, usePage } from '@inertiajs/react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
    Activity,
    Bell,
    Boxes,
    ChartNoAxesCombined,
    ChevronRight,
    Cloud,
    Code2,
    CreditCard,
    Database,
    FileText,
    Gauge,
    Globe2,
    Home,
    KeyRound,
    Mail,
    Menu,
    Package,
    Search,
    Settings,
    ShieldCheck,
    ShoppingCart,
    Users,
    Zap,
    type LucideIcon,
} from 'lucide-react';
import LockedBrand from '@/components/locked-brand';
import '../../css/owner-lock.css';
import '../../css/owner-module-shell.css';

type Workspace = {
    label: string;
    href: string;
    icon: LucideIcon;
};

// The owner subpages reuse the visual vocabulary of /operator, without
// changing customer pages, authorization, product rights or data fetching.
const groups: { title: string; items: Workspace[] }[] = [
    {
        title: 'BUSINESS',
        items: [
            {
                label: 'Products & Catalog',
                href: '/operator/products',
                icon: Package,
            },
            {
                label: 'Customers & Orgs',
                href: '/operator/directory',
                icon: Users,
            },
            {
                label: 'Orders & Payments',
                href: '/operator#commercial-orders',
                icon: ShoppingCart,
            },
            {
                label: 'Payment Gateways',
                href: '/operator/payments',
                icon: CreditCard,
            },
            {
                label: 'Licensing & Entitlements',
                href: '/operator/kslp',
                icon: KeyRound,
            },
            {
                label: 'Subscriptions & Plans',
                href: '/operator/kslp',
                icon: FileText,
            },
            {
                label: 'Revenue & Analytics',
                href: '/operator#owner-revenue',
                icon: ChartNoAxesCombined,
            },
        ],
    },
    {
        title: 'PLATFORM',
        items: [
            {
                label: 'Developer Apps & Keys',
                href: '/developer/apps',
                icon: Code2,
            },
            {
                label: 'CodeBridge & Devices',
                href: '/operator/codebridge/owner-plan',
                icon: Boxes,
            },
            { label: 'ModelFabric & AI', href: '/operator/ops', icon: Gauge },
            {
                label: 'CloudOS & Infrastructure',
                href: '/operator/ops',
                icon: Cloud,
            },
            {
                label: 'OmniDesk Remote Access',
                href: '/operator/products',
                icon: Globe2,
            },
            {
                label: 'CineCore & Calibration',
                href: '/operator/products',
                icon: Gauge,
            },
            {
                label: 'Content & Website',
                href: '/operator/products',
                icon: FileText,
            },
            {
                label: 'Communication (Mail/SMS)',
                href: '/operator/ops',
                icon: Mail,
            },
        ],
    },
    {
        title: 'OPERATIONS',
        items: [
            { label: 'System Health', href: '/operator/ops', icon: Activity },
            {
                label: 'Backups & Restore',
                href: '/operator/ops',
                icon: Database,
            },
            {
                label: 'Security & Access',
                href: '/settings/security',
                icon: ShieldCheck,
            },
            { label: 'Audit Logs', href: '/operator/ops', icon: FileText },
            { label: 'Monitoring & Alerts', href: '/operator/ops', icon: Bell },
            { label: 'Task Automation', href: '/operator/ops', icon: Zap },
            {
                label: 'Settings & Configuration',
                href: '/operator/ops',
                icon: Settings,
            },
        ],
    },
];

export default function OwnerModuleShell({
    children,
}: {
    children: ReactNode;
}) {
    const { auth } = usePage().props;
    const url = usePage().url.split('?')[0];
    const name = auth.user?.name?.trim() || 'Platform Owner';
    const parts = name.split(/\s+/);
    const initials = (
        (parts[0]?.[0] ?? '') + (parts.at(-1)?.[0] ?? '')
    ).toLocaleUpperCase();
    const [navOpen, setNavOpen] = useState(false);
    const menuButton = useRef<HTMLButtonElement>(null);

    useEffect(() => {
        if (!navOpen) return;

        const closeOnEscape = (event: KeyboardEvent) => {
            if (event.key !== 'Escape') return;
            setNavOpen(false);
            menuButton.current?.focus();
        };
        window.addEventListener('keydown', closeOnEscape);
        return () => window.removeEventListener('keydown', closeOnEscape);
    }, [navOpen]);

    return (
        <div className="owner-lock owner-module-shell">
            <a className="owner-skip" href="#owner-main">
                Skip to owner module
            </a>
            <header className="owner-header">
                <Link
                    href="/"
                    className="owner-brand"
                    aria-label="KMJ TECHNO home"
                >
                    <LockedBrand compact />
                </Link>
                <button
                    ref={menuButton}
                    type="button"
                    className="owner-mobile-nav"
                    aria-label={
                        navOpen
                            ? 'Close owner navigation'
                            : 'Open owner navigation'
                    }
                    aria-controls="owner-module-navigation"
                    aria-expanded={navOpen}
                    onClick={() => setNavOpen((open) => !open)}
                >
                    <Menu aria-hidden="true" />
                </button>
                <Link
                    href="/operator"
                    className="owner-search"
                    aria-label="Open Command Center search"
                >
                    <Search size={17} aria-hidden="true" />
                    <span>Search in Command Center</span>
                </Link>
                <Link
                    href="/operator/ops"
                    className="owner-status"
                    aria-current={url === '/operator/ops' ? 'page' : undefined}
                >
                    <span />
                    System Status
                </Link>
                <div className="owner-identity">
                    <span className="owner-initials">{initials}</span>
                    <div>
                        <strong>{name}</strong>
                        <small>Platform Owner / Super Admin</small>
                    </div>
                    <ChevronRight size={13} aria-hidden="true" />
                </div>
            </header>
            <aside
                id="owner-module-navigation"
                className={'owner-sidebar ' + (navOpen ? 'is-open' : '')}
                aria-label="Owner navigation"
            >
                <Link href="/operator" onClick={() => setNavOpen(false)}>
                    <Home size={17} aria-hidden="true" />
                    Dashboard
                </Link>
                <Link href="/operator" onClick={() => setNavOpen(false)}>
                    <Gauge size={17} aria-hidden="true" />
                    Command Center
                    <ChevronRight size={12} aria-hidden="true" />
                </Link>
                {groups.map((group) => (
                    <nav key={group.title} aria-label={group.title}>
                        <h2>{group.title}</h2>
                        {group.items.map(({ label, href, icon: Icon }) => (
                            <Link
                                key={label}
                                href={href}
                                aria-current={
                                    href === url &&
                                    (href === '/operator/ops'
                                        ? label === 'System Health'
                                        : href === '/operator/products'
                                          ? label === 'Products & Catalog'
                                          : href === '/operator/kslp'
                                            ? label ===
                                              'Licensing & Entitlements'
                                            : true)
                                        ? 'page'
                                        : undefined
                                }
                                onClick={() => setNavOpen(false)}
                            >
                                <Icon size={17} aria-hidden="true" />
                                {label}
                            </Link>
                        ))}
                    </nav>
                ))}
                <Link
                    href="/operator#owner-kristi"
                    className="owner-sidebar-kristi"
                    onClick={() => setNavOpen(false)}
                >
                    <img src="/assets/locked/kristi-owner.webp" alt="" />
                    <div>
                        <strong>Kristi AI Assistant</strong>
                        <small>Open guided assistant</small>
                        <em>Guided mode</em>
                    </div>
                </Link>
            </aside>
            <div className="owner-body owner-module-body">
                <main id="owner-main" className="owner-main owner-module-main">
                    <div className="owner-module-content">{children}</div>
                </main>
            </div>
        </div>
    );
}
