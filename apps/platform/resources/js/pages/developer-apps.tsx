import { Head, Link, useForm } from '@inertiajs/react';
import { useMemo, useState } from 'react';
import {
    ArrowRight, BookOpen, CheckCircle2, Code2, Copy, KeyRound,
    Layers3, LockKeyhole, Plus, ShieldCheck,
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
    canIssueKeys: boolean;
    newKey: IssuedKey | null;
};

const languages = [
    'TypeScript', 'Python', 'C# / .NET', 'C++ / Qt',
    'Rust', 'Go', 'Java', 'PHP',
] as const;

function sdkConfiguration(language: string, productCode: string): string {
    // Generate source-only integration starters from a canonical public
    // configuration. Never embed an issuer private key or customer's key.
    const product = JSON.stringify(productCode);
    const contract = JSON.stringify('/api/v1/kslp/contract');
    const keys = JSON.stringify('/api/v1/kslp/keys/license');
    const warning = 'STAGING STARTER ONLY: obtain and verify signed KSLP leases,';
    const warning2 = 'never trust an activation ID as a commercial entitlement.';

    switch (language) {
        case 'TypeScript':
            return [
                '// ' + warning, '// ' + warning2,
                'export const kmjLicense = {',
                '    product: ' + product + ',',
                '    contractUrl: ' + contract + ',',
                '    publicKeyUrl: ' + keys + ',',
                '    requireEd25519: true,',
                '} as const;',
            ].join('\n');
        case 'Python':
            return [
                '# ' + warning, '# ' + warning2,
                'KMJ_LICENSE = {',
                '    "product": ' + product + ',',
                '    "contract_url": ' + contract + ',',
                '    "public_key_url": ' + keys + ',',
                '    "require_ed25519": True,',
                '}',
            ].join('\n');
        case 'C# / .NET':
            return [
                '// ' + warning, '// ' + warning2,
                'internal static class KmjLicenseConfig {',
                '    public const string Product = ' + product + ';',
                '    public const string ContractUrl = ' + contract + ';',
                '    public const string PublicKeysUrl = ' + keys + ';',
                '}',
            ].join('\n');
        case 'C++ / Qt':
            return [
                '// ' + warning, '// ' + warning2,
                '#include <string_view>',
                'namespace kmj {',
                'constexpr std::string_view product = ' + product + ';',
                'constexpr std::string_view contract_url = ' + contract + ';',
                'constexpr std::string_view public_keys_url = ' + keys + ';',
                '}',
            ].join('\n');
        case 'Rust':
            return [
                '// ' + warning, '// ' + warning2,
                'pub const KMJ_PRODUCT: &str = ' + product + ';',
                'pub const KMJ_CONTRACT: &str = ' + contract + ';',
                'pub const KMJ_PUBLIC_KEYS: &str = ' + keys + ';',
            ].join('\n');
        case 'Go':
            return [
                '// ' + warning, '// ' + warning2,
                'package licensing',
                'const Product = ' + product,
                'const ContractURL = ' + contract,
                'const PublicKeysURL = ' + keys,
            ].join('\n');
        case 'Java':
            return [
                '// ' + warning, '// ' + warning2,
                'public final class KmjLicenseConfig {',
                '    public static final String PRODUCT = ' + product + ';',
                '    public static final String CONTRACT_URL = ' + contract + ';',
                '    public static final String PUBLIC_KEYS_URL = ' + keys + ';',
                '    private KmjLicenseConfig() {}',
                '}',
            ].join('\n');
        default:
            return [
                '<?php',
                '// ' + warning, '// ' + warning2,
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
    canIssueKeys,
    newKey,
}: Props) {
    const [language, setLanguage] = useState<string>('TypeScript');
    const [selectedApp, setSelectedApp] = useState<string>('');
    const [copied, setCopied] = useState(false);
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

    const eligibleApps = applications.filter(
        (app) => app.organization_id === issueKey.data.organization_id && app.status === 'active',
    );
    const displayedApp = applications.find((app) => app.id === selectedApp);
    const selectedIssuer = organizations.find(
        (org) => org.id === createApp.data.organization_id,
    );
    const sdkText = useMemo(
        () => sdkConfiguration(language, displayedApp?.product_code ?? 'YOUR_APP'),
        [language, displayedApp?.product_code],
    );
    const canRegister = canIssueKeys && selectedIssuer?.issuer_status === 'active';

    const downloadSetup = () => {
        const extension: Record<string, string> = {
            TypeScript: 'ts', Python: 'py', 'C# / .NET': 'cs',
            'C++ / Qt': 'cpp', Rust: 'rs', Go: 'go', Java: 'java', PHP: 'php',
        };
        const file = new Blob([sdkText + '\n'], { type: 'text/plain;charset=utf-8' });
        const objectUrl = URL.createObjectURL(file);
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = 'kmj-licensing-setup.' + (extension[language] ?? 'txt');
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
                            <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-amber-300">
                                <Layers3 className="size-4" /> KMJ Developer Console
                            </div>
                            <h1 className="text-3xl font-black tracking-tight sm:text-4xl">
                                Your apps. Your license keys.
                            </h1>
                            <p className="mt-3 text-sm leading-6 text-slate-300">
                                Register an application, issue a customer key, connect a verified
                                device and prepare a language-specific SDK. KMJ Main Platform
                                remains the single licensing authority.
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
                            ['1', 'Create your app', 'Register under an approved developer organization'],
                            ['2', 'Generate a key', 'Issue against an authorized subscription and license'],
                            ['3', 'Integrate SDK', 'Select language and complete device activation'],
                        ].map(([step, title, detail]) => (
                            <div key={step} className="rounded-xl border border-white/10 bg-white/5 p-4">
                                <span className="text-xs font-black text-amber-300">STEP {step}</span>
                                <h2 className="mt-2 font-bold">{title}</h2>
                                <p className="mt-1 text-xs leading-5 text-slate-300">{detail}</p>
                            </div>
                        ))}
                    </div>
                </section>

                {!canIssueKeys && (
                    <section role="status" className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm">
                        <div className="flex items-center gap-2 font-bold">
                            <LockKeyhole className="size-4" /> Protected rollout — issuance disabled
                        </div>
                        <p className="text-muted-foreground mt-1">
                            Storage migration, integration tests and device activation verification
                            must pass before application registration and customer keys are enabled.
                            Existing Sandbox License Center remains available for testing.
                        </p>
                    </section>
                )}
                {newKey && (
                    <section className="rounded-xl border border-emerald-500/35 bg-emerald-500/5 p-5" aria-label="New license key">
                        <h2 className="flex items-center gap-2 font-bold">
                            <CheckCircle2 className="size-5 text-emerald-600" /> License key created
                        </h2>
                        <p className="text-muted-foreground mt-2 text-xs">
                            This is the only full-key display. Save it in a secure password manager.
                            It is a bootstrap key, not a signed offline entitlement.
                        </p>
                        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                            <input className="bg-background w-full min-w-0 rounded-lg border px-3 py-3 font-mono text-xs" value={newKey.key} readOnly aria-label="One-time license key" />
                            <button type="button" className="inline-flex items-center justify-center gap-2 rounded-lg border px-4 py-2 text-xs font-bold" onClick={() => void copyText(newKey.key)}>
                                <Copy className="size-4" /> {copied ? 'Copied' : 'Copy key'}
                            </button>
                        </div>
                        <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
                            App: {newKey.product_code} · License ID: {newKey.license_id}
                        </p>
                    </section>
                )}

                {organizations.length === 0 && (
                    <section className="rounded-2xl border bg-card p-5 sm:p-6">
                        <h2 className="text-lg font-bold">Start by creating your organization</h2>
                        <p className="text-muted-foreground mt-1 text-sm">
                            A workspace separates your apps and customer licences from other accounts.
                            An approved developer subscription will still be required before issuance.
                        </p>
                        <form className="mt-4 flex flex-col gap-3 sm:flex-row" onSubmit={(event) => {
                            event.preventDefault();
                            createOrganization.post('/developer/organizations');
                        }}>
                            <input
                                aria-label="Organization name"
                                placeholder="Your company or developer team"
                                className="bg-background min-h-11 flex-1 rounded-xl border px-3 text-sm"
                                maxLength={160}
                                value={createOrganization.data.name}
                                onChange={(event) => createOrganization.setData('name', event.target.value)}
                                required
                            />
                            <button type="submit" disabled={createOrganization.processing} className="min-h-11 rounded-xl bg-red-600 px-5 text-sm font-bold text-white disabled:opacity-50">
                                Create organization
                            </button>
                        </form>
                        {Object.values(createOrganization.errors).map((error, index) => <p className="mt-2 text-xs text-red-500" key={index}>{error}</p>)}
                    </section>
                )}
                <div className="grid gap-5 xl:grid-cols-2">
                    <section id="developer-app-create" className="rounded-2xl border bg-card p-5 sm:p-6">
                        <h2 className="flex items-center gap-2 text-lg font-bold">
                            <Plus className="size-5 text-red-500" /> 1. Register an application
                        </h2>
                        <p className="text-muted-foreground mt-1 text-xs">
                            You need an active issuer subscription. Registration never creates
                            a paid entitlement automatically.
                        </p>
                        <form className="mt-5 space-y-3" onSubmit={(event) => {
                            event.preventDefault();
                            createApp.post('/developer/apps', { preserveScroll: true });
                        }}>
                            <label className="block text-xs font-semibold" htmlFor="application-org">Organization</label>
                            <select id="application-org" className="bg-background h-11 w-full rounded-xl border px-3 text-sm" value={createApp.data.organization_id} onChange={(event) => createApp.setData('organization_id', event.target.value)}>
                                {organizations.length === 0 && <option value="">No manageable organization</option>}
                                {organizations.map((org) => <option key={org.id} value={org.id}>{org.name} · {org.issuer_status}</option>)}
                            </select>
                            <label className="block text-xs font-semibold" htmlFor="application-name">Application name</label>
                            <input id="application-name" className="bg-background h-11 w-full rounded-xl border px-3 text-sm" maxLength={160} placeholder="My Cinema Player" value={createApp.data.name} onChange={(event) => createApp.setData('name', event.target.value)} required />
                            <label className="block text-xs font-semibold" htmlFor="application-code">Unique application ID</label>
                            <input id="application-code" className="bg-background h-11 w-full rounded-xl border px-3 font-mono text-sm" maxLength={96} placeholder="MYCOMPANY.CINEMA" value={createApp.data.product_code} onChange={(event) => createApp.setData('product_code', event.target.value.toUpperCase().replace(/[^A-Z0-9_.:-]/g, ''))} required />
                            <p className="text-muted-foreground text-xs">Use 3–96 uppercase letters, numbers, dot, dash, underscore or colon.</p>
                            {Object.values(createApp.errors).map((error, index) => <p className="text-xs text-red-500" key={index}>{error}</p>)}
                            <button type="submit" disabled={!canRegister || createApp.processing} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-bold text-white disabled:opacity-40">
                                <Plus className="size-4" /> {createApp.processing ? 'Registering…' : 'Register application'}
                            </button>
                        </form>
                    </section>

                    <section id="developer-app-key" className="rounded-2xl border bg-card p-5 sm:p-6">
                        <h2 className="flex items-center gap-2 text-lg font-bold">
                            <KeyRound className="size-5 text-red-500" /> 2. Issue a customer license key
                        </h2>
                        <p className="text-muted-foreground mt-1 text-xs">
                            Cryptographically random, stored only as a digest. Requires authorized
                            app, issuer quota and recent password confirmation.
                        </p>
                        <form className="mt-5 space-y-3" onSubmit={(event) => {
                            event.preventDefault();
                            issueKey.post('/developer/keys', { preserveScroll: true });
                        }}>
                            <label className="block text-xs font-semibold" htmlFor="key-org">Organization</label>
                            <select id="key-org" className="bg-background h-11 w-full rounded-xl border px-3 text-sm" value={issueKey.data.organization_id} onChange={(event) => issueKey.setData({ ...issueKey.data, organization_id: event.target.value, product_code: '' })}>
                                {organizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}
                            </select>
                            <label className="block text-xs font-semibold" htmlFor="key-app">Registered app</label>
                            <select id="key-app" className="bg-background h-11 w-full rounded-xl border px-3 text-sm" value={issueKey.data.product_code} onChange={(event) => issueKey.setData('product_code', event.target.value)} required>
                                <option value="">Select your app</option>
                                {eligibleApps.map((app) => <option value={app.product_code} key={app.id}>{app.name} ({app.product_code})</option>)}
                            </select>
                            <label className="block text-xs font-semibold" htmlFor="key-customer">Customer reference</label>
                            <input id="key-customer" className="bg-background h-11 w-full rounded-xl border px-3 text-sm" maxLength={128} placeholder="customer-001" value={issueKey.data.customer_id} onChange={(event) => issueKey.setData('customer_id', event.target.value)} required />
                            <label className="block text-xs font-semibold" htmlFor="key-plan">License plan</label>
                            <select id="key-plan" className="bg-background h-11 w-full rounded-xl border px-3 text-sm" value={issueKey.data.plan} onChange={(event) => issueKey.setData('plan', event.target.value)}>
                                {['trial', 'professional', 'business', 'enterprise', 'custom_oem'].map((plan) => <option value={plan} key={plan}>{plan}</option>)}
                            </select>
                            {Object.values(issueKey.errors).map((error, index) => <p className="text-xs text-red-500" key={index}>{error}</p>)}
                            <button type="submit" disabled={!canIssueKeys || !issueKey.data.product_code || issueKey.processing} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-bold text-white disabled:opacity-40">
                                <KeyRound className="size-4" /> {issueKey.processing ? 'Generating…' : 'Generate license key'}
                            </button>
                        </form>
                    </section>
                </div>

                <section className="rounded-2xl border bg-card p-5 sm:p-6">
                    <h2 className="font-bold">Your applications and issued licenses</h2>
                    <p className="text-muted-foreground mt-1 text-xs">
                        Tenant-scoped records. Existing keys cannot be retrieved in plaintext.
                    </p>
                    <div className="mt-4 grid gap-4 lg:grid-cols-2">
                        <div className="space-y-2">
                            {applications.length === 0 ? (
                                <p className="rounded-xl border border-dashed p-5 text-sm text-muted-foreground">No developer applications yet.</p>
                            ) : applications.map((app) => (
                                <article key={app.id} className="rounded-xl border p-3">
                                    <div className="flex items-center justify-between gap-2">
                                        <p className="font-semibold">{app.name}</p>
                                        <span className="rounded-full border px-2 py-1 text-[11px]">{app.status}</span>
                                    </div>
                                    <p className="mt-1 font-mono text-xs text-muted-foreground">{app.product_code}</p>
                                </article>
                            ))}
                        </div>
                        <div className="space-y-2">
                            {keys.length === 0 ? (
                                <p className="rounded-xl border border-dashed p-5 text-sm text-muted-foreground">No customer keys issued yet.</p>
                            ) : keys.map((key) => (
                                <article key={key.id} className="rounded-xl border p-3">
                                    <p className="font-mono text-xs font-semibold">{key.display_prefix}••••••</p>
                                    <p className="mt-1 text-xs text-muted-foreground">{key.customer_id} · {key.plan}</p>
                                    <p className="mt-1 text-xs text-muted-foreground">
                                        {key.revoked_at ? 'Revoked' : key.first_activated_at ? 'First activation recorded' : 'Not yet activated'}
                                    </p>
                                </article>
                            ))}
                        </div>
                    </div>
                </section>

                <section id="developer-app-sdk" className="rounded-2xl border bg-card p-5 sm:p-6">
                    <h2 className="flex items-center gap-2 text-lg font-bold">
                        <Code2 className="size-5 text-red-500" /> 3. SDK & integration
                    </h2>
                    <p className="text-muted-foreground mt-1 max-w-3xl text-sm">
                        Select the app and language to generate its setup manifest.
                        Full runnable, security-tested client SDK packages and first-activation
                        API are under development; this starter is not a license verifier.
                    </p>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        <label className="space-y-2 text-xs font-semibold">Application
                            <select className="bg-background mt-2 h-11 w-full rounded-xl border px-3 text-sm" value={selectedApp} onChange={(event) => setSelectedApp(event.target.value)}>
                                <option value="">Example application</option>
                                {applications.map((app) => <option key={app.id} value={app.id}>{app.name}</option>)}
                            </select>
                        </label>
                        <label className="space-y-2 text-xs font-semibold">Programming language
                            <select className="bg-background mt-2 h-11 w-full rounded-xl border px-3 text-sm" value={language} onChange={(event) => setLanguage(event.target.value)}>
                                {languages.map((item) => <option key={item} value={item}>{item}</option>)}
                            </select>
                        </label>
                    </div>
                    <pre className="mt-4 overflow-x-auto rounded-xl bg-[#111827] p-4 text-xs leading-6 text-slate-100"><code>{sdkText}</code></pre>
                    <div className="mt-3 flex flex-wrap gap-2">
                        <button type="button" className="inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 text-sm font-bold" onClick={() => void copyText(sdkText)}>
                            <Copy className="size-4" /> Copy starter code
                        </button>
                        <button type="button" className="inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 text-sm font-bold" onClick={downloadSetup}>
                            Download {language} setup
                        </button>
                    </div>
                    <div className="mt-5 grid gap-3 sm:grid-cols-2">
                        <Link href="/sandbox-licenses" className="flex items-center justify-between rounded-xl border p-4 text-sm font-semibold">
                            <span className="flex items-center gap-2"><BookOpen className="size-4" /> Test sandbox licenses</span><ArrowRight className="size-4" />
                        </Link>
                        <Link href="/settings/security" className="flex items-center justify-between rounded-xl border p-4 text-sm font-semibold">
                            <span className="flex items-center gap-2"><ShieldCheck className="size-4" /> Protect your account</span><ArrowRight className="size-4" />
                        </Link>
                    </div>
                </section>
            </main>
        </>
    );
}
