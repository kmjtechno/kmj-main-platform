import { Link } from '@inertiajs/react';
import { codeBridgeDeviceQuotaDisplay } from './device-policy-display';
import type { ReactNode } from 'react';
import {
    Activity,
    ArrowRight,
    Cable,
    CreditCard,
    KeyRound,
    MonitorSmartphone,
    RefreshCw,
    Settings2,
    ShieldCheck,
    Users,
} from 'lucide-react';

export type CodeBridgeSection =
    | 'overview'
    | 'devices'
    | 'setup'
    | 'usage'
    | 'billing'
    | 'clients'
    | 'settings';

type Props = {
    organizationName: string;
    plan: string | null;
    licenseStatus: string;
    licenseExpiresAt: string | null;
    managedDevices: number;
    deviceLimit: number | null;
    pendingPairings: number;
    authorizedClientGrants: number;
    oauthReady: boolean;
    canManageOwnerPlan: boolean;
    activeSection: CodeBridgeSection;
    onSectionChange: (section: CodeBridgeSection) => void;
    children: ReactNode;
};

const navigation = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'devices', label: 'Devices & projects', icon: MonitorSmartphone },
    { id: 'setup', label: 'Setup & integrations', icon: Cable },
    { id: 'usage', label: 'Usage & limits', icon: RefreshCw },
    { id: 'billing', label: 'Plan & billing', icon: CreditCard },
    { id: 'clients', label: 'Connected apps', icon: Users },
    { id: 'settings', label: 'Security & settings', icon: Settings2 },
] as const;

function validDate(value: string | null): string {
    if (!value) return 'Not reported';
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? 'Not reported'
        : date.toLocaleDateString(undefined, { dateStyle: 'medium' });
}

function Metric({
    label,
    value,
    detail,
}: {
    label: string;
    value: string | number;
    detail: string;
}) {
    return (
        <div className="bg-background rounded-xl border p-4">
            <p className="text-muted-foreground text-xs font-semibold uppercase">
                {label}
            </p>
            <p className="mt-1 text-xl font-black">{value}</p>
            <p className="text-muted-foreground mt-1 text-xs leading-5">
                {detail}
            </p>
        </div>
    );
}

export default function CodeBridgeControlCenterHub({
    organizationName,
    plan,
    licenseStatus,
    licenseExpiresAt,
    managedDevices,
    deviceLimit,
    pendingPairings,
    authorizedClientGrants,
    oauthReady,
    canManageOwnerPlan,
    activeSection,
    onSectionChange,
    children,
}: Props) {
    return (
        <section
            aria-label="CodeBridge workspace management"
            className="grid min-w-0 gap-5 lg:grid-cols-[220px_minmax(0,1fr)]"
        >
            <aside className="bg-card h-fit rounded-2xl border p-4 lg:sticky lg:top-4">
                <div className="flex items-center gap-2">
                    <Cable className="h-4 w-4 text-red-500" />
                    <h2 className="text-sm font-black">Control Center</h2>
                </div>
                <p className="text-muted-foreground mt-2 text-xs leading-5">
                    Manage your authorized CodeBridge workspace.
                </p>
                <nav
                    aria-label="CodeBridge sections"
                    className="mt-4 grid grid-cols-2 gap-1 sm:grid-cols-3 lg:grid-cols-1"
                >
                    {navigation.map(({ id, label, icon: Icon }) => (
                        <button
                            key={id}
                            type="button"
                            aria-pressed={activeSection === id}
                            onClick={() => onSectionChange(id)}
                            className={[
                                'focus-visible:ring-ring flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm font-semibold transition focus-visible:ring-2 focus-visible:outline-none',
                                activeSection === id
                                    ? 'bg-red-500/10 text-foreground'
                                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                            ].join(' ')}
                        >
                            <Icon
                                aria-hidden="true"
                                className="h-4 w-4 shrink-0 text-red-500"
                            />
                            {label}
                        </button>
                    ))}
                </nav>
                <a
                    href="/install-codebridge-windows.cmd"
                    download="KMJ-CodeBridge-Connect-Windows.cmd"
                    className="mt-4 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-3 text-xs font-black text-white hover:bg-red-500"
                >
                    <MonitorSmartphone className="h-4 w-4" />
                    Connect Windows device
                </a>
            </aside>

            <div className="min-w-0 space-y-5">
                <section
                    id="codebridge-overview"
                    hidden={activeSection !== 'overview'}
                    aria-labelledby="codebridge-overview-heading"
                    className="bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
                >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                            <h2
                                id="codebridge-overview-heading"
                                className="font-black"
                            >
                                Workspace overview
                            </h2>
                            <p className="text-muted-foreground mt-1 text-xs">
                                {organizationName}
                            </p>
                        </div>
                        <Link
                            href="/codebridge/pair"
                            className="inline-flex min-h-10 items-center gap-2 rounded-xl border px-4 text-xs font-bold hover:border-red-500/40"
                        >
                            Approve a new pairing
                            <ArrowRight className="h-4 w-4" />
                        </Link>
                    </div>
                    <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        <Metric
                            label="Registered devices"
                            value={managedDevices}
                            detail="Registration does not establish live presence"
                        />
                        <Metric
                            label="Pending pairings"
                            value={pendingPairings}
                            detail="Codes awaiting approval or expiry"
                        />
                        <Metric
                            label="Authorized app grants"
                            value={authorizedClientGrants}
                            detail="Refresh grants, not live app sessions"
                        />
                    </div>
                </section>

                <section
                    id="codebridge-usage"
                    hidden={activeSection !== 'usage'}
                    aria-labelledby="codebridge-usage-heading"
                    className="bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
                >
                    <div className="flex items-center gap-2">
                        <Activity className="h-5 w-5 text-red-500" />
                        <h2
                            id="codebridge-usage-heading"
                            className="font-black"
                        >
                            Usage & limits
                        </h2>
                    </div>
                    <p className="text-muted-foreground mt-2 text-xs leading-5">
                        Accurate counters only. This page does not yet receive
                        verified job, token, model or monthly call metering from
                        CodeBridge.
                    </p>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        <Metric
                            label="Device allocation"
                            value={
                                codeBridgeDeviceQuotaDisplay(
                                    plan,
                                    managedDevices,
                                    deviceLimit,
                                ).value
                            }
                            detail={
                                codeBridgeDeviceQuotaDisplay(
                                    plan,
                                    managedDevices,
                                    deviceLimit,
                                ).detail
                            }
                        />
                        <Metric
                            label="Monthly execution usage"
                            value="Not reported"
                            detail="No authoritative metering feed connected"
                        />
                    </div>
                    <p className="text-muted-foreground mt-3 text-xs">
                        Model quotas and concurrency depend on the actual
                        provider, device capacity and signed KMJ entitlement. No
                        free or unlimited allowance is assumed.
                    </p>
                </section>

                <section
                    id="codebridge-plan-billing"
                    hidden={activeSection !== 'billing'}
                    aria-labelledby="codebridge-billing-heading"
                    className="bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
                >
                    <div className="flex items-center gap-2">
                        <CreditCard className="h-5 w-5 text-red-500" />
                        <h2
                            id="codebridge-billing-heading"
                            className="font-black"
                        >
                            Plan & billing
                        </h2>
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        <Metric
                            label="Current plan"
                            value={plan ?? 'Not reported'}
                            detail={`License status: ${licenseStatus}`}
                        />
                        <Metric
                            label="License valid until"
                            value={validDate(licenseExpiresAt)}
                            detail="From the KMJ licensing authority"
                        />
                    </div>
                    <p className="text-muted-foreground mt-3 text-xs leading-5">
                        This view shows entitlements, not a payment transaction
                        history. Invoices and paid consumption must be obtained
                        from verified billing records.
                    </p>
                    <div className="mt-4 flex flex-wrap gap-2">
                        <Link
                            href="/purchase"
                            className="inline-flex min-h-10 items-center gap-2 rounded-xl border px-4 text-xs font-bold hover:border-red-500/40"
                        >
                            Open Purchase Center
                            <ArrowRight className="h-4 w-4" />
                        </Link>
                        {canManageOwnerPlan && (
                            <Link
                                href="/operator/codebridge/owner-plan"
                                className="inline-flex min-h-10 items-center rounded-xl border px-4 text-xs font-bold"
                            >
                                Manage internal Owner Plan
                            </Link>
                        )}
                    </div>
                </section>

                <section
                    id="codebridge-settings"
                    hidden={activeSection !== 'settings'}
                    aria-labelledby="codebridge-settings-heading"
                    className="bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
                >
                    <div className="flex items-center gap-2">
                        <Settings2 className="h-5 w-5 text-red-500" />
                        <h2
                            id="codebridge-settings-heading"
                            className="font-black"
                        >
                            Settings & security
                        </h2>
                    </div>
                    <p className="text-muted-foreground mt-2 text-xs leading-5">
                        OAuth discovery:{' '}
                        {oauthReady ? 'Available' : 'Not verified'}. Device
                        credential revocation is available in the Devices
                        section. Connected app grants are managed below.
                    </p>
                    <div className="mt-4 flex flex-wrap gap-2">
                        <button
                            type="button"
                            onClick={() => onSectionChange('devices')}
                            className="inline-flex min-h-10 items-center gap-2 rounded-xl border px-4 text-xs font-bold hover:border-red-500/40"
                        >
                            <MonitorSmartphone className="h-4 w-4 text-red-500" />
                            Manage device approvals
                        </button>
                        <Link
                            href="/settings/security"
                            className="inline-flex min-h-10 items-center gap-2 rounded-xl border px-4 text-xs font-bold hover:border-red-500/40"
                        >
                            <KeyRound className="h-4 w-4 text-red-500" />
                            Account security
                        </Link>
                        <button
                            type="button"
                            onClick={() => onSectionChange('clients')}
                            className="inline-flex min-h-10 items-center gap-2 rounded-xl border px-4 text-xs font-bold"
                        >
                            <ShieldCheck className="h-4 w-4 text-red-500" />
                            Review app grants
                        </button>
                    </div>
                </section>
                {children}
            </div>
        </section>
    );
}
