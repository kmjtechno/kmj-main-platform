import { FormEvent } from 'react';
import { Head, useForm } from '@inertiajs/react';
import {
    ArrowRight,
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
                <section className="overflow-hidden rounded-2xl border border-sidebar-border/70 bg-gradient-to-br from-background via-background to-red-950/10 p-6 sm:p-8 dark:border-sidebar-border">
                    <div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
                        <div className="max-w-2xl">
                            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-red-500/15 bg-red-500/5 px-3 py-1 text-xs font-semibold text-red-500">
                                <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                                Authority Core · Active
                            </div>
                            <h1 className="text-3xl font-black tracking-tight sm:text-4xl">
                                KMJ Main Platform Control Center
                            </h1>
                            <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
                                Create an organization and the platform will establish the first verified
                                authority chain: organization ownership → sandbox product → explicit
                                entitlement policy → active entitlement.
                            </p>
                        </div>

                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                            <Metric label="Organizations" value={organizations.length} />
                            <Metric label="Entitlements" value={entitlementCount} />
                            <div className="col-span-2 sm:col-span-1">
                                <Metric label="Authority" value="Online" />
                            </div>
                        </div>
                    </div>
                </section>

                <div className="grid gap-6 xl:grid-cols-[380px_1fr]">
                    <section className="rounded-2xl border border-sidebar-border/70 bg-card p-5 dark:border-sidebar-border sm:p-6">
                        <div className="flex items-center gap-3">
                            <span className="grid h-10 w-10 place-items-center rounded-xl bg-red-500/10 text-red-500">
                                <Plus className="h-5 w-5" />
                            </span>
                            <div>
                                <h2 className="font-bold">Create organization</h2>
                                <p className="text-xs text-muted-foreground">
                                    Starts a real sandbox authority chain
                                </p>
                            </div>
                        </div>

                        <form onSubmit={submit} className="mt-6 space-y-4">
                            <div>
                                <label htmlFor="organization-name" className="text-xs font-semibold">
                                    Organization name
                                </label>
                                <input
                                    id="organization-name"
                                    value={form.data.name}
                                    onChange={(event) => form.setData('name', event.target.value)}
                                    placeholder="Example: KMJ Product Lab"
                                    className="mt-2 h-11 w-full rounded-xl border border-input bg-background px-3 text-sm outline-none transition focus:border-red-500/50 focus:ring-2 focus:ring-red-500/10"
                                    autoComplete="organization"
                                    required
                                    minLength={2}
                                    maxLength={160}
                                />
                                {form.errors.name && (
                                    <p className="mt-2 text-xs text-destructive">{form.errors.name}</p>
                                )}
                            </div>

                            <button
                                type="submit"
                                disabled={form.processing}
                                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-bold text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                {form.processing ? 'Creating authority…' : 'Create & initialize'}
                                {!form.processing && <ArrowRight className="h-4 w-4" />}
                            </button>
                        </form>

                        <div className="mt-6 space-y-3 border-t pt-5">
                            <FlowStep icon={Building2} text="Organization + owner membership" />
                            <FlowStep icon={Layers3} text="Sandbox product authority" />
                            <FlowStep icon={KeyRound} text="Explicit entitlement policy" />
                            <FlowStep icon={ShieldCheck} text="Idempotent active entitlement" />
                        </div>
                    </section>

                    <section className="rounded-2xl border border-sidebar-border/70 bg-card p-5 dark:border-sidebar-border sm:p-6">
                        <div className="flex items-center justify-between gap-4">
                            <div>
                                <h2 className="font-bold">Organizations & rights</h2>
                                <p className="mt-1 text-xs text-muted-foreground">
                                    Live authority records owned by your account
                                </p>
                            </div>
                            <span className="rounded-full border px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">
                                PostgreSQL authority
                            </span>
                        </div>

                        {organizations.length === 0 ? (
                            <div className="mt-8 grid min-h-72 place-items-center rounded-xl border border-dashed bg-muted/20 p-8 text-center">
                                <div>
                                    <Building2 className="mx-auto h-9 w-9 text-muted-foreground/40" />
                                    <h3 className="mt-4 text-sm font-bold">No organization yet</h3>
                                    <p className="mx-auto mt-2 max-w-sm text-xs leading-5 text-muted-foreground">
                                        Create the first organization to activate the Main Platform authority
                                        chain and make this dashboard operational.
                                    </p>
                                </div>
                            </div>
                        ) : (
                            <div className="mt-5 space-y-4">
                                {organizations.map((organization) => (
                                    <article
                                        key={organization.id}
                                        className="rounded-xl border bg-background/60 p-4 sm:p-5"
                                    >
                                        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                                            <div className="flex items-start gap-3">
                                                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-muted">
                                                    <Building2 className="h-5 w-5" />
                                                </span>
                                                <div>
                                                    <h3 className="font-bold">{organization.name}</h3>
                                                    <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                                                        <span>{organization.role}</span>
                                                        <span>·</span>
                                                        <span className="font-mono">{organization.id.slice(0, 8)}</span>
                                                    </div>
                                                </div>
                                            </div>
                                            <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-emerald-500/15 bg-emerald-500/5 px-2.5 py-1 text-[10px] font-bold text-emerald-600 dark:text-emerald-400">
                                                <CheckCircle2 className="h-3 w-3" />
                                                Authority active
                                            </span>
                                        </div>

                                        <div className="mt-4 border-t pt-4">
                                            <div className="text-[10px] font-bold tracking-wider text-muted-foreground uppercase">
                                                Entitlements
                                            </div>
                                            <div className="mt-2 space-y-2">
                                                {organization.entitlements.map((entitlement) => (
                                                    <div
                                                        key={entitlement.id}
                                                        className="flex flex-col justify-between gap-2 rounded-lg bg-muted/40 px-3 py-3 text-xs sm:flex-row sm:items-center"
                                                    >
                                                        <div className="flex items-center gap-2">
                                                            <KeyRound className="h-3.5 w-3.5 text-red-500" />
                                                            <span className="font-semibold">
                                                                {entitlement.capability}
                                                            </span>
                                                        </div>
                                                        <span className="text-[10px] font-bold text-emerald-600 uppercase dark:text-emerald-400">
                                                            {entitlement.status}
                                                        </span>
                                                    </div>
                                                ))}
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
        <div className="min-w-28 rounded-xl border bg-background/70 px-4 py-3">
            <div className="text-lg font-black">{value}</div>
            <div className="mt-0.5 text-[10px] text-muted-foreground">{label}</div>
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
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-muted text-foreground">
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
