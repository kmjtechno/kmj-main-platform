import { RecordExplainer } from '@/components/customer/record-explainer';
import {
    accessStatusLabel,
    featureLabel,
    isUsableLicenseState,
    licenseStateLabel,
    planLabel,
    productLabel,
} from '@/lib/customer-labels';
import { formatIstDate } from '@/lib/format-ist-date-time';
import { Head, Link } from '@inertiajs/react';
import {
    ArrowRight,
    BadgeCheck,
    CreditCard,
    Crown,
    Download,
    KeyRound,
    Laptop2,
    Package,
    Server,
    ShieldCheck,
    TerminalSquare,
    Users,
    Activity,
    Wrench,
} from 'lucide-react';
import { dashboard } from '@/routes';

type CodeBridgeService = {
    kind: 'codebridge';
    plan: string | null;
    license_status: string;
    license_expires_at: string | null;
    managed_devices: number;
    pending_pairings: number;
    endpoint: string;
    oauth_ready: boolean;
    permissions: string[];
};

type Entitlement = {
    id: string;
    product_id: string;
    product_name: string;
    product_slug: string;
    capability: string;
    status: string;
    starts_at: string;
    service?: CodeBridgeService | null;
    release: {
        id: string;
        version: string;
        digest: string;
        filename: string;
        size_bytes: number | null;
        download_url: string;
    } | null;
};

type Organization = {
    id: string;
    name: string;
    role: string;
    entitlements: Entitlement[];
};

type OwnerProduct = {
    id: string;
    slug: string;
    name: string;
    status: string;
    lifecycle: string;
    is_public: boolean;
    image_path: string | null;
    purchase_enabled: boolean;
    licensing_enabled: boolean;
    active_entitlements: number;
};

type DiscoverableProduct = {
    slug: string;
    name: string;
    lifecycle_label: string;
    purchase_enabled: boolean;
    summary: string;
};

type LicenseRecord = {
    id: string;
    product: string;
    plan: string;
    state: string;
    subject_label: string;
    expires_at: string;
};

type DashboardProps = {
    licenses: LicenseRecord[];
    licenseCount: number;
    organizations: Organization[];
    discoverableProducts: DiscoverableProduct[];
    hasPasskey: boolean;
    canManageCodeBridgeOwnerPlan: boolean;
    ownerProducts: OwnerProduct[] | null;
};

const CHATGPT_DESKTOP_SETUP_URL = '/install-chatgpt-desktop.ps1';

const productImages: Record<string, string> = {
    'kmj-cloudos': '/assets/products/kmj-cloudos.webp',
    'kmj-calibration-pro': '/assets/products/kmj-calibration.webp',
    'kmj-forge': '/assets/products/kmj-forge.webp',
    'kmj-connect': '/assets/products/kmj-connect.webp',
    'kmj-cloud-nexus': '/assets/products/kmj-cloud-nexus.webp',
    'kmj-agent': '/assets/products/kmj-agent.webp',
    'kmj-creative-studio': '/assets/products/kmj-creative-studio.webp',
    'kmj-cinema-platform': '/assets/products/kmj-cinema-platform.webp',
    'kmj-360-dome': '/assets/products/kmj-cinema-platform.webp',
    'kmj-cinema-player': '/assets/products/kmj-cinema-platform.webp',
    'kmj-licensing-hub': '/assets/products/kmj-licensing-hub.webp',
};

export default function Dashboard({
    licenses,
    licenseCount,
    organizations,
    discoverableProducts,
    hasPasskey,
    canManageCodeBridgeOwnerPlan,
    ownerProducts,
}: DashboardProps) {
    const services = organizations.flatMap((organization) =>
        organization.entitlements.map((entitlement) => ({
            ...entitlement,
            organization_name: organization.name,
        })),
    );
    const activeServices = services.filter(
        (entitlement) => entitlement.status === 'active',
    );

    const usableLicenses = licenses.filter((license) =>
        isUsableLicenseState(license.state),
    );

    const availableProducts = discoverableProducts.filter(
        (product) => product.purchase_enabled,
    );
    const upcomingProducts = discoverableProducts.filter(
        (product) => !product.purchase_enabled,
    );
    const renderProduct = (product: DiscoverableProduct) => (
        <article
            key={product.slug}
            className="flex min-w-0 gap-4 rounded-xl border p-4"
        >
            {productImages[product.slug] && (
                <img
                    src={productImages[product.slug]}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    className="bg-muted/30 hidden size-24 shrink-0 rounded-lg border object-contain p-2 sm:block"
                />
            )}
            <div className="flex min-w-0 flex-1 flex-col">
                <h3 className="font-bold">{product.name}</h3>
                <p className="text-muted-foreground mt-1 text-xs">
                    {product.lifecycle_label}
                    {product.purchase_enabled
                        ? ' · You can request access'
                        : ' · Not available to buy yet'}
                </p>
                <p className="text-muted-foreground mt-2 line-clamp-3 text-sm leading-6">
                    {product.summary}
                </p>
                <div className="mt-auto flex flex-wrap gap-x-5 pt-2">
                    {product.purchase_enabled && (
                        <Link
                            href="/purchase"
                            className="inline-flex min-h-11 items-center gap-2 text-sm font-bold text-red-600 dark:text-red-400"
                        >
                            Request access <ArrowRight className="size-4" />
                        </Link>
                    )}
                    <Link
                        href={`/products/${encodeURIComponent(product.slug)}`}
                        className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold hover:underline"
                    >
                        Product details
                    </Link>
                </div>
            </div>
        </article>
    );
    // auto-fit: one product fills the row instead of leaving empty columns.
    const productGrid =
        'grid grid-cols-[repeat(auto-fit,minmax(min(100%,20rem),1fr))] gap-3';

    return (
        <>
            <Head title="My Services" />

            <div className="kmj-premium-dashboard flex h-full min-w-0 flex-1 flex-col gap-6 overflow-x-auto p-4 sm:p-6 lg:p-8">
                <section className="kmj-admin-hero rounded-[1.65rem] p-5 sm:p-8">
                    <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
                        <div className="max-w-2xl">
                            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-red-500/15 bg-red-500/5 px-3 py-1 text-xs font-semibold text-red-500">
                                <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                                KMJ Licensing Hub · Customer access
                            </div>
                            <h1 className="text-3xl font-black tracking-tight sm:text-4xl">
                                My Services
                            </h1>
                            <p className="text-muted-foreground mt-3 max-w-xl text-sm leading-6">
                                Your licenses and the products switched on for
                                your account. Seeing a product in the catalog
                                does not give you access to it.
                            </p>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <Metric
                                label="Usable licenses"
                                value={usableLicenses.length}
                            />
                            <Metric
                                label="Products switched on"
                                value={
                                    new Set(
                                        activeServices.map(
                                            (service) => service.product_id,
                                        ),
                                    ).size
                                }
                            />
                        </div>
                    </div>
                </section>

                {ownerProducts !== null && (
                    <OwnerProductsPanel products={ownerProducts} />
                )}

                {licenses.length > 0 && (
                    <section
                        aria-labelledby="dashboard-licenses-heading"
                        className="bg-card rounded-2xl border p-5 sm:p-6"
                    >
                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <h2
                                id="dashboard-licenses-heading"
                                className="flex items-center gap-2 font-bold"
                            >
                                <KeyRound className="size-5 text-red-500" />
                                Your licenses
                            </h2>
                            <Link
                                href="/licensing#my-licenses"
                                className="inline-flex min-h-11 items-center gap-2 text-sm font-bold text-red-600 dark:text-red-400"
                            >
                                {licenseCount > 3
                                    ? `All ${licenseCount} licenses`
                                    : 'License details'}
                                <ArrowRight className="size-4" />
                            </Link>
                        </div>
                        <ul className="mt-3 grid grid-cols-[repeat(auto-fit,minmax(min(100%,18rem),1fr))] gap-3">
                            {licenses.slice(0, 3).map((license) => (
                                <li
                                    key={license.id}
                                    className="flex flex-wrap items-start justify-between gap-3 rounded-xl border p-4"
                                >
                                    <div className="min-w-0">
                                        <h3 className="font-bold">
                                            {productLabel(license.product)}
                                        </h3>
                                        <p className="text-muted-foreground mt-1 text-sm">
                                            {planLabel(license.plan)} plan ·{' '}
                                            {license.subject_label}
                                        </p>
                                        <p className="text-muted-foreground text-sm">
                                            Expires{' '}
                                            {formatDate(license.expires_at)}
                                        </p>
                                    </div>
                                    <span className="bg-muted rounded-full px-3 py-1 text-xs font-bold">
                                        {licenseStateLabel(license.state)}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    </section>
                )}

                <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                    <div className="flex items-center gap-2">
                        <BadgeCheck className="h-5 w-5 text-red-500" />
                        <h2 className="font-bold">Your products</h2>
                    </div>
                    <p className="text-muted-foreground mt-1 text-sm">
                        Products and features switched on for your organization.
                    </p>

                    {services.length === 0 ? (
                        licenses.length > 0 ? (
                            <div
                                className="bg-muted/20 mt-4 rounded-xl border border-dashed p-5"
                                data-testid="license-without-access"
                            >
                                <p className="text-sm font-bold">
                                    No product access is switched on yet
                                </p>
                                <p className="text-muted-foreground mt-1 max-w-2xl text-sm leading-6">
                                    You do have a license record (shown above).
                                    A license and product access are separate
                                    records, so no product or download appears
                                    here. If you expected one, email{' '}
                                    <a
                                        className="underline"
                                        href="mailto:info@kmjtechno.com"
                                    >
                                        info@kmjtechno.com
                                    </a>
                                    .
                                </p>
                            </div>
                        ) : (
                            <div className="bg-muted/20 mt-4 rounded-xl border border-dashed p-5 sm:p-6">
                                <div className="text-sm font-bold">
                                    No authorized service yet
                                </div>
                                <ol className="text-muted-foreground mt-3 space-y-1 text-sm leading-6">
                                    <li>1. Pick a product from the catalog.</li>
                                    <li>
                                        2. Send a purchase request for your
                                        organization.
                                    </li>
                                    <li>
                                        3. The KMJ team confirms payment and
                                        switches on your access.
                                    </li>
                                </ol>
                                <div className="mt-4 flex flex-wrap gap-3">
                                    <Link
                                        href="/purchase"
                                        className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-bold text-white"
                                    >
                                        Request a product{' '}
                                        <ArrowRight className="size-4" />
                                    </Link>
                                    <Link
                                        href="/products"
                                        className="inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 text-sm font-bold hover:border-red-500/40"
                                    >
                                        Browse products
                                    </Link>
                                </div>
                            </div>
                        )
                    ) : (
                        <div className="mt-5 grid gap-4">
                            {services.map((service) =>
                                service.product_slug === 'kmj-codebridge' ? (
                                    <CodeBridgeCard
                                        key={service.id}
                                        service={service}
                                        canManageOwnerPlan={
                                            canManageCodeBridgeOwnerPlan
                                        }
                                    />
                                ) : (
                                    <GenericServiceCard
                                        key={service.id}
                                        service={service}
                                    />
                                ),
                            )}
                        </div>
                    )}
                </section>

                {ownerProducts === null && (
                    <section className="border-sidebar-border/70 bg-card rounded-2xl border p-5 sm:p-6">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <h2 className="text-lg font-bold">
                                Explore KMJ products
                            </h2>
                            <Link
                                href="/products"
                                className="inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 text-sm font-bold hover:border-red-500/40"
                            >
                                Browse products{' '}
                                <ArrowRight className="size-4" />
                            </Link>
                        </div>

                        {discoverableProducts.length === 0 ? (
                            <p className="text-muted-foreground mt-5 rounded-xl border border-dashed p-5 text-sm">
                                No publicly listed products at present.
                            </p>
                        ) : (
                            <>
                                {availableProducts.length > 0 ? (
                                    <div
                                        className={`mt-4 ${productGrid}`}
                                        data-testid="products-available"
                                    >
                                        {availableProducts.map(renderProduct)}
                                    </div>
                                ) : (
                                    <p className="text-muted-foreground mt-5 rounded-xl border border-dashed p-5 text-sm">
                                        No product accepts access requests right
                                        now.
                                    </p>
                                )}
                                {upcomingProducts.length > 0 && (
                                    <details
                                        className="mt-4 rounded-xl border p-4"
                                        data-testid="products-upcoming"
                                    >
                                        <summary className="min-h-6 cursor-pointer text-sm font-bold">
                                            In development (
                                            {upcomingProducts.length}) · not
                                            available to buy
                                        </summary>
                                        <div className={`mt-4 ${productGrid}`}>
                                            {upcomingProducts.map(
                                                renderProduct,
                                            )}
                                        </div>
                                    </details>
                                )}
                            </>
                        )}
                    </section>
                )}

                {ownerProducts === null && <RecordExplainer />}

                <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                        <div className="flex items-start gap-3">
                            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-red-500/10 text-red-500">
                                <ShieldCheck className="h-5 w-5" />
                            </span>
                            <div>
                                <div className="text-xs font-bold tracking-wider text-red-500 uppercase">
                                    Account security
                                </div>
                                <h2 className="mt-1 font-bold">
                                    {hasPasskey
                                        ? 'Security protection is active'
                                        : 'Add a phishing-resistant passkey'}
                                </h2>
                                <p className="text-muted-foreground mt-1 max-w-2xl text-xs leading-5">
                                    {hasPasskey
                                        ? 'Your KMJ account has a passkey. Manage sign-in and security settings here.'
                                        : 'Add a passkey for stronger sign-in to your KMJ services.'}
                                </p>
                            </div>
                        </div>
                        <Link
                            href="/settings/security"
                            className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-bold transition hover:border-red-500/40 hover:text-red-500"
                        >
                            Security settings
                            <ArrowRight className="h-3.5 w-3.5" />
                        </Link>
                    </div>
                </section>
                <p className="text-muted-foreground text-sm">
                    Do you build software that needs KMJ license keys?{' '}
                    <Link
                        href="/developer/apps"
                        className="inline-flex min-h-11 items-center font-semibold text-red-600 hover:underline dark:text-red-400"
                    >
                        Open Developer Apps
                    </Link>
                </p>
            </div>
        </>
    );
}

function CodeBridgeCard({
    service,
    canManageOwnerPlan,
}: {
    service: Entitlement & { organization_name: string };
    canManageOwnerPlan: boolean;
}) {
    const detail = service.service;
    const permissions = detail?.permissions ?? [];

    return (
        <article className="from-background to-muted/20 overflow-hidden rounded-2xl border bg-gradient-to-br">
            <div className="p-5 sm:p-6">
                <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
                    <div className="flex min-w-0 items-start gap-4">
                        <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl border border-red-500/20 bg-red-500/10 text-red-500">
                            <img
                                src="/assets/kmj-codebridge-icon.png"
                                alt="KMJ CodeBridge product icon"
                                className="size-8 object-contain"
                                loading="lazy"
                            />
                        </span>
                        <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                                <h3 className="text-lg font-black">
                                    KMJ CodeBridge
                                </h3>
                                <StatusBadge status={service.status} />
                            </div>
                            <p className="text-muted-foreground mt-1 text-xs">
                                {service.organization_name}
                            </p>
                            <p className="text-muted-foreground mt-3 max-w-2xl text-sm leading-6">
                                Secure, project-scoped AI coding for authorized
                                computers and VPSs. Inspect code, apply guarded
                                edits and run administrator-approved quality
                                gates from ChatGPT.
                            </p>
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                        <a
                            href={CHATGPT_DESKTOP_SETUP_URL}
                            download
                            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-black text-white transition hover:bg-red-500"
                        >
                            Set up ChatGPT Desktop
                            <ArrowRight className="h-3.5 w-3.5" />
                        </a>
                        <Link
                            href="/services/kmj-codebridge#codebridge-device-control"
                            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-bold transition hover:border-red-500/40 hover:text-red-500"
                        >
                            Manage devices & CodeBridge
                            <ArrowRight className="h-3.5 w-3.5" />
                        </Link>
                        {canManageOwnerPlan && (
                            <Link
                                href="/operator/codebridge/owner-plan"
                                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-red-500/25 bg-red-500/5 px-4 text-xs font-bold text-red-500 transition hover:bg-red-500/10"
                            >
                                Owner plan controls
                                <ShieldCheck className="h-4 w-4" />
                            </Link>
                        )}
                        {service.release && (
                            <a
                                href={service.release.download_url}
                                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-bold transition hover:border-red-500/40 hover:text-red-500"
                            >
                                <Download className="h-3.5 w-3.5" />
                                Download v{service.release.version}
                            </a>
                        )}
                    </div>
                </div>

                <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <ServiceMetric
                        label="License"
                        value={detail?.license_status ?? service.status}
                        hint={
                            detail?.plan
                                ? titleCase(detail.plan) + ' plan'
                                : 'Account access'
                        }
                    />
                    <ServiceMetric
                        label="ChatGPT sign-in"
                        value={detail?.oauth_ready ? 'Ready' : 'Setup required'}
                        hint="Secure connection"
                    />
                    <ServiceMetric
                        label="Managed devices"
                        value={detail?.managed_devices ?? 0}
                        hint={
                            detail?.pending_pairings
                                ? detail.pending_pairings + ' pairing pending'
                                : 'Project-scoped access'
                        }
                    />
                    <ServiceMetric
                        label="License valid until"
                        value={formatDate(detail?.license_expires_at)}
                        hint="From your license"
                    />
                </div>

                <div className="mt-5 grid gap-3 lg:grid-cols-[1.25fr_1fr]">
                    <div className="rounded-xl border bg-black/5 p-4 dark:bg-white/[0.02]">
                        <div className="flex items-center gap-2 text-xs font-black">
                            <Server className="h-4 w-4 text-red-500" />
                            Connection
                        </div>
                        <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                            <code className="bg-muted/60 overflow-x-auto rounded-lg px-3 py-2 text-[11px]">
                                {detail?.endpoint ||
                                    'https://kmjtechno.com/mcp'}
                            </code>
                            <span className="inline-flex items-center gap-1.5 text-[11px] font-bold text-emerald-600 dark:text-emerald-400">
                                <Server className="h-3.5 w-3.5" />
                                Endpoint configured · Live status unverified
                            </span>
                        </div>
                    </div>

                    <div className="rounded-xl border bg-black/5 p-4 dark:bg-white/[0.02]">
                        <div className="text-xs font-black">
                            Authorized capabilities
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                            {permissions.length === 0 && (
                                <span
                                    role="status"
                                    className="text-muted-foreground text-xs"
                                >
                                    No authorized capabilities reported
                                </span>
                            )}
                            {permissions.map((permission) => (
                                <span
                                    key={permission}
                                    className="rounded-lg border px-2.5 py-1 text-xs font-bold uppercase"
                                >
                                    {permission}
                                </span>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="mt-5 grid gap-3 md:grid-cols-3">
                    <Capability
                        icon={Laptop2}
                        title="Inspect projects"
                        text="Read authorized project files, Git status, diffs and history."
                    />
                    <Capability
                        icon={Wrench}
                        title="Guarded edits"
                        text="Make hash-checked file changes only inside authorized projects."
                    />
                    <Capability
                        icon={TerminalSquare}
                        title="Quality gates"
                        text="Run approved checks without exposing unrestricted shell access."
                    />
                </div>
            </div>
        </article>
    );
}

function GenericServiceCard({
    service,
}: {
    service: Entitlement & { organization_name: string };
}) {
    return (
        <article className="bg-background/60 overflow-hidden rounded-xl border">
            <div className="grid gap-4 p-4 sm:grid-cols-[96px_1fr]">
                <div className="bg-muted/30 grid h-24 w-24 place-items-center overflow-hidden rounded-xl border">
                    <img
                        src={
                            productImages[service.product_slug] ??
                            '/assets/brand/kmj-social-card.webp'
                        }
                        alt={service.product_name}
                        loading="lazy"
                        decoding="async"
                        className="h-full w-full object-contain p-2"
                    />
                </div>
                <div className="min-w-0">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <h3 className="font-black">
                                {service.product_name}
                            </h3>
                            <p className="text-muted-foreground mt-1 text-xs">
                                {service.organization_name}
                            </p>
                        </div>
                        <StatusBadge
                            status={accessStatusLabel(service.status)}
                        />
                    </div>
                    <div className="mt-3 rounded-lg border border-red-500/10 bg-red-500/5 px-3 py-2 text-sm">
                        <div className="font-bold">
                            {featureLabel(service.capability)}
                        </div>
                        <p className="text-muted-foreground mt-1">
                            {service.status === 'active'
                                ? 'Switched on for your organization. The product may run its own checks.'
                                : 'Not active: this gives no feature access.'}
                        </p>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-3">
                        <Link
                            href={'/products/' + service.product_slug}
                            className="inline-flex min-h-11 items-center gap-1 text-sm font-bold text-red-500"
                        >
                            Product details
                            <ArrowRight className="h-3 w-3" />
                        </Link>
                        {service.release && (
                            <a
                                href={service.release.download_url}
                                className="inline-flex min-h-11 items-center gap-1 text-sm font-black text-emerald-600 dark:text-emerald-400"
                            >
                                <Download className="h-3 w-3" />
                                Download v{service.release.version}
                            </a>
                        )}
                    </div>
                </div>
            </div>
        </article>
    );
}

function Capability({
    icon: Icon,
    title,
    text,
}: {
    icon: typeof Laptop2;
    title: string;
    text: string;
}) {
    return (
        <div className="rounded-xl border p-4">
            <Icon className="h-4 w-4 text-red-500" />
            <div className="mt-3 text-xs font-black">{title}</div>
            <p className="text-muted-foreground mt-1 text-[11px] leading-5">
                {text}
            </p>
        </div>
    );
}

function ServiceMetric({
    label,
    value,
    hint,
}: {
    label: string;
    value: string | number;
    hint: string;
}) {
    return (
        <div className="bg-background/70 rounded-xl border px-4 py-3">
            <div className="text-muted-foreground text-xs font-bold tracking-wider uppercase">
                {label}
            </div>
            <div className="mt-1 text-sm font-black">{value}</div>
            <div className="text-muted-foreground mt-1 text-xs">{hint}</div>
        </div>
    );
}

function OwnerProductsPanel({ products }: { products: OwnerProduct[] }) {
    const publicCount = products.filter((p) => p.is_public).length;
    const activeLicensing = products.filter((p) => p.licensing_enabled).length;
    return (
        <section
            id="owner-products"
            aria-labelledby="owner-products-heading"
            className="kmj-admin-hero rounded-[1.65rem] p-6 sm:p-8"
        >
            <div className="flex flex-col items-start justify-between gap-5 lg:flex-row lg:items-center">
                <div className="flex items-start gap-3">
                    <span className="grid size-12 shrink-0 place-items-center rounded-2xl border border-red-500/20 bg-red-500/10 text-red-500">
                        <Crown className="size-6" />
                    </span>
                    <div>
                        <h2
                            id="owner-products-heading"
                            className="text-xl font-extrabold tracking-tight sm:text-2xl"
                        >
                            Super Admin Control Center
                        </h2>
                        <p className="text-muted-foreground mt-1 max-w-xl text-sm">
                            Find the right task in one owner-only command
                            center. People, products, revenue and operations are
                            clearly grouped; your personal services stay
                            separate below.
                        </p>
                        <p
                            className="text-muted-foreground mt-2 text-xs"
                            role="status"
                        >
                            {products.length} products · {publicCount} public ·{' '}
                            {activeLicensing} licensing-enabled
                        </p>
                    </div>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Link
                        href="/operator"
                        className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-semibold text-white hover:bg-red-500"
                    >
                        Open Command Center <ArrowRight className="size-4" />
                    </Link>
                    <Link
                        href="/operator/kslp"
                        className="hover:bg-accent border-border/80 bg-card/60 inline-flex min-h-11 items-center gap-2 rounded-xl border px-5 text-sm font-semibold transition"
                    >
                        Licensing Hub · Owner <KeyRound className="size-4" />
                    </Link>
                </div>
            </div>
            <nav
                aria-label="Super Admin quick access"
                className="border-border/60 mt-6 grid gap-3 border-t pt-6 sm:grid-cols-2 xl:grid-cols-4"
            >
                {[
                    {
                        title: 'Product catalog',
                        detail: 'Publish and configure products',
                        href: '/operator/products',
                        icon: Package,
                    },
                    {
                        title: 'Customers',
                        detail: 'Accounts and organizations',
                        href: '/operator/directory',
                        icon: Users,
                    },
                    {
                        title: 'Payment controls',
                        detail: 'Gateway status and credentials',
                        href: '/operator/payments',
                        icon: CreditCard,
                    },
                    {
                        title: 'Operations',
                        detail: 'Delivery and backup evidence',
                        href: '/operator/ops',
                        icon: Activity,
                    },
                ].map(({ title, detail, href, icon: Icon }) => (
                    <Link
                        key={href}
                        href={href}
                        className="group border-border/70 bg-card/60 hover:bg-accent/60 flex min-h-24 items-center gap-3 rounded-2xl border p-4 transition hover:-translate-y-0.5 hover:border-red-500/35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500"
                    >
                        <span className="border-border/60 bg-muted/60 grid size-10 shrink-0 place-items-center rounded-xl border">
                            <Icon
                                className="text-foreground/80 size-5"
                                aria-hidden="true"
                            />
                        </span>
                        <span className="min-w-0 flex-1">
                            <span className="block text-sm font-bold">
                                {title}
                            </span>
                            <span className="text-muted-foreground mt-1 block text-xs leading-5">
                                {detail}
                            </span>
                        </span>
                        <ArrowRight
                            className="text-muted-foreground group-hover:text-foreground size-4 shrink-0 transition-transform group-hover:translate-x-1"
                            aria-hidden="true"
                        />
                    </Link>
                ))}
            </nav>
        </section>
    );
}

function StatusBadge({ status }: { status: string }) {
    return (
        <span className="rounded-full border border-emerald-500/15 bg-emerald-500/5 px-2 py-1 text-[11px] font-black text-emerald-600 uppercase dark:text-emerald-400">
            {status}
        </span>
    );
}

function Metric({ label, value }: { label: string; value: number | string }) {
    return (
        <div className="kmj-admin-metric min-w-28 px-4 py-3">
            <div className="text-lg font-black">{value}</div>
            <div className="text-muted-foreground mt-0.5 text-xs">{label}</div>
        </div>
    );
}

function titleCase(value: string): string {
    return value
        .split(/[-_]/)
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ');
}

function formatDate(value?: string | null): string {
    if (!value) return '—';
    return formatIstDate(value, value);
}

Dashboard.layout = {
    breadcrumbs: [
        {
            title: 'My Services',
            href: dashboard(),
        },
    ],
};
