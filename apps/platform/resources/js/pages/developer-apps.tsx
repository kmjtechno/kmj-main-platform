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
    current_period_end: string | null;
};

type Application = {
    id: string;
    organization_id: string;
    product_code: string;
    name: string;
    status: string;
    created_at: string;
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
    status: string;
    grace_until: string | null;
};

type ActiveDevice = {
    id: string;
    license_id: string;
    activated_at: string;
};

type IssuedKey = {
    key: string;
    license_id: string;
    product_code: string;
};

type Props = {
    organizations: Organization[];
    applications: Application[];
    keys: LicenseKey[];
    activeDevices: ActiveDevice[];
    canIssueKeys: boolean;
    newKey: IssuedKey | null;
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

function suggestProductCode(name: string): string {
    // An editable default only: never replace an ID the developer customized.
    const slug = name
        .normalize('NFKD')
        .replace(/[\u0300-\u036f]/g, '')
        .toUpperCase()
        .replace(/[^A-Z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '')
        .slice(0, 92);
    return slug ? `APP.${slug}` : '';
}

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

export default function DeveloperApps({
    organizations,
    applications,
    keys,
    activeDevices,
    canIssueKeys,
    newKey,
}: Props) {
    const preferredOrg =
        organizations.find((org) => org.issuer_status === 'active') ??
        organizations[0];
    const initialApp = applications.find(
        (app) =>
            app.status === 'active' &&
            app.organization_id === preferredOrg?.id,
    );
    const [language, setLanguage] = useState<string>('TypeScript');
    const [selectedApp, setSelectedApp] = useState<string>(
        initialApp?.id ?? '',
    );
    const [customProductCode, setCustomProductCode] = useState(false);
    const [copied, setCopied] = useState(false);
    const [revokeKeyId, setRevokeKeyId] = useState<string | null>(null);
    const [releaseDeviceId, setReleaseDeviceId] = useState<string | null>(
        null,
    );
    const [licenseSearch, setLicenseSearch] = useState('');
    const revokeForm = useForm({ reason: '' });
    const releaseDeviceForm = useForm({ reason: '' });
    const createOrganization = useForm({ name: '' });
    const createApp = useForm({
        organization_id: preferredOrg?.id ?? '',
        name: '',
        product_code: '',
    });
    const issueKey = useForm({
        organization_id: preferredOrg?.id ?? '',
        product_code: initialApp?.product_code ?? '',
        customer_id: '',
        plan: 'trial',
    });

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
    const activeApps = applications.filter((app) => app.status === 'active');
    const liveKeys = keys.filter(
        (key) => !key.revoked_at && key.status === 'active',
    );
    const visibleKeys = keys.filter((key) => {
        const match = licenseSearch.trim().toLowerCase();
        if (!match) return true;
        const app = applications.find(
            (item) => item.id === key.licensed_product_id,
        );
        return [key.customer_id, key.display_prefix, app?.name, app?.product_code]
            .filter(Boolean)
            .some((value) => value?.toLowerCase().includes(match));
    });
    const readyToIssue =
        canIssueKeys &&
        organizations.some(
            (org) =>
                org.id === issueKey.data.organization_id &&
                org.issuer_status === 'active',
        ) &&
        activeApps.some(
            (app) =>
                app.organization_id === issueKey.data.organization_id &&
                app.product_code === issueKey.data.product_code,
        );
    const onboarding = [
        {
            step: '01',
            title: 'Organization',
            detail:
                organizations.length === 0
                    ? 'Create your workspace'
                    : preferredOrg?.issuer_status === 'active'
                      ? 'Issuer approved'
                      : 'Issuer approval required',
            ready: preferredOrg?.issuer_status === 'active',
            href:
                organizations.length === 0
                    ? '#developer-org-create'
                    : '#developer-app-create',
        },
        {
            step: '02',
            title: 'Application',
            detail:
                activeApps.length > 0
                    ? `${activeApps.length} registered app(s)`
                    : 'Name your app; its ID is suggested',
            ready: activeApps.length > 0,
            href: '#developer-app-create',
        },
        {
            step: '03',
            title: 'Customer key',
            detail:
                liveKeys.length > 0
                    ? `${liveKeys.length} active trial key(s)`
                    : 'Issue a governed trial key',
            ready: liveKeys.length > 0,
            href: '#developer-app-key',
        },
        {
            step: '04',
            title: 'Integrate',
            detail: 'Choose language; starter only, not a signed SDK',
            ready: false,
            href: '#developer-app-sdk',
        },
    ] as const;

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
            <Head title="Developer Apps & Licensing" />
            <main className="flex min-w-0 flex-1 flex-col gap-6 p-4 sm:p-7">
                <section className="overflow-hidden rounded-2xl border bg-gradient-to-br from-[#111b29] via-[#10151f] to-[#231523] p-6 text-white sm:p-8">
                    <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-center">
                        <div className="max-w-2xl">
                            <div className="mb-3 flex items-center gap-2 text-xs font-bold tracking-[0.14em] text-amber-300 uppercase">
                                <Layers3 className="size-4" /> KMJ Developer
                                Console
                            </div>
                            <h1 className="text-3xl font-black tracking-tight sm:text-4xl">
                                Your apps. Your license keys.
                            </h1>
                            <p className="mt-3 text-sm leading-6 text-slate-300">
                                Register an application, issue a customer key,
                                connect a verified device and prepare a
                                language-specific SDK. KMJ Main Platform remains
                                the single licensing authority.
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
                    <nav
                        aria-label="Four-step licensing setup"
                        className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
                    >
                        {onboarding.map((step) => (
                            <a
                                key={step.step}
                                href={step.href}
                                className="group rounded-xl border border-white/15 bg-white/5 p-4 transition-colors hover:border-amber-300/60 hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs font-black text-amber-300">
                                        STEP {step.step}
                                    </span>
                                    <span
                                        className={`text-[11px] font-semibold ${step.ready ? 'text-emerald-300' : 'text-slate-300'}`}
                                    >
                                        {step.ready ? 'Ready' : 'Next / gated'}
                                    </span>
                                </div>
                                <h2 className="mt-2 flex items-center gap-2 font-bold">
                                    {step.title}
                                    <ArrowRight className="size-3.5" />
                                </h2>
                                <p className="mt-1 text-xs leading-5 text-slate-300">
                                    {step.detail}
                                </p>
                            </a>
                        ))}
                    </nav>
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
                        <a
                            href="#developer-app-sdk"
                            onClick={() => {
                                const app = applications.find(
                                    (item) =>
                                        item.product_code ===
                                        newKey.product_code,
                                );
                                if (app) {
                                    setSelectedApp(app.id);
                                }
                            }}
                            className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-lg border px-4 text-sm font-semibold"
                        >
                            Continue to integration starter{' '}
                            <ArrowRight className="size-4" />
                        </a>
                    </section>
                )}

                {organizations.length === 0 && (
                    <section
                        id="developer-org-create"
                        className="bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
                    >
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
                {organizations.length > 0 &&
                    !organizations.some((org) => org.issuer_status === 'active') && (
                        <section
                            role="status"
                            className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm"
                        >
                            Your workspace is created. An active,
                            owner-approved issuer subscription is required
                            before registering an app or issuing customer keys.
                            No payment or license is granted automatically.
                        </section>
                    )}
                <div className="grid gap-5 xl:grid-cols-2">
                    <section
                        id="developer-app-create"
                        className="bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
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
                                    onSuccess: () => {
                                        createApp.reset('name', 'product_code');
                                        setCustomProductCode(false);
                                    },
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
                                onChange={(event) => {
                                    const name = event.target.value;
                                    createApp.setData({
                                        ...createApp.data,
                                        name,
                                        product_code: customProductCode
                                            ? createApp.data.product_code
                                            : suggestProductCode(name),
                                    });
                                }}
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
                                onChange={(event) => {
                                    setCustomProductCode(true);
                                    createApp.setData(
                                        'product_code',
                                        event.target.value
                                            .toUpperCase()
                                            .replace(/[^A-Z0-9_.:-]/g, ''),
                                    );
                                }}
                                required
                            />
                            <p className="text-muted-foreground text-xs">
                                Suggested automatically from the name. You can
                                edit it; it must contain 3–96 uppercase letters,
                                numbers, dot, dash, underscore or colon.
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
                        className="bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
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
                                    !readyToIssue ||
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

                <section className="bg-card rounded-2xl border p-5 sm:p-6">
                    <h2 className="font-bold">
                        Your applications and issued licenses
                    </h2>
                    <p className="text-muted-foreground mt-1 text-xs">
                        Tenant-scoped records. Existing keys cannot be retrieved
                        in plaintext. Device identities and machine fingerprints
                        are never displayed. Showing up to 100 recent keys.
                    </p>
                    <label className="mt-4 block space-y-2 text-xs font-semibold">
                        Find a license by customer, app or key prefix
                        <input
                            className="bg-background h-11 w-full rounded-xl border px-3 text-sm"
                            placeholder="Search visible licenses"
                            aria-label="Search issued licenses"
                            maxLength={128}
                            value={licenseSearch}
                            onChange={(event) => setLicenseSearch(event.target.value)}
                        />
                    </label>
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
                                        {app.status === 'active' && (
                                            <a
                                                href="#developer-app-key"
                                                onClick={() => {
                                                    setSelectedApp(app.id);
                                                    issueKey.setData({
                                                        ...issueKey.data,
                                                        organization_id:
                                                            app.organization_id,
                                                        product_code:
                                                            app.product_code,
                                                    });
                                                }}
                                                className="mt-3 inline-flex min-h-10 items-center gap-1 rounded-lg border px-3 text-xs font-semibold hover:border-red-500/40 focus-visible:outline-2 focus-visible:outline-red-500"
                                            >
                                                Use this app{' '}
                                                <ArrowRight className="size-3.5" />
                                            </a>
                                        )}
                                    </article>
                                ))
                            )}
                        </div>
                        <div className="space-y-2">
                            {visibleKeys.length === 0 ? (
                                <p className="text-muted-foreground rounded-xl border border-dashed p-5 text-sm">
                                    No licenses match this search in the recent list.
                                </p>
                            ) : (
                                visibleKeys.map((key) => (
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
                                        <p className="text-muted-foreground mt-1 text-xs">
                                            License: {key.status} · Expires{' '}
                                            {new Date(key.expires_at).toLocaleDateString()} ·
                                            Active device seats:{' '}
                                            {activeDevices.filter(
                                                (device) =>
                                                    device.license_id === key.license_id,
                                            ).length}
                                        </p>
                                        <p className="text-muted-foreground mt-1 text-xs">
                                            Activation is device registration only,
                                            not a signed commercial lease.
                                        </p>
                                        {!key.revoked_at &&
                                            key.status === 'active' &&
                                            activeDevices
                                                .filter(
                                                    (device) =>
                                                        device.license_id === key.license_id,
                                                )
                                                .map((device) => (
                                                    <div
                                                        className="mt-3 rounded-xl border p-3"
                                                        key={device.id}
                                                    >
                                                        <p className="text-xs font-semibold">
                                                            Device registered{' '}
                                                            {new Date(
                                                                device.activated_at,
                                                            ).toLocaleDateString()}
                                                        </p>
                                                        <p className="text-muted-foreground mt-1 text-xs">
                                                            Release this seat only if
                                                            the device was replaced,
                                                            lost or is no longer in use.
                                                        </p>
                                                        {canIssueKeys &&
                                                            releaseDeviceId !== device.id && (
                                                                <button
                                                                    type="button"
                                                                    className="mt-2 min-h-10 rounded-lg border px-3 text-xs font-bold"
                                                                    onClick={() => {
                                                                        setReleaseDeviceId(device.id);
                                                                        releaseDeviceForm.reset();
                                                                    }}
                                                                >
                                                                    Release device seat
                                                                </button>
                                                            )}
                                                        {releaseDeviceId === device.id &&
                                                            canIssueKeys && (
                                                                <form
                                                                    className="mt-3 space-y-2"
                                                                    onSubmit={(event) => {
                                                                        event.preventDefault();
                                                                        releaseDeviceForm.post(
                                                                            '/developer/keys/' +
                                                                                key.id +
                                                                                '/devices/' +
                                                                                device.id +
                                                                                '/release',
                                                                            {
                                                                                preserveScroll: true,
                                                                                onSuccess: () => {
                                                                                    setReleaseDeviceId(null);
                                                                                    releaseDeviceForm.reset();
                                                                                },
                                                                            },
                                                                        );
                                                                    }}
                                                                >
                                                                    <label
                                                                        htmlFor={'release-' + device.id}
                                                                        className="block text-xs font-semibold"
                                                                    >
                                                                        Why release this device?
                                                                    </label>
                                                                    <input
                                                                        id={'release-' + device.id}
                                                                        className="bg-background h-10 w-full rounded-lg border px-3 text-xs"
                                                                        placeholder="Device replaced or lost"
                                                                        value={releaseDeviceForm.data.reason}
                                                                        onChange={(event) =>
                                                                            releaseDeviceForm.setData(
                                                                                'reason',
                                                                                event.target.value,
                                                                            )
                                                                        }
                                                                        minLength={3}
                                                                        maxLength={500}
                                                                        required
                                                                    />
                                                                    {releaseDeviceForm.errors.reason && (
                                                                        <p className="text-xs text-red-500">
                                                                            {releaseDeviceForm.errors.reason}
                                                                        </p>
                                                                    )}
                                                                    <div className="flex flex-wrap gap-2">
                                                                        <button
                                                                            type="submit"
                                                                            disabled={releaseDeviceForm.processing}
                                                                            className="min-h-10 rounded-lg bg-red-600 px-3 text-xs font-bold text-white disabled:opacity-50"
                                                                        >
                                                                            Confirm seat release
                                                                        </button>
                                                                        <button
                                                                            type="button"
                                                                            className="min-h-10 rounded-lg border px-3 text-xs"
                                                                            onClick={() => {
                                                                                setReleaseDeviceId(null);
                                                                                releaseDeviceForm.reset();
                                                                            }}
                                                                        >
                                                                            Cancel
                                                                        </button>
                                                                    </div>
                                                                </form>
                                                            )}
                                                    </div>
                                                ))}
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
                                <option value="">Select an application</option>
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
                            disabled={!displayedApp}
                        >
                            <Copy className="size-4" /> Copy starter code
                        </button>
                        <button
                            type="button"
                            className="inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 text-sm font-bold"
                            onClick={downloadSetup}
                            disabled={!displayedApp}
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
            </main>
        </>
    );
}
