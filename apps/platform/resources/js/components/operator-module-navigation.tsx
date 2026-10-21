import { Link } from '@inertiajs/react';
import {
    Activity,
    Boxes,
    CreditCard,
    KeyRound,
    LayoutDashboard,
    Package,
    Search,
    ShieldCheck,
    ShoppingCart,
    Users,
} from 'lucide-react';
import { useMemo, useState } from 'react';

const modules = [
    {
        key: 'overview',
        label: 'Overview',
        href: '/super-admin',
        icon: LayoutDashboard,
        help: 'Business overview and decisions',
    },
    {
        key: 'products',
        label: 'Products',
        href: '/operator/products',
        icon: Package,
        help: 'Catalog and pricing controls',
    },
    {
        key: 'orders',
        label: 'Orders',
        href: '/super-admin#commercial-orders',
        icon: ShoppingCart,
        help: 'Sales and fulfillment',
    },
    {
        key: 'customers',
        label: 'Customers',
        href: '/operator/directory',
        icon: Users,
        help: 'Users and organizations',
    },
    {
        key: 'payments',
        label: 'Payments',
        href: '/operator/payments',
        icon: CreditCard,
        help: 'Gateway settings and verification',
    },
    {
        key: 'licensing',
        label: 'Licensing',
        href: '/operator/kslp',
        icon: KeyRound,
        help: 'Plans, entitlements and audit',
    },
    {
        key: 'codebridge',
        label: 'CodeBridge',
        href: '/operator/codebridge/owner-plan',
        icon: Boxes,
        help: 'Managed devices and owner plans',
    },
    {
        key: 'operations',
        label: 'Operations',
        href: '/operator/ops',
        icon: Activity,
        help: 'Health, jobs, backups and release evidence',
    },
    {
        key: 'security',
        label: 'Security',
        href: '/settings/security',
        icon: ShieldCheck,
        help: 'Account safeguards',
    },
] as const;

type AdminModule = (typeof modules)[number]['key'];

export default function OperatorModuleNavigation({
    active,
}: {
    active: AdminModule;
}) {
    const [query, setQuery] = useState('');
    const visible = useMemo(() => {
        const value = query.trim().toLocaleLowerCase();
        return value
            ? modules.filter((module) =>
                  `${module.label} ${module.help}`
                      .toLocaleLowerCase()
                      .includes(value),
              )
            : modules;
    }, [query]);

    return (
        <nav
            aria-label="Super Admin modules"
            className="kmj-admin-nav w-full rounded-2xl p-3 sm:p-4"
        >
            <div className="flex flex-wrap items-center justify-between gap-4 px-1 pb-4">
                <div className="flex items-center gap-3">
                    <span className="grid size-11 shrink-0 place-items-center rounded-xl border border-red-500/20 bg-red-500/10 text-red-500">
                        <LayoutDashboard
                            className="size-5"
                            aria-hidden="true"
                        />
                    </span>
                    <div>
                        <p className="text-xs font-extrabold tracking-[0.13em] text-red-500 uppercase">
                            KMJ TECHNO · Owner Workspace
                        </p>
                        <p className="text-muted-foreground mt-0.5 text-xs">
                            Nine connected modules. Every privileged action
                            remains authorization-gated.
                        </p>
                    </div>
                </div>
                <label className="relative w-full sm:w-56">
                    <Search
                        className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
                        aria-hidden="true"
                    />
                    <span className="sr-only">Find an admin module</span>
                    <input
                        type="search"
                        aria-label="Find an admin module"
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        placeholder="Find a workspace..."
                        className="bg-background/45 focus-visible:ring-ring/60 border-border min-h-10 w-full rounded-xl border pr-3 pl-9 text-xs outline-none focus-visible:ring-2"
                    />
                </label>
            </div>
            <div
                className="flex gap-1.5 overflow-x-auto pb-1"
                role="list"
                aria-label="Available admin sections"
            >
                {visible.map(({ key, label, href, icon: Icon, help }) => (
                    <div role="listitem" key={key}>
                        <Link
                            href={href}
                            title={help}
                            aria-current={key === active ? 'page' : undefined}
                            className="kmj-admin-tab"
                        >
                            <Icon
                                className="size-4 shrink-0"
                                aria-hidden="true"
                            />
                            <span>{label}</span>
                        </Link>
                    </div>
                ))}
                {visible.length === 0 && (
                    <p
                        role="status"
                        className="text-muted-foreground px-3 py-3 text-sm"
                    >
                        No matching module. Clear the search to see every
                        workspace.
                    </p>
                )}
            </div>
        </nav>
    );
}
