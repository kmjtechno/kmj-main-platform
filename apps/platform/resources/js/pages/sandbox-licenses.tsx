import { Head, Link, router, useForm, usePage } from '@inertiajs/react';
import {
    ArrowUpRight,
    Building2,
    CheckCircle2,
    History,
    KeyRound,
    ShieldAlert,
    ShieldCheck,
} from 'lucide-react';

type Entitlement = {
    id: string;
    product_id: string;
    capability: string;
    status: string;
};

type Organization = {
    id: string;
    name: string;
    role: string;
    entitlements: Entitlement[];
};

type ValidationResult = {
    valid: boolean;
    reason: string | null;
    claims: Record<string, unknown> | null;
};

type LicenseResult = {
    token: string;
    validation: ValidationResult;
};

type AuditEvent = {
    id: number | string;
    organization_id: string | null;
    action: string;
    status: string;
    jti: string | null;
    metadata: Record<string, unknown> | null;
    created_at: string | null;
};

type Props = {
    organizations: Organization[];
    licenseResult: LicenseResult | null;
    validationResult: ValidationResult | null;
    auditEvents: AuditEvent[];
    validationEngine: string;
};

export default function SandboxLicenses({
    organizations,
    licenseResult,
    validationResult,
    auditEvents,
    validationEngine,
}: Props) {
    const claimedOrganizationId =
        licenseResult?.validation.claims?.['organization_id'];
    const issuedOrganizationId =
        typeof claimedOrganizationId === 'string' &&
        organizations.some(
            (organization) => organization.id === claimedOrganizationId,
        )
            ? claimedOrganizationId
            : '';

    const issue = useForm({ organization_id: '', entitlement_id: '' });
    const organizationSetup = useForm({ name: '' });
    const canManagePlatform = Boolean(
        (usePage().props.operator as { enabled?: boolean } | undefined)?.enabled,
    );
    const hasOrganization = organizations.length > 0;
    const hasActiveEntitlement = organizations.some((organization) =>
        organization.entitlements.some((entitlement) => entitlement.status === 'active'),
    );
    const validate = useForm({
        organization_id: issuedOrganizationId,
        license: licenseResult?.token ?? '',
    });
    const revoke = useForm({
        organization_id: issuedOrganizationId,
        license: licenseResult?.token ?? '',
        reason: '',
    });

    const selectedOrganization = organizations.find(
        (organization) => organization.id === issue.data.organization_id,
    );
    const organizationNames = new Map(
        organizations.map((organization) => [
            organization.id,
            organization.name,
        ]),
    );
    const lifecycleState = validationResult
        ? validationResult.valid
            ? {
                  current: 'Validated',
                  next: 'Revoke when access should end',
                  step: 3,
              }
            : {
                  current: 'Invalid or revoked',
                  next: 'Issue a new license if access is still required',
                  step: 1,
              }
        : licenseResult
          ? { current: 'Issued', next: 'Validate the issued token', step: 2 }
          : {
                current: 'Ready to issue',
                next: 'Issue a license from an active entitlement',
                step: 1,
            };

    return (
        <>
            <Head title="Sandbox Licensing" />
            <div className="flex h-full flex-1 flex-col gap-6 overflow-x-auto p-4 sm:p-6">
                <section className="border-sidebar-border/70 bg-card rounded-2xl border p-6">
                    <div className="flex items-start gap-4">
                        <span className="grid h-11 w-11 place-items-center rounded-xl bg-red-500/10 text-red-500">
                            <ShieldCheck className="h-5 w-5" />
                        </span>
                        <div>
                            <div className="text-xs font-bold tracking-wider text-red-500 uppercase">
                                Sandbox authority
                            </div>
                            <h1 className="mt-1 text-2xl font-black tracking-tight">
                                License Control Center
                            </h1>
                            <p className="text-muted-foreground mt-2 max-w-2xl text-sm leading-6">
                                Issue a short-lived license only from an active
                                entitlement, validate it, then revoke it and
                                confirm the same token fails closed.
                            </p>
                            {canManagePlatform && (
                                <Link
                                    href="/operator"
                                    className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm font-bold text-red-500 hover:bg-red-500/15"
                                >
                                    Open Super Admin <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
                                </Link>
                            )}
                            <div className="mt-3 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold">
                                Validation engine
                                <span className="font-mono text-red-500">
                                    {validationEngine}
                                </span>
                            </div>
                        </div>
                    </div>
                </section>

                <section className="border-sidebar-border/70 bg-card rounded-2xl border p-5">
                    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                        <div>
                            <div className="text-xs font-bold tracking-wider text-red-500 uppercase">
                                License lifecycle
                            </div>
                            <h2 className="mt-1 font-bold">
                                {lifecycleState.current}
                            </h2>
                            <p className="text-muted-foreground mt-1 text-xs">
                                Next safe action: {lifecycleState.next}
                            </p>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-center text-xs font-semibold sm:min-w-80">
                            {['Issue', 'Validate', 'Revoke'].map(
                                (label, index) => {
                                    const step = index + 1;
                                    const active = lifecycleState.step === step;
                                    return (
                                        <div
                                            key={label}
                                            className={`rounded-xl border px-3 py-2 ${active ? 'border-red-500/40 bg-red-500/10 text-red-500' : 'text-muted-foreground'}`}
                                        >
                                            {step}. {label}
                                        </div>
                                    );
                                },
                            )}
                        </div>
                    </div>
                </section>

                {!hasActiveEntitlement && (
                    <section className="border-amber-500/30 bg-amber-500/5 rounded-2xl border p-5 sm:p-6" aria-label="License setup required">
                        <div className="flex items-start gap-3">
                            <Building2 className="mt-1 h-5 w-5 shrink-0 text-amber-500" aria-hidden="true" />
                            <div className="min-w-0 flex-1">
                                <h2 className="font-bold">{hasOrganization ? 'No active entitlement available' : 'Set up your first organization'}</h2>
                                <p className="text-muted-foreground mt-2 text-sm leading-6">
                                    {hasOrganization
                                        ? 'Your organization exists, but no active sandbox entitlement is assigned. A license cannot be issued until an authorized entitlement is available.'
                                        : 'A sandbox license requires your organization and an active entitlement. Creating a sandbox organization also provisions the existing Main Platform sandbox access policy; it does not create a paid subscription.'}
                                </p>
                                {!hasOrganization ? (
                                    <form
                                        className="mt-4 flex flex-col gap-3 sm:flex-row"
                                        onSubmit={(event) => {
                                            event.preventDefault();
                                            organizationSetup.post('/organizations', {
                                                onSuccess: () => {
                                                    organizationSetup.reset();
                                                    router.visit('/sandbox-licenses');
                                                },
                                            });
                                        }}
                                    >
                                        <label className="min-w-0 flex-1 text-xs font-semibold">
                                            <span className="sr-only">Organization name</span>
                                            <input
                                                name="name"
                                                type="text"
                                                required
                                                minLength={2}
                                                maxLength={160}
                                                value={organizationSetup.data.name}
                                                onChange={(event) => organizationSetup.setData('name', event.target.value)}
                                                placeholder="Organization name (e.g. KMJ TECHNO)"
                                                className="border-input bg-background min-h-11 w-full rounded-xl border px-3 text-sm"
                                            />
                                            {organizationSetup.errors.name && <span className="mt-1 block text-red-500" role="alert">{organizationSetup.errors.name}</span>}
                                        </label>
                                        <button type="submit" disabled={organizationSetup.processing}
                                            className="min-h-11 rounded-xl bg-red-600 px-5 text-sm font-semibold text-white disabled:opacity-50">
                                            {organizationSetup.processing ? 'Creating…' : 'Create sandbox organization'}
                                        </button>
                                    </form>
                                ) : (
                                    <Link className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 py-2 text-sm font-semibold hover:bg-amber-500/10" href="/purchase">
                                        View available products and access <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
                                    </Link>
                                )}
                            </div>
                        </div>
                    </section>
                )}

                <div className="grid gap-6 xl:grid-cols-3">
                    <section className="border-sidebar-border/70 bg-card rounded-2xl border p-5">
                        <h2 className="font-bold">1. Issue license</h2>
                        <p className="text-muted-foreground mt-1 text-xs">
                            Owner-scoped, entitlement-backed, 30-minute sandbox
                            token.
                        </p>
                        <form
                            className="mt-5 space-y-4"
                            onSubmit={(event) => {
                                event.preventDefault();
                                issue.post('/sandbox-licenses');
                            }}
                        >
                            <select
                                className="border-input bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                value={issue.data.organization_id}
                                onChange={(event) => {
                                    issue.setData({
                                        organization_id: event.target.value,
                                        entitlement_id: '',
                                    });
                                }}
                                required
                            >
                                <option value="">Select organization</option>
                                {organizations.map((organization) => (
                                    <option
                                        key={organization.id}
                                        value={organization.id}
                                    >
                                        {organization.name}
                                    </option>
                                ))}
                            </select>

                            <select
                                className="border-input bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                value={issue.data.entitlement_id}
                                onChange={(event) =>
                                    issue.setData(
                                        'entitlement_id',
                                        event.target.value,
                                    )
                                }
                                required
                                disabled={!selectedOrganization}
                            >
                                <option value="">
                                    Select active entitlement
                                </option>
                                {selectedOrganization?.entitlements
                                    .filter(
                                        (entitlement) =>
                                            entitlement.status === 'active',
                                    )
                                    .map((entitlement) => (
                                        <option
                                            key={entitlement.id}
                                            value={entitlement.id}
                                        >
                                            {entitlement.capability}
                                        </option>
                                    ))}
                            </select>

                            <button
                                type="submit"
                                disabled={issue.processing || !hasActiveEntitlement || !issue.data.entitlement_id}
                                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-bold text-white disabled:opacity-60"
                            >
                                <KeyRound className="h-4 w-4" />
                                {issue.processing
                                    ? 'Issuing…'
                                    : 'Issue sandbox license'}
                            </button>
                        </form>
                    </section>

                    <section className="border-sidebar-border/70 bg-card rounded-2xl border p-5">
                        <h2 className="font-bold">2. Validate token</h2>
                        <p className="text-muted-foreground mt-1 text-xs">
                            Checks signature, environment, expiry and persisted
                            revocation state.
                        </p>
                        <form
                            className="mt-5 space-y-4"
                            onSubmit={(event) => {
                                event.preventDefault();
                                validate.post('/sandbox-licenses/validate');
                            }}
                        >
                            <select
                                className="border-input bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                value={validate.data.organization_id}
                                onChange={(event) =>
                                    validate.setData(
                                        'organization_id',
                                        event.target.value,
                                    )
                                }
                                required
                            >
                                <option value="">Select organization</option>
                                {organizations.map((organization) => (
                                    <option
                                        key={organization.id}
                                        value={organization.id}
                                    >
                                        {organization.name}
                                    </option>
                                ))}
                            </select>
                            <textarea
                                className="border-input bg-background min-h-36 w-full rounded-xl border p-3 font-mono text-xs"
                                value={validate.data.license}
                                onChange={(event) =>
                                    validate.setData(
                                        'license',
                                        event.target.value,
                                    )
                                }
                                placeholder="Paste sandbox license token"
                                required
                            />
                            <button
                                type="submit"
                                disabled={validate.processing}
                                className="h-11 w-full rounded-xl border px-4 text-sm font-bold disabled:opacity-60"
                            >
                                {validate.processing
                                    ? 'Validating…'
                                    : 'Validate license'}
                            </button>
                        </form>
                    </section>

                    <section className="border-sidebar-border/70 bg-card rounded-2xl border p-5">
                        <h2 className="font-bold">3. Revoke token</h2>
                        <p className="text-muted-foreground mt-1 text-xs">
                            Persists the JTI revocation and immediately
                            re-validates the token.
                        </p>
                        <form
                            className="mt-5 space-y-4"
                            onSubmit={(event) => {
                                event.preventDefault();
                                revoke.post('/sandbox-licenses/revoke');
                            }}
                        >
                            <select
                                className="border-input bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                value={revoke.data.organization_id}
                                onChange={(event) =>
                                    revoke.setData(
                                        'organization_id',
                                        event.target.value,
                                    )
                                }
                                required
                            >
                                <option value="">Select organization</option>
                                {organizations.map((organization) => (
                                    <option
                                        key={organization.id}
                                        value={organization.id}
                                    >
                                        {organization.name}
                                    </option>
                                ))}
                            </select>
                            <textarea
                                className="border-input bg-background min-h-28 w-full rounded-xl border p-3 font-mono text-xs"
                                value={revoke.data.license}
                                onChange={(event) =>
                                    revoke.setData(
                                        'license',
                                        event.target.value,
                                    )
                                }
                                placeholder="Paste token to revoke"
                                required
                            />
                            <input
                                className="border-input bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                value={revoke.data.reason}
                                onChange={(event) =>
                                    revoke.setData('reason', event.target.value)
                                }
                                placeholder="Reason (optional)"
                                maxLength={255}
                            />
                            <button
                                type="submit"
                                disabled={revoke.processing}
                                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-red-500/30 px-4 text-sm font-bold text-red-500 disabled:opacity-60"
                            >
                                <ShieldAlert className="h-4 w-4" />
                                {revoke.processing
                                    ? 'Revoking…'
                                    : 'Revoke license'}
                            </button>
                        </form>
                    </section>
                </div>

                {licenseResult && (
                    <section className="border-sidebar-border/70 bg-card rounded-2xl border p-5">
                        <div className="flex items-center gap-2 text-sm font-bold text-emerald-600 dark:text-emerald-400">
                            <CheckCircle2 className="h-4 w-4" />
                            Sandbox license issued and validated
                        </div>
                        <textarea
                            readOnly
                            value={licenseResult.token}
                            className="bg-muted/30 mt-4 min-h-28 w-full rounded-xl border p-3 font-mono text-xs"
                        />
                    </section>
                )}

                {validationResult && (
                    <section className="border-sidebar-border/70 bg-card rounded-2xl border p-5">
                        <div className="flex items-center gap-2">
                            {validationResult.valid ? (
                                <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                            ) : (
                                <ShieldAlert className="h-5 w-5 text-red-500" />
                            )}
                            <h2 className="font-bold">
                                Validation:{' '}
                                {validationResult.valid ? 'VALID' : 'INVALID'}
                            </h2>
                        </div>
                        <p className="text-muted-foreground mt-2 text-xs">
                            Reason: {validationResult.reason ?? 'none'}
                        </p>
                        {validationResult.claims && (
                            <pre className="bg-muted/30 mt-4 overflow-x-auto rounded-xl border p-4 text-xs">
                                {JSON.stringify(
                                    validationResult.claims,
                                    null,
                                    2,
                                )}
                            </pre>
                        )}
                    </section>
                )}

                <section className="border-sidebar-border/70 bg-card rounded-2xl border p-5">
                    <div className="flex items-center gap-2">
                        <History className="h-5 w-5 text-red-500" />
                        <div>
                            <h2 className="font-bold">
                                Recent license audit trail
                            </h2>
                            <p className="text-muted-foreground mt-1 text-xs">
                                Latest tenant-scoped issue, validation and
                                revocation evidence.
                            </p>
                        </div>
                    </div>
                    {auditEvents.length === 0 ? (
                        <p className="text-muted-foreground mt-5 text-sm">
                            No sandbox license audit events yet.
                        </p>
                    ) : (
                        <div className="mt-5 overflow-x-auto">
                            <table className="w-full min-w-[760px] text-left text-xs">
                                <thead className="text-muted-foreground border-b">
                                    <tr>
                                        <th className="px-3 py-3 font-semibold">
                                            Time
                                        </th>
                                        <th className="px-3 py-3 font-semibold">
                                            Organization
                                        </th>
                                        <th className="px-3 py-3 font-semibold">
                                            Action
                                        </th>
                                        <th className="px-3 py-3 font-semibold">
                                            Status
                                        </th>
                                        <th className="px-3 py-3 font-semibold">
                                            JTI
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {auditEvents.map((event) => (
                                        <tr
                                            key={event.id}
                                            className="border-b last:border-0"
                                        >
                                            <td className="px-3 py-3 whitespace-nowrap">
                                                {event.created_at
                                                    ? new Date(
                                                          event.created_at,
                                                      ).toLocaleString()
                                                    : '—'}
                                            </td>
                                            <td className="px-3 py-3 font-medium">
                                                {event.organization_id
                                                    ? (organizationNames.get(
                                                          event.organization_id,
                                                      ) ??
                                                      event.organization_id)
                                                    : '—'}
                                            </td>
                                            <td className="px-3 py-3 font-mono">
                                                {event.action}
                                            </td>
                                            <td className="px-3 py-3 uppercase">
                                                {event.status}
                                            </td>
                                            <td className="px-3 py-3 font-mono">
                                                {event.jti
                                                    ? `${event.jti.slice(0, 12)}…`
                                                    : '—'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </section>
            </div>
        </>
    );
}
