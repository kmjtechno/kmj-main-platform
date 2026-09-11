import { Head, useForm } from '@inertiajs/react';
import { CheckCircle2, KeyRound, ShieldAlert, ShieldCheck } from 'lucide-react';

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

type Props = {
    organizations: Organization[];
    licenseResult: LicenseResult | null;
    validationResult: ValidationResult | null;
};

export default function SandboxLicenses({
    organizations,
    licenseResult,
    validationResult,
}: Props) {
    const issue = useForm({ organization_id: '', entitlement_id: '' });
    const validate = useForm({ license: licenseResult?.token ?? '' });
    const revoke = useForm({ license: licenseResult?.token ?? '', reason: '' });

    const selectedOrganization = organizations.find(
        (organization) => organization.id === issue.data.organization_id,
    );

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
                                Issue a short-lived license only from an active entitlement, validate it, then revoke it and confirm the same token fails closed.
                            </p>
                        </div>
                    </div>
                </section>

                <div className="grid gap-6 xl:grid-cols-3">
                    <section className="border-sidebar-border/70 bg-card rounded-2xl border p-5">
                        <h2 className="font-bold">1. Issue license</h2>
                        <p className="text-muted-foreground mt-1 text-xs">Owner-scoped, entitlement-backed, 30-minute sandbox token.</p>
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
                                    <option key={organization.id} value={organization.id}>
                                        {organization.name}
                                    </option>
                                ))}
                            </select>

                            <select
                                className="border-input bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                value={issue.data.entitlement_id}
                                onChange={(event) => issue.setData('entitlement_id', event.target.value)}
                                required
                                disabled={!selectedOrganization}
                            >
                                <option value="">Select active entitlement</option>
                                {selectedOrganization?.entitlements
                                    .filter((entitlement) => entitlement.status === 'active')
                                    .map((entitlement) => (
                                        <option key={entitlement.id} value={entitlement.id}>
                                            {entitlement.capability}
                                        </option>
                                    ))}
                            </select>

                            <button
                                type="submit"
                                disabled={issue.processing}
                                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-bold text-white disabled:opacity-60"
                            >
                                <KeyRound className="h-4 w-4" />
                                {issue.processing ? 'Issuing…' : 'Issue sandbox license'}
                            </button>
                        </form>
                    </section>

                    <section className="border-sidebar-border/70 bg-card rounded-2xl border p-5">
                        <h2 className="font-bold">2. Validate token</h2>
                        <p className="text-muted-foreground mt-1 text-xs">Checks signature, environment, expiry and persisted revocation state.</p>
                        <form
                            className="mt-5 space-y-4"
                            onSubmit={(event) => {
                                event.preventDefault();
                                validate.post('/sandbox-licenses/validate');
                            }}
                        >
                            <textarea
                                className="border-input bg-background min-h-36 w-full rounded-xl border p-3 font-mono text-xs"
                                value={validate.data.license}
                                onChange={(event) => validate.setData('license', event.target.value)}
                                placeholder="Paste sandbox license token"
                                required
                            />
                            <button
                                type="submit"
                                disabled={validate.processing}
                                className="h-11 w-full rounded-xl border px-4 text-sm font-bold disabled:opacity-60"
                            >
                                {validate.processing ? 'Validating…' : 'Validate license'}
                            </button>
                        </form>
                    </section>

                    <section className="border-sidebar-border/70 bg-card rounded-2xl border p-5">
                        <h2 className="font-bold">3. Revoke token</h2>
                        <p className="text-muted-foreground mt-1 text-xs">Persists the JTI revocation and immediately re-validates the token.</p>
                        <form
                            className="mt-5 space-y-4"
                            onSubmit={(event) => {
                                event.preventDefault();
                                revoke.post('/sandbox-licenses/revoke');
                            }}
                        >
                            <textarea
                                className="border-input bg-background min-h-28 w-full rounded-xl border p-3 font-mono text-xs"
                                value={revoke.data.license}
                                onChange={(event) => revoke.setData('license', event.target.value)}
                                placeholder="Paste token to revoke"
                                required
                            />
                            <input
                                className="border-input bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                value={revoke.data.reason}
                                onChange={(event) => revoke.setData('reason', event.target.value)}
                                placeholder="Reason (optional)"
                                maxLength={255}
                            />
                            <button
                                type="submit"
                                disabled={revoke.processing}
                                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-red-500/30 px-4 text-sm font-bold text-red-500 disabled:opacity-60"
                            >
                                <ShieldAlert className="h-4 w-4" />
                                {revoke.processing ? 'Revoking…' : 'Revoke license'}
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
                                Validation: {validationResult.valid ? 'VALID' : 'INVALID'}
                            </h2>
                        </div>
                        <p className="text-muted-foreground mt-2 text-xs">
                            Reason: {validationResult.reason ?? 'none'}
                        </p>
                        {validationResult.claims && (
                            <pre className="bg-muted/30 mt-4 overflow-x-auto rounded-xl border p-4 text-xs">
                                {JSON.stringify(validationResult.claims, null, 2)}
                            </pre>
                        )}
                    </section>
                )}
            </div>
        </>
    );
}
