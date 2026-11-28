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
import { ArrowRight, Boxes, KeyRound } from 'lucide-react';

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
    authorization_source: 'authenticated_verified_membership';
    device_reset_enabled: false;
    paid_issuance_enabled: false;
    trusted_download_source: string;
};

function readableDate(value: string | null): string {
    if (!value) return 'Not set';
    return formatIstDate(value, 'Not available');
}

const actionClass =
    'inline-flex min-h-11 items-center gap-2 rounded-xl px-4 text-sm font-bold';
const linkClass =
    'inline-flex min-h-11 items-center font-semibold text-red-600 hover:underline dark:text-red-400';

export default function LicensingHub({
    licenses,
    license_count,
    licenses_truncated,
    product_entitlements,
    organizations,
    trusted_download_source,
}: Props) {
    const usableLicenses = licenses.filter((license) =>
        isUsableLicenseState(license.state),
    );
    const renewalAttention = licenses.filter((license) =>
        ['RENEWAL_DUE', 'GRACE'].includes(license.state),
    );
    const accessReview = licenses.filter((license) =>
        ['REVOKED', 'RESTRICTED'].includes(license.state),
    );

    const nextStep =
        renewalAttention.length > 0
            ? {
                  title: 'A license needs renewal',
                  detail: 'Check the dates below and ask KMJ about renewal.',
                  href: '#my-renewals',
                  action: 'See what needs attention',
              }
            : accessReview.length > 0
              ? {
                    title: 'A license cannot be used',
                    detail: 'KMJ support has to review it.',
                    href: '#my-renewals',
                    action: 'See what needs attention',
                }
              : license_count > 0
                ? {
                      title:
                          usableLicenses.length > 0
                              ? 'Nothing to do right now'
                              : 'Your license has not started yet',
                      detail: 'Your license dates are listed below.',
                      href: '#my-licenses',
                      action: 'View my licenses',
                  }
                : product_entitlements.length > 0
                  ? {
                        title: 'You have product access',
                        detail: 'There is no separate license record on this account.',
                        href: '#my-products',
                        action: 'View my product access',
                    }
                  : {
                        title: 'No license yet',
                        detail:
                            organizations.length > 0
                                ? 'Send a purchase request to get started.'
                                : 'Your account has no organization yet. Contact info@kmjtechno.com.',
                        href: '/purchase',
                        action: 'Request a product',
                    };

    return (
        <>
            <Head title="Licensing Hub | KMJ TECHNO" />
            <main className="flex w-full flex-col gap-3 p-3">
                <section
                    id="getting-started"
                    aria-labelledby="licensing-heading"
                    className="bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-7"
                >
                    <h1
                        id="licensing-heading"
                        className="text-3xl font-black tracking-tight"
                    >
                        Licensing Hub
                    </h1>
                    <p className="text-muted-foreground mt-2 text-sm">
                        Your licenses and product access in one place. No
                        automatic charges are made from this page.
                    </p>
                    <div className="bg-muted/40 mt-5 flex flex-col justify-between gap-3 rounded-xl border p-4 sm:flex-row sm:items-center">
                        <div>
                            <h2 className="font-bold">{nextStep.title}</h2>
                            <p className="text-muted-foreground mt-1 text-sm">
                                {nextStep.detail}
                            </p>
                        </div>
                        {nextStep.href.startsWith('#') ? (
                            <a
                                href={nextStep.href}
                                className={`${actionClass} shrink-0 justify-center border hover:border-red-500/40`}
                            >
                                {nextStep.action}
                                <ArrowRight
                                    className="size-4"
                                    aria-hidden="true"
                                />
                            </a>
                        ) : (
                            <Link
                                href="/purchase"
                                className={`${actionClass} shrink-0 justify-center bg-red-600 text-white hover:bg-red-500`}
                            >
                                {nextStep.action}
                                <ArrowRight
                                    className="size-4"
                                    aria-hidden="true"
                                />
                            </Link>
                        )}
                    </div>
                </section>

                {(renewalAttention.length > 0 || accessReview.length > 0) && (
                    <section
                        id="my-renewals"
                        aria-labelledby="renewals-heading"
                        className="scroll-mt-6 rounded-2xl border border-amber-500/40 p-5 sm:p-6"
                    >
                        <h2 id="renewals-heading" className="font-bold">
                            Needs your attention
                        </h2>
                        <ul className="mt-3 space-y-4">
                            {renewalAttention.map((license) => (
                                <li key={license.id} className="text-sm">
                                    <p className="font-bold">
                                        {productLabel(license.product)} ·{' '}
                                        {licenseStateLabel(license.state)}
                                    </p>
                                    <p className="text-muted-foreground mt-1">
                                        Expires{' '}
                                        {readableDate(license.expires_at)}
                                        {license.state === 'GRACE' &&
                                            license.grace_until &&
                                            ` · Grace period ends ${readableDate(license.grace_until)}`}
                                        . A renewal is not automatic: KMJ has to
                                        confirm it before your dates change.
                                    </p>
                                    <Link
                                        href="/purchase"
                                        className={linkClass}
                                    >
                                        Ask about renewal · no payment here
                                    </Link>
                                </li>
                            ))}
                            {accessReview.map((license) => (
                                <li key={license.id} className="text-sm">
                                    <p className="font-bold">
                                        {productLabel(license.product)} ·{' '}
                                        {licenseStateLabel(license.state)}
                                    </p>
                                    <p className="text-muted-foreground mt-1">
                                        Email info@kmjtechno.com and quote
                                        reference {license.id.slice(0, 8)}.
                                        Buying another plan cannot bypass
                                        revocation or a restriction.
                                    </p>
                                </li>
                            ))}
                        </ul>
                    </section>
                )}

                <section
                    id="my-licenses"
                    aria-labelledby="licenses-heading"
                    className="bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
                >
                    <h2
                        id="licenses-heading"
                        className="flex items-center gap-2 font-bold"
                    >
                        <KeyRound
                            className="size-5 text-red-500"
                            aria-hidden="true"
                        />
                        My licenses ({license_count})
                    </h2>
                    {licenses_truncated && (
                        <p className="mt-3 text-sm text-amber-700 dark:text-amber-300">
                            Showing the latest 100 licenses only. Contact KMJ
                            support for older ones.
                        </p>
                    )}
                    {license_count === 0 ? (
                        <p className="text-muted-foreground mt-3 text-sm">
                            No license is linked to your account or
                            organizations.
                        </p>
                    ) : (
                        <ul className="mt-4 grid gap-3">
                            {licenses.map((license) => (
                                <li
                                    key={license.id}
                                    className="rounded-xl border p-4"
                                >
                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div className="min-w-0">
                                            <h3 className="font-bold">
                                                {productLabel(license.product)}
                                            </h3>
                                            <p className="text-muted-foreground mt-1 text-sm">
                                                {planLabel(license.plan)} plan ·{' '}
                                                {license.subject_label}
                                            </p>
                                        </div>
                                        <span className="bg-muted rounded-full px-3 py-1 text-xs font-bold">
                                            {licenseStateLabel(license.state)}
                                        </span>
                                    </div>
                                    <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
                                        <div>
                                            <dt className="text-muted-foreground text-xs">
                                                {license.state === 'NOT_STARTED'
                                                    ? 'Starts'
                                                    : 'Expires'}
                                            </dt>
                                            <dd>
                                                {readableDate(
                                                    license.state ===
                                                        'NOT_STARTED'
                                                        ? license.starts_at
                                                        : license.expires_at,
                                                )}
                                            </dd>
                                        </div>
                                        <div>
                                            <dt className="text-muted-foreground text-xs">
                                                Computers registered
                                            </dt>
                                            <dd>
                                                {
                                                    license.non_deactivated_devices
                                                }
                                            </dd>
                                        </div>
                                        <div>
                                            <dt className="text-muted-foreground text-xs">
                                                Support reference
                                            </dt>
                                            <dd className="font-mono">
                                                {license.id.slice(0, 8)}
                                            </dd>
                                        </div>
                                    </dl>
                                </li>
                            ))}
                        </ul>
                    )}
                    {license_count > 0 && (
                        <p className="text-muted-foreground mt-3 text-xs">
                            A registered computer is a saved record. It does not
                            show whether that computer is online now.
                        </p>
                    )}
                </section>

                <section
                    id="my-products"
                    aria-labelledby="products-heading"
                    className="bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
                >
                    <h2
                        id="products-heading"
                        className="flex items-center gap-2 font-bold"
                    >
                        <Boxes
                            className="size-5 text-red-500"
                            aria-hidden="true"
                        />
                        Product access
                    </h2>
                    {product_entitlements.length > 0 ? (
                        <ul className="mt-4 grid grid-cols-[repeat(auto-fit,minmax(min(100%,18rem),1fr))] gap-3">
                            {product_entitlements.map((access) => (
                                <li
                                    key={access.id}
                                    className="rounded-xl border p-4 text-sm"
                                >
                                    <p className="font-bold">
                                        {access.product_name}
                                    </p>
                                    <p className="text-muted-foreground mt-1">
                                        {access.organization_name} ·{' '}
                                        {featureLabel(access.capability)}
                                    </p>
                                    <p className="mt-2">
                                        {accessStatusLabel(access.status)}
                                        {access.ends_at &&
                                            ` · Ends ${readableDate(access.ends_at)}`}
                                    </p>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="text-muted-foreground mt-3 text-sm">
                            No product access is switched on for your
                            organizations.
                            {license_count > 0 &&
                                ' Your license is a separate record and stays listed above.'}
                        </p>
                    )}
                </section>

                <RecordExplainer />

                <section
                    aria-label="More help"
                    className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,16rem),1fr))] gap-3"
                >
                    <div
                        id="my-downloads"
                        className="scroll-mt-6 rounded-xl border p-4 text-sm"
                    >
                        <h2 className="font-bold">Downloads</h2>
                        <p className="text-muted-foreground mt-1">
                            Downloads appear on My Services, next to a product
                            that is switched on.
                        </p>
                        <Link
                            href={trusted_download_source}
                            className={linkClass}
                        >
                            Open My Services
                        </Link>
                    </div>
                    <div
                        id="my-devices"
                        className="scroll-mt-6 rounded-xl border p-4 text-sm"
                    >
                        <h2 className="font-bold">Moving to a new computer</h2>
                        <p className="text-muted-foreground mt-1">
                            Self-service transfer is not available yet. Email
                            KMJ support with your license reference.
                        </p>
                        <a
                            href="mailto:info@kmjtechno.com"
                            className={linkClass}
                        >
                            info@kmjtechno.com
                        </a>
                    </div>
                    <div className="rounded-xl border p-4 text-sm">
                        <h2 className="font-bold">For software developers</h2>
                        <p className="text-muted-foreground mt-1">
                            Issuing keys for your own software needs a separate
                            developer permission.
                        </p>
                        <Link href="/developer/apps" className={linkClass}>
                            Open Developer Apps
                        </Link>
                    </div>
                    <div
                        id="codebridge-usage-preview"
                        className="rounded-xl border p-4 text-sm"
                        role="status"
                    >
                        <h2 className="font-bold">CodeBridge monthly usage</h2>
                        <p className="text-muted-foreground mt-1">
                            Live usage: Not available yet. No usage numbers or
                            plan prices are shown until they are real.
                        </p>
                    </div>
                </section>
            </main>
        </>
    );
}
