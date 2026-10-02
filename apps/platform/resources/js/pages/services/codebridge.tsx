[Reading 359 lines from start (total: 359 lines, 0 remaining)]

import { Head, Link } from "@inertiajs/react";
import {
    ArrowLeft,
    Cable,
    CheckCircle2,
    KeyRound,
    Laptop2,
    Link2,
    Server,
    ShieldCheck,
    TerminalSquare,
    Wrench,
} from "lucide-react";

type Organization = {
    id: string;
    name: string;
    role: string;
};

type Entitlement = {
    id: string;
    capability: string;
    status: string;
    starts_at: string;
};

type Service = {
    endpoint: string;
    oauth_ready: boolean;
    plan: string | null;
    license_status: string;
    license_starts_at: string | null;
    license_expires_at: string | null;
    permissions: string[];
    device_limit: number | null;
    managed_devices: number;
    pending_pairings: number;
};

type Props = {
    organization: Organization;
    entitlement: Entitlement;
    service: Service;
};

export default function CodeBridgeService({
    organization,
    entitlement,
    service,
}: Props) {
    return (
        <>
            <Head title="KMJ CodeBridge" />

            <div className="flex h-full flex-1 flex-col gap-6 overflow-x-auto p-4 sm:p-6">
                <section className="border-sidebar-border/70 from-background via-background dark:border-sidebar-border overflow-hidden rounded-2xl border bg-gradient-to-br to-red-950/10 p-6 sm:p-8">
                    <Link
                        href="/dashboard"
                        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-2 text-xs font-bold"
                    >
                        <ArrowLeft className="h-3.5 w-3.5" />
                        Back to My Services
                    </Link>

                    <div className="mt-6 flex flex-col justify-between gap-6 lg:flex-row lg:items-start">
                        <div className="flex items-start gap-4">
                            <span className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl border border-red-500/20 bg-red-500/10 text-red-500">
                                <Cable className="h-7 w-7" />
                            </span>
                            <div>
                                <div className="flex flex-wrap items-center gap-2">
                                    <h1 className="text-3xl font-black tracking-tight">
                                        KMJ CodeBridge
                                    </h1>
                                    <span className="rounded-full border border-emerald-500/15 bg-emerald-500/5 px-2 py-1 text-[9px] font-black text-emerald-600 uppercase dark:text-emerald-400">
                                        {entitlement.status}
                                    </span>
                                </div>
                                <p className="text-muted-foreground mt-1 text-xs">
                                    {organization.name}
                                </p>
                                <p className="text-muted-foreground mt-4 max-w-2xl text-sm leading-6">
                                    Connect ChatGPT to authorized computers and
                                    VPS projects through a secure,
                                    project-scoped MCP bridge. CodeBridge
                                    exposes only approved files, Git operations
                                    and quality gates.
                                </p>
                            </div>
                        </div>

                        <div className="flex flex-wrap gap-2">
                            <a
                                href="https://chatgpt.com/"
                                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-black text-white transition hover:bg-red-500"
                            >
                                <Link2 className="h-3.5 w-3.5" />
                                Open ChatGPT
                            </a>
                            <Link
                                href="/codebridge/pair"
                                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-bold transition hover:border-red-500/40 hover:text-red-500"
                            >
                                <Laptop2 className="h-3.5 w-3.5" />
                                Pair a device
                            </Link>
                        </div>
                    </div>
                </section>

                <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <Metric
                        label="License"
                        value={service.license_status}
                        hint={
                            service.plan
                                ? titleCase(service.plan) + " plan"
                                : "Setup required"
                        }
                    />
                    <Metric
                        label="OAuth"
                        value={service.oauth_ready ? "Ready" : "Unavailable"}
                        hint="ChatGPT account linking"
                    />
                    <Metric
                        label="Managed devices"
                        value={service.managed_devices}
                        hint={
                            service.device_limit
                                ? "Limit " + service.device_limit
                                : "No plan limit reported"
                        }
                    />
                    <Metric
                        label="Valid until"
                        value={formatDate(service.license_expires_at)}
                        hint="Main Platform license authority"
                    />
                </section>

                <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
                    <div className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                        <div className="flex items-center gap-2">
                            <Server className="h-5 w-5 text-red-500" />
                            <h2 className="font-black">Connection</h2>
                        </div>
                        <p className="text-muted-foreground mt-1 text-xs">
                            Use this endpoint when connecting KMJ CodeBridge as
                            an MCP service.
                        </p>

                        <div className="mt-5 rounded-xl border bg-black/5 p-4 dark:bg-white/[0.02]">
                            <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider">
                                MCP endpoint
                            </div>
                            <code className="mt-2 block overflow-x-auto rounded-lg bg-black/5 px-3 py-2 text-xs dark:bg-white/[0.03]">
                                {service.endpoint}
                            </code>
                            <div className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-bold text-emerald-600 dark:text-emerald-400">
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                Protected by OAuth 2.1 + PKCE
                            </div>
                        </div>

                        <div className="mt-5">
                            <div className="text-xs font-black">
                                Connect from ChatGPT
                            </div>
                            <ol className="text-muted-foreground mt-3 space-y-3 text-xs leading-5">
                                <li className="flex gap-3">
                                    <StepNumber value="1" />
                                    Open KMJ CodeBridge in ChatGPT and choose
                                    Connect.
                                </li>
                                <li className="flex gap-3">
                                    <StepNumber value="2" />
                                    Sign in with this KMJ account and approve
                                    the requested CodeBridge permissions.
                                </li>
                                <li className="flex gap-3">
                                    <StepNumber value="3" />
                                    Return to ChatGPT and select an authorized
                                    device and project.
                                </li>
                            </ol>
                        </div>
                    </div>

                    <div className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                        <div className="flex items-center gap-2">
                            <ShieldCheck className="h-5 w-5 text-red-500" />
                            <h2 className="font-black">Access & security</h2>
                        </div>

                        <div className="mt-5 space-y-3">
                            <InfoRow
                                label="Organization"
                                value={organization.name}
                            />
                            <InfoRow
                                label="Capability"
                                value={entitlement.capability}
                            />
                            <InfoRow
                                label="Plan"
                                value={
                                    service.plan ? titleCase(service.plan) : "—"
                                }
                            />
                            <InfoRow
                                label="Started"
                                value={formatDate(service.license_starts_at)}
                            />
                            <InfoRow
                                label="Pending pairings"
                                value={String(service.pending_pairings)}
                            />
                        </div>

                        <div className="mt-5 rounded-xl border p-4">
                            <div className="text-xs font-black">
                                Authorized permissions
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2">
                                {(service.permissions.length
                                    ? service.permissions
                                    : ["read", "write", "execute"]
                                ).map((permission) => (
                                    <span
                                        key={permission}
                                        className="rounded-lg border px-2.5 py-1 text-[10px] font-bold uppercase"
                                    >
                                        {permission}
                                    </span>
                                ))}
                            </div>
                        </div>

                        <Link
                            href="/settings/security"
                            className="mt-5 inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl border px-4 text-xs font-bold transition hover:border-red-500/40 hover:text-red-500"
                        >
                            <KeyRound className="h-3.5 w-3.5" />
                            Account security
                        </Link>
                    </div>
                </section>

                <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                    <div>
                        <h2 className="font-black">What CodeBridge can do</h2>
                        <p className="text-muted-foreground mt-1 text-xs">
                            Capabilities remain scoped to authorized projects
                            and administrator-approved operations.
                        </p>
                    </div>

                    <div className="mt-5 grid gap-3 md:grid-cols-3">
                        <Capability
                            icon={Laptop2}
                            title="Inspect authorized projects"
                            text="Read project structure, files, Git status, diffs and recent history."
                        />
                        <Capability
                            icon={Wrench}
                            title="Guarded code changes"
                            text="Edit files using hash preconditions so stale writes are rejected."
                        />
                        <Capability
                            icon={TerminalSquare}
                            title="Verified quality gates"
                            text="Run configured checks without exposing unrestricted shell access."
                        />
                    </div>
                </section>
            </div>
        </>
    );
}

function Metric({
    label,
    value,
    hint,
}: {
    label: string;
    value: string | number;
    hint: string;
}) {
    return (
        <div className="bg-card rounded-2xl border p-4">
            <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider">
                {label}
            </div>
            <div className="mt-1 text-lg font-black">{value}</div>
            <div className="text-muted-foreground mt-1 text-[10px]">{hint}</div>
        </div>
    );
}

function InfoRow({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex items-start justify-between gap-4 rounded-xl border px-3 py-2.5">
            <span className="text-muted-foreground text-[11px]">{label}</span>
            <span className="max-w-[65%] text-right text-[11px] font-bold">
                {value}
            </span>
        </div>
    );
}

function Capability({
    icon: Icon,
    title,
    text,
}: {
    icon: typeof Laptop2;
    title: string;
    text: string;
}) {
    return (
        <div className="rounded-xl border p-4">
            <Icon className="h-4 w-4 text-red-500" />
            <div className="mt-3 text-xs font-black">{title}</div>
            <p className="text-muted-foreground mt-1 text-[11px] leading-5">
                {text}
            </p>
        </div>
    );
}

function StepNumber({ value }: { value: string }) {
    return (
        <span className="bg-muted text-foreground grid h-6 w-6 shrink-0 place-items-center rounded-lg text-[10px] font-black">
            {value}
        </span>
    );
}

function titleCase(value: string): string {
    return value
        .split(/[-_]/)
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

function formatDate(value?: string | null): string {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("en", {
        year: "numeric",
        month: "short",
        day: "2-digit",
    }).format(date);
}

[executed on device: kmjtechnonetgmailcom (cbe1c3e2-c299-4851-9d11-9fafa86b4357)]