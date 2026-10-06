import { Head, Link } from '@inertiajs/react';
import {
    ArrowLeft,
    ArrowRight,
    CalendarDays,
    CheckCircle2,
    Download,
    ExternalLink,
    Fingerprint,
    FolderKanban,
    PackageCheck,
    ShieldCheck,
    ShoppingBag,
} from 'lucide-react';
import LockedBrand from '@/components/locked-brand';

type Organization = {
    id: string;
    name: string;
};

type Entitlement = {
    id: string;
    product_name: string;
    product_slug: string;
    capability: string;
    status: string;
    starts_at: string;
};

type Product = {
    summary: string;
    category: string;
    lifecycle_label: string;
    purchase_enabled: boolean;
    image_path?: string | null;
} | null;

type Release = {
    version: string;
    filename: string;
    download_url: string;
} | null;

type Props = {
    organization: Organization;
    entitlement: Entitlement;
    product: Product;
    release: Release;
};

const actionClass =
    'inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 text-xs font-semibold text-white transition hover:border-red-400/60 hover:bg-red-500/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-400';

function readableDate(raw: string): string {
    const date = new Date(raw);
    if (Number.isNaN(date.getTime())) return 'Not available';
    return new Intl.DateTimeFormat('en', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
    }).format(date);
}

function Detail({
    label,
    value,
}: {
    label: string;
    value: string;
}) {
    return (
        <div className="flex flex-col gap-1 rounded-xl border border-white/10 bg-white/[0.03] p-4">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
                {label}
            </span>
            <span className="break-words text-sm font-semibold text-white">
                {value}
            </span>
        </div>
    );
}

export default function CustomerServiceDetails({
    organization,
    entitlement,
    product,
    release,
}: Props) {
    const codebridge = entitlement.product_slug === 'kmj-codebridge';
    const active = entitlement.status === 'active';
    return (
        <>
            <Head title={entitlement.product_name + ' — KMJ TECHNO'} />
            <main className="min-w-0 space-y-5 bg-[#090a0f] p-4 text-white sm:p-6 lg:p-8">
                <section className="overflow-hidden rounded-2xl border border-red-500/20 bg-gradient-to-br from-[#191018] to-[#0f1117] p-5 sm:p-7">
                    <LockedBrand compact className="mb-5" />
                    <Link
                        href="/dashboard#my-services"
                        className="inline-flex items-center gap-2 text-xs text-zinc-300 hover:text-white"
                    >
                        <ArrowLeft className="h-4 w-4" />
                        Back to My Services
                    </Link>
                    <div className="mt-5 flex flex-wrap items-start justify-between gap-4">
                        <div className="max-w-2xl">
                            <p className="text-xs font-semibold uppercase tracking-wider text-red-300">
                                Authorized KMJ service
                            </p>
                            <h1 className="mt-3 break-words text-2xl font-black tracking-tight sm:text-3xl">
                                {entitlement.product_name}
                            </h1>
                            <p className="mt-2 text-xs text-zinc-300">
                                {organization.name}
                            </p>
                            <p className="mt-4 text-sm leading-6 text-zinc-300">
                                {product?.summary ||
                                    'This service is available through your verified organization entitlement.'}
                            </p>
                        </div>
                        <span
                            className={
                                'rounded-xl border px-3 py-2 text-xs font-bold capitalize ' +
                                (active
                                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                                    : 'border-amber-500/30 bg-amber-500/10 text-amber-300')
                            }
                        >
                            {entitlement.status.replaceAll('_', ' ')}
                        </span>
                    </div>
                </section>

                <section
                    className="grid gap-3 md:grid-cols-2 xl:grid-cols-4"
                    aria-label="Service details"
                >
                    <Detail
                        label="Organization"
                        value={organization.name}
                    />
                    <Detail
                        label="Access status"
                        value={entitlement.status.replaceAll('_', ' ')}
                    />
                    <Detail
                        label="Entitlement started"
                        value={readableDate(entitlement.starts_at)}
                    />
                    <Detail
                        label="Product lifecycle"
                        value={product?.lifecycle_label || 'Internal service'}
                    />
                </section>

                <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
                    <section className="rounded-2xl border border-white/10 bg-[#111318] p-5">
                        <h2 className="flex items-center gap-2 text-base font-bold">
                            <ShieldCheck className="h-5 w-5 text-red-400" />
                            Your service access
                        </h2>
                        <p className="mt-2 text-xs leading-5 text-zinc-300">
                            Permissions are granted by the KMJ Main Platform
                            entitlement authority. This page cannot issue a
                            license or bypass product policy.
                        </p>
                        <div className="mt-4 space-y-3">
                            <div className="flex items-start gap-3 rounded-xl border border-white/10 p-3 text-xs">
                                <Fingerprint className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
                                <div className="min-w-0">
                                    <div className="font-semibold">
                                        Authorized capability
                                    </div>
                                    <div className="mt-1 break-all font-mono text-zinc-300">
                                        {entitlement.capability}
                                    </div>
                                </div>
                            </div>
                            <div className="flex items-start gap-3 rounded-xl border border-white/10 p-3 text-xs">
                                <CalendarDays className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
                                <div>
                                    <div className="font-semibold">
                                        Access started
                                    </div>
                                    <div className="mt-1 text-zinc-300">
                                        {readableDate(entitlement.starts_at)}
                                    </div>
                                </div>
                            </div>
                            <div className="flex items-start gap-3 rounded-xl border border-white/10 p-3 text-xs">
                                <FolderKanban className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
                                <div>
                                    <div className="font-semibold">
                                        Organization-scoped authorization
                                    </div>
                                    <div className="mt-1 text-zinc-300">
                                        Devices, credentials and projects are
                                        managed through the appropriate
                                        product-specific setup.
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>

                    <section className="rounded-2xl border border-white/10 bg-[#111318] p-5">
                        <h2 className="flex items-center gap-2 text-base font-bold">
                            <PackageCheck className="h-5 w-5 text-red-400" />
                            Verified release & actions
                        </h2>
                        {release ? (
                            <div className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
                                <div className="flex items-center gap-2 text-xs font-semibold text-emerald-300">
                                    <CheckCircle2 className="h-4 w-4" />
                                    Verified release v{release.version}
                                </div>
                                <p className="mt-2 break-all text-xs text-zinc-300">
                                    {release.filename}
                                </p>
                                <a
                                    href={release.download_url}
                                    className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-bold text-white hover:bg-red-500"
                                >
                                    <Download className="h-4 w-4" />
                                    Download release
                                </a>
                            </div>
                        ) : (
                            <p className="mt-4 rounded-xl border border-dashed border-white/15 p-4 text-xs leading-5 text-zinc-300">
                                No customer-authorized release artifact is
                                available yet. The platform will offer a
                                download only after release verification and
                                authorization.
                            </p>
                        )}
                        <div className="mt-5 flex flex-wrap gap-2">
                            {codebridge && active && (
                                <Link
                                    href="/services/kmj-codebridge#device-center"
                                    className={actionClass}
                                >
                                    <FolderKanban className="h-4 w-4" />
                                    Devices & projects
                                </Link>
                            )}
                            {product && (
                                <Link
                                    href={
                                        '/products/' +
                                        encodeURIComponent(
                                            entitlement.product_slug,
                                        )
                                    }
                                    className={actionClass}
                                >
                                    <ExternalLink className="h-4 w-4" />
                                    Product information
                                </Link>
                            )}
                            <Link
                                href="/purchase"
                                className={actionClass}
                            >
                                <ShoppingBag className="h-4 w-4" />
                                Add services
                                <ArrowRight className="h-4 w-4" />
                            </Link>
                        </div>
                    </section>
                </div>
                <p className="text-xs text-zinc-400">
                    This view uses your current KMJ entitlement and verified
                    release data. Usage telemetry, pricing, renewals and
                    device-online state are not inferred where unavailable.
                </p>
            </main>
        </>
    );
}
