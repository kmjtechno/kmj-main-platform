import { Link } from '@inertiajs/react';
import {
    Activity,
    ArrowRight,
    Boxes,
    CreditCard,
    FileClock,
    Globe2,
    KeyRound,
    Mail,
    Package,
    Search,
    ShieldCheck,
    ShoppingCart,
    Users,
    Wrench,
} from 'lucide-react';
import { useMemo, useState } from 'react';

/**
 * Route existence ≠ entitlement, verified operation or production readiness.
 * Only route-backed modules are clickable; roadmap concepts stay informative.
 * This map intentionally does not read or infer tenancy, payment or mail state.
 */
const workspaceGroups = [
    {
        key: 'people',
        title: 'People & access',
        description: 'Accounts, organizations and account safeguards.',
        icon: Users,
        tone: 'text-sky-600 dark:text-sky-300',
        items: [
            { label: 'Customers & Organizations', description: 'Search the owner directory', href: '/operator/directory', icon: Users },
            { label: 'Security settings', description: 'Passkeys and sign-in safeguards', href: '/settings/security', icon: ShieldCheck },
        ],
    },
    {
        key: 'products',
        title: 'Products & lifecycle',
        description: 'Catalog authority, visibility and release evidence.',
        icon: Package,
        tone: 'text-violet-600 dark:text-violet-300',
        items: [
            { label: 'Product Management', description: 'Edit, categorize and govern listings', href: '/operator/products', icon: Package },
            { label: 'Public product catalog', description: 'Review the customer-facing catalog', href: '/products', icon: Globe2 },
        ],
    },
    {
        key: 'commerce',
        title: 'Revenue & entitlements',
        description: 'Payment evidence, commercial orders and license rights.',
        icon: CreditCard,
        tone: 'text-amber-700 dark:text-amber-300',
        items: [
            { label: 'Commercial orders', description: 'Review and confirm order evidence', href: '/operator#commercial-orders', icon: ShoppingCart },
            { label: 'Payment Gateways', description: 'Sandbox credentials and readiness', href: '/operator/payments', icon: CreditCard },
            { label: 'Licensing Center', description: 'Plans, issuance, revocation and audit', href: '/operator/kslp', icon: KeyRound },
        ],
    },
    {
        key: 'operations',
        title: 'Systems & developers',
        description: 'Infrastructure, authorized devices and developer access.',
        icon: Activity,
        tone: 'text-emerald-700 dark:text-emerald-300',
        items: [
            { label: 'Operations', description: 'Health, backups, jobs and audit', href: '/operator/ops', icon: Activity },
            { label: 'CodeBridge Owner Controls', description: 'Govern managed devices and plans', href: '/operator/codebridge/owner-plan', icon: Boxes },
            { label: 'Developer Apps & Keys', description: 'Registered clients and scoped keys', href: '/developer/apps', icon: Wrench },
            { label: 'Sandbox Token Lab', description: 'Inspect the sandbox license lifecycle', href: '/sandbox-licenses', icon: KeyRound },
        ],
    },
] as const;

const roadmapQueue = [
    { label: 'KMJ Mail administration', detail: 'Outbound delivery, inbox and support workflow', icon: Mail },
    { label: 'Support & Trust cases', detail: 'Case queues, incidents and disclosure governance', icon: ShieldCheck },
    { label: 'Content & SEO studio', detail: 'Editorial revisions, locales and publishing approvals', icon: Globe2 },
    { label: 'Release registry', detail: 'Signed artifacts, channels and promotion evidence', icon: FileClock },
] as const;

export default function OperatorWorkspaceMap() {
    const [query, setQuery] = useState('');
    const [showRoadmap, setShowRoadmap] = useState(false);
    const value = query.trim().toLocaleLowerCase();
    const visibleGroups = useMemo(
        () =>
            workspaceGroups
                .map((group) => ({
                    ...group,
                    items: group.items.filter(
                        (item) =>
                            (group.title + ' ' + item.label + ' ' + item.description)
                                .toLocaleLowerCase()
                                .includes(value),
                    ),
                }))
                .filter((group) => group.items.length > 0),
        [value],
    );
    const visibleRoadmap = roadmapQueue.filter(
        (item) =>
            (item.label + ' ' + item.detail)
                .toLocaleLowerCase()
                .includes(value),
    );
    const listRoadmap = value.length > 0 || showRoadmap;

    return (
        <section className="kmj-admin-workspace-map space-y-5" aria-labelledby="workspace-map-heading">
            <header className="kmj-admin-hero flex flex-wrap items-start justify-between gap-5 rounded-[1.6rem] p-5 sm:p-7">
                <div className="max-w-2xl">
                    <span className="text-xs font-bold tracking-[0.14em] text-red-500 uppercase">
                        KMJ TECHNO · Operating workspace
                    </span>
                    <h2 id="workspace-map-heading" className="mt-2 text-2xl font-extrabold tracking-tight sm:text-3xl">
                        Everything in its place.
                    </h2>
                    <p className="text-muted-foreground mt-2 text-sm leading-6">
                        Find the right workspace by task, not by technical module name.
                        Commercial approval, license issuance and production publishing
                        remain independent, audited actions.
                    </p>
                </div>
                <label className="relative block w-full max-w-sm">
                    <Search aria-hidden="true" className="text-muted-foreground pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2" />
                    <span className="sr-only">Search owner tasks and modules</span>
                    <input
                        value={query}
                        type="search"
                        onChange={(event) => setQuery(event.target.value)}
                        aria-label="Search owner tasks and modules"
                        placeholder="Find products, payments, licenses..."
                        className="border-border bg-background/65 focus-visible:ring-ring min-h-12 w-full rounded-xl border pr-4 pl-12 text-sm outline-none focus-visible:ring-2"
                    />
                </label>
            </header>

            <div className="grid gap-4 xl:grid-cols-2" aria-label="Owner task categories">
                {visibleGroups.map((group) => {
                    const GroupIcon = group.icon;
                    return (
                        <section key={group.key} aria-labelledby={'kmj-group-' + group.key} className="kmj-admin-category rounded-2xl p-5 sm:p-6">
                            <div className="flex items-start gap-3">
                                <span className="bg-muted/60 grid size-12 shrink-0 place-items-center rounded-xl border border-border/60">
                                    <GroupIcon aria-hidden="true" className={'size-5 ' + group.tone} />
                                </span>
                                <div className="min-w-0">
                                    <h3 id={'kmj-group-' + group.key} className="text-lg font-bold tracking-tight">
                                        {group.title}
                                    </h3>
                                    <p className="text-muted-foreground mt-1 text-xs leading-5">{group.description}</p>
                                </div>
                            </div>
                            <div className="mt-5 space-y-1.5">
                                {group.items.map((item) => {
                                    const Icon = item.icon;
                                    return (
                                        <Link
                                            key={item.href}
                                            href={item.href}
                                            className="group flex min-h-16 items-center gap-3 rounded-xl border border-transparent px-3 py-2.5 transition hover:border-border/75 hover:bg-accent/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500"
                                        >
                                            <span className="bg-background/70 text-muted-foreground grid size-9 shrink-0 place-items-center rounded-lg border border-border/60">
                                                <Icon aria-hidden="true" className="size-4" />
                                            </span>
                                            <span className="min-w-0 flex-1">
                                                <span className="block text-sm font-semibold">{item.label}</span>
                                                <span className="text-muted-foreground mt-0.5 block text-xs leading-5">{item.description}</span>
                                            </span>
                                            <ArrowRight className="text-muted-foreground group-hover:text-foreground size-4 shrink-0 transition-transform group-hover:translate-x-1" aria-hidden="true" />
                                        </Link>
                                    );
                                })}
                            </div>
                        </section>
                    );
                })}
            </div>

            {visibleGroups.length === 0 && visibleRoadmap.length === 0 && (
                <p role="status" className="bg-card text-muted-foreground rounded-xl border p-5 text-sm">
                    No matching workspace. Try products, customers, orders or operations.
                </p>
            )}

            <section className="rounded-2xl border border-dashed border-border/80 bg-card/45 p-5" aria-labelledby="roadmap-queue-heading">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <h3 id="roadmap-queue-heading" className="text-base font-bold">Future workspace modules</h3>
                        <p className="text-muted-foreground mt-1 text-xs leading-5">
                            Roadmap concepts, not live services or available controls.
                        </p>
                    </div>
                    {!value && (
                        <button
                            type="button"
                            onClick={() => setShowRoadmap((current) => !current)}
                            aria-expanded={showRoadmap}
                            aria-controls="kmj-roadmap-modules"
                            className="border-border bg-card hover:bg-accent min-h-11 rounded-xl border px-4 text-sm font-semibold"
                        >
                            {showRoadmap ? 'Hide roadmap' : 'View roadmap'}
                        </button>
                    )}
                </div>
                {listRoadmap && (
                    <div id="kmj-roadmap-modules" className="mt-4 grid gap-3 sm:grid-cols-2">
                        {visibleRoadmap.map((item) => {
                            const Icon = item.icon;
                            return (
                                <div key={item.label} className="flex items-start gap-3 rounded-xl border border-border/60 bg-muted/30 p-4">
                                    <Icon aria-hidden="true" className="text-muted-foreground mt-1 size-4 shrink-0" />
                                    <div className="min-w-0 flex-1">
                                        <p className="text-sm font-semibold">{item.label}</p>
                                        <p className="text-muted-foreground mt-1 text-xs leading-5">{item.detail}</p>
                                    </div>
                                    <span className="text-muted-foreground rounded-full border border-border/70 px-2 py-1 text-[11px] font-medium">
                                        Planned
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                )}
            </section>
        </section>
    );
}
