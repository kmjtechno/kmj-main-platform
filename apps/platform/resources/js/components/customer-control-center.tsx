import { Link } from '@inertiajs/react';
import { useMemo, useState } from 'react';
import {
    Activity,
    ArrowRight,
    ArrowUpRight,
    Building2,
    Cable,
    CalendarDays,
    CheckCircle2,
    Download,
    FolderKanban,
    KeyRound,
    Layers3,
    LockKeyhole,
    Plus,
    Search,
    ShieldCheck,
    ShoppingBag,
    Sparkles,
} from 'lucide-react';
import LockedBrand from '@/components/locked-brand';

type Release = {
    version: string;
    download_url: string;
} | null;

type CodeBridgeDetails = {
    kind: 'codebridge';
    plan: string | null;
    managed_devices: number;
    pending_pairings: number;
    license_expires_at: string | null;
    oauth_ready: boolean;
};

type Entitlement = {
    id: string;
    product_slug: string;
    product_name: string;
    capability: string;
    status: string;
    service?: CodeBridgeDetails | null;
    release: Release;
};

type Organization = {
    id: string;
    name: string;
    role: string;
    entitlements: Entitlement[];
};

type CatalogProduct = {
    slug: string;
    name: string;
    summary: string;
    category: string;
    lifecycle_label: string;
    purchase_enabled: boolean;
    image_path?: string | null;
};

type Props = {
    organizations: Organization[];
    catalog: CatalogProduct[];
    hasPasskey: boolean;
};

type ServiceRow = Entitlement & {
    organization_id: string;
    organization_name: string;
};

const actionClass =
    'inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/[0.05] px-3 text-xs font-semibold text-zinc-100 transition hover:border-red-400/60 hover:bg-red-500/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-400';
const primaryClass =
    'inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-bold text-white transition hover:bg-red-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-400';
const panelClass = 'rounded-2xl border border-white/10 bg-[#101217] p-4 sm:p-5';

const legacyProductImages: Record<string, string> = {
    'kmj-codebridge': '/assets/brand/kmj-mark.webp',
    'kmj-omnidesk': '/assets/products/kmj-omnidesk.webp',
    'kmj-cloudos': '/assets/products/kmj-cloudos.webp',
    'kmj-calibration-pro': '/assets/products/kmj-calibration.webp',
    'kmj-cinema-platform': '/assets/products/kmj-cinema-platform.webp',
    'kmj-forge': '/assets/products/kmj-forge.webp',
    'kmj-cloud-nexus': '/assets/products/kmj-cloud-nexus.webp',
};

function imageFor(product: { slug: string; image_path?: string | null }) {
    return (
        product.image_path ||
        legacyProductImages[product.slug] ||
        '/assets/brand/kmj-mark.webp'
    );
}

function statusAppearance(status: string) {
    if (status === 'active') {
        return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
    }
    if (status === 'pending' || status === 'trial') {
        return 'border-amber-500/30 bg-amber-500/10 text-amber-300';
    }
    return 'border-zinc-500/30 bg-zinc-500/10 text-zinc-300';
}

function Status({ status }: { status: string }) {
    return (
        <span
            className={
                'inline-flex items-center rounded-lg border px-2 py-1 text-[10px] font-semibold capitalize ' +
                statusAppearance(status)
            }
        >
            {status.replaceAll('_', ' ')}
        </span>
    );
}

function Stat({
    icon: Icon,
    label,
    value,
    detail,
}: {
    icon: typeof Layers3;
    label: string;
    value: string | number;
    detail: string;
}) {
    return (
        <div className="min-w-0 rounded-2xl border border-white/10 bg-[#12141a] p-4">
            <div className="flex items-center gap-2 text-zinc-300">
                <Icon className="h-4 w-4 text-red-400" aria-hidden="true" />
                <span className="text-xs font-medium">{label}</span>
            </div>
            <div
                className={
                    'mt-3 font-bold tracking-tight text-white ' +
                    (typeof value === 'string' && value.length > 8
                        ? 'text-base sm:text-lg'
                        : 'text-3xl')
                }
            >
                {value}
            </div>
            <div className="mt-1 text-[11px] text-zinc-400">{detail}</div>
        </div>
    );
}

function ServiceCard({
    row,
    catalogProduct,
}: {
    row: ServiceRow;
    catalogProduct?: CatalogProduct;
}) {
    const isCodeBridge = row.product_slug === 'kmj-codebridge';
    const managedUrl =
        isCodeBridge && row.status === 'active'
            ? '/services/kmj-codebridge?organization=' +
              encodeURIComponent(row.organization_id)
            : '/services/entitlements/' + encodeURIComponent(row.id);

    return (
        <article className="flex min-w-0 flex-col justify-between rounded-2xl border border-white/10 bg-[#14161c] p-4 transition hover:border-red-500/35">
            <div>
                <div className="flex items-start justify-between gap-3">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-white/10 bg-black/30 p-2">
                        <img
                            src={imageFor({
                                slug: row.product_slug,
                                image_path: catalogProduct?.image_path,
                            })}
                            alt=""
                            loading="lazy"
                            className="h-full w-full object-contain"
                        />
                    </div>
                    <Status status={row.status} />
                </div>
                <h3 className="mt-4 text-base font-bold text-white">
                    {row.product_name}
                </h3>
                <p className="mt-1 truncate text-xs text-zinc-300">
                    {row.organization_name}
                </p>
                <p className="mt-3 line-clamp-2 min-h-10 text-xs leading-5 text-zinc-400">
                    {row.capability}
                </p>
                {isCodeBridge && row.service?.kind === 'codebridge' && (
                    <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-zinc-300">
                        <span className="rounded-md bg-white/5 px-2 py-1">
                            {row.service.managed_devices} enrolled devices
                        </span>
                        {row.service.pending_pairings > 0 && (
                            <span className="rounded-md bg-amber-500/10 px-2 py-1 text-amber-300">
                                {row.service.pending_pairings} pending pairing
                            </span>
                        )}
                    </div>
                )}
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-2">
                <Link href={managedUrl} className={primaryClass}>
                    Manage service
                    <ArrowUpRight className="h-3.5 w-3.5" />
                </Link>
                {row.release && (
                    <a
                        href={row.release.download_url}
                        className={actionClass}
                    >
                        <Download className="h-3.5 w-3.5" />
                        v{row.release.version}
                    </a>
                )}
            </div>
        </article>
    );
}

export default function CustomerControlCenter({
    organizations,
    catalog,
    hasPasskey,
}: Props) {
    const [organizationId, setOrganizationId] = useState('all');
    const purchaseUrl =
        organizationId === 'all'
            ? '/purchase'
            : '/purchase?organization=' +
              encodeURIComponent(organizationId);
    const [query, setQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const selectedOrganizations = useMemo(
        () =>
            organizationId === 'all'
                ? organizations
                : organizations.filter((item) => item.id === organizationId),
        [organizationId, organizations],
    );
    const services = useMemo<ServiceRow[]>(
        () =>
            selectedOrganizations.flatMap((organization) =>
                organization.entitlements
                    .filter(
                        (entitlement) =>
                            entitlement.product_slug !==
                                'kmj-main-platform-sandbox' &&
                            entitlement.capability !==
                                'sandbox.product.access',
                    )
                    .map((entitlement) => ({
                        ...entitlement,
                        organization_id: organization.id,
                        organization_name: organization.name,
                    })),
            ),
        [selectedOrganizations],
    );
    // An entitlement owned by one organization does not make a product
    // unavailable to the customer's other organizations. In the "all" view,
    // retain the discovery cards and require organization selection at checkout.
    const ownedSlugs = useMemo(
        () =>
            new Set(
                organizationId === 'all'
                    ? []
                    : services.map((item) => item.product_slug),
            ),
        [organizationId, services],
    );
    const visibleServices = useMemo(
        () =>
            services.filter((service) => {
                const matchesQuery = [
                    service.product_name,
                    service.product_slug,
                    service.organization_name,
                    service.capability,
                ]
                    .join(' ')
                    .toLowerCase()
                    .includes(query.trim().toLowerCase());
                return (
                    matchesQuery &&
                    (statusFilter === 'all' ||
                        (statusFilter === 'active'
                            ? service.status === 'active'
                            : service.status !== 'active'))
                );
            }),
        [query, services, statusFilter],
    );
    const catalogBySlug = useMemo(
        () =>
            new Map<string, CatalogProduct>(
                catalog.map((product) => [product.slug, product] as const),
            ),
        [catalog],
    );
    const availableProducts = catalog.filter(
        (product) =>
            !ownedSlugs.has(product.slug) &&
            [product.name, product.summary, product.category]
                .join(' ')
                .toLowerCase()
                .includes(query.trim().toLowerCase()),
    );
    const activeCount = services.filter(
        (service) => service.status === 'active',
    ).length;
    const actionCount = services.length - activeCount;
    const codebridgeDeviceCount = selectedOrganizations.reduce(
        (total, organization) =>
            total +
            Math.max(
                0,
                ...organization.entitlements
                    .filter((item) => item.service?.kind === 'codebridge')
                    .map((item) => item.service?.managed_devices ?? 0),
            ),
        0,
    );
    const codebridgeOwned = services.some(
        (service) =>
            service.product_slug === 'kmj-codebridge' &&
            service.status === 'active',
    );
    const categoryTotals = services.reduce<Record<string, number>>(
        (totals, service) => {
            const category =
                catalogBySlug.get(service.product_slug)?.category ??
                'Other authorized services';
            totals[category] = (totals[category] ?? 0) + 1;
            return totals;
        },
        {},
    );
    const sortedCategories = Object.entries(categoryTotals).sort(
        (left, right) => right[1] - left[1],
    );
    const nextRenewalDates = services
        .filter((item) => item.service?.kind === 'codebridge')
        .map((item) => item.service?.license_expires_at)
        .filter((date): date is string => Boolean(date))
        .map((date) => new Date(date))
        .filter((date) => !Number.isNaN(date.getTime()))
        .sort((a, b) => a.getTime() - b.getTime());
    const nextRenewal = nextRenewalDates[0];
    const readyRenewal = nextRenewal
        ? new Intl.DateTimeFormat('en', {
              day: '2-digit',
              month: 'short',
              year: 'numeric',
          }).format(nextRenewal)
        : 'Not available';

    return (
        <div className="min-w-0 space-y-5 bg-[#090a0f] p-4 text-white sm:p-6 lg:p-8">
            <section className="relative overflow-hidden rounded-2xl border border-red-500/20 bg-gradient-to-br from-[#191018] via-[#101116] to-[#0b0d12] p-5 sm:p-7">
                <div className="pointer-events-none absolute -right-24 -top-32 h-80 w-80 rounded-full bg-red-600/10 blur-3xl" />
                <div className="relative flex flex-col justify-between gap-5 md:flex-row md:items-center">
                    <div>
                        <LockedBrand compact className="mb-5" />
                        <div className="inline-flex items-center gap-2 rounded-full border border-red-500/25 bg-red-500/10 px-3 py-1 text-[11px] font-semibold text-red-200">
                            <Sparkles className="h-3.5 w-3.5" />
                            Customer Control Center
                        </div>
                        <h1 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">
                            All your KMJ services. One place.
                        </h1>
                        <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-300">
                            View your licensed products, manage verified
                            access, request more services and keep each
                            organization separate.
                        </p>
                    </div>
                    <Link href={purchaseUrl} className={primaryClass}>
                        <ShoppingBag className="h-4 w-4" />
                        Add services
                        <ArrowRight className="h-4 w-4" />
                    </Link>
                </div>
            </section>

            <div className="flex flex-wrap items-center justify-between gap-3">
                <label className="flex items-center gap-2 text-xs font-semibold text-zinc-200">
                    <Building2 className="h-4 w-4 text-red-400" />
                    Organization
                    <select
                        aria-label="Choose organization"
                        className="max-w-[240px] rounded-lg border border-white/15 bg-[#16181d] px-3 py-2 text-xs text-white"
                        value={organizationId}
                        onChange={(event) =>
                            setOrganizationId(event.target.value)
                        }
                    >
                        <option value="all">All authorized organizations</option>
                        {organizations.map((organization) => (
                            <option
                                key={organization.id}
                                value={organization.id}
                            >
                                {organization.name}
                            </option>
                        ))}
                    </select>
                </label>
                <span className="text-[11px] text-zinc-400">
                    Showing only entitlements granted to your account.
                </span>
            </div>

            <section aria-label="Service overview" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <Stat
                    icon={Layers3}
                    label="Owned products"
                    value={ownedSlugs.size}
                    detail="Unique commercial products"
                />
                <Stat
                    icon={CheckCircle2}
                    label="Active assignments"
                    value={activeCount}
                    detail="Currently active entitlements"
                />
                <Stat
                    icon={Building2}
                    label="Organizations"
                    value={selectedOrganizations.length}
                    detail="Within selected account scope"
                />
                <Stat
                    icon={Cable}
                    label="CodeBridge devices"
                    value={codebridgeDeviceCount}
                    detail="Active enrolled credentials, not live connections"
                />
                <Stat
                    icon={CalendarDays}
                    label="Next known license end"
                    value={readyRenewal}
                    detail="Shown where license dates are available"
                />
            </section>

            <section className={panelClass} aria-labelledby="quick-actions-heading">
                <h2 id="quick-actions-heading" className="flex items-center gap-2 text-sm font-bold">
                    <Activity className="h-4 w-4 text-red-400" />
                    Quick actions
                </h2>
                <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                    <Link href={purchaseUrl} className={actionClass}>
                        <Plus className="h-4 w-4" /> Request services
                    </Link>
                    <Link href="/sandbox-licenses" className={actionClass}>
                        <KeyRound className="h-4 w-4" /> Sandbox license tools
                    </Link>
                    <Link
                        href={
                            codebridgeOwned
                                ? '/services/kmj-codebridge'
                                : '/products/kmj-codebridge'
                        }
                        className={actionClass}
                    >
                        <FolderKanban className="h-4 w-4" />
                        {codebridgeOwned
                            ? 'CodeBridge devices & projects'
                            : 'Explore CodeBridge'}
                    </Link>
                    <Link href="/settings/security" className={actionClass}>
                        <ShieldCheck className="h-4 w-4" /> Account security
                    </Link>
                </div>
            </section>

            <section id="my-services" className={panelClass} aria-labelledby="owned-heading">
                <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
                    <div>
                        <h2 id="owned-heading" className="text-lg font-bold">
                            My services
                        </h2>
                        <p className="mt-1 text-xs text-zinc-400">
                            {services.length} account-scoped entitlement
                            assignments. Each card links to an actual product
                            or verified management page.
                        </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        <label className="flex min-h-10 items-center gap-2 rounded-xl border border-white/15 bg-[#090a0f] px-3">
                            <Search className="h-4 w-4 text-zinc-400" />
                            <span className="sr-only">Search services</span>
                            <input
                                type="search"
                                value={query}
                                onChange={(event) =>
                                    setQuery(event.target.value)
                                }
                                placeholder="Search services"
                                className="w-36 border-0 bg-transparent py-2 text-xs text-white outline-none placeholder:text-zinc-500"
                            />
                        </label>
                        <select
                            aria-label="Filter service status"
                            value={statusFilter}
                            onChange={(event) =>
                                setStatusFilter(event.target.value)
                            }
                            className="min-h-10 rounded-xl border border-white/15 bg-[#15171c] px-3 text-xs text-white"
                        >
                            <option value="all">All statuses</option>
                            <option value="active">Active</option>
                            <option value="attention">Needs attention</option>
                        </select>
                    </div>
                </div>
                {visibleServices.length === 0 ? (
                    <div className="mt-4 rounded-xl border border-dashed border-white/15 px-5 py-8 text-center text-sm text-zinc-300">
                        {services.length === 0
                            ? 'No commercial services are assigned yet. Sandbox access remains available in Sandbox license tools.'
                            : 'No services match your filters.'}
                        {services.length === 0 && (
                            <div className="mt-4">
                                <Link href={purchaseUrl} className={primaryClass}>
                                    Browse purchasable products
                                </Link>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="mt-4 grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
                        {visibleServices.map((row) => (
                            <ServiceCard
                                key={row.organization_id + ':' + row.id}
                                row={row}
                                catalogProduct={catalogBySlug.get(
                                    row.product_slug,
                                )}
                            />
                        ))}
                    </div>
                )}
            </section>

            <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
                <section className={panelClass} aria-labelledby="distribution-heading">
                    <h2 id="distribution-heading" className="text-sm font-bold">
                        Portfolio distribution
                    </h2>
                    <p className="mt-1 text-[11px] text-zinc-400">
                        Real entitlement count by product category — not
                        estimated revenue or invented usage history.
                    </p>
                    <div className="mt-5 space-y-4">
                        {sortedCategories.length === 0 ? (
                            <p className="text-xs text-zinc-400">
                                Category data appears when a product is assigned.
                            </p>
                        ) : (
                            sortedCategories.map(([category, count]) => (
                                <div key={category}>
                                    <div className="mb-1 flex justify-between gap-3 text-xs">
                                        <span className="min-w-0 truncate text-zinc-200">
                                            {category}
                                        </span>
                                        <span className="font-semibold text-white">
                                            {count}
                                        </span>
                                    </div>
                                    <div
                                        className="h-2 overflow-hidden rounded-full bg-white/10"
                                        role="meter"
                                        aria-label={category + ' assignments'}
                                        aria-valuemin={0}
                                        aria-valuemax={services.length}
                                        aria-valuenow={count}
                                    >
                                        <div
                                            className="h-full rounded-full bg-gradient-to-r from-red-700 to-red-400"
                                            style={{
                                                width:
                                                    (count /
                                                        Math.max(
                                                            1,
                                                            services.length,
                                                        )) *
                                                        100 +
                                                    '%',
                                            }}
                                        />
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </section>
                <section id="access-security" className={panelClass + ' scroll-mt-6'} aria-labelledby="health-heading">
                    <h2 id="health-heading" className="flex items-center gap-2 text-sm font-bold">
                        <LockKeyhole className="h-4 w-4 text-red-400" />
                        Access & entitlements
                    </h2>
                    <div className="mt-4 space-y-3 text-xs">
                        <div className="flex items-center justify-between gap-2 rounded-xl bg-white/[0.04] p-3">
                            <span className="text-zinc-300">Active entitlements</span>
                            <span className="font-semibold text-emerald-300">
                                {activeCount}
                            </span>
                        </div>
                        <div className="flex items-center justify-between gap-2 rounded-xl bg-white/[0.04] p-3">
                            <span className="text-zinc-300">Non-active entitlements</span>
                            <span className="font-semibold text-amber-300">
                                {actionCount}
                            </span>
                        </div>
                        <div className="flex items-center justify-between gap-2 rounded-xl bg-white/[0.04] p-3">
                            <span className="text-zinc-300">Account passkey</span>
                            <span className={hasPasskey ? 'text-emerald-300' : 'text-amber-300'}>
                                {hasPasskey ? 'Enabled' : 'Not configured'}
                            </span>
                        </div>
                        <Link
                            href="/settings/security"
                            className="inline-flex items-center gap-2 font-semibold text-red-300 underline-offset-4 hover:underline"
                        >
                            Review account security
                            <ArrowRight className="h-3.5 w-3.5" />
                        </Link>
                    </div>
                </section>
            </div>

            <section id="discover-products" className={panelClass} aria-labelledby="catalog-heading">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <h2 id="catalog-heading" className="text-lg font-bold">
                            Discover more KMJ products
                        </h2>
                        <p className="mt-1 text-xs text-zinc-400">
                            Availability and commercial eligibility come from
                            the actual product catalog.
                        </p>
                    </div>
                    <Link href="/products" className={actionClass}>
                        All products <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                </div>
                {availableProducts.length === 0 ? (
                    <p className="mt-5 text-xs text-zinc-400">
                        No additional products match your search.
                    </p>
                ) : (
                    <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        {availableProducts.slice(0, 9).map((product) => (
                            <article
                                key={product.slug}
                                className="flex flex-col justify-between rounded-xl border border-white/10 bg-[#0c0e12] p-4"
                            >
                                <div>
                                    <div className="flex items-center gap-3">
                                        <img
                                            src={imageFor(product)}
                                            alt=""
                                            loading="lazy"
                                            className="h-10 w-10 rounded-lg object-contain"
                                        />
                                        <div className="min-w-0">
                                            <h3 className="truncate text-sm font-bold">
                                                {product.name}
                                            </h3>
                                            <p className="mt-1 text-[10px] text-zinc-400">
                                                {product.category}
                                            </p>
                                        </div>
                                    </div>
                                    <p className="mt-3 line-clamp-2 text-xs leading-5 text-zinc-300">
                                        {product.summary}
                                    </p>
                                </div>
                                <div className="mt-4 flex items-center justify-between gap-2">
                                    <Status status={product.lifecycle_label.toLowerCase()} />
                                    <Link
                                        href={
                                            product.purchase_enabled
                                                ? purchaseUrl +
                                                  (purchaseUrl.includes('?')
                                                      ? '&'
                                                      : '?') +
                                                  'product=' +
                                                  encodeURIComponent(
                                                      product.slug,
                                                  )
                                                : '/products/' +
                                                  encodeURIComponent(
                                                      product.slug,
                                                  )
                                        }
                                        className="inline-flex items-center gap-1 text-xs font-semibold text-red-300 hover:text-red-200"
                                    >
                                        {product.purchase_enabled
                                            ? 'Request access'
                                            : 'Learn more'}
                                        <ArrowRight className="h-3.5 w-3.5" />
                                    </Link>
                                </div>
                            </article>
                        ))}
                    </div>
                )}
            </section>

            <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4 text-[11px] text-zinc-400">
                <span>
                    KMJ Main Platform governs purchases, licenses and access;
                    products remain separate.
                </span>
                <Link href={purchaseUrl} className="inline-flex items-center gap-1 text-red-300">
                    Request additional services
                    <ArrowRight className="h-3 w-3" />
                </Link>
            </footer>
        </div>
    );
}
