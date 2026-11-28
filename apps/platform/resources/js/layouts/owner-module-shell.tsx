import { Link, usePage } from '@inertiajs/react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
    Activity,
    Bell,
    Boxes,
    ChartNoAxesCombined,
    ChevronRight,
    Cloud,
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
    Rocket,
    Search,
    HelpCircle,
    Sparkles,
    Settings,
    ShieldCheck,
    ShoppingCart,
    Users,
    Zap,
    type LucideIcon,
} from 'lucide-react';
import LockedBrand from '@/components/locked-brand';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { UserMenuContent } from '@/components/user-menu-content';
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
                label: 'Website & Team',
                href: '/operator/website',
                icon: Globe2,
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
                label: 'KMJ Licensing Hub',
                href: '/operator/kslp',
                icon: KeyRound,
            },
            {
                label: 'Revenue & Analytics',
                href: '/super-admin#owner-revenue',
                icon: ChartNoAxesCombined,
            },
        ],
    },
    {
        title: 'PLATFORM',
        items: [
            {
                label: 'CodeBridge & Devices',
                href: '/services/kmj-codebridge#codebridge-device-control',
                icon: Boxes,
            },
            {
                label: 'ModelFabric & AI',
                href: '/operator/modelfabric',
                icon: Gauge,
            },
            {
                label: 'CloudOS & Infrastructure',
                href: '/operator/ops',
                icon: Cloud,
            },
            {
                label: 'OmniDesk Remote Access',
                href: '/operator/products?product=kmj-omnidesk',
                icon: Globe2,
            },
            {
                label: 'CineCore & Calibration',
                href: '/operator/products?product=kmj-cinema-platform',
                icon: Gauge,
            },
            {
                label: 'Content & Website',
                href: '/operator/products',
                icon: FileText,
            },
            {
                label: 'Communication (Mail)',
                href: '/operator/mail',
                icon: Mail,
            },
        ],
    },
    {
        title: 'OPERATIONS',
        items: [
            {
                label: 'System Health',
                href: '/operator/ops#owner-readiness',
                icon: Activity,
            },
            {
                label: 'Backups & Restore',
                href: '/operator/ops#owner-backup-freshness',
                icon: Database,
            },
            {
                label: 'Security & Access',
                href: '/settings/security',
                icon: ShieldCheck,
            },
            {
                label: 'Audit Logs',
                href: '/operator/ops#owner-action-audit',
                icon: FileText,
            },
            {
                label: 'Monitoring & Alerts',
                href: '/operator/ops#owner-guardrail-signals',
                icon: Bell,
            },
            { label: 'Task Automation', href: '/operator/ops', icon: Zap },
            {
                label: 'Release Center',
                href: '/operator/release-center',
                icon: Rocket,
            },
            {
                label: 'Settings & Configuration',
                href: '/settings/profile',
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
    const pageUrl = usePage().url;
    const url = pageUrl.split('?')[0];
    const isMailPage = url === '/operator/mail';
    const [mailSearch, setMailSearch] = useState(
        new URLSearchParams(pageUrl.split('?')[1] ?? '').get('q') ?? '',
    );
    const searchRef = useRef<HTMLInputElement>(null);
    const name = auth.user?.name?.trim() || 'Platform Owner';
    const parts = name.split(/\s+/);
    const initials = (
        (parts[0]?.[0] ?? '') + (parts.at(-1)?.[0] ?? '')
    ).toLocaleUpperCase();
    const [navOpen, setNavOpen] = useState(false);
    const [activeHash, setActiveHash] = useState('');
    const menuButton = useRef<HTMLButtonElement>(null);

    useEffect(() => {
        const syncHash = () => setActiveHash(window.location.hash);
        syncHash();
        window.addEventListener('hashchange', syncHash);
        return () => window.removeEventListener('hashchange', syncHash);
    }, [url]);

    useEffect(() => {
        if (!isMailPage) return;
        const shortcut = (event: KeyboardEvent) => {
            if (
                (event.ctrlKey || event.metaKey) &&
                event.key.toLowerCase() === 'k'
            ) {
                event.preventDefault();
                searchRef.current?.focus();
            }
            if (
                event.key === 'Escape' &&
                document.activeElement === searchRef.current
            ) {
                searchRef.current?.blur();
            }
        };
        window.addEventListener('keydown', shortcut);
        return () => window.removeEventListener('keydown', shortcut);
    }, [isMailPage]);

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
        <div
            className="owner-lock owner-module-shell kmj-panel dark"
            data-owner-design="command-center-v1"
            data-owner-mail={isMailPage ? 'true' : undefined}
        >
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
                {isMailPage ? (
                    <>
                        <form
                            action="/operator/mail"
                            method="get"
                            role="search"
                            className="owner-mail-global-search"
                        >
                            <Search size={18} aria-hidden="true" />
                            <input
                                ref={searchRef}
                                type="search"
                                name="q"
                                maxLength={80}
                                value={mailSearch}
                                onChange={(event) =>
                                    setMailSearch(event.target.value)
                                }
                                placeholder="Search mail, people or subject"
                                aria-label="Search your private KMJ mailbox"
                            />
                            <kbd>Ctrl + K</kbd>
                        </form>
                        <a
                            href="#kmj-ai-copilot"
                            className="owner-mail-ai-link"
                            aria-label="Open KMJ Mail AI Copilot"
                        >
                            <Sparkles size={15} aria-hidden="true" /> KMJ AI
                        </a>
                        <Link
                            href="/operator/ops#owner-guardrail-signals"
                            aria-label="Open notification and monitoring alerts"
                            className="owner-mail-header-icon"
                        >
                            <Bell size={19} aria-hidden="true" />
                        </Link>
                        <Link
                            href="/operator/modelfabric"
                            aria-label="Configure KMJ AI providers"
                            className="owner-mail-header-icon"
                        >
                            <Settings size={19} aria-hidden="true" />
                        </Link>
                        <a
                            href="#kmj-mail-help"
                            aria-label="KMJ Mail help and limitations"
                            className="owner-mail-header-icon"
                        >
                            <HelpCircle size={19} aria-hidden="true" />
                        </a>
                    </>
                ) : (
                    <>
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
                            aria-current={
                                url === '/operator/ops' ? 'page' : undefined
                            }
                        >
                            <span />
                            System Status
                        </Link>
                    </>
                )}
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <button
                            type="button"
                            className="owner-identity"
                            aria-label="Open profile and logout menu"
                            data-test="owner-profile-menu-trigger"
                        >
                            <span className="owner-initials">{initials}</span>
                            <span className="owner-identity-details">
                                <strong>{name}</strong>
                                <small>Platform Owner / Super Admin</small>
                            </span>
                            <ChevronRight size={13} aria-hidden="true" />
                        </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="z-[150] w-64">
                        {auth.user && <UserMenuContent user={auth.user} />}
                    </DropdownMenuContent>
                </DropdownMenu>
            </header>
            <aside
                id="owner-module-navigation"
                className={'owner-sidebar ' + (navOpen ? 'is-open' : '')}
                aria-label="Owner navigation"
            >
                <Link href="/super-admin" onClick={() => setNavOpen(false)}>
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
                                    href.split('#')[0] === url &&
                                    (href.startsWith('/operator/ops#')
                                        ? activeHash
                                            ? href.endsWith(activeHash)
                                            : label === 'System Health'
                                        : href === '/operator/ops'
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
                                onClick={() => {
                                    setNavOpen(false);
                                    setActiveHash(
                                        href.includes('#')
                                            ? '#' + href.split('#')[1]
                                            : '',
                                    );
                                }}
                            >
                                <Icon size={17} aria-hidden="true" />
                                {label}
                            </Link>
                        ))}
                    </nav>
                ))}
                <Link
                    href="/super-admin#owner-kristi"
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
