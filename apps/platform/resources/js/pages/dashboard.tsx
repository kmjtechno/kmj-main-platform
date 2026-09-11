import type { FormEvent } from 'react';
import { Head, useForm } from '@inertiajs/react';
import {
    ArrowRight,
    BadgeCheck,
    Building2,
    CheckCircle2,
    KeyRound,
    Layers3,
    Plus,
    ShieldCheck,
} from 'lucide-react';
import { dashboard } from '@/routes';

type Entitlement = {
    id: string;
    product_id: string;
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
};

const deliveryPath = [
    { label: 'Organization', status: 'Active' },
    { label: 'Product', status: 'Active' },
    { label: 'Entitlement', status: 'Active' },
    { label: 'Sandbox license', status: 'Implemented' },
    { label: 'Validation', status: 'Implemented' },
    { label: 'Revocation', status: 'Implemented' },
];

export default function Dashboard({ organizations }: DashboardProps) {
    const form = useForm({ name: '' });

    const submit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        form.post('/organizations', {
            preserveScroll: true,
            onSuccess: () => form.reset(),
        });
    };

    const entitlementCount = organizations.reduce(
        (count, organization) => count + organization.entitlements.length,
        0,
    );

    return (
        <>
            <Head title="Control Center" />

            <div className="flex h-full flex-1 flex-col gap-6 overflow-x-auto p-4 sm:p-6">
                <section className="border-sidebar-border/70 from-background via-background dark:border-sidebar-border overflow-hidden rounded-2xl border bg-gradient-to-br to-red-950/10 p-6 sm:p-8">
                    <div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
                        <div className="max-w-2xl">
                            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-red-500/15 bg-red-500/5 px-3 py-1 text-xs font-semibold text-red-500">
                                <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                                Authority + Licensing · Active development
                            </div>
                            <h1 className="text-3xl font-black tracking-tight sm:text-4xl">
                                KMJ Main Platform Control Center
                            </h1>
                            <p className="text-muted-foreground mt-3 max-w-xl text-sm leading-6">
                                The working authority path now covers
                                organization, product and entitlement authority
                                plus the sandbox license lifecycle: issue →
                                validate → revoke.
                            </p>
                        </div>

                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                            <Metric
                                label="Organizations"
                                value={organizations.length}
                            />
                            <Metric
                                label="Entitlements"
                                value={entitlementCount}
                            />
                            <Metric label="Licensing" value="Ready" />
                            <Metric label="Authority" value="Online" />
                        </div>
                    </div>
                </section>

                <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                        <div>
                            <h2 className="font-bold">
                                Minimum working product path
                            </h2>
                            <p className="text-muted-foreground mt-1 text-xs">
                                Current implementation progress surfaced directly
                                in the control center
                            </p>
                        </div>
                        <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-emerald-500/15 bg-emerald-500/5 px-2.5 py-1 text-[10px] font-bold text-emerald-600 dark:text-emerald-400">
                            <BadgeCheck className="h-3 w-3" />
                            P0 path advancing
                        </span>
                    </div>

                    <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                        {deliveryPath.map((step, index) => (
                            <div
                                key={step.label}
                                className="bg-background/60 rounded-xl border p-4"
                            >
                                <div className="text-muted-foreground text-[10px] font-bold tracking-wider uppercase">
                                    Step {String(index + 1).padStart(2, '0')}
                                </div>
                                <div className="mt-2 text-sm font-bold">
                                    {step.label}
                                </div>
                                <div className="mt-3 inline-flex items-center gap-1.5 text-[10px] font-bold text-emerald-600 uppercase dark:text-emerald-400">
                                    <CheckCircle2 className="h-3 w-3" />
                                    {step.status}
                                </div>
                            </div>
                        ))}
                    </div>
                </section>

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
                                    Starts a real sandbox authority chain
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
                                    ? 'Creating authority…'
                                    : 'Create & initialize'}
                                {!form.processing && (
                                    <ArrowRight className="h-4 w-4" />
                                )}
                            </button>
                        </form>

                        <div className="mt-6 space-y-3 border-t pt-5">
                            <FlowStep
                                icon={Building2}
                                text="Organization + owner membership"
                            />
                            <FlowStep
                                icon={Layers3}
                                text="Sandbox product authority"
                            />
                            <FlowStep
                                icon={KeyRound}
                                text="Explicit entitlement policy"
                            />
                            <FlowStep
                                icon={ShieldCheck}
                                text="Idempotent active entitlement"
                            />
                            <FlowStep
                                icon={BadgeCheck}
                                text="Signed sandbox license lifecycle"
                            />
                            <FlowStep
                                icon={ShieldCheck}
                                text="Validation + revocation checks"
                            />
                        </div>
                    </section>

                    <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                        <div className="flex items-center justify-between gap-4">
                            <div>
                                <h2 className="font-bold">
                                    Organizations & rights
                                </h2>
                                <p className="text-muted-foreground mt-1 text-xs">
                                    Live authority records owned by your account
                                </p>
                            </div>
                            <span className="text-muted-foreground rounded-full border px-2.5 py-1 text-[10px] font-semibold">
                                PostgreSQL authority
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
                                        Create the first organization to
                                        activate the Main Platform authority
                                        chain and make this dashboard
                                        operational.
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
                                                            <div className="flex items-center gap-2">
                                                                <KeyRound className="h-3.5 w-3.5 text-red-500" />
                                                                <span className="font-semibold">
                                                                    {
                                                                        entitlement.capability
                                                                    }
                                                                </span>
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
