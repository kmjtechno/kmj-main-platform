[Reading 229 lines from start (total: 229 lines, 0 remaining)]

import { Head, Link } from '@inertiajs/react';
import { ArrowRight, BadgeCheck, Download, KeyRound, ShieldCheck } from 'lucide-react';
import { dashboard } from '@/routes';

type Entitlement = {
    id: string;
    product_id: string;
    product_name: string;
    product_slug: string;
    capability: string;
    status: string;
    starts_at: string;
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

type DashboardProps = {
    organizations: Organization[];
    hasPasskey: boolean;
};

const productImages: Record<string, string> = {
    'kmj-codebridge': '/assets/brand/kmj-social-card.webp',
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

export default function Dashboard({ organizations, hasPasskey }: DashboardProps) {
    const services = organizations.flatMap((organization) =>
        organization.entitlements.map((entitlement) => ({
            ...entitlement,
            organization_name: organization.name,
        })),
    );
    const activeServices = services.filter(
        (entitlement) => entitlement.status === 'active',
    );

    return (
        <>
            <Head title="My KMJ Services" />

            <div className="flex h-full flex-1 flex-col gap-6 overflow-x-auto p-4 sm:p-6">
                <section className="border-sidebar-border/70 from-background via-background dark:border-sidebar-border overflow-hidden rounded-2xl border bg-gradient-to-br to-red-950/10 p-6 sm:p-8">
                    <div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
                        <div className="max-w-2xl">
                            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-red-500/15 bg-red-500/5 px-3 py-1 text-xs font-semibold text-red-500">
                                <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                                KMJ TECHNO · Secure customer access
                            </div>
                            <h1 className="text-3xl font-black tracking-tight sm:text-4xl">
                                My KMJ Services
                            </h1>
                            <p className="text-muted-foreground mt-3 max-w-xl text-sm leading-6">
                                Only the KMJ services authorized for your account are shown here.
                                Service access, downloads and security remain isolated from
                                unrelated KMJ products.
                            </p>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <Metric label="Authorized services" value={services.length} />
                            <Metric label="Active" value={activeServices.length} />
                        </div>
                    </div>
                </section>

                <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                    <div>
                        <div className="flex items-center gap-2">
                            <BadgeCheck className="h-5 w-5 text-red-500" />
                            <h2 className="font-bold">Your authorized services</h2>
                        </div>
                        <p className="text-muted-foreground mt-1 text-xs">
                            Service details are derived only from access granted to your account.
                        </p>
                    </div>

                    {services.length === 0 ? (
                        <div className="bg-muted/20 mt-5 rounded-xl border border-dashed p-8 text-center">
                            <KeyRound className="text-muted-foreground/40 mx-auto h-8 w-8" />
                            <div className="mt-3 text-sm font-bold">No authorized service yet</div>
                            <p className="text-muted-foreground mx-auto mt-1 max-w-xl text-xs leading-5">
                                Your account is active, but no KMJ service has been assigned yet.
                            </p>
                        </div>
                    ) : (
                        <div className="mt-5 grid gap-4 lg:grid-cols-2">
                            {services.map((service) => (
                                <article
                                    key={service.id}
                                    className="bg-background/60 overflow-hidden rounded-xl border"
                                >
                                    <div className="grid grid-cols-[112px_1fr]">
                                        <img
                                            src={
                                                productImages[service.product_slug] ??
                                                '/assets/brand/kmj-social-card.webp'
                                            }
                                            alt={service.product_name}
                                            loading="lazy"
                                            decoding="async"
                                            className="h-full min-h-32 w-28 object-cover"
                                        />
                                        <div className="min-w-0 p-4">
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="min-w-0">
                                                    <h3 className="truncate text-base font-black">
                                                        {service.product_name}
                                                    </h3>
                                                    <p className="text-muted-foreground mt-1 truncate text-[11px]">
                                                        {service.organization_name}
                                                    </p>
                                                </div>
                                                <span className="rounded-full border border-emerald-500/15 bg-emerald-500/5 px-2 py-1 text-[9px] font-black text-emerald-600 uppercase dark:text-emerald-400">
                                                    {service.status}
                                                </span>
                                            </div>

                                            <div className="mt-3 rounded-lg border bg-muted/20 px-3 py-2">
                                                <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider">
                                                    Access
                                                </div>
                                                <div className="mt-1 text-xs font-semibold">
                                                    {service.capability}
                                                </div>
                                            </div>

                                            <div className="mt-4 flex flex-wrap gap-3">
                                                <Link
                                                    href={'/products/' + service.product_slug}
                                                    className="inline-flex items-center gap-1 text-[11px] font-bold text-red-500"
                                                >
                                                    Service details
                                                    <ArrowRight className="h-3 w-3" />
                                                </Link>
                                                {service.release && (
                                                    <a
                                                        href={service.release.download_url}
                                                        className="inline-flex items-center gap-1 text-[11px] font-black text-emerald-600 dark:text-emerald-400"
                                                    >
                                                        <Download className="h-3 w-3" />
                                                        Download v{service.release.version}
                                                    </a>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </article>
                            ))}
                        </div>
                    )}
                </section>

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
                                        ? 'Manage your sign-in and security settings from the secure account area.'
                                        : 'Add a passkey for faster and stronger sign-in to your KMJ services.'}
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
            </div>
        </>
    );
}

function Metric({ label, value }: { label: string; value: number | string }) {
    return (
        <div className="bg-background/70 min-w-28 rounded-xl border px-4 py-3">
            <div className="text-lg font-black">{value}</div>
            <div className="text-muted-foreground mt-0.5 text-[10px]">{label}</div>
        </div>
    );
}

Dashboard.layout = {
    breadcrumbs: [
        {
            title: 'My Services',
            href: dashboard(),
        },
    ],
};

[executed on device: kmjtechnonetgmailcom (cbe1c3e2-c299-4851-9d11-9fafa86b4357)]