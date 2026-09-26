import type { FormEvent } from 'react';
import { Head, Link, useForm } from '@inertiajs/react';
import {
    ArrowRight,
    BadgeCheck,
    Building2,
    CheckCircle2,
    KeyRound,
    Layers3,
    Plus,
} from 'lucide-react';
import { dashboard } from '@/routes';

type Entitlement = {
    id: string;
    product_id: string;
    product_name: string;
    product_slug: string;
    capability: string;
    status: string;
    starts_at: string;
};

type Organization = {
    id: string;
    name: string;
    role: string;
    entitlements: Entitlement[];
};

type DashboardProps = {
    organizations: Organization[];
    hasPasskey: boolean;
};

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
    organizations,
    hasPasskey,
}: DashboardProps) {
    const form = useForm({ name: '' });
    const productAccess = organizations.flatMap((organization) =>
        organization.entitlements.map((entitlement) => ({
            ...entitlement,
            organization_name: organization.name,
        })),
    );
    const entitlementCount = productAccess.length;
    const activeEntitlementCount = productAccess.filter(
        (entitlement) => entitlement.status === 'active',
    ).length;
    const hasOrganization = organizations.length > 0;
    const hasActiveEntitlement = activeEntitlementCount > 0;

    const submit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        form.post('/organizations', {
            preserveScroll: true,
            onSuccess: () => form.reset(),
        });
    };

    return (
        <>
            <Head title="Control Center" />

            <div className="flex h-full flex-1 flex-col gap-6 overflow-x-auto p-4 sm:p-6">
                <section className="border-sidebar-border/70 from-background via-background dark:border-sidebar-border overflow-hidden rounded-2xl border bg-gradient-to-br to-red-950/10 p-6 sm:p-8">
                    <div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
                        <div className="max-w-2xl">
                            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-red-500/15 bg-red-500/5 px-3 py-1 text-xs font-semibold text-red-500">
                                <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                                KMJ Customer Platform · Secure access
                            </div>
                            <h1 className="text-3xl font-black tracking-tight sm:text-4xl">
                                Your products, licenses and organizations
                            </h1>
                            <p className="text-muted-foreground mt-3 max-w-xl text-sm leading-6">
                                Manage KMJ product access from one customer
                                control center. Organizations, entitlements and
                                licensing stay connected to the same governed
                                Main Platform authority.
                            </p>
                        </div>

                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                            <Metric
                                label="Organizations"
                                value={organizations.length}
                            />
                            <Metric label="Products" value={entitlementCount} />
                            <Metric
                                label="Active access"
                                value={activeEntitlementCount}
                            />
                            <Metric label="Platform" value="Online" />
                        </div>
                    </div>
                </section>

                <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
                        <div>
                            <div className="flex items-center gap-2">
                                <BadgeCheck className="h-5 w-5 text-red-500" />
                                <h2 className="font-bold">
                                    My products & licenses
                                </h2>
                            </div>
                            <p className="text-muted-foreground mt-1 text-xs">
                                Product access granted to your organizations
                                from the KMJ Main Platform.
                            </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Link
                                href="/products"
                                className="inline-flex h-9 items-center justify-center gap-2 rounded-xl border px-3 text-xs font-bold transition hover:border-red-500/40 hover:text-red-500"
                            >
                                Explore products
                                <ArrowRight className="h-3.5 w-3.5" />
                            </Link>
                            {hasOrganization && (
                                <Link
                                    href="/purchase"
                                    className="inline-flex h-9 items-center justify-center gap-2 rounded-xl bg-red-600 px-3 text-xs font-bold text-white transition hover:bg-red-500"
                                >
                                    Request access
                                    <ArrowRight className="h-3.5 w-3.5" />
                                </Link>
                            )}
                        </div>
                    </div>

                    {productAccess.length === 0 ? (
                        <div className="bg-muted/20 mt-5 rounded-xl border border-dashed p-7 text-center">
                            <KeyRound className="text-muted-foreground/40 mx-auto h-8 w-8" />
                            <div className="mt-3 text-sm font-bold">
                                No product access yet
                            </div>
                            <p className="text-muted-foreground mx-auto mt-1 max-w-xl text-xs leading-5">
                                Browse the KMJ portfolio, create an organization
                                and request access to commercially available
                                products.
                            </p>
                        </div>
                    ) : (
                        <div className="mt-5 grid gap-3 lg:grid-cols-2">
                            {productAccess.map((entitlement) => (
                                <article
                                    key={entitlement.id}
                                    className="bg-background/60 overflow-hidden rounded-xl border"
                                >
                                    <div className="grid grid-cols-[112px_1fr]">
                                        <img
                                            src={
                                                productImages[
                                                    entitlement.product_slug
                                                ] ??
                                                '/assets/brand/kmj-social-card.webp'
                                            }
                                            alt={entitlement.product_name}
                                            loading="lazy"
                                            decoding="async"
                                            className="h-full min-h-28 w-28 object-cover"
                                        />
                                        <div className="min-w-0 p-4">
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="min-w-0">
                                                    <h3 className="truncate text-sm font-black">
                                                        {
                                                            entitlement.product_name
                                                        }
                                                    </h3>
                                                    <p className="text-muted-foreground mt-1 truncate text-[11px]">
                                                        {
                                                            entitlement.organization_name
                                                        }
                                                    </p>
                                                </div>
                                                <span className="rounded-full border border-emerald-500/15 bg-emerald-500/5 px-2 py-1 text-[9px] font-black text-emerald-600 uppercase dark:text-emerald-400">
                                                    {entitlement.status}
                                                </span>
                                            </div>
                                            <div className="text-muted-foreground mt-3 text-[10px]">
                                                {entitlement.capability}
                                            </div>
                                            <div className="mt-4 flex flex-wrap gap-3">
                                                <Link
                                                    href={
                                                        '/products/' +
                                                        entitlement.product_slug
                                                    }
                                                    className="text-[11px] font-bold text-red-500"
                                                >
                                                    Product details →
                                                </Link>
                                                {entitlement.status ===
                                                    'active' && (
                                                    <Link
                                                        href="/sandbox-licenses"
                                                        className="text-muted-foreground hover:text-foreground text-[11px] font-bold"
                                                    >
                                                        License control →
                                                    </Link>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </article>
                            ))}
                        </div>
                    )}
                </section>
                {!hasPasskey && (
                    <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                            <div>
                                <div className="text-xs font-bold tracking-wider text-red-500 uppercase">
                                    Account security
                                </div>
                                <h2 className="mt-1 font-bold">
                                    Add a phishing-resistant passkey
                                </h2>
                                <p className="text-muted-foreground mt-1 max-w-2xl text-xs leading-5">
                                    Your account is active, but no passkey is
                                    enrolled yet. Add one from Security settings
                                    for faster and stronger sign-in.
                                </p>
                            </div>
                            <Link
                                href="/settings/security"
                                className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-bold transition hover:border-red-500/40 hover:text-red-500"
                            >
                                Add passkey
                                <ArrowRight className="h-3.5 w-3.5" />
                            </Link>
                        </div>
                    </section>
                )}

                {hasOrganization && (
                    <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                            <div>
                                <div className="text-xs font-bold tracking-wider text-red-500 uppercase">
                                    Customer actions
                                </div>
                                <h2 className="mt-1 font-bold">
                                    {hasActiveEntitlement
                                        ? 'Your product access is ready'
                                        : 'Your organization is ready for product access'}
                                </h2>
                                <p className="text-muted-foreground mt-1 max-w-2xl text-xs leading-5">
                                    {hasActiveEntitlement
                                        ? 'Manage licenses, review your products or request additional commercial access from one place.'
                                        : 'Browse commercially available KMJ products and submit an access request for this organization.'}
                                </p>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <Link
                                    href="/purchase"
                                    className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-bold text-white transition hover:bg-red-500"
                                >
                                    Purchase center
                                    <ArrowRight className="h-3.5 w-3.5" />
                                </Link>
                                {hasActiveEntitlement && (
                                    <Link
                                        href="/sandbox-licenses"
                                        className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-bold transition hover:border-red-500/40 hover:text-red-500"
                                    >
                                        License center
                                        <KeyRound className="h-3.5 w-3.5" />
                                    </Link>
                                )}
                            </div>
                        </div>
                    </section>
                )}
                <div className="grid gap-6 xl:grid-cols-[380px_1fr]">
                    <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                        <div className="flex items-center gap-3">
                            <span className="grid h-10 w-10 place-items-center rounded-xl bg-red-500/10 text-red-500">
                                <Plus className="h-5 w-5" />
                            </span>
                            <div>
                                <h2 className="font-bold">
                                    Create organization
                                </h2>
                                <p className="text-muted-foreground text-xs">
                                    Create a workspace for product access and
                                    licensing
                                </p>
                            </div>
                        </div>

                        <form onSubmit={submit} className="mt-6 space-y-4">
                            <div>
                                <label
                                    htmlFor="organization-name"
                                    className="text-xs font-semibold"
                                >
                                    Organization name
                                </label>
                                <input
                                    id="organization-name"
                                    value={form.data.name}
                                    onChange={(event) =>
                                        form.setData('name', event.target.value)
                                    }
                                    placeholder="Example: KMJ Product Lab"
                                    className="border-input bg-background mt-2 h-11 w-full rounded-xl border px-3 text-sm transition outline-none focus:border-red-500/50 focus:ring-2 focus:ring-red-500/10"
                                    autoComplete="organization"
                                    required
                                    minLength={2}
                                    maxLength={160}
                                />
                                {form.errors.name && (
                                    <p className="text-destructive mt-2 text-xs">
                                        {form.errors.name}
                                    </p>
                                )}
                            </div>

                            <button
                                type="submit"
                                disabled={form.processing}
                                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-bold text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                {form.processing
                                    ? 'Creating workspace…'
                                    : 'Create organization'}
                                {!form.processing && (
                                    <ArrowRight className="h-4 w-4" />
                                )}
                            </button>
                        </form>

                        <div className="mt-6 space-y-3 border-t pt-5">
                            <FlowStep
                                icon={Building2}
                                text="Create your organization workspace"
                            />
                            <FlowStep
                                icon={Layers3}
                                text="Request access to available KMJ products"
                            />
                            <FlowStep
                                icon={BadgeCheck}
                                text="Receive governed product entitlement"
                            />
                            <FlowStep
                                icon={KeyRound}
                                text="Manage the license lifecycle from one place"
                            />
                        </div>
                    </section>

                    <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                        <div className="flex items-center justify-between gap-4">
                            <div>
                                <h2 className="font-bold">
                                    Organizations & product access
                                </h2>
                                <p className="text-muted-foreground mt-1 text-xs">
                                    Customer workspaces connected to your KMJ
                                    account
                                </p>
                            </div>
                            <span className="text-muted-foreground rounded-full border px-2.5 py-1 text-[10px] font-semibold">
                                Secure account authority
                            </span>
                        </div>

                        {organizations.length === 0 ? (
                            <div className="bg-muted/20 mt-8 grid min-h-72 place-items-center rounded-xl border border-dashed p-8 text-center">
                                <div>
                                    <Building2 className="text-muted-foreground/40 mx-auto h-9 w-9" />
                                    <h3 className="mt-4 text-sm font-bold">
                                        No organization yet
                                    </h3>
                                    <p className="text-muted-foreground mx-auto mt-2 max-w-sm text-xs leading-5">
                                        Create your first organization to
                                        request product access and manage
                                        licenses from this customer portal.
                                    </p>
                                </div>
                            </div>
                        ) : (
                            <div className="mt-5 space-y-4">
                                {organizations.map((organization) => (
                                    <article
                                        key={organization.id}
                                        className="bg-background/60 rounded-xl border p-4 sm:p-5"
                                    >
                                        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                                            <div className="flex items-start gap-3">
                                                <span className="bg-muted grid h-10 w-10 shrink-0 place-items-center rounded-xl">
                                                    <Building2 className="h-5 w-5" />
                                                </span>
                                                <div>
                                                    <h3 className="font-bold">
                                                        {organization.name}
                                                    </h3>
                                                    <div className="text-muted-foreground mt-1 flex items-center gap-2 text-[11px]">
                                                        <span>
                                                            {organization.role}
                                                        </span>
                                                        <span>·</span>
                                                        <span className="font-mono">
                                                            {organization.id.slice(
                                                                0,
                                                                8,
                                                            )}
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                            <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-emerald-500/15 bg-emerald-500/5 px-2.5 py-1 text-[10px] font-bold text-emerald-600 dark:text-emerald-400">
                                                <CheckCircle2 className="h-3 w-3" />
                                                Authority active
                                            </span>
                                        </div>

                                        <div className="mt-4 border-t pt-4">
                                            <div className="text-muted-foreground text-[10px] font-bold tracking-wider uppercase">
                                                Entitlements
                                            </div>
                                            <div className="mt-2 space-y-2">
                                                {organization.entitlements.map(
                                                    (entitlement) => (
                                                        <div
                                                            key={entitlement.id}
                                                            className="bg-muted/40 flex flex-col justify-between gap-2 rounded-lg px-3 py-3 text-xs sm:flex-row sm:items-center"
                                                        >
                                                            <div className="flex min-w-0 items-start gap-2">
                                                                <KeyRound className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-500" />
                                                                <div className="min-w-0">
                                                                    <div className="truncate font-semibold">
                                                                        {
                                                                            entitlement.product_name
                                                                        }
                                                                    </div>
                                                                    <div className="text-muted-foreground mt-0.5 truncate font-mono text-[10px]">
                                                                        {
                                                                            entitlement.product_slug
                                                                        }
                                                                    </div>
                                                                    <div className="text-muted-foreground mt-1 text-[10px]">
                                                                        {
                                                                            entitlement.capability
                                                                        }
                                                                    </div>
                                                                </div>
                                                            </div>
                                                            <span className="text-[10px] font-bold text-emerald-600 uppercase dark:text-emerald-400">
                                                                {
                                                                    entitlement.status
                                                                }
                                                            </span>
                                                        </div>
                                                    ),
                                                )}
                                            </div>
                                        </div>
                                    </article>
                                ))}
                            </div>
                        )}
                    </section>
                </div>
            </div>
        </>
    );
}

function Metric({ label, value }: { label: string; value: number | string }) {
    return (
        <div className="bg-background/70 min-w-28 rounded-xl border px-4 py-3">
            <div className="text-lg font-black">{value}</div>
            <div className="text-muted-foreground mt-0.5 text-[10px]">
                {label}
            </div>
        </div>
    );
}

function FlowStep({
    icon: Icon,
    text,
}: {
    icon: typeof Building2;
    text: string;
}) {
    return (
        <div className="text-muted-foreground flex items-center gap-3 text-xs">
            <span className="bg-muted text-foreground grid h-7 w-7 shrink-0 place-items-center rounded-lg">
                <Icon className="h-3.5 w-3.5" />
            </span>
            <span>{text}</span>
        </div>
    );
}

Dashboard.layout = {
    breadcrumbs: [
        {
            title: 'Control Center',
            href: dashboard(),
        },
    ],
};
