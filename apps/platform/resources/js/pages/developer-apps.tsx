import { Head, Link, useForm } from '@inertiajs/react';
import { useMemo, useState } from 'react';
import {
    ArrowRight,
    BookOpen,
    CheckCircle2,
    Code2,
    Copy,
    KeyRound,
    Layers3,
    LockKeyhole,
    Plus,
    ShieldCheck,
} from 'lucide-react';

type Organization = {
    id: string;
    name: string;
    role: string;
    issuer_status: string;
    product_limit: number;
    monthly_issue_limit: number | null;
    registered_products: number;
    monthly_issued: number;
    product_remaining: number | null;
    monthly_remaining: number | null;
    current_period_end: string | null;
};

type Application = {
    id: string;
    organization_id: string;
    product_code: string;
    name: string;
    status: string;
    created_at: string;
    pending_reseller_evidence_count?: number | null;
};

type LicenseKey = {
    id: string;
    organization_id: string;
    licensed_product_id: string;
    license_id: string;
    customer_id: string;
    display_prefix: string;
    plan: string;
    expires_at: string;
    revoked_at: string | null;
    first_activated_at: string | null;
    recorded_binding_count: number;
    non_deactivated_binding_count: number;
    last_activation_at: string | null;
};

type IssuedKey = {
    key: string;
    license_id: string;
    product_code: string;
};

type IssuedBatchKey = IssuedKey & {
    customer_id: string;
};

type ResellerReviewProduct = {
    id: string;
    name: string;
    product_code: string;
    expires_at: string;
    pending_evidence_count: number | null;
};

export type DeveloperWorkspaceProps = {
    organizations: Organization[];
    applications: Application[];
    keys: LicenseKey[];
    canIssueKeys: boolean;
    resellerReview?: {
        products: ResellerReviewProduct[];
        truncated: boolean;
    };
    canAccessOwnerHub: boolean;
    newKey: IssuedKey | null;
    newKeys: IssuedBatchKey[] | null;
};

const languages = [
    'TypeScript',
    'Python',
    'C# / .NET',
    'C++ / Qt',
    'Rust',
    'Go',
    'Java',
    'PHP',
] as const;

function sdkConfiguration(language: string, productCode: string): string {
    // Generate source-only integration starters from a canonical public
    // configuration. Never embed an issuer private key or customer's key.
    const product = JSON.stringify(productCode);
    const contract = JSON.stringify(
        'https://kmjtechno.com/api/v1/kslp/contract',
    );
    const keys = JSON.stringify(
        'https://kmjtechno.com/api/v1/kslp/keys/license',
    );
    const warning =
        'STAGING STARTER ONLY: obtain and verify signed KSLP leases,';
    const warning2 =
        'never trust an activation ID as a commercial entitlement.';

    switch (language) {
        case 'TypeScript':
            return [
                '// ' + warning,
                '// ' + warning2,
                'export const kmjLicense = {',
                '    product: ' + product + ',',
                '    contractUrl: ' + contract + ',',
                '    publicKeyUrl: ' + keys + ',',
                '    requireEd25519: true,',
                '} as const;',
            ].join('\n');
        case 'Python':
            return [
                '# ' + warning,
                '# ' + warning2,
                'KMJ_LICENSE = {',
                '    "product": ' + product + ',',
                '    "contract_url": ' + contract + ',',
                '    "public_key_url": ' + keys + ',',
                '    "require_ed25519": True,',
                '}',
            ].join('\n');
        case 'C# / .NET':
            return [
                '// ' + warning,
                '// ' + warning2,
                'internal static class KmjLicenseConfig {',
                '    public const string Product = ' + product + ';',
                '    public const string ContractUrl = ' + contract + ';',
                '    public const string PublicKeysUrl = ' + keys + ';',
                '}',
            ].join('\n');
        case 'C++ / Qt':
            return [
                '// ' + warning,
                '// ' + warning2,
                '#include <string_view>',
                'namespace kmj {',
                'constexpr std::string_view product = ' + product + ';',
                'constexpr std::string_view contract_url = ' + contract + ';',
                'constexpr std::string_view public_keys_url = ' + keys + ';',
                '}',
            ].join('\n');
        case 'Rust':
            return [
                '// ' + warning,
                '// ' + warning2,
                'pub const KMJ_PRODUCT: &str = ' + product + ';',
                'pub const KMJ_CONTRACT: &str = ' + contract + ';',
                'pub const KMJ_PUBLIC_KEYS: &str = ' + keys + ';',
            ].join('\n');
        case 'Go':
            return [
                '// ' + warning,
                '// ' + warning2,
                'package licensing',
                'const Product = ' + product,
                'const ContractURL = ' + contract,
                'const PublicKeysURL = ' + keys,
            ].join('\n');
        case 'Java':
            return [
                '// ' + warning,
                '// ' + warning2,
                'public final class KmjLicenseConfig {',
                '    public static final String PRODUCT = ' + product + ';',
                '    public static final String CONTRACT_URL = ' +
                    contract +
                    ';',
                '    public static final String PUBLIC_KEYS_URL = ' +
                    keys +
                    ';',
                '    private KmjLicenseConfig() {}',
                '}',
            ].join('\n');
        default:
            return [
                '<?php',
                '// ' + warning,
                '// ' + warning2,
                '$kmjLicense = [',
                '    "product" => ' + product + ',',
                '    "contract_url" => ' + contract + ',',
                '    "public_key_url" => ' + keys + ',',
                '];',
            ].join('\n');
    }
}

export function DeveloperAppsWorkspace({
    organizations,
    applications,
    keys,
    canIssueKeys,
    resellerReview,
    canAccessOwnerHub,
    newKey,
    newKeys,
    embedded = false,
}: DeveloperWorkspaceProps & { embedded?: boolean }) {
    const [language, setLanguage] = useState<string>('TypeScript');
    const [selectedApp, setSelectedApp] = useState<string>('');
    const [copied, setCopied] = useState(false);
    const [revokeKeyId, setRevokeKeyId] = useState<string | null>(null);
    const [manageAppId, setManageAppId] = useState<string | null>(null);
    const revokeForm = useForm({ reason: '' });
    const manageAppForm = useForm({
        organization_id: '',
        action: 'pause',
        name: '',
        reason: '',
    });
    const createOrganization = useForm({ name: '' });
    const createApp = useForm({
        organization_id: organizations[0]?.id ?? '',
        name: '',
        product_code: '',
    });
    const issueKey = useForm({
        organization_id: organizations[0]?.id ?? '',
        product_code: '',
        customer_id: '',
        plan: 'trial',
    });
    const batchKeys = useForm({
        organization_id: organizations[0]?.id ?? '',
        product_code: '',
        customers: '',
        reason: '',
    });

    const batchEligibleApps = applications.filter(
        (app) =>
            app.organization_id === batchKeys.data.organization_id &&
            app.status === 'active',
    );
    const batchIssuer = organizations.find(
        (org) => org.id === batchKeys.data.organization_id,
    );
    const canIssueBatch =
        canIssueKeys && batchIssuer?.issuer_status === 'active';
    const eligibleApps = applications.filter(
        (app) =>
            app.organization_id === issueKey.data.organization_id &&
            app.status === 'active',
    );
    const displayedApp = applications.find((app) => app.id === selectedApp);
    const selectedIssuer = organizations.find(
        (org) => org.id === createApp.data.organization_id,
    );
    const sdkText = useMemo(
        () =>
            sdkConfiguration(
                language,
                displayedApp?.product_code ?? 'YOUR_APP',
            ),
        [language, displayedApp?.product_code],
    );
    const canRegister =
        canIssueKeys && selectedIssuer?.issuer_status === 'active';
    const selectedKeyIssuer = organizations.find(
        (org) => org.id === issueKey.data.organization_id,
    );
    const canGenerateTrialKey =
        canIssueKeys && selectedKeyIssuer?.issuer_status === 'active';

    const downloadSetup = () => {
        const extension: Record<string, string> = {
            TypeScript: 'ts',
            Python: 'py',
            'C# / .NET': 'cs',
            'C++ / Qt': 'cpp',
            Rust: 'rs',
            Go: 'go',
            Java: 'java',
            PHP: 'php',
        };
        const file = new Blob([sdkText + '\n'], {
            type: 'text/plain;charset=utf-8',
        });
        const objectUrl = URL.createObjectURL(file);
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download =
            language === 'Java'
                ? 'KmjLicenseConfig.java'
                : 'kmj-licensing-setup.' + (extension[language] ?? 'txt');
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(objectUrl);
    };

    const copyText = async (value: string) => {
        try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
        } catch {
            setCopied(false);
        }
    };

    return (
        <>
            {!embedded && <Head title="KMJ Licensing Hub · Developer Apps" />}
            <div
                className={
                    embedded
                        ? 'flex min-w-0 flex-col gap-6'
                        : 'owner-shared-page flex min-w-0 flex-1 flex-col gap-6 p-4 sm:p-7'
                }
            >
                <section
                    className={
                        embedded
                            ? 'hidden'
                            : 'overflow-hidden rounded-2xl border bg-gradient-to-br from-[#111b29] via-[#10151f] to-[#231523] p-6 text-white sm:p-8'
                    }
                >
                    <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-center">
                        <div className="max-w-2xl">
                            <div className="mb-3 flex items-center gap-2 text-xs font-bold tracking-[0.14em] text-amber-300 uppercase">
                                <Layers3 className="size-4" /> KMJ Licensing Hub
                                · Developer Console
                            </div>
                            <h1 className="text-3xl font-black tracking-tight sm:text-4xl">
                                Your apps. Your license keys.
                            </h1>
                            <p className="mt-3 text-sm leading-6 text-slate-300">
                                Register an application, issue a customer key,
                                connect a verified device and prepare a
                                language-specific SDK. This developer workspace
                                only manages permitted organization apps and
                                keys; global customer/license policy remains
                                Super Admin-only in KMJ Main Platform.
                            </p>
                        </div>
                        <div className="flex flex-wrap gap-2 text-xs">
                            <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-emerald-200">
                                Ed25519 trust model
                            </span>
                            <span className="rounded-full border border-white/20 px-3 py-2 text-slate-200">
                                Tenant-isolated
                            </span>
                        </div>
                    </div>
                    <div className="mt-7 grid gap-3 sm:grid-cols-3">
                        {[
                            [
                                '1',
                                'Create your app',
                                'Register under an approved developer organization',
                            ],
                            [
                                '2',
                                'Generate a key',
                                'Issue against an authorized subscription and license',
                            ],
                            [
                                '3',
                                'Integrate SDK',
                                'Select language and complete device activation',
                            ],
                        ].map(([step, title, detail]) => (
                            <div
                                key={step}
                                className="rounded-xl border border-white/10 bg-white/5 p-4"
                            >
                                <span className="text-xs font-black text-amber-300">
                                    STEP {step}
                                </span>
                                <h2 className="mt-2 font-bold">{title}</h2>
                                <p className="mt-1 text-xs leading-5 text-slate-300">
                                    {detail}
                                </p>
                            </div>
                        ))}
                    </div>
                </section>

                <section
                    aria-label="KMJ licensing authority and workspaces"
                    className="bg-card rounded-2xl border p-5 sm:p-6"
                >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                            <h2 className="text-base font-bold">
                                One KMJ Licensing Hub · Developer workspace
                            </h2>
                            <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-6">
                                This is your organization-scoped app and
                                trial-key workspace. The Super Admin Licensing
                                Hub governs platform-wide CloudOS commercial
                                licenses, policies, renewals and audit. These
                                are different records under the same KMJ
                                authority: an existing commercial license does
                                not create a developer issuer subscription.
                            </p>
                        </div>
                        {canAccessOwnerHub && (
                            <Link
                                href="/operator/kslp#issuer-workspaces"
                                className="inline-flex min-h-10 items-center gap-2 rounded-xl border px-3 py-2 text-xs font-bold hover:border-red-500/40"
                            >
                                Super Admin · Issuer overview
                                <ArrowRight className="size-4" />
                            </Link>
                        )}
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                        <div className="rounded-xl border p-3">
                            <p className="text-xs font-semibold">
                                Developer rollout
                            </p>
                            <p className="mt-1 text-sm font-bold">
                                {canIssueKeys
                                    ? 'Available for authorized issuers'
                                    : 'Protected — globally disabled'}
                            </p>
                        </div>
                        <div className="rounded-xl border p-3">
                            <p className="text-xs font-semibold">
                                Selected issuer subscription
                            </p>
                            <p className="mt-1 text-sm font-bold">
                                {selectedIssuer?.issuer_status ??
                                    'No organization'}
                            </p>
                        </div>
                        <div className="rounded-xl border p-3">
                            <p className="text-xs font-semibold">
                                Commercial customer licenses
                            </p>
                            <p className="text-muted-foreground mt-1 text-xs">
                                Issued by governed KSLP entitlement authority,
                                not by an unverified trial-key form
                            </p>
                        </div>
                    </div>
                    {!canRegister && organizations.length > 0 && (
                        <p
                            role="status"
                            className="text-muted-foreground mt-3 text-xs leading-5"
                        >
                            {canIssueKeys
                                ? 'This organization has no currently active issuer subscription. Owner approval and recorded commercial entitlement are required before app registration.'
                                : 'Developer issuance is paused by a platform-wide release gate. An active owner-issued license does not bypass this gate or create an issuer subscription.'}
                        </p>
                    )}
                </section>

                {resellerReview && resellerReview.products.length > 0 && (
                    <section
                        aria-labelledby="reseller-review-heading"
                        className="bg-card rounded-2xl border p-5 sm:p-6"
                    >
                        <h2
                            id="reseller-review-heading"
                            className="text-base font-bold"
                        >
                            Reseller workspace · Evidence review
                        </h2>
                        <p className="text-muted-foreground mt-2 text-sm">
                            Only products explicitly delegated to your current
                            verified membership are shown. Review access does
                            not authorize license management, payments, credits
                            or paid issuance.
                        </p>
                        <div className="mt-4 grid gap-3 sm:grid-cols-2">
                            {resellerReview.products.map((product) => (
                                <article
                                    key={product.id}
                                    className="rounded-xl border p-4"
                                >
                                    <h3 className="font-semibold">
                                        {product.name}
                                    </h3>
                                    <p className="text-muted-foreground mt-1 font-mono text-xs">
                                        {product.product_code}
                                    </p>
                                    <p className="mt-3 text-sm font-bold">
                                        {product.pending_evidence_count === null
                                            ? 'Evidence not available'
                                            : `${product.pending_evidence_count} pending review`}
                                    </p>
                                    <p className="text-muted-foreground mt-2 text-xs">
                                        Review permission expires:{' '}
                                        {product.expires_at}
                                    </p>
                                </article>
                            ))}
                        </div>
                        {resellerReview.truncated && (
                            <p className="text-muted-foreground mt-3 text-xs">
                                Showing the first 50 authorized products.
                            </p>
                        )}
                    </section>
                )}

                <section
                    id="issuer-quota-snapshot"
                    aria-labelledby="issuer-quota-heading"
                    className="bg-card rounded-2xl border p-5 sm:p-6"
                >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                            <h2
                                id="issuer-quota-heading"
                                className="text-base font-bold"
                            >
                                Issuer limits · Read-only snapshot
                            </h2>
                            <p className="text-muted-foreground mt-2 max-w-3xl text-xs leading-5">
                                Issuer quota is not a reseller wallet balance.
                                Counts use the same server-month window as the
                                delegated license gate. Revoked keys still count
                                toward issued licenses. Only organizations where
                                you have license management permission are
                                shown.
                            </p>
                        </div>
                        <span className="rounded-full border px-3 py-1 text-xs font-semibold">
                            {canIssueKeys
                                ? 'Issuance still requires server approval'
                                : 'Issuance currently disabled'}
                        </span>
                    </div>
                    {organizations.length === 0 ? (
                        <p className="text-muted-foreground mt-4 text-xs">
                            No authorized issuer organization is linked to this
                            account. No quota or credit entitlement is implied.
                        </p>
                    ) : (
                        <div className="mt-4 grid gap-3 lg:grid-cols-2">
                            {organizations.map((organization) => (
                                <article
                                    key={organization.id}
                                    className="border-border rounded-xl border p-4"
                                >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <h3 className="text-sm font-bold">
                                            {organization.name}
                                        </h3>
                                        <span className="bg-muted rounded-full px-3 py-1 text-xs font-bold">
                                            {organization.issuer_status}
                                        </span>
                                    </div>
                                    <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
                                        <div>
                                            <dt className="text-muted-foreground">
                                                Registered apps
                                            </dt>
                                            <dd className="mt-1 font-semibold tabular-nums">
                                                {
                                                    organization.registered_products
                                                }
                                                {' / '}
                                                {organization.issuer_status ===
                                                'not_subscribed'
                                                    ? 'Not subscribed'
                                                    : organization.product_limit}
                                            </dd>
                                        </div>
                                        <div>
                                            <dt className="text-muted-foreground">
                                                Monthly licenses issued
                                            </dt>
                                            <dd className="mt-1 font-semibold tabular-nums">
                                                {organization.monthly_issued}
                                                {' / '}
                                                {organization.monthly_issue_limit ??
                                                    'Not subscribed'}
                                            </dd>
                                        </div>
                                        <div>
                                            <dt className="text-muted-foreground">
                                                Apps remaining
                                            </dt>
                                            <dd className="mt-1 font-semibold tabular-nums">
                                                {organization.product_remaining ??
                                                    'Not available'}
                                            </dd>
                                        </div>
                                        <div>
                                            <dt className="text-muted-foreground">
                                                Monthly issues remaining
                                            </dt>
                                            <dd className="mt-1 font-semibold tabular-nums">
                                                {organization.monthly_remaining ??
                                                    'Not available'}
                                            </dd>
                                        </div>
                                    </dl>
                                    <p className="text-muted-foreground mt-4 text-xs leading-5">
                                        Remaining figures are policy snapshots,
                                        not spendable credits, payment proof,
                                        trial activation or authorization to
                                        create signed commercial licenses.
                                    </p>
                                </article>
                            ))}
                        </div>
                    )}
                </section>

                {!canIssueKeys && (
                    <section
                        role="status"
                        className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm"
                    >
                        <div className="flex items-center gap-2 font-bold">
                            <LockKeyhole className="size-4" /> Protected rollout
                            — issuance disabled
                        </div>
                        <p className="text-muted-foreground mt-1">
                            Storage migration, integration tests and device
                            activation verification must pass before application
                            registration and customer keys are enabled. Existing
                            Sandbox License Center remains available for
                            testing.
                        </p>
                    </section>
                )}
                {newKey && (
                    <section
                        className="rounded-xl border border-emerald-500/35 bg-emerald-500/5 p-5"
                        aria-label="New license key"
                    >
                        <h2 className="flex items-center gap-2 font-bold">
                            <CheckCircle2 className="size-5 text-emerald-600" />{' '}
                            License key created
                        </h2>
                        <p className="text-muted-foreground mt-2 text-xs">
                            This is the only full-key display. Save it in a
                            secure password manager. It is a bootstrap key, not
                            a signed offline entitlement.
                        </p>
                        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                            <input
                                className="bg-background w-full min-w-0 rounded-lg border px-3 py-3 font-mono text-xs"
                                value={newKey.key}
                                readOnly
                                aria-label="One-time license key"
                            />
                            <button
                                type="button"
                                className="inline-flex items-center justify-center gap-2 rounded-lg border px-4 py-2 text-xs font-bold"
                                onClick={() => void copyText(newKey.key)}
                            >
                                <Copy className="size-4" />{' '}
                                {copied ? 'Copied' : 'Copy key'}
                            </button>
                        </div>
                        <p className="text-muted-foreground mt-2 font-mono text-xs break-all">
                            App: {newKey.product_code} · License ID:{' '}
                            {newKey.license_id}
                        </p>
                    </section>
                )}
                {newKeys && newKeys.length > 0 && (
                    <section
                        className="rounded-xl border border-emerald-500/35 bg-emerald-500/5 p-5"
                        aria-label="One-time trial batch keys"
                    >
                        <h2 className="font-bold">
                            Trial batch created — {newKeys.length} one-time keys
                        </h2>
                        <p className="text-muted-foreground mt-2 text-xs">
                            Save these secrets in your approved password manager
                            now. They cannot be retrieved again. These are trial
                            bootstrap keys, NOT paid rights or signed offline
                            licenses.
                        </p>
                        <div className="mt-3 space-y-2">
                            {newKeys.map((issued) => (
                                <div
                                    key={issued.license_id}
                                    className="flex flex-wrap items-center gap-2 rounded-lg border p-2 text-xs"
                                >
                                    <span className="min-w-0 flex-1 font-mono break-all">
                                        {issued.customer_id}: {issued.key}
                                    </span>
                                    <button
                                        type="button"
                                        className="min-h-10 rounded-lg border px-3"
                                        onClick={() =>
                                            void copyText(issued.key)
                                        }
                                    >
                                        Copy
                                    </button>
                                </div>
                            ))}
                        </div>
                        <button
                            type="button"
                            className="mt-3 min-h-10 rounded-lg border px-4 text-xs font-bold"
                            onClick={() =>
                                void copyText(
                                    newKeys
                                        .map(
                                            (key) =>
                                                key.customer_id +
                                                ': ' +
                                                key.key,
                                        )
                                        .join('\n'),
                                )
                            }
                        >
                            Copy one-time batch
                        </button>
                    </section>
                )}

                {organizations.length === 0 && (
                    <section className="bg-card rounded-2xl border p-5 sm:p-6">
                        <h2 className="text-lg font-bold">
                            Start by creating your organization
                        </h2>
                        <p className="text-muted-foreground mt-1 text-sm">
                            A workspace separates your apps and customer
                            licences from other accounts. An approved developer
                            subscription will still be required before issuance.
                        </p>
                        <form
                            className="mt-4 flex flex-col gap-3 sm:flex-row"
                            onSubmit={(event) => {
                                event.preventDefault();
                                createOrganization.post(
                                    '/developer/organizations',
                                );
                            }}
                        >
                            <input
                                aria-label="Organization name"
                                placeholder="Your company or developer team"
                                className="bg-background min-h-11 flex-1 rounded-xl border px-3 text-sm"
                                maxLength={160}
                                value={createOrganization.data.name}
                                onChange={(event) =>
                                    createOrganization.setData(
                                        'name',
                                        event.target.value,
                                    )
                                }
                                required
                            />
                            <button
                                type="submit"
                                disabled={createOrganization.processing}
                                className="min-h-11 rounded-xl bg-red-600 px-5 text-sm font-bold text-white disabled:opacity-50"
                            >
                                Create organization
                            </button>
                        </form>
                        {Object.values(createOrganization.errors).map(
                            (error, index) => (
                                <p
                                    className="mt-2 text-xs text-red-500"
                                    key={index}
                                >
                                    {error}
                                </p>
                            ),
                        )}
                    </section>
                )}
                <div className="grid gap-5 xl:grid-cols-2">
                    <section
                        id="developer-app-create"
                        className="bg-card rounded-2xl border p-5 sm:p-6"
                    >
                        <h2 className="flex items-center gap-2 text-lg font-bold">
                            <Plus className="size-5 text-red-500" /> 1. Register
                            an application
                        </h2>
                        <p className="text-muted-foreground mt-1 text-xs">
                            You need an active issuer subscription. Registration
                            never creates a paid entitlement automatically.
                        </p>
                        <form
                            className="mt-5 space-y-3"
                            onSubmit={(event) => {
                                event.preventDefault();
                                createApp.post('/developer/apps', {
                                    preserveScroll: true,
                                });
                            }}
                        >
                            <label
                                className="block text-xs font-semibold"
                                htmlFor="application-org"
                            >
                                Organization
                            </label>
                            <select
                                id="application-org"
                                className="bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                value={createApp.data.organization_id}
                                onChange={(event) =>
                                    createApp.setData(
                                        'organization_id',
                                        event.target.value,
                                    )
                                }
                            >
                                {organizations.length === 0 && (
                                    <option value="">
                                        No manageable organization
                                    </option>
                                )}
                                {organizations.map((org) => (
                                    <option key={org.id} value={org.id}>
                                        {org.name} · {org.issuer_status}
                                    </option>
                                ))}
                            </select>
                            <label
                                className="block text-xs font-semibold"
                                htmlFor="application-name"
                            >
                                Application name
                            </label>
                            <input
                                id="application-name"
                                className="bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                maxLength={160}
                                placeholder="My Cinema Player"
                                value={createApp.data.name}
                                onChange={(event) =>
                                    createApp.setData(
                                        'name',
                                        event.target.value,
                                    )
                                }
                                required
                            />
                            <label
                                className="block text-xs font-semibold"
                                htmlFor="application-code"
                            >
                                Unique application ID
                            </label>
                            <input
                                id="application-code"
                                className="bg-background h-11 w-full rounded-xl border px-3 font-mono text-sm"
                                maxLength={96}
                                placeholder="MYCOMPANY.CINEMA"
                                value={createApp.data.product_code}
                                onChange={(event) =>
                                    createApp.setData(
                                        'product_code',
                                        event.target.value
                                            .toUpperCase()
                                            .replace(/[^A-Z0-9_.:-]/g, ''),
                                    )
                                }
                                required
                            />
                            <p className="text-muted-foreground text-xs">
                                Use 3–96 uppercase letters, numbers, dot, dash,
                                underscore or colon.
                            </p>
                            {Object.values(createApp.errors).map(
                                (error, index) => (
                                    <p
                                        className="text-xs text-red-500"
                                        key={index}
                                    >
                                        {error}
                                    </p>
                                ),
                            )}
                            <button
                                type="submit"
                                disabled={!canRegister || createApp.processing}
                                className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-bold text-white disabled:opacity-40"
                            >
                                <Plus className="size-4" />{' '}
                                {createApp.processing
                                    ? 'Registering…'
                                    : 'Register application'}
                            </button>
                        </form>
                    </section>

                    <section
                        id="developer-app-key"
                        className="bg-card rounded-2xl border p-5 sm:p-6"
                    >
                        <h2 className="flex items-center gap-2 text-lg font-bold">
                            <KeyRound className="size-5 text-red-500" /> 2.
                            Issue a customer license key
                        </h2>
                        <p className="text-muted-foreground mt-1 text-xs">
                            Cryptographically random, stored only as a digest.
                            Requires authorized app, issuer quota and recent
                            password confirmation.
                        </p>
                        <form
                            className="mt-5 space-y-3"
                            onSubmit={(event) => {
                                event.preventDefault();
                                issueKey.post('/developer/keys', {
                                    preserveScroll: true,
                                });
                            }}
                        >
                            <label
                                className="block text-xs font-semibold"
                                htmlFor="key-org"
                            >
                                Organization
                            </label>
                            <select
                                id="key-org"
                                className="bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                value={issueKey.data.organization_id}
                                onChange={(event) =>
                                    issueKey.setData({
                                        ...issueKey.data,
                                        organization_id: event.target.value,
                                        product_code: '',
                                    })
                                }
                            >
                                {organizations.map((org) => (
                                    <option key={org.id} value={org.id}>
                                        {org.name}
                                    </option>
                                ))}
                            </select>
                            <label
                                className="block text-xs font-semibold"
                                htmlFor="key-app"
                            >
                                Registered app
                            </label>
                            <select
                                id="key-app"
                                className="bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                value={issueKey.data.product_code}
                                onChange={(event) =>
                                    issueKey.setData(
                                        'product_code',
                                        event.target.value,
                                    )
                                }
                                required
                            >
                                <option value="">Select your app</option>
                                {eligibleApps.map((app) => (
                                    <option
                                        value={app.product_code}
                                        key={app.id}
                                    >
                                        {app.name} ({app.product_code})
                                    </option>
                                ))}
                            </select>
                            <label
                                className="block text-xs font-semibold"
                                htmlFor="key-customer"
                            >
                                Customer reference
                            </label>
                            <input
                                id="key-customer"
                                className="bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                maxLength={128}
                                placeholder="customer-001"
                                value={issueKey.data.customer_id}
                                onChange={(event) =>
                                    issueKey.setData(
                                        'customer_id',
                                        event.target.value,
                                    )
                                }
                                required
                            />
                            <label
                                className="block text-xs font-semibold"
                                htmlFor="key-plan"
                            >
                                License plan
                            </label>
                            <select
                                id="key-plan"
                                className="bg-background h-11 w-full rounded-xl border px-3 text-sm"
                                value={issueKey.data.plan}
                                onChange={(event) =>
                                    issueKey.setData('plan', event.target.value)
                                }
                            >
                                {['trial'].map((plan) => (
                                    <option value={plan} key={plan}>
                                        {plan} — pending commercial payment
                                        verification
                                    </option>
                                ))}
                            </select>
                            {Object.values(issueKey.errors).map(
                                (error, index) => (
                                    <p
                                        className="text-xs text-red-500"
                                        key={index}
                                    >
                                        {error}
                                    </p>
                                ),
                            )}
                            <button
                                type="submit"
                                disabled={
                                    !canGenerateTrialKey ||
                                    !issueKey.data.product_code ||
                                    issueKey.processing
                                }
                                className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-bold text-white disabled:opacity-40"
                            >
                                <KeyRound className="size-4" />{' '}
                                {issueKey.processing
                                    ? 'Generating…'
                                    : 'Generate license key'}
                            </button>
                        </form>
                    </section>
                </div>

                <section
                    id="developer-trial-batch"
                    className="bg-card rounded-2xl border p-5 sm:p-6"
                >
                    <h2 className="flex items-center gap-2 text-lg font-bold">
                        <Layers3 className="size-5 text-red-500" />
                        Trial batch — 2 to 10 customers
                    </h2>
                    <p className="text-muted-foreground mt-1 text-xs">
                        Enter one unique customer reference per line. Either all
                        keys are issued or none. This is trial-only; commercial
                        license issuance requires verified payment rights.
                    </p>
                    <form
                        className="mt-4 grid gap-3 md:grid-cols-2"
                        onSubmit={(event) => {
                            event.preventDefault();
                            batchKeys.post('/developer/keys/batch', {
                                preserveScroll: true,
                                onSuccess: () =>
                                    batchKeys.reset('customers', 'reason'),
                            });
                        }}
                    >
                        <div className="space-y-2">
                            <label
                                className="block text-xs font-semibold"
                                htmlFor="batch-org"
                            >
                                Authorized issuer organization
                            </label>
                            <select
                                id="batch-org"
                                className="bg-background min-h-11 w-full rounded-lg border px-3 text-sm"
                                value={batchKeys.data.organization_id}
                                onChange={(event) =>
                                    batchKeys.setData({
                                        ...batchKeys.data,
                                        organization_id: event.target.value,
                                        product_code: '',
                                    })
                                }
                            >
                                {organizations.map((org) => (
                                    <option key={org.id} value={org.id}>
                                        {org.name}
                                    </option>
                                ))}
                            </select>
                            <label
                                className="block text-xs font-semibold"
                                htmlFor="batch-app"
                            >
                                Registered application
                            </label>
                            <select
                                id="batch-app"
                                className="bg-background min-h-11 w-full rounded-lg border px-3 text-sm"
                                value={batchKeys.data.product_code}
                                onChange={(event) =>
                                    batchKeys.setData(
                                        'product_code',
                                        event.target.value,
                                    )
                                }
                                required
                            >
                                <option value="">Select your app</option>
                                {batchEligibleApps.map((app) => (
                                    <option
                                        key={app.id}
                                        value={app.product_code}
                                    >
                                        {app.name} ({app.product_code})
                                    </option>
                                ))}
                            </select>
                            <label
                                className="block text-xs font-semibold"
                                htmlFor="batch-reason"
                            >
                                Audit reason
                            </label>
                            <input
                                id="batch-reason"
                                className="bg-background min-h-11 w-full rounded-lg border px-3 text-sm"
                                minLength={8}
                                maxLength={240}
                                placeholder="Approved QA trial for customer onboarding"
                                value={batchKeys.data.reason}
                                onChange={(event) =>
                                    batchKeys.setData(
                                        'reason',
                                        event.target.value,
                                    )
                                }
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <label
                                className="block text-xs font-semibold"
                                htmlFor="batch-customers"
                            >
                                Customer references (one per line)
                            </label>
                            <textarea
                                id="batch-customers"
                                className="bg-background min-h-32 w-full rounded-lg border p-3 font-mono text-sm"
                                rows={5}
                                maxLength={1400}
                                placeholder={'customer-001\ncustomer-002'}
                                value={batchKeys.data.customers}
                                onChange={(event) =>
                                    batchKeys.setData(
                                        'customers',
                                        event.target.value,
                                    )
                                }
                                required
                            />
                            <p className="text-muted-foreground text-xs">
                                2–10 unique references, 3–128 characters each.
                                Letters, digits, dot, dash, underscore, colon
                                and @ only.
                            </p>
                            {Object.values(batchKeys.errors).map(
                                (error, index) => (
                                    <p
                                        key={index}
                                        className="text-xs text-red-500"
                                    >
                                        {error}
                                    </p>
                                ),
                            )}
                            <button
                                type="submit"
                                disabled={
                                    !canIssueBatch ||
                                    !batchKeys.data.product_code ||
                                    batchKeys.processing
                                }
                                className="min-h-11 w-full rounded-xl bg-red-600 px-4 text-sm font-bold text-white disabled:opacity-40"
                            >
                                {batchKeys.processing
                                    ? 'Issuing secured trial batch…'
                                    : 'Issue trial batch — one-time keys'}
                            </button>
                        </div>
                    </form>
                </section>

                <section className="bg-card rounded-2xl border p-5 sm:p-6">
                    <h2 className="font-bold">
                        Your applications and issued licenses
                    </h2>
                    <p className="text-muted-foreground mt-1 text-xs">
                        Tenant-scoped records. Existing keys cannot be retrieved
                        in plaintext.
                    </p>
                    <div className="mt-4 grid gap-4 lg:grid-cols-2">
                        <div className="space-y-2">
                            {applications.length === 0 ? (
                                <p className="text-muted-foreground rounded-xl border border-dashed p-5 text-sm">
                                    No developer applications yet.
                                </p>
                            ) : (
                                applications.map((app) => (
                                    <article
                                        key={app.id}
                                        className="rounded-xl border p-3"
                                    >
                                        <div className="flex items-center justify-between gap-2">
                                            <p className="font-semibold">
                                                {app.name}
                                            </p>
                                            <span className="rounded-full border px-2 py-1 text-[11px]">
                                                {app.status}
                                            </span>
                                        </div>
                                        <p className="text-muted-foreground mt-1 font-mono text-xs">
                                            {app.product_code}
                                        </p>
                                        <div className="mt-3 rounded-lg border p-3">
                                            <p className="text-xs font-semibold">
                                                Reseller funding evidence
                                            </p>
                                            <p className="mt-1 text-sm font-bold">
                                                {app.pending_reseller_evidence_count ==
                                                null
                                                    ? 'Evidence not available'
                                                    : `${app.pending_reseller_evidence_count} pending review`}
                                            </p>
                                            <p className="text-muted-foreground mt-1 text-xs leading-5">
                                                Unverified evidence only. No
                                                spendable credits or paid
                                                issuance are enabled.
                                            </p>
                                        </div>
                                        {(app.status === 'active' ||
                                            (canIssueKeys &&
                                                app.status === 'paused')) && (
                                            <button
                                                type="button"
                                                className="mt-3 min-h-10 rounded-lg border px-3 text-xs font-bold"
                                                onClick={() => {
                                                    if (
                                                        manageAppId === app.id
                                                    ) {
                                                        setManageAppId(null);
                                                        return;
                                                    }
                                                    setManageAppId(app.id);
                                                    manageAppForm.clearErrors();
                                                    manageAppForm.setData({
                                                        organization_id:
                                                            app.organization_id,
                                                        action:
                                                            app.status ===
                                                            'active'
                                                                ? 'pause'
                                                                : 'resume',
                                                        name: app.name,
                                                        reason: '',
                                                    });
                                                }}
                                            >
                                                {manageAppId === app.id
                                                    ? 'Close'
                                                    : 'Manage application'}
                                            </button>
                                        )}
                                        {manageAppId === app.id && (
                                            <form
                                                className="mt-3 space-y-3 border-t pt-3"
                                                onSubmit={(event) => {
                                                    event.preventDefault();
                                                    manageAppForm.post(
                                                        '/developer/apps/' +
                                                            app.id +
                                                            '/manage',
                                                        {
                                                            preserveScroll: true,
                                                            onSuccess: () => {
                                                                setManageAppId(
                                                                    null,
                                                                );
                                                                manageAppForm.reset();
                                                            },
                                                        },
                                                    );
                                                }}
                                            >
                                                <label
                                                    className="block text-xs font-semibold"
                                                    htmlFor={
                                                        'app-action-' + app.id
                                                    }
                                                >
                                                    Action
                                                </label>
                                                <select
                                                    id={'app-action-' + app.id}
                                                    className="bg-background h-10 w-full rounded-lg border px-3 text-sm"
                                                    value={
                                                        manageAppForm.data
                                                            .action
                                                    }
                                                    onChange={(event) =>
                                                        manageAppForm.setData(
                                                            'action',
                                                            event.target.value,
                                                        )
                                                    }
                                                >
                                                    {canIssueKeys && (
                                                        <option value="rename">
                                                            Rename display name
                                                        </option>
                                                    )}
                                                    {app.status ===
                                                        'active' && (
                                                        <option value="pause">
                                                            Pause online
                                                            issuance
                                                        </option>
                                                    )}
                                                    {canIssueKeys &&
                                                        app.status ===
                                                            'paused' && (
                                                            <option value="resume">
                                                                Resume online
                                                                issuance
                                                            </option>
                                                        )}
                                                </select>
                                                {manageAppForm.data.action ===
                                                    'rename' && (
                                                    <>
                                                        <label
                                                            className="block text-xs font-semibold"
                                                            htmlFor={
                                                                'app-name-' +
                                                                app.id
                                                            }
                                                        >
                                                            Display name
                                                            (product code cannot
                                                            change)
                                                        </label>
                                                        <input
                                                            id={
                                                                'app-name-' +
                                                                app.id
                                                            }
                                                            className="bg-background h-10 w-full rounded-lg border px-3 text-sm"
                                                            maxLength={160}
                                                            minLength={2}
                                                            required
                                                            value={
                                                                manageAppForm
                                                                    .data.name
                                                            }
                                                            onChange={(event) =>
                                                                manageAppForm.setData(
                                                                    'name',
                                                                    event.target
                                                                        .value,
                                                                )
                                                            }
                                                        />
                                                    </>
                                                )}
                                                <label
                                                    className="block text-xs font-semibold"
                                                    htmlFor={
                                                        'app-reason-' + app.id
                                                    }
                                                >
                                                    Audit reason
                                                </label>
                                                <textarea
                                                    id={'app-reason-' + app.id}
                                                    className="bg-background w-full rounded-lg border px-3 py-2 text-sm"
                                                    rows={2}
                                                    minLength={8}
                                                    maxLength={240}
                                                    required
                                                    value={
                                                        manageAppForm.data
                                                            .reason
                                                    }
                                                    onChange={(event) =>
                                                        manageAppForm.setData(
                                                            'reason',
                                                            event.target.value,
                                                        )
                                                    }
                                                />
                                                {Object.values(
                                                    manageAppForm.errors,
                                                ).map((error, index) => (
                                                    <p
                                                        className="text-xs text-red-500"
                                                        key={index}
                                                    >
                                                        {error}
                                                    </p>
                                                ))}
                                                <p className="text-muted-foreground text-xs">
                                                    Pause blocks new keys and
                                                    online bootstrap redemption.
                                                    Existing offline-signed
                                                    leases expire on their own
                                                    schedule.
                                                </p>
                                                <button
                                                    type="submit"
                                                    disabled={
                                                        manageAppForm.processing
                                                    }
                                                    className="min-h-10 rounded-lg bg-red-600 px-3 text-xs font-bold text-white disabled:opacity-50"
                                                >
                                                    {manageAppForm.processing
                                                        ? 'Applying…'
                                                        : 'Confirm audited action'}
                                                </button>
                                            </form>
                                        )}
                                    </article>
                                ))
                            )}
                        </div>
                        <div className="space-y-2">
                            {keys.length === 0 ? (
                                <p className="text-muted-foreground rounded-xl border border-dashed p-5 text-sm">
                                    No customer keys issued yet.
                                </p>
                            ) : (
                                keys.map((key) => (
                                    <article
                                        key={key.id}
                                        className="rounded-xl border p-3"
                                    >
                                        <p className="font-mono text-xs font-semibold">
                                            {key.display_prefix}••••••
                                        </p>
                                        <p className="text-muted-foreground mt-1 text-xs">
                                            {key.customer_id} · {key.plan}
                                        </p>
                                        <p className="text-muted-foreground mt-1 text-xs">
                                            {key.revoked_at
                                                ? 'Revoked'
                                                : key.first_activated_at
                                                  ? 'First activation recorded'
                                                  : 'Not yet activated'}
                                        </p>
                                        <div className="mt-2 rounded-lg border p-2 text-xs">
                                            <p className="font-semibold">
                                                Device bindings:{' '}
                                                {key.recorded_binding_count}{' '}
                                                recorded
                                                {' · '}
                                                {
                                                    key.non_deactivated_binding_count
                                                }{' '}
                                                not deactivated
                                            </p>
                                            {key.last_activation_at && (
                                                <p className="text-muted-foreground mt-1">
                                                    Latest recorded activation:{' '}
                                                    {key.last_activation_at
                                                        .slice(0, 19)
                                                        .replace('T', ' ')}
                                                </p>
                                            )}
                                            <p className="text-muted-foreground mt-1">
                                                Recorded bindings are not online
                                                presence or valid license
                                                entitlement. No hardware
                                                identifiers are displayed.
                                            </p>
                                        </div>
                                        {!key.revoked_at && canIssueKeys && (
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    setRevokeKeyId(key.id);
                                                    revokeForm.reset();
                                                }}
                                                className="mt-2 min-h-10 rounded-lg border border-red-500/25 px-3 text-xs font-bold text-red-500"
                                            >
                                                Revoke key
                                            </button>
                                        )}
                                        {revokeKeyId === key.id && (
                                            <form
                                                className="mt-3 space-y-2 border-t pt-3"
                                                onSubmit={(event) => {
                                                    event.preventDefault();
                                                    revokeForm.post(
                                                        '/developer/keys/' +
                                                            key.id +
                                                            '/revoke',
                                                        {
                                                            preserveScroll: true,
                                                            onSuccess: () => {
                                                                setRevokeKeyId(
                                                                    null,
                                                                );
                                                                revokeForm.reset();
                                                            },
                                                        },
                                                    );
                                                }}
                                            >
                                                <label
                                                    className="block text-xs font-semibold"
                                                    htmlFor={'revoke-' + key.id}
                                                >
                                                    Reason for revocation
                                                </label>
                                                <input
                                                    id={'revoke-' + key.id}
                                                    className="bg-background h-10 w-full rounded-lg border px-3 text-xs"
                                                    placeholder="Compromised key / customer request"
                                                    value={
                                                        revokeForm.data.reason
                                                    }
                                                    onChange={(event) =>
                                                        revokeForm.setData(
                                                            'reason',
                                                            event.target.value,
                                                        )
                                                    }
                                                    minLength={3}
                                                    maxLength={500}
                                                    required
                                                />
                                                {revokeForm.errors.reason && (
                                                    <p className="text-xs text-red-500">
                                                        {
                                                            revokeForm.errors
                                                                .reason
                                                        }
                                                    </p>
                                                )}
                                                <div className="flex gap-2">
                                                    <button
                                                        type="submit"
                                                        disabled={
                                                            revokeForm.processing
                                                        }
                                                        className="min-h-10 rounded-lg bg-red-600 px-3 text-xs font-bold text-white disabled:opacity-50"
                                                    >
                                                        Confirm revoke
                                                    </button>
                                                    <button
                                                        type="button"
                                                        className="min-h-10 rounded-lg border px-3 text-xs"
                                                        onClick={() =>
                                                            setRevokeKeyId(null)
                                                        }
                                                    >
                                                        Cancel
                                                    </button>
                                                </div>
                                            </form>
                                        )}
                                    </article>
                                ))
                            )}
                        </div>
                    </div>
                </section>

                <section
                    id="developer-app-sdk"
                    className="bg-card rounded-2xl border p-5 sm:p-6"
                >
                    <h2 className="flex items-center gap-2 text-lg font-bold">
                        <Code2 className="size-5 text-red-500" /> 3. SDK &
                        integration
                    </h2>
                    <p className="text-muted-foreground mt-1 max-w-3xl text-sm">
                        Select the app and language to generate its setup
                        manifest. Full runnable, security-tested client SDK
                        packages and first-activation API are under development;
                        this starter is not a license verifier.
                    </p>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        <label className="space-y-2 text-xs font-semibold">
                            Application
                            <select
                                className="bg-background mt-2 h-11 w-full rounded-xl border px-3 text-sm"
                                value={selectedApp}
                                onChange={(event) =>
                                    setSelectedApp(event.target.value)
                                }
                            >
                                <option value="">Example application</option>
                                {applications.map((app) => (
                                    <option key={app.id} value={app.id}>
                                        {app.name}
                                    </option>
                                ))}
                            </select>
                        </label>
                        <label className="space-y-2 text-xs font-semibold">
                            Programming language
                            <select
                                className="bg-background mt-2 h-11 w-full rounded-xl border px-3 text-sm"
                                value={language}
                                onChange={(event) =>
                                    setLanguage(event.target.value)
                                }
                            >
                                {languages.map((item) => (
                                    <option key={item} value={item}>
                                        {item}
                                    </option>
                                ))}
                            </select>
                        </label>
                    </div>
                    <pre className="mt-4 overflow-x-auto rounded-xl bg-[#111827] p-4 text-xs leading-6 text-slate-100">
                        <code>{sdkText}</code>
                    </pre>
                    <div className="mt-3 flex flex-wrap gap-2">
                        <button
                            type="button"
                            className="inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 text-sm font-bold"
                            onClick={() => void copyText(sdkText)}
                        >
                            <Copy className="size-4" /> Copy starter code
                        </button>
                        <button
                            type="button"
                            className="inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 text-sm font-bold"
                            onClick={downloadSetup}
                        >
                            Download {language} setup
                        </button>
                    </div>
                    <div className="mt-5 grid gap-3 sm:grid-cols-2">
                        <Link
                            href="/sandbox-licenses"
                            className="flex items-center justify-between rounded-xl border p-4 text-sm font-semibold"
                        >
                            <span className="flex items-center gap-2">
                                <BookOpen className="size-4" /> Test sandbox
                                licenses
                            </span>
                            <ArrowRight className="size-4" />
                        </Link>
                        <Link
                            href="/settings/security"
                            className="flex items-center justify-between rounded-xl border p-4 text-sm font-semibold"
                        >
                            <span className="flex items-center gap-2">
                                <ShieldCheck className="size-4" /> Protect your
                                account
                            </span>
                            <ArrowRight className="size-4" />
                        </Link>
                    </div>
                </section>
            </div>
        </>
    );
}

// Non-owner developers retain a restricted view of the SAME KSLP authority.
export default function DeveloperApps(props: DeveloperWorkspaceProps) {
    return <DeveloperAppsWorkspace {...props} />;
}
