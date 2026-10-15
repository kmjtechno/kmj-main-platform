import { Link } from '@inertiajs/react';
import OperatorWorkspaceMap from '@/components/operator-workspace-map';
import {
    Activity,
    ArrowRight,
    Boxes,
    CreditCard,
    KeyRound,
    Package,
    ShieldCheck,
    Users,
} from 'lucide-react';

type CatalogSnapshot = {
    slug: string;
    name: string;
    is_public: boolean;
    licensing_enabled: boolean;
    active_policy_count: number;
};

type OrderSnapshot = {
    status: string;
    fulfillment_state: string;
};

type Props = {
    products: CatalogSnapshot[];
    orders: OrderSnapshot[];
    canonicalProductCount: number;
    missingCanonicalSlugs: string[];
};

const modules = [
    {
        name: 'Product Management',
        description: 'Catalog, categories, visibility and launch stages',
        accent: 'text-violet-600 dark:text-violet-300',
        href: '/operator/products',
        icon: Package,
    },
    {
        name: 'Customers',
        description: 'Account and organization directory',
        accent: 'text-sky-600 dark:text-sky-300',
        href: '/operator/directory',
        icon: Users,
    },
    {
        name: 'Licensing Center',
        description: 'Owner-governed plans, entitlements and audit history',
        accent: 'text-amber-700 dark:text-amber-300',
        href: '/operator/kslp',
        icon: KeyRound,
    },
    {
        name: 'Payment Gateways',
        description: 'Credentials readiness, webhooks and transaction proof',
        accent: 'text-emerald-700 dark:text-emerald-300',
        href: '/operator/payments',
        icon: CreditCard,
    },
    {
        name: 'CodeBridge',
        description: 'Device permissions and owner plan controls',
        accent: 'text-rose-600 dark:text-rose-300',
        href: '/operator/codebridge/owner-plan',
        icon: Boxes,
    },
    {
        name: 'Operations',
        description: 'Infrastructure, backup and release verification',
        accent: 'text-cyan-700 dark:text-cyan-300',
        href: '/operator/ops',
        icon: Activity,
    },
] as const;

function SummaryMetric({
    label,
    count,
    description,
}: {
    label: string;
    count: number;
    description: string;
}) {
    return (
        <div className="kmj-admin-metric p-5">
            <p className="text-muted-foreground text-sm">{label}</p>
            <p className="mt-2 text-3xl font-bold tracking-tight tabular-nums">
                {count}
            </p>
            <p className="text-muted-foreground mt-1 text-xs leading-5">
                {description}
            </p>
        </div>
    );
}

export default function OperatorControlOverview({
    products,
    orders,
    canonicalProductCount,
    missingCanonicalSlugs,
}: Props) {
    const publicProducts = products.filter((product) => product.is_public);
    const licensingProducts = products.filter(
        (product) => product.licensing_enabled,
    );
    const publicWithoutPolicy = publicProducts.filter(
        (product) => product.active_policy_count === 0,
    );
    const awaitingConfirmation = orders.filter(
        (order) => order.status === 'requested',
    ).length;
    const readyForFulfillment = orders.filter(
        (order) => order.fulfillment_state === 'ready',
    ).length;

    const actionItems = [
        {
            label: 'Payment confirmation',
            count: awaitingConfirmation,
            detail: 'Orders requiring manual payment evidence review',
            href: '/operator#commercial-orders',
        },
        {
            label: 'Entitlement fulfillment',
            count: readyForFulfillment,
            detail: 'Confirmed orders awaiting explicit entitlement issuance',
            href: '/operator#commercial-orders',
        },
        {
            label: 'Catalog reconciliation',
            count: missingCanonicalSlugs.length,
            detail: 'Canonical product entries not present in the current catalog',
            href: '/operator/products',
        },
    ].filter((item) => item.count > 0);

    return (
        <div className="space-y-6">
            {actionItems.length > 0 && (
                <section
                    aria-labelledby="owner-attention-queue"
                    className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.035] p-5 sm:p-6"
                >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                            <p className="text-xs font-bold tracking-widest text-amber-700 uppercase dark:text-amber-300">
                                Owner action snapshot
                            </p>
                            <h2
                                id="owner-attention-queue"
                                className="mt-2 text-xl font-extrabold tracking-tight"
                            >
                                Needs attention
                            </h2>
                        </div>
                        <span className="rounded-full border border-amber-500/25 px-3 py-1.5 text-xs font-semibold text-amber-700 dark:text-amber-300">
                            {actionItems.length} review{' '}
                            {actionItems.length === 1 ? 'area' : 'areas'}
                        </span>
                    </div>
                    <p className="text-muted-foreground mt-2 text-xs leading-5">
                        Based on the current catalog and displayed recent orders
                        — not a live payment provider health check.
                    </p>
                    <div className="mt-5 grid gap-3 md:grid-cols-3">
                        {actionItems.map((item) => (
                            <Link
                                key={item.label}
                                href={item.href}
                                className="group border-border/70 bg-card/70 hover:bg-accent/50 flex min-h-28 items-start gap-4 rounded-xl border p-4 transition hover:border-amber-500/30 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500"
                            >
                                <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-amber-500/10 text-lg font-black text-amber-700 tabular-nums dark:text-amber-300">
                                    {item.count}
                                </span>
                                <span className="min-w-0 flex-1">
                                    <span className="block text-sm font-bold">
                                        {item.label}
                                    </span>
                                    <span className="text-muted-foreground mt-1 block text-xs leading-5">
                                        {item.detail}
                                    </span>
                                </span>
                                <ArrowRight
                                    className="text-muted-foreground mt-1 size-4 shrink-0 transition-transform group-hover:translate-x-1"
                                    aria-hidden="true"
                                />
                            </Link>
                        ))}
                    </div>
                </section>
            )}
            <OperatorWorkspaceMap />
            <details className="rounded-2xl border border-border/70 bg-card/35 p-4 sm:p-5">
                <summary className="cursor-pointer text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500">
                    Advanced module index
                    <span className="text-muted-foreground ml-2 text-xs font-normal">Open the legacy six-module directory</span>
                </summary>
                <div className="mt-4">
            <section
                className="bg-card rounded-2xl border p-5 sm:p-6"
                aria-labelledby="control-modules-title"
            >
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                        <p className="text-muted-foreground text-xs font-semibold tracking-widest uppercase">
                            Super Admin workspace
                        </p>
                        <h2
                            id="control-modules-title"
                            className="mt-2 text-xl font-bold tracking-tight"
                        >
                            Manage your platform
                        </h2>
                        <p className="text-muted-foreground mt-2 max-w-2xl text-sm leading-6">
                            Each area has its own controls. Product visibility,
                            accepting payments and issuing a customer license
                            remain separate, permission-gated actions.
                        </p>
                    </div>
                    <span className="inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-semibold">
                        <ShieldCheck className="size-4 text-emerald-500" />
                        Owner-only access
                    </span>
                </div>
                <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    {modules.map(
                        ({ name, description, href, icon: Icon, accent }) => (
                            <Link
                                key={href}
                                href={href}
                                className="kmj-admin-module-card group focus-visible:ring-ring flex min-h-40 flex-col justify-between gap-5 rounded-2xl border p-5 transition focus-visible:ring-2 focus-visible:outline-none"
                            >
                                <div className="flex items-start justify-between gap-3">
                                    <span className="border-border/60 bg-muted/50 grid size-11 place-items-center rounded-xl border">
                                        <Icon
                                            className={`size-5 ${accent}`}
                                            aria-hidden="true"
                                        />
                                    </span>
                                    <ArrowRight
                                        className="text-muted-foreground group-hover:text-foreground size-4"
                                        aria-hidden="true"
                                    />
                                </div>
                                <div>
                                    <h3 className="text-base font-bold tracking-tight">
                                        {name}
                                    </h3>
                                    <p className="text-muted-foreground mt-1 text-xs leading-5">
                                        {description}
                                    </p>
                                </div>
                            </Link>
                        ),
                    )}
                </div>
            </section>

                </div>
            </details>
            <section
                className="bg-card rounded-2xl border p-5 sm:p-6"
                aria-labelledby="catalog-health-heading"
            >
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <h2
                            id="catalog-health-heading"
                            className="text-lg font-bold"
                        >
                            Catalog overview
                        </h2>
                        <p className="text-muted-foreground mt-1 text-sm">
                            Read-only visibility into product registration and
                            licensing readiness.
                        </p>
                    </div>
                    <Link
                        href="/operator/products"
                        className="inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 text-sm font-semibold hover:border-red-500/40"
                    >
                        Open full inventory
                        <ArrowRight className="size-4" aria-hidden="true" />
                    </Link>
                </div>
                <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <SummaryMetric
                        label="Registered products"
                        count={products.length}
                        description={`Of ${canonicalProductCount} canonical entries`}
                    />
                    <SummaryMetric
                        label="Public listings"
                        count={publicProducts.length}
                        description="Visibility does not imply a sale or license"
                    />
                    <SummaryMetric
                        label="Licensing configured"
                        count={licensingProducts.length}
                        description="Customer entitlements are granted separately"
                    />
                    <SummaryMetric
                        label="Public listings without a policy"
                        count={publicWithoutPolicy.length}
                        description="Review if commercial licensing is intended"
                    />
                </div>
                {missingCanonicalSlugs.length > 0 && (
                    <div
                        role="status"
                        className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4"
                    >
                        <p className="text-sm font-semibold">
                            {missingCanonicalSlugs.length} canonical product
                            registrations need review
                        </p>
                        <p className="text-muted-foreground mt-1 text-xs leading-5">
                            Entries missing from the database do not grant
                            customer access. Reconcile in staging before any
                            audited production sync.
                        </p>
                        <details className="mt-3">
                            <summary className="cursor-pointer text-sm font-semibold">
                                View missing product slugs
                            </summary>
                            <div className="mt-3 flex flex-wrap gap-2">
                                {missingCanonicalSlugs.map((slug) => (
                                    <code
                                        key={slug}
                                        className="bg-background rounded-md border px-2 py-1 text-xs"
                                    >
                                        {slug}
                                    </code>
                                ))}
                            </div>
                        </details>
                    </div>
                )}
            </section>

            <section
                className="bg-card rounded-2xl border p-5 sm:p-6"
                aria-labelledby="owner-attention-heading"
            >
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <h2
                            id="owner-attention-heading"
                            className="text-lg font-bold"
                        >
                            Requires owner review
                        </h2>
                        <p className="text-muted-foreground mt-1 text-sm">
                            Based on the most recent {orders.length} orders
                            shown in this console, not a live payment gateway
                            health signal.
                        </p>
                    </div>
                    <a
                        href="#commercial-orders"
                        className="inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 text-sm font-semibold hover:border-red-500/40"
                    >
                        View recent orders
                        <ArrowRight className="size-4" aria-hidden="true" />
                    </a>
                </div>
                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                    <SummaryMetric
                        label="Awaiting payment confirmation"
                        count={awaitingConfirmation}
                        description="Verify external payment evidence before confirmation"
                    />
                    <SummaryMetric
                        label="Ready for explicit fulfillment"
                        count={readyForFulfillment}
                        description="Entitlement issuance requires a separate owner action"
                    />
                </div>
            </section>
        </div>
    );
}
