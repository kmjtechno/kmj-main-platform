import type { OmniDeskOffer } from '@/components/omnidesk-pricing-cards';
import OperatorModuleNavigation from '@/components/operator-module-navigation';
import {
    DeveloperAppsWorkspace,
    type DeveloperWorkspaceProps,
} from './developer-apps';
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

type IssuerWorkspace = {
    id: string;
    name: string;
    issuer_status: string;
    tier: string | null;
    registered_apps: number;
    product_limit: number;
    monthly_issue_limit: number;
    current_period_end: string | null;
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
    issuerWorkspaces: IssuerWorkspace[];
    omnideskOffers: OmniDeskOffer[];
    omnideskOfferVersion: string;
    omnideskReleaseFlags: {
        trial: boolean;
        paid: boolean;
        gateway: boolean;
    };
    developerIssuanceEnabled: boolean;
    developerWorkspace: DeveloperWorkspaceProps;
    unverifiedEmailCleanup: {
        unverified: number;
        eligible: number;
        protected: number;
        sha256: string;
        status: string;
        enabled: boolean;
    };
};

const LIST_PAGE_SIZE = 10;

type PageControlsProps = {
    label: string;
    page: number;
    pageCount: number;
    total: number;
    onPageChange: (page: number) => void;
};

function PageControls({
    label,
    page,
    pageCount,
    total,
    onPageChange,
}: PageControlsProps) {
    if (pageCount <= 1) return null;

    const start = page * LIST_PAGE_SIZE + 1;
    const end = Math.min((page + 1) * LIST_PAGE_SIZE, total);

    return (
        <nav
            aria-label={label + ' pages'}
            className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-3"
        >
            <span role="status" className="text-muted-foreground text-xs">
                Showing {start}–{end} of {total} loaded
            </span>
            <div className="flex items-center gap-2">
                <button
                    type="button"
                    className="hover:bg-accent rounded-lg border px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-40"
                    disabled={page === 0}
                    onClick={() => onPageChange(page - 1)}
                >
                    Previous
                </button>
                <span className="text-muted-foreground text-xs tabular-nums">
                    Page {page + 1} / {pageCount}
                </span>
                <button
                    type="button"
                    className="hover:bg-accent rounded-lg border px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-40"
                    disabled={page >= pageCount - 1}
                    onClick={() => onPageChange(page + 1)}
                >
                    Next
                </button>
            </div>
        </nav>
    );
}

export default function OperatorKslp({
    metrics,
    licenses,
    events,
    filters,
    matchingCount,
    customerOptions,
    productEntitlements,
    issuerWorkspaces,
    omnideskOffers,
    omnideskOfferVersion,
    omnideskReleaseFlags,
    developerIssuanceEnabled,
    developerWorkspace,
    unverifiedEmailCleanup,
}: Props) {
    const [actionReason, setActionReason] = useState('');
    const [purgingUnverified, setPurgingUnverified] = useState(false);
    const [customerQuery, setCustomerQuery] = useState(filters.customer_q);
    const [planQuery, setPlanQuery] = useState(filters.plan);
    const [stateQuery, setStateQuery] = useState('all');
    const [issuerSearch, setIssuerSearch] = useState('');
    const [issuerPage, setIssuerPage] = useState(0);
    const [entitlementPage, setEntitlementPage] = useState(0);
    const [auditPage, setAuditPage] = useState(0);
    const cleanupPreviewAvailable =
        unverifiedEmailCleanup.enabled &&
        unverifiedEmailCleanup.status === 'PREVIEW_ONLY';
    const issuerNeedle = issuerSearch.trim().toLocaleLowerCase();
    const filteredIssuers = issuerWorkspaces.filter((issuer) =>
        [issuer.name, issuer.issuer_status, issuer.tier ?? ''].some((value) =>
            value.toLocaleLowerCase().includes(issuerNeedle),
        ),
    );
    const issuerPageCount = Math.max(
        1,
        Math.ceil(filteredIssuers.length / LIST_PAGE_SIZE),
    );
    const currentIssuerPage = Math.min(issuerPage, issuerPageCount - 1);
    const issuerRows = filteredIssuers.slice(
        currentIssuerPage * LIST_PAGE_SIZE,
        (currentIssuerPage + 1) * LIST_PAGE_SIZE,
    );
    const entitlementPageCount = Math.max(
        1,
        Math.ceil(productEntitlements.length / LIST_PAGE_SIZE),
    );
    const currentEntitlementPage = Math.min(
        entitlementPage,
        entitlementPageCount - 1,
    );
    const entitlementRows = productEntitlements.slice(
        currentEntitlementPage * LIST_PAGE_SIZE,
        (currentEntitlementPage + 1) * LIST_PAGE_SIZE,
    );
    const auditPageCount = Math.max(
        1,
        Math.ceil(events.length / LIST_PAGE_SIZE),
    );
    const currentAuditPage = Math.min(auditPage, auditPageCount - 1);
    const auditRows = events.slice(
        currentAuditPage * LIST_PAGE_SIZE,
        (currentAuditPage + 1) * LIST_PAGE_SIZE,
    );
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
            <Head title="KMJ Licensing Hub · Super Admin" />
            <div className="owner-admin-page kmj-admin-shell flex h-full min-w-0 flex-1 flex-col gap-6 overflow-x-auto p-4 sm:p-6 lg:p-8">
                <OperatorModuleNavigation active="licensing" />
                <nav
                    aria-label="KMJ Licensing Hub Super Admin sections"
                    className="bg-card flex flex-wrap gap-2 rounded-xl border p-3 text-xs font-semibold"
                >
                    {[
                        ['#license-overview', 'Overview'],
                        ['#omnidesk-offers', 'OmniDesk pricing'],
                        ['#issuer-workspaces', 'Developer issuers'],
                        ['#developer-workspace', 'Apps, Keys & SDK'],
                        ['#unverified-accounts', 'Unverified accounts'],
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
                    id="omnidesk-offers"
                    aria-labelledby="omnidesk-offers-title"
                    className="bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
                >
                    <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                            <h2
                                id="omnidesk-offers-title"
                                className="text-lg font-extrabold"
                            >
                                OmniDesk · India launch pricing
                            </h2>
                            <p className="text-muted-foreground mt-2 max-w-2xl text-xs leading-5">
                                Version {omnideskOfferVersion}. A no-card trial,
                                personal free tier and monthly/yearly business
                                offers live in this ONE Licensing Hub. Preparing
                                a price creates PAUSED catalog plans only: no
                                payment, customer entitlement, signed lease or
                                automatic renewal is enabled.
                            </p>
                            <p className="text-muted-foreground mt-2 text-xs">
                                Trial rollout:{' '}
                                {omnideskReleaseFlags.trial
                                    ? 'configured'
                                    : 'off'}
                                {' · '}
                                Paid fulfillment:{' '}
                                {omnideskReleaseFlags.paid
                                    ? 'configured'
                                    : 'off'}
                                {' · '}
                                Live gateway:{' '}
                                {omnideskReleaseFlags.gateway
                                    ? 'configured'
                                    : 'off'}
                            </p>
                        </div>
                        <button
                            type="button"
                            onClick={() =>
                                router.post(
                                    '/operator/kslp/omnidesk/offers/prepare',
                                    {},
                                    { preserveScroll: true },
                                )
                            }
                            className="min-h-11 rounded-xl bg-red-600 px-4 text-xs font-bold text-white hover:bg-red-500"
                        >
                            Prepare paused INR plans
                        </button>
                    </div>
                    <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {omnideskOffers.map((offer) => (
                            <article
                                key={offer.code}
                                className="border-border rounded-xl border p-4"
                            >
                                <p className="text-sm font-bold">
                                    {offer.name}
                                </p>
                                <p className="mt-1 text-lg font-black tabular-nums">
                                    {offer.amount_minor === null
                                        ? offer.trial_days > 0
                                            ? `${offer.trial_days} days free`
                                            : 'Free / quote'
                                        : `₹${(offer.amount_minor / 100).toLocaleString('en-IN')} / ${offer.billing_interval}`}
                                </p>
                                <p className="text-muted-foreground mt-2 text-xs">
                                    {offer.licensed_users} users ·{' '}
                                    {offer.managed_devices} devices
                                    {' · '}
                                    {offer.concurrent_sessions} concurrent
                                    sessions
                                </p>
                                <p className="text-muted-foreground mt-2 text-xs">
                                    {offer.available
                                        ? 'Catalog active (other release gates still apply)'
                                        : 'Not for sale · prepared or awaiting approval'}
                                </p>
                            </article>
                        ))}
                    </div>
                    <p className="text-muted-foreground mt-4 text-xs">
                        Launch pricing excludes applicable taxes. Owner merchant
                        onboarding and verified LIVE provider payment must pass
                        before activating any paid plan. Personal Free is
                        non-commercial and direct-only.
                    </p>
                </section>

                <section
                    id="license-overview"
                    className="owner-admin-hero kmj-admin-hero scroll-mt-6 rounded-[1.65rem] p-6 sm:p-8"
                >
                    <div className="flex gap-4">
                        <span className="grid h-11 w-11 place-items-center rounded-xl bg-red-500/10 text-red-500">
                            <ShieldCheck className="h-5 w-5" />
                        </span>
                        <div>
                            <div className="text-xs font-bold tracking-wider text-red-500 uppercase">
                                KMJ Licensing Hub · Owner Authority
                            </div>
                            <h1 className="mt-1 text-2xl font-black">
                                KMJ Licensing Hub
                            </h1>
                            <p className="text-muted-foreground mt-2 max-w-3xl text-sm">
                                Super Admin exclusively controls platform-wide
                                product licensing, subscriptions, entitlements,
                                device activations and audit. Customer accounts
                                only see their own subscribed capabilities;
                                unreleased product protocols remain gated until
                                their signed interoperability tests pass.
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
                    id="issuer-workspaces"
                    aria-label="Developer issuer organizations"
                    className="bg-card scroll-mt-6 rounded-2xl border p-5"
                >
                    <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                            <h2 className="font-bold">
                                Developer issuer organizations
                            </h2>
                            <p className="text-muted-foreground mt-1 max-w-3xl text-xs leading-5">
                                AuthSP-style application and developer workflow
                                visibility. These are issuer subscription and
                                registered-app records, not commercial customer
                                licenses. Active KSLP licenses above do not
                                automatically entitle an organization to create
                                apps or generate customer keys.
                            </p>
                        </div>
                        <a
                            href="/developer/apps"
                            className="inline-flex min-h-10 items-center rounded-lg border px-3 text-xs font-bold hover:border-red-500/40"
                        >
                            Open Developer Apps &amp; Keys
                        </a>
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        <div className="rounded-xl border p-3">
                            <p className="text-muted-foreground text-xs">
                                Developer self-service release gate
                            </p>
                            <p className="mt-1 text-sm font-bold">
                                {developerIssuanceEnabled
                                    ? 'Enabled for eligible subscribed issuers'
                                    : 'Protected rollout — disabled'}
                            </p>
                        </div>
                        <div className="rounded-xl border p-3">
                            <p className="text-muted-foreground text-xs">
                                Active issuer subscriptions
                            </p>
                            <p className="mt-1 text-sm font-bold">
                                {metrics.issuerSubscriptions} · distinct from{' '}
                                {metrics.active} active commercial licenses
                            </p>
                        </div>
                    </div>
                    <label
                        className="mt-4 block max-w-lg text-xs font-semibold"
                        htmlFor="issuer-workspace-search"
                    >
                        Search loaded issuer organizations
                    </label>
                    <input
                        id="issuer-workspace-search"
                        type="search"
                        className="bg-background mt-2 h-10 w-full max-w-lg rounded-lg border px-3 text-sm"
                        placeholder="Organization, issuer status or tier"
                        value={issuerSearch}
                        onChange={(event) => {
                            setIssuerSearch(event.target.value);
                            setIssuerPage(0);
                        }}
                    />
                    <div className="mt-4 overflow-x-auto">
                        <table className="w-full min-w-[740px] text-left text-xs">
                            <thead className="text-muted-foreground">
                                <tr>
                                    {[
                                        'Organization',
                                        'Issuer status',
                                        'Tier',
                                        'Apps / limit',
                                        'Monthly issue quota',
                                        'Period end',
                                    ].map((name) => (
                                        <th
                                            className="border-b px-3 py-2"
                                            key={name}
                                        >
                                            {name}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {issuerRows.map((issuer) => (
                                    <tr
                                        className="border-b last:border-0"
                                        key={issuer.id}
                                    >
                                        <td className="px-3 py-3 font-semibold">
                                            {issuer.name}
                                        </td>
                                        <td className="px-3 py-3">
                                            {issuer.issuer_status}
                                        </td>
                                        <td className="px-3 py-3">
                                            {issuer.tier ?? '—'}
                                        </td>
                                        <td className="px-3 py-3">
                                            {issuer.registered_apps} /{' '}
                                            {issuer.product_limit}
                                        </td>
                                        <td className="px-3 py-3">
                                            {issuer.monthly_issue_limit}
                                        </td>
                                        <td className="px-3 py-3">
                                            {issuer.current_period_end ?? '—'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {filteredIssuers.length === 0 && (
                            <p
                                className="text-muted-foreground p-4 text-xs"
                                role="status"
                            >
                                {issuerSearch.trim()
                                    ? 'No matching issuer organizations in the loaded records.'
                                    : 'No issuer organizations available.'}
                            </p>
                        )}
                    </div>
                    <PageControls
                        label="Developer issuer organizations"
                        page={currentIssuerPage}
                        pageCount={issuerPageCount}
                        total={filteredIssuers.length}
                        onPageChange={setIssuerPage}
                    />
                    <p className="text-muted-foreground mt-3 text-xs">
                        Read-only, first 60 organizations. Subscription
                        approval, reseller quotas, commercial settlement, and
                        customer key issuance require their separate verified
                        workflows. This table cannot grant licenses or unlock
                        the release gate.
                    </p>
                </section>
                <section
                    id="developer-workspace"
                    aria-label="Applications, keys and SDK setup"
                    className="bg-card scroll-mt-6 rounded-2xl border border-red-500/20 p-4 sm:p-6"
                >
                    <h2 className="text-xl font-black">
                        Applications, license keys & SDK
                    </h2>
                    <p className="text-muted-foreground mt-2 mb-4 text-sm leading-6">
                        One KMJ Licensing Hub. Developer actions use the same
                        tenant-scoped KSLP authorization as the restricted
                        developer view. Global commercial licensing policy and
                        paid entitlements remain owner-only.
                    </p>
                    <details
                        className="rounded-xl border p-3"
                        open={
                            developerWorkspace.newKey !== null ||
                            (developerWorkspace.newKeys?.length ?? 0) > 0
                        }
                    >
                        <summary className="cursor-pointer rounded-lg px-2 py-3 text-sm font-bold focus-visible:outline-2 focus-visible:outline-red-500">
                            Open application registration, license keys and SDK
                            tools
                        </summary>
                        <div className="mt-3">
                            <DeveloperAppsWorkspace
                                {...developerWorkspace}
                                embedded
                            />
                        </div>
                    </details>
                </section>
                <section
                    id="unverified-accounts"
                    aria-label="Unverified email account cleanup"
                    className="bg-card scroll-mt-6 rounded-2xl border border-amber-500/20 p-5 sm:p-6"
                >
                    <h2 className="text-lg font-black">
                        Unverified email accounts
                    </h2>
                    <p className="text-muted-foreground mt-2 max-w-3xl text-sm leading-6">
                        Only old, standalone accounts without a verified email,
                        owner privileges, recent sessions, passkeys,
                        organization memberships, licensing or other linked
                        business records can be deleted. Verified and linked
                        accounts are protected.
                    </p>
                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                        <div className="rounded-xl border p-4">
                            <div className="text-muted-foreground text-xs">
                                Unverified
                            </div>
                            <div className="mt-1 text-2xl font-black">
                                {unverifiedEmailCleanup.unverified}
                            </div>
                        </div>
                        <div className="rounded-xl border p-4">
                            <div className="text-muted-foreground text-xs">
                                Eligible for removal
                            </div>
                            <div className="mt-1 text-2xl font-black">
                                {cleanupPreviewAvailable
                                    ? unverifiedEmailCleanup.eligible
                                    : '—'}
                            </div>
                        </div>
                        <div className="rounded-xl border p-4">
                            <div className="text-muted-foreground text-xs">
                                Protected or recent
                            </div>
                            <div className="mt-1 text-2xl font-black">
                                {cleanupPreviewAvailable
                                    ? unverifiedEmailCleanup.protected
                                    : '—'}
                            </div>
                        </div>
                    </div>
                    <div className="mt-4 flex flex-wrap items-center gap-3">
                        <button
                            type="button"
                            disabled={
                                purgingUnverified ||
                                !unverifiedEmailCleanup.enabled ||
                                unverifiedEmailCleanup.status !==
                                    'PREVIEW_ONLY' ||
                                unverifiedEmailCleanup.eligible === 0
                            }
                            onClick={() => {
                                if (
                                    !window.confirm(
                                        'Permanently remove exactly ' +
                                            unverifiedEmailCleanup.eligible +
                                            ' old, unverified, standalone accounts? Linked, recent and verified users remain protected. A recent backup and approved rollout are required.',
                                    )
                                ) {
                                    return;
                                }
                                setPurgingUnverified(true);
                                router.post(
                                    '/operator/kslp/unverified-accounts/purge',
                                    {
                                        confirmation:
                                            'REMOVE_UNVERIFIED_EMAIL_USERS',
                                        expected:
                                            unverifiedEmailCleanup.eligible,
                                        sha256: unverifiedEmailCleanup.sha256,
                                    },
                                    {
                                        preserveScroll: true,
                                        onFinish: () =>
                                            setPurgingUnverified(false),
                                    },
                                );
                            }}
                            className="rounded-xl border border-red-500/50 bg-red-600 px-4 py-2 text-xs font-bold text-white disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {purgingUnverified
                                ? 'Verifying and removing…'
                                : 'Remove eligible unverified users'}
                        </button>
                        <span className="text-muted-foreground text-xs">
                            {unverifiedEmailCleanup.enabled
                                ? 'Owner step-up and exact snapshot confirmation required'
                                : 'Cleanup blocked pending protected release and backup approval'}
                        </span>
                    </div>
                    {!cleanupPreviewAvailable && (
                        <p
                            role="status"
                            className="mt-3 text-xs text-amber-600"
                        >
                            {unverifiedEmailCleanup.enabled
                                ? 'Safety preview unavailable: eligibility and protected-account counts were not assessed. No deletion is authorized.'
                                : 'Protected cleanup rollout is disabled: eligibility and protected-account counts were not assessed. No deletion is authorized.'}
                        </p>
                    )}
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
                            aria-label="Customer or organization ID"
                            value={issue.data.customer_id}
                            onChange={(e) =>
                                issue.setData('customer_id', e.target.value)
                            }
                            required
                        />
                        <select
                            className="bg-background h-10 rounded-lg border px-3 text-sm"
                            aria-label="License plan"
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
                            aria-label="Reason for license issuance"
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
                                    {entitlementRows.map((entitlement) => (
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
                            <PageControls
                                label="Product entitlements"
                                page={currentEntitlementPage}
                                pageCount={entitlementPageCount}
                                total={productEntitlements.length}
                                onPageChange={setEntitlementPage}
                            />
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
                        {auditRows.map((e) => (
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
                        {events.length === 0 && (
                            <p
                                className="text-muted-foreground rounded-lg border border-dashed p-4 text-xs"
                                role="status"
                            >
                                No license lifecycle events have been recorded
                                in this view.
                            </p>
                        )}
                    </div>
                    <PageControls
                        label="License lifecycle audit trail"
                        page={currentAuditPage}
                        pageCount={auditPageCount}
                        total={events.length}
                        onPageChange={setAuditPage}
                    />
                </section>
            </div>
        </>
    );
}
