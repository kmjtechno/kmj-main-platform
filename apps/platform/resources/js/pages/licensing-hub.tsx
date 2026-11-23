import { Head, Link, router } from '@inertiajs/react';
import { useState } from 'react';
import {
    ArrowRight,
    BadgeCheck,
    Boxes,
    Clock3,
    Code2,
    Download,
    KeyRound,
    Laptop2,
    ShieldCheck,
} from 'lucide-react';

type CustomerLicense = {
    id: string;
    product: string;
    plan: string;
    state: string;
    subject_label: string;
    starts_at: string;
    expires_at: string;
    grace_until: string | null;
    recorded_devices: number;
    non_deactivated_devices: number;
    last_activation_at: string | null;
    online_status: 'not_verified';
    device_recovery_available: false;
    signed_download_verified: false;
};

type CustomerEntitlement = {
    id: string;
    organization_name: string;
    product_name: string;
    product_slug: string;
    capability: string;
    status: string;
    starts_at: string | null;
    ends_at: string | null;
    signed_license_issued: false;
};

type Props = {
    licenses: CustomerLicense[];
    license_count: number;
    licenses_truncated: boolean;
    product_entitlements: CustomerEntitlement[];
    organizations: { id: string; name: string }[];
    omnidesk_trial_organizations: {
        organization_id: string;
        organization_name: string;
        trial_days: number;
    }[];
    authorization_source: 'authenticated_verified_membership';
    device_reset_enabled: false;
    paid_issuance_enabled: false;
    trusted_download_source: string;
};

function readableDate(value: string | null): string {
    if (!value) return 'Not specified';
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? 'Not available'
        : date.toLocaleDateString(undefined, {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
          });
}

const stateLabels: Record<string, string> = {
    ACTIVE: 'Active',
    RENEWAL_DUE: 'Renewal due',
    GRACE: 'Grace period',
    NOT_STARTED: 'Not started',
    REVOKED: 'Revoked',
    RESTRICTED: 'Restricted',
};

export default function LicensingHub({
    licenses,
    license_count,
    licenses_truncated,
    product_entitlements,
    organizations,
    omnidesk_trial_organizations,
    trusted_download_source,
}: Props) {
    const [trialSubmitting, setTrialSubmitting] = useState(false);
    const [trialFeedback, setTrialFeedback] = useState<string | null>(null);

    const requestTrial = (organizationId: string) => {
        setTrialSubmitting(true);
        setTrialFeedback(null);
        router.post(
            '/licensing/omnidesk/trial',
            { organization_id: organizationId },
            {
                preserveScroll: true,
                onSuccess: () =>
                    setTrialFeedback(
                        'Trial recorded in your Licensing Hub. A signed device activation is still required.',
                    ),
                onError: () =>
                    setTrialFeedback(
                        'Trial cannot be started under the current product or organization policy.',
                    ),
                onFinish: () => setTrialSubmitting(false),
            },
        );
    };
    const activeLicenses = licenses.filter((license) =>
        ['ACTIVE', 'RENEWAL_DUE', 'GRACE'].includes(license.state),
    ).length;
    const nonDeactivatedDevices = licenses.reduce(
        (count, license) => count + license.non_deactivated_devices,
        0,
    );

    return (
        <>
            <Head title="Licensing Hub | KMJ TECHNO" />
            <main className="mx-auto flex w-full max-w-7xl flex-col gap-7 px-4 py-8 sm:px-6 lg:px-8">
                <section className="relative overflow-hidden rounded-[28px] border border-white/10 bg-[linear-gradient(135deg,#181d27_0%,#10131b_65%,#250c13_100%)] p-6 text-white shadow-xl sm:p-9">
                    <div className="pointer-events-none absolute -top-20 -right-16 size-64 rounded-full bg-red-600/10 blur-3xl" />
                    <p className="relative flex items-center gap-2 text-xs font-bold tracking-[0.2em] text-red-300 uppercase">
                        <ShieldCheck className="size-4" aria-hidden="true" />
                        KMJ TECHNO · One secure licensing authority
                    </p>
                    <h1 className="relative mt-3 text-3xl font-black tracking-tight sm:text-4xl">
                        Licensing Hub
                    </h1>
                    <p className="relative mt-3 max-w-2xl text-sm leading-6 text-slate-300">
                        Your products, signed-license records and device-seat
                        history in one verified KMJ account. Issuance, payments
                        and device transfers still require their independent
                        server-side security gates.
                    </p>
                    <div className="relative mt-6 flex flex-wrap gap-3">
                        <Link
                            href="/developer/apps"
                            className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-red-600 px-4 py-2 text-xs font-bold text-white hover:bg-red-500"
                        >
                            <Code2 className="size-4" aria-hidden="true" />
                            Developer Apps & Keys
                            <ArrowRight className="size-4" aria-hidden="true" />
                        </Link>
                        <Link
                            href="/purchase"
                            className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-white/20 px-4 py-2 text-xs font-semibold text-white hover:bg-white/10"
                        >
                            Plans & purchases
                        </Link>
                    </div>
                </section>

                {omnidesk_trial_organizations.length > 0 && (
                    <section
                        aria-labelledby="omnidesk-trial-heading"
                        className="border-border bg-card rounded-2xl border p-5 sm:p-6"
                    >
                        <div className="flex flex-wrap items-start justify-between gap-4">
                            <div className="max-w-2xl">
                                <h2
                                    id="omnidesk-trial-heading"
                                    className="text-lg font-bold"
                                >
                                    OmniDesk · First-party trial
                                </h2>
                                <p className="text-muted-foreground mt-2 text-xs leading-5">
                                    Eligible verified organizations can create
                                    one no-charge trial record automatically.
                                    A trial is not a signed remote-access lease,
                                    and device activation remains separately
                                    verified by KMJ Main Platform.
                                </p>
                            </div>
                            <ShieldCheck
                                className="size-5 text-red-500"
                                aria-hidden="true"
                            />
                        </div>
                        <div className="mt-4 flex flex-wrap gap-3">
                            {omnidesk_trial_organizations.map((organization) => (
                                <button
                                    key={organization.organization_id}
                                    type="button"
                                    disabled={trialSubmitting}
                                    onClick={() =>
                                        requestTrial(organization.organization_id)
                                    }
                                    className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-red-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                    <BadgeCheck
                                        className="size-4"
                                        aria-hidden="true"
                                    />
                                    {trialSubmitting
                                        ? 'Submitting…'
                                        : `Start ${organization.trial_days}-day trial · ${organization.organization_name}`}
                                </button>
                            ))}
                        </div>
                        {trialFeedback && (
                            <p
                                className="text-muted-foreground mt-3 text-xs"
                                role="status"
                                aria-live="polite"
                            >
                                {trialFeedback}
                            </p>
                        )}
                    </section>
                )}

                <nav
                    aria-label="Licensing workflow sections"
                    className="flex flex-wrap gap-2"
                >
                    {[
                        ['My products', '#my-products'],
                        ['Licenses', '#my-licenses'],
                        ['Devices', '#my-devices'],
                        ['Downloads', '#my-downloads'],
                    ].map(([label, href]) => (
                        <a
                            key={href}
                            href={href}
                            className="border-border bg-card hover:bg-accent rounded-full border px-4 py-2 text-xs font-bold transition"
                        >
                            {label}
                        </a>
                    ))}
                </nav>

                <section
                    className="grid gap-3 sm:grid-cols-3"
                    aria-label="Licensing overview"
                >
                    {[
                        {
                            label: 'License records',
                            number: license_count,
                            icon: KeyRound,
                        },
                        {
                            label: 'Currently eligible in shown records',
                            number: activeLicenses,
                            icon: BadgeCheck,
                        },
                        {
                            label: 'Non-deactivated device bindings',
                            number: nonDeactivatedDevices,
                            icon: Laptop2,
                        },
                    ].map(({ label, number, icon: Icon }) => (
                        <div
                            key={label}
                            className="border-border bg-card rounded-2xl border p-5"
                        >
                            <Icon
                                className="mb-3 size-5 text-red-500"
                                aria-hidden="true"
                            />
                            <p className="text-3xl font-extrabold tabular-nums">
                                {number}
                            </p>
                            <p className="text-muted-foreground mt-1 text-xs">
                                {label}
                            </p>
                        </div>
                    ))}
                </section>

                <section
                    id="my-products"
                    aria-labelledby="products-heading"
                    className="border-border bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
                >
                    <div className="flex items-start gap-3">
                        <Boxes
                            className="mt-0.5 size-5 text-red-500"
                            aria-hidden="true"
                        />
                        <div>
                            <h2
                                id="products-heading"
                                className="text-lg font-bold"
                            >
                                My Products
                            </h2>
                            <p className="text-muted-foreground text-xs">
                                Recorded organization entitlements. An
                                entitlement record is not itself a signed
                                license.
                            </p>
                        </div>
                    </div>
                    {product_entitlements.length === 0 ? (
                        <p className="text-muted-foreground mt-5 text-sm">
                            No product entitlements are linked to your verified
                            organization memberships yet.
                        </p>
                    ) : (
                        <div className="mt-5 grid gap-3 sm:grid-cols-2">
                            {product_entitlements.map((product) => (
                                <div
                                    key={product.id}
                                    className="border-border rounded-xl border p-4"
                                >
                                    <p className="text-sm font-bold">
                                        {product.product_name}
                                    </p>
                                    <p className="text-muted-foreground mt-1 text-xs">
                                        {product.organization_name} ·{' '}
                                        {product.capability}
                                    </p>
                                    <p className="mt-2 text-xs">
                                        Entitlement: {product.status}
                                    </p>
                                    <p className="text-muted-foreground mt-1 text-xs">
                                        Ends: {readableDate(product.ends_at)}
                                    </p>
                                    <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
                                        Signed license not attested here
                                    </p>
                                </div>
                            ))}
                        </div>
                    )}
                </section>

                <section
                    id="my-licenses"
                    aria-labelledby="licenses-heading"
                    className="border-border bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
                >
                    <div className="flex items-start gap-3">
                        <KeyRound
                            className="mt-0.5 size-5 text-red-500"
                            aria-hidden="true"
                        />
                        <div>
                            <h2
                                id="licenses-heading"
                                className="text-lg font-bold"
                            >
                                My Licenses
                            </h2>
                            <p className="text-muted-foreground text-xs">
                                KSLP license status, plan, renewal and expiry;
                                no plaintext keys or device fingerprints.
                            </p>
                        </div>
                    </div>
                    {licenses_truncated && (
                        <p className="mt-4 text-xs text-amber-600 dark:text-amber-400">
                            Showing the latest 100 records only. Contact KMJ
                            support for older history.
                        </p>
                    )}
                    {licenses.length === 0 ? (
                        <p className="text-muted-foreground mt-5 text-sm">
                            No KSLP licenses were found for your verified
                            account or organization memberships.
                        </p>
                    ) : (
                        <div className="mt-5 grid gap-3">
                            {licenses.map((license) => (
                                <article
                                    key={license.id}
                                    className="border-border rounded-xl border p-4"
                                >
                                    <div className="flex flex-wrap justify-between gap-3">
                                        <div>
                                            <h3 className="text-sm font-bold">
                                                {license.product}
                                            </h3>
                                            <p className="text-muted-foreground mt-1 text-xs">
                                                {license.subject_label} ·{' '}
                                                {license.plan} · Ref{' '}
                                                {license.id.slice(0, 8)}
                                            </p>
                                        </div>
                                        <span className="bg-muted rounded-full px-3 py-1 text-xs font-bold">
                                            {stateLabels[license.state] ??
                                                'Unknown'}
                                        </span>
                                    </div>
                                    <div className="text-muted-foreground mt-3 flex flex-wrap gap-4 text-xs">
                                        <span className="inline-flex items-center gap-1">
                                            <Clock3
                                                className="size-4"
                                                aria-hidden="true"
                                            />
                                            Expires{' '}
                                            {readableDate(license.expires_at)}
                                        </span>
                                        <span>
                                            Device bindings:{' '}
                                            {license.non_deactivated_devices}
                                        </span>
                                        <span>Online status: not verified</span>
                                    </div>
                                </article>
                            ))}
                        </div>
                    )}
                </section>

                <section
                    id="my-devices"
                    aria-labelledby="devices-heading"
                    className="border-border bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
                >
                    <div className="flex items-start gap-3">
                        <Laptop2
                            className="mt-0.5 size-5 text-red-500"
                            aria-hidden="true"
                        />
                        <div>
                            <h2
                                id="devices-heading"
                                className="text-lg font-bold"
                            >
                                Devices & recovery
                            </h2>
                            <p className="text-muted-foreground text-xs">
                                Only aggregate historical activation evidence is
                                shown. No hardware identity or device secret
                                leaves the licensing server.
                            </p>
                        </div>
                    </div>
                    <div className="bg-muted/50 mt-5 rounded-xl p-4">
                        <p className="text-sm font-semibold">
                            Secure device reset / transfer: not enabled
                        </p>
                        <p className="text-muted-foreground mt-2 text-xs leading-5">
                            Moving a seat must first verify device key
                            possession, license ownership, cooldown and
                            revocation sequence. A browser-only reset would
                            bypass those protections. Use KMJ support for
                            recovery until the reviewed flow is enabled.
                        </p>
                        {organizations.length > 0 && (
                            <p className="text-muted-foreground mt-2 text-xs">
                                Linked organizations: {organizations.length}
                            </p>
                        )}
                    </div>
                </section>

                <section
                    id="my-downloads"
                    aria-labelledby="downloads-heading"
                    className="border-border bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
                >
                    <div className="flex items-start gap-3">
                        <Download
                            className="mt-0.5 size-5 text-red-500"
                            aria-hidden="true"
                        />
                        <div>
                            <h2
                                id="downloads-heading"
                                className="text-lg font-bold"
                            >
                                Downloads & releases
                            </h2>
                            <p className="text-muted-foreground text-xs">
                                Obtain downloads only from the existing
                                entitlement-aware account dashboard. This page
                                does not grant or fabricate a signed release.
                            </p>
                        </div>
                    </div>
                    <Link
                        href={trusted_download_source}
                        className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-xl border border-red-500/30 px-4 text-xs font-bold text-red-600 hover:bg-red-500/5"
                    >
                        <Download className="size-4" aria-hidden="true" />
                        View authorized account downloads
                        <ArrowRight className="size-4" aria-hidden="true" />
                    </Link>
                </section>

                <p className="text-muted-foreground text-center text-xs">
                    One KMJ Main Platform / KSLP authority. No legacy AuthSP
                    login, payment shortcut, client-side licensing keys or
                    independent signer.
                </p>
            </main>
        </>
    );
}
