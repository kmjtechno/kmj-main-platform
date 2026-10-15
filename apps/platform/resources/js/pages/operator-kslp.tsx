import OperatorModuleNavigation from '@/components/operator-module-navigation';
import { Head, router, useForm } from '@inertiajs/react';
import { useState } from 'react';
import {
    KeyRound,
    ShieldCheck,
    Server,
    RefreshCw,
    Ban,
    Activity,
} from 'lucide-react';

type License = {
    id: string;
    customer_id: string;
    product: string;
    plan: string;
    status: string;
    state: string;
    sequence: number;
    expires_at: string;
    grace_until: string | null;
    active_activations: number;
};
type ProductEntitlement = {
    id: string;
    organization_id: string;
    organization_name: string;
    product_slug: string;
    product_name: string;
    capability: string;
    status: string;
    starts_at: string | null;
    ends_at: string | null;
};

type Event = {
    id: number;
    license_id: string;
    action: string;
    actor_id: string;
    reason: string | null;
    correlation_id: string;
    created_at: string;
};
type Props = {
    metrics: {
        licenses: number;
        active: number;
        trials: number;
        activations: number;
        revoked: number;
        issuerSubscriptions: number;
    };
    licenses: License[];
    events: Event[];
    filters: { customer_q: string; plan: string };
    matchingCount: number;
    customerOptions: { id: string; name: string; email: string }[];
    productEntitlements: ProductEntitlement[];
};

export default function OperatorKslp({
    metrics,
    licenses,
    events,
    filters,
    matchingCount,
    customerOptions,
    productEntitlements,
}: Props) {
    const [actionReason, setActionReason] = useState('');
    const [customerQuery, setCustomerQuery] = useState(filters.customer_q);
    const [planQuery, setPlanQuery] = useState(filters.plan);
    const [stateQuery, setStateQuery] = useState('all');
    const visibleLicenses = licenses.filter(
        (license) => stateQuery === 'all' || license.state === stateQuery,
    );
    const applyFilters = () =>
        router.get(
            '/operator/kslp',
            {
                customer_q: customerQuery,
                plan: planQuery,
            },
            { preserveState: true, preserveScroll: true },
        );
    const [pendingPlans, setPendingPlans] = useState<Record<string, string>>(
        {},
    );
    const issue = useForm({
        customer_id: '',
        plan: 'trial',
        reason: 'Commercial license issued by platform owner',
    });
    const cards = [
        ['Licenses', metrics.licenses],
        ['Active', metrics.active],
        ['Trials', metrics.trials],
        ['Activations', metrics.activations],
        ['Revoked', metrics.revoked],
        ['Issuer subscriptions', metrics.issuerSubscriptions],
    ] as const;
    const action = (
        id: string,
        a: string,
        extra: Record<string, unknown> = {},
    ) => {
        const reason = actionReason.trim();
        if (reason.length < 3) return;
        if (
            !window.confirm(
                `Confirm ${a.replace('_', ' ')} for license ${id}? This action is audited.`,
            )
        )
            return;

        router.post(
            `/operator/kslp/licenses/${id}/action`,
            { action: a, reason, ...extra },
            {
                preserveScroll: true,
                onSuccess: () => setActionReason(''),
            },
        );
    };
    return (
        <>
            <Head title="Licensing Center · Super Admin" />
            <div className="kmj-admin-shell flex h-full min-w-0 flex-1 flex-col gap-6 overflow-x-auto p-4 sm:p-6 lg:p-8">
                <OperatorModuleNavigation active="licensing" />
                <nav
                    aria-label="Licensing Center sections"
                    className="bg-card flex flex-wrap gap-2 rounded-xl border p-3 text-xs font-semibold"
                >
                    {[
                        ['#license-overview', 'Overview'],
                        ['#license-issue', 'Issue license'],
                        ['#license-search', 'Find customer'],
                        ['#license-register', 'Manage plans'],
                        ['#license-entitlements', 'All products'],
                        ['#license-audit', 'Audit trail'],
                    ].map(([href, label]) => (
                        <a
                            key={href}
                            href={href}
                            className="hover:bg-accent rounded-lg border px-3 py-2 hover:border-red-500/40 focus-visible:outline-2 focus-visible:outline-red-500"
                        >
                            {label}
                        </a>
                    ))}
                </nav>
                <section
                    id="license-overview"
                    className="kmj-admin-hero scroll-mt-6 rounded-[1.65rem] p-6 sm:p-8"
                >
                    <div className="flex gap-4">
                        <span className="grid h-11 w-11 place-items-center rounded-xl bg-red-500/10 text-red-500">
                            <ShieldCheck className="h-5 w-5" />
                        </span>
                        <div>
                            <div className="text-xs font-bold tracking-wider text-red-500 uppercase">
                                KMJ Main Platform authority
                            </div>
                            <h1 className="mt-1 text-2xl font-black">
                                KMJ Licensing Center
                            </h1>
                            <p className="text-muted-foreground mt-2 max-w-3xl text-sm">
                                Main Platform is the common commercial
                                authority. Search customers and manage existing
                                KSLP license plans, renewals, activations and
                                audit. Other product license protocols remain
                                gated until their signed interoperability tests
                                pass.
                            </p>
                        </div>
                    </div>
                </section>
                <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                    {cards.map(([l, v]) => (
                        <div key={l} className="bg-card rounded-xl border p-4">
                            <div className="text-muted-foreground text-xs">
                                {l}
                            </div>
                            <div className="mt-2 text-2xl font-black">{v}</div>
                        </div>
                    ))}
                </section>
                <section
                    id="license-issue"
                    className="bg-card scroll-mt-6 rounded-2xl border p-5"
                >
                    <h2 className="font-bold">
                        Issue a governed KMJ CloudOS license
                    </h2>
                    <p className="text-muted-foreground mt-1 text-xs">
                        Select a customer account below or enter an authorized
                        customer / organization ID. Other KMJ products retain
                        their own release-gated license profiles until signed
                        interoperability is verified.
                    </p>
                    <label className="mt-4 block text-xs font-semibold">
                        Find a registered customer
                        <select
                            className="bg-background mt-2 h-10 w-full rounded-lg border px-3 text-sm"
                            value={
                                customerOptions.some(
                                    (customer) =>
                                        customer.id === issue.data.customer_id,
                                )
                                    ? issue.data.customer_id
                                    : ''
                            }
                            onChange={(event) =>
                                issue.setData('customer_id', event.target.value)
                            }
                        >
                            <option value="">
                                Select an account (or enter ID manually)
                            </option>
                            {customerOptions.map((customer) => (
                                <option key={customer.id} value={customer.id}>
                                    {customer.name} · {customer.email}
                                </option>
                            ))}
                        </select>
                    </label>
                    <form
                        className="mt-4 grid gap-3 lg:grid-cols-[1.2fr_.7fr_1.5fr_auto]"
                        onSubmit={(e) => {
                            e.preventDefault();
                            issue.post('/operator/kslp/licenses', {
                                preserveScroll: true,
                                onSuccess: () => issue.reset('customer_id'),
                            });
                        }}
                    >
                        <input
                            className="bg-background h-10 rounded-lg border px-3 text-sm"
                            placeholder="Customer / organization ID"
                            value={issue.data.customer_id}
                            onChange={(e) =>
                                issue.setData('customer_id', e.target.value)
                            }
                            required
                        />
                        <select
                            className="bg-background h-10 rounded-lg border px-3 text-sm"
                            value={issue.data.plan}
                            onChange={(e) =>
                                issue.setData('plan', e.target.value)
                            }
                        >
                            {[
                                'trial',
                                'professional',
                                'business',
                                'enterprise',
                                'custom_oem',
                            ].map((p) => (
                                <option key={p} value={p}>
                                    {p}
                                </option>
                            ))}
                        </select>
                        <input
                            className="bg-background h-10 rounded-lg border px-3 text-sm"
                            value={issue.data.reason}
                            onChange={(e) =>
                                issue.setData('reason', e.target.value)
                            }
                            required
                        />
                        <button
                            disabled={issue.processing}
                            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-red-600 px-4 text-xs font-bold text-white"
                        >
                            <KeyRound className="h-4 w-4" />
                            Issue
                        </button>
                    </form>
                    {Object.keys(issue.errors).length > 0 && (
                        <p className="mt-2 text-xs text-red-500">
                            {Object.values(issue.errors)[0]}
                        </p>
                    )}
                </section>
                <section
                    id="license-search"
                    className="bg-card scroll-mt-6 rounded-2xl border p-5"
                    aria-label="License search"
                >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                        <div>
                            <h2 className="font-bold">
                                Find customer licenses
                            </h2>
                            <p className="text-muted-foreground mt-1 text-xs">
                                Search across the license register by customer
                                ID, product code or exact license UUID.
                            </p>
                        </div>
                        <a
                            href="/operator/directory"
                            className="text-sm font-semibold text-red-500 underline-offset-4 hover:underline"
                        >
                            Customers &amp; organizations
                        </a>
                    </div>
                    <form
                        className="mt-4 grid gap-3 md:grid-cols-[minmax(160px,1fr)_minmax(150px,.45fr)_auto]"
                        onSubmit={(event) => {
                            event.preventDefault();
                            applyFilters();
                        }}
                    >
                        <label className="text-xs font-semibold">
                            Customer or license search
                            <input
                                value={customerQuery}
                                onChange={(event) =>
                                    setCustomerQuery(event.target.value)
                                }
                                maxLength={96}
                                className="bg-background mt-1 h-11 w-full rounded-lg border px-3 text-sm"
                                placeholder="Customer ID, product, license UUID"
                            />
                        </label>
                        <label className="text-xs font-semibold">
                            Plan
                            <select
                                value={planQuery}
                                onChange={(event) =>
                                    setPlanQuery(event.target.value)
                                }
                                className="bg-background mt-1 h-11 w-full rounded-lg border px-3 text-sm"
                            >
                                <option value="">All plans</option>
                                {[
                                    'trial',
                                    'professional',
                                    'business',
                                    'enterprise',
                                    'custom_oem',
                                ].map((plan) => (
                                    <option key={plan} value={plan}>
                                        {plan}
                                    </option>
                                ))}
                            </select>
                        </label>
                        <button
                            type="submit"
                            className="h-11 self-end rounded-lg bg-red-600 px-5 text-sm font-bold text-white"
                        >
                            Search
                        </button>
                    </form>
                    <p
                        role="status"
                        className="text-muted-foreground mt-3 text-xs"
                    >
                        {matchingCount} matching license(s). Showing up to 100;
                        refine your search to find an older record.
                    </p>
                </section>
                <section
                    id="license-register"
                    className="bg-card scroll-mt-6 rounded-2xl border p-5"
                >
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="font-bold">Commercial licenses</h2>
                            <p className="text-muted-foreground mt-1 text-xs">
                                Lifecycle mutations require platform-owner
                                access and recent password confirmation.
                            </p>
                        </div>
                        <Server className="h-5 w-5 text-red-500" />
                    </div>
                    <div className="mt-4 grid gap-2 rounded-xl border border-red-500/20 bg-red-500/5 p-3 sm:grid-cols-[1fr_auto]">
                        <div>
                            <label
                                htmlFor="kslp-action-reason"
                                className="text-xs font-bold"
                            >
                                Required reason for lifecycle changes
                            </label>
                            <input
                                id="kslp-action-reason"
                                value={actionReason}
                                onChange={(e) =>
                                    setActionReason(e.target.value)
                                }
                                placeholder="Enter the specific approved reason before revoke, renew, reactivate, or plan change"
                                className="bg-background mt-2 h-10 w-full rounded-lg border px-3 text-sm"
                            />
                        </div>
                        <div className="text-muted-foreground self-end text-xs">
                            Minimum 3 characters · recorded in audit trail
                        </div>
                    </div>
                    <div className="mt-4 flex items-center gap-3">
                        <label
                            htmlFor="license-state"
                            className="text-xs font-semibold"
                        >
                            State
                        </label>
                        <select
                            id="license-state"
                            value={stateQuery}
                            onChange={(event) =>
                                setStateQuery(event.target.value)
                            }
                            className="bg-background h-9 rounded-lg border px-2 text-xs"
                        >
                            <option value="all">All states</option>
                            {[
                                'ACTIVE',
                                'RENEWAL_DUE',
                                'GRACE',
                                'RESTRICTED',
                                'REVOKED',
                            ].map((state) => (
                                <option key={state} value={state}>
                                    {state}
                                </option>
                            ))}
                        </select>
                        <span
                            role="status"
                            className="text-muted-foreground text-xs"
                        >
                            {visibleLicenses.length} visible
                        </span>
                    </div>
                    <div className="mt-4 overflow-x-auto">
                        <table className="w-full min-w-[980px] text-left text-xs">
                            <thead className="text-muted-foreground">
                                <tr>
                                    {[
                                        'License / customer',
                                        'Product / plan',
                                        'State',
                                        'Sequence',
                                        'Expiry',
                                        'Activations',
                                        'Actions',
                                    ].map((x) => (
                                        <th key={x} className="border-b p-3">
                                            {x}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {visibleLicenses.map((l) => (
                                    <tr
                                        key={l.id}
                                        className="border-b last:border-0"
                                    >
                                        <td className="p-3">
                                            <div className="font-mono font-semibold">
                                                {l.id}
                                            </div>
                                            <div className="text-muted-foreground mt-1">
                                                {l.customer_id}
                                            </div>
                                        </td>
                                        <td className="p-3">
                                            <b>{l.product}</b>
                                            <div>{l.plan}</div>
                                        </td>
                                        <td className="p-3 font-bold">
                                            {l.state}
                                        </td>
                                        <td className="p-3">{l.sequence}</td>
                                        <td className="p-3">{l.expires_at}</td>
                                        <td className="p-3">
                                            {l.active_activations}
                                        </td>
                                        <td className="p-3">
                                            <div className="flex flex-wrap gap-2">
                                                {l.state === 'REVOKED' ? (
                                                    <button
                                                        onClick={() =>
                                                            action(
                                                                l.id,
                                                                'reactivate',
                                                            )
                                                        }
                                                        disabled={
                                                            actionReason.trim()
                                                                .length < 3
                                                        }
                                                        className="rounded border px-2 py-1 disabled:cursor-not-allowed disabled:opacity-40"
                                                    >
                                                        <RefreshCw className="inline h-3 w-3" />{' '}
                                                        Reactivate
                                                    </button>
                                                ) : (
                                                    <button
                                                        onClick={() =>
                                                            action(
                                                                l.id,
                                                                'revoke',
                                                            )
                                                        }
                                                        disabled={
                                                            actionReason.trim()
                                                                .length < 3
                                                        }
                                                        className="rounded border px-2 py-1 disabled:cursor-not-allowed disabled:opacity-40"
                                                    >
                                                        <Ban className="inline h-3 w-3" />{' '}
                                                        Revoke
                                                    </button>
                                                )}
                                                <button
                                                    disabled={
                                                        actionReason.trim()
                                                            .length < 3
                                                    }
                                                    onClick={() =>
                                                        action(l.id, 'renew', {
                                                            days: 365,
                                                        })
                                                    }
                                                    className="rounded border px-2 py-1 disabled:cursor-not-allowed disabled:opacity-40"
                                                >
                                                    Renew 1y
                                                </button>
                                                <select
                                                    aria-label="Select new plan"
                                                    value={
                                                        pendingPlans[l.id] ??
                                                        (l.plan === 'trial'
                                                            ? 'professional'
                                                            : l.plan)
                                                    }
                                                    onChange={(e) =>
                                                        setPendingPlans(
                                                            (current) => ({
                                                                ...current,
                                                                [l.id]: e.target
                                                                    .value,
                                                            }),
                                                        )
                                                    }
                                                    className="bg-background rounded border px-2 py-1"
                                                >
                                                    {[
                                                        'professional',
                                                        'business',
                                                        'enterprise',
                                                        'custom_oem',
                                                    ].map((p) => (
                                                        <option
                                                            key={p}
                                                            value={p}
                                                        >
                                                            {p}
                                                        </option>
                                                    ))}
                                                </select>
                                                <button
                                                    disabled={
                                                        actionReason.trim()
                                                            .length < 3
                                                    }
                                                    onClick={() =>
                                                        action(
                                                            l.id,
                                                            'change_plan',
                                                            {
                                                                plan:
                                                                    pendingPlans[
                                                                        l.id
                                                                    ] ??
                                                                    (l.plan ===
                                                                    'trial'
                                                                        ? 'professional'
                                                                        : l.plan),
                                                            },
                                                        )
                                                    }
                                                    className="rounded border px-2 py-1 disabled:cursor-not-allowed disabled:opacity-40"
                                                >
                                                    Apply plan
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
                <section
                    id="license-entitlements"
                    className="bg-card scroll-mt-6 rounded-2xl border p-5"
                >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                            <h2 className="font-bold">
                                All-product entitlement register
                            </h2>
                            <p className="text-muted-foreground mt-1 max-w-3xl text-xs leading-5">
                                Read-only overview of organizational access
                                across the KMJ catalog. An entitlement is not
                                automatically an activated signed device license
                                or a paid plan. Product-specific license
                                management remains gated.
                            </p>
                        </div>
                        <span className="rounded-lg border px-3 py-2 text-xs font-semibold">
                            Up to 60 recent matches
                        </span>
                    </div>
                    {productEntitlements.length === 0 ? (
                        <p className="text-muted-foreground mt-4 rounded-lg border border-dashed p-5 text-sm">
                            No matching product entitlements in this view.
                        </p>
                    ) : (
                        <div className="mt-4 overflow-x-auto">
                            <table className="w-full min-w-[720px] text-left text-xs">
                                <thead>
                                    <tr className="text-muted-foreground">
                                        {[
                                            'Organization',
                                            'Product',
                                            'Capability',
                                            'State',
                                            'Access end',
                                        ].map((label) => (
                                            <th
                                                key={label}
                                                className="border-b px-3 py-2"
                                            >
                                                {label}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {productEntitlements.map((entitlement) => (
                                        <tr
                                            key={entitlement.id}
                                            className="border-b last:border-0"
                                        >
                                            <td className="px-3 py-3">
                                                <span className="font-semibold">
                                                    {
                                                        entitlement.organization_name
                                                    }
                                                </span>
                                                <div className="text-muted-foreground">
                                                    {
                                                        entitlement.organization_id
                                                    }
                                                </div>
                                            </td>
                                            <td className="px-3 py-3">
                                                <span className="font-semibold">
                                                    {entitlement.product_name}
                                                </span>
                                                <div className="text-muted-foreground">
                                                    {entitlement.product_slug}
                                                </div>
                                            </td>
                                            <td className="px-3 py-3">
                                                {entitlement.capability}
                                            </td>
                                            <td className="px-3 py-3 font-semibold">
                                                {entitlement.status}
                                            </td>
                                            <td className="px-3 py-3">
                                                {entitlement.ends_at ??
                                                    'No recorded end'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </section>
                <section
                    id="license-audit"
                    className="bg-card scroll-mt-6 rounded-2xl border p-5"
                >
                    <div className="flex items-center gap-2">
                        <Activity className="h-4 w-4 text-red-500" />
                        <h2 className="font-bold">
                            Immutable lifecycle audit trail
                        </h2>
                    </div>
                    <div className="mt-4 grid gap-2">
                        {events.map((e) => (
                            <div
                                key={e.id}
                                className="grid gap-1 rounded-xl border p-3 text-xs md:grid-cols-[1fr_.8fr_1fr_1.5fr]"
                            >
                                <b>{e.action}</b>
                                <span>{e.created_at}</span>
                                <span className="font-mono">
                                    {e.license_id}
                                </span>
                                <span className="text-muted-foreground">
                                    {e.reason ?? '—'}
                                </span>
                            </div>
                        ))}
                    </div>
                </section>
            </div>
        </>
    );
}
