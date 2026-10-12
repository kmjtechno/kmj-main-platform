import { Link } from '@inertiajs/react';
import {
    Activity,
    Boxes,
    CreditCard,
    KeyRound,
    LayoutDashboard,
    Package,
    ShieldCheck,
    ShoppingCart,
} from 'lucide-react';

const modules = [
    { label: 'Overview', href: '/operator', icon: LayoutDashboard, help: 'Platform summary' },
    { label: 'Products', href: '/operator#product-manager', icon: Package, help: 'Catalog and pricing controls' },
    { label: 'Orders', href: '/operator#commercial-orders', icon: ShoppingCart, help: 'Sales and fulfillment' },
    { label: 'Payments', href: '/operator/payments', icon: CreditCard, help: 'Gateway configuration' },
    { label: 'Licensing', href: '/operator/kslp', icon: KeyRound, help: 'License governance' },
    { label: 'CodeBridge', href: '/operator/codebridge/owner-plan', icon: Boxes, help: 'Device and owner plans' },
    { label: 'Operations', href: '/operator/ops', icon: Activity, help: 'Servers and backups' },
    { label: 'Security', href: '/settings/security', icon: ShieldCheck, help: 'Account safeguards' },
] as const;

export default function OperatorModuleNavigation({
    active,
}: {
    active: 'overview' | 'payments' | 'operations' | 'licensing' | 'codebridge';
}) {
    return (
        <nav aria-label="Super Admin modules" className="w-full rounded-2xl border border-border bg-card p-3">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 px-2">
                <div>
                    <p className="text-xs font-black uppercase tracking-[0.16em] text-red-500">
                        KMJ Control Center
                    </p>
                    <p className="text-muted-foreground mt-1 text-xs">
                        Select a module. Every action stays governed by your owner permissions.
                    </p>
                </div>
                <span className="rounded-full border border-emerald-500/25 px-3 py-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-300">
                    Passkey-protected
                </span>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8">
                {modules.map(({ label, href, icon: Icon, help }) => {
                    const selected = label.toLowerCase() === active;
                    return (
                        <Link
                            key={label}
                            href={href}
                            aria-current={selected ? 'page' : undefined}
                            title={help}
                            className={[
                                'flex min-h-16 flex-col items-start justify-center gap-1.5 rounded-xl border p-3 text-sm font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500',
                                selected
                                    ? 'border-red-500/35 bg-red-500/10 text-red-600 dark:text-red-300'
                                    : 'border-border/60 bg-background/50 hover:border-red-500/30 hover:bg-accent',
                            ].join(' ')}
                        >
                            <Icon className="h-5 w-5" aria-hidden="true" />
                            <span>{label}</span>
                        </Link>
                    );
                })}
            </div>
        </nav>
    );
}
