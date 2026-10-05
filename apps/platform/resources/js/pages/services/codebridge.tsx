import { Head, Link, router, useForm } from '@inertiajs/react';
import { useMemo, useState, type FormEvent, type ReactNode } from 'react';
import {
    ArrowLeft,
    Cable,
    CheckCircle2,
    FolderGit2,
    KeyRound,
    Laptop2,
    Link2,
    Plus,
    Server,
    ShieldCheck,
    TerminalSquare,
    Wrench,
} from 'lucide-react';

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

type ConnectedClient = {
    client_id: string;
    client_name: string;
    sessions: number;
    scopes: string[];
    connected_at: string | null;
    last_active_at: string | null;
};

type ManagedDevice = {
    id: string;
    name: string;
    platform: string | null;
    arch: string | null;
};

type ManagedProject = {
    device_id: string;
    project_id: string;
    project_name: string;
    repository: string | null;
    permissions: string[];
    gate_preset: string;
    status: string;
    updated_at: string | null;
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
    devices: ManagedDevice[];
    projects: ManagedProject[];
    connected_clients: ConnectedClient[];
    access_token_ttl_seconds: number;
};

type Props = {
    organization: Organization;
    entitlement: Entitlement;
    service: Service;
};

const CHATGPT_DESKTOP_SETUP_URL = '/install-chatgpt-desktop.ps1';
const DESKTOP_INSTALL_DESCRIPTION =
    'Download the KMJ Desktop setup once. It adds the official KMJ marketplace; CodeBridge is installed by default and opens browser OAuth on first use.';
const CONNECTED_CLIENTS_DESCRIPTION =
    'Review OAuth clients connected to this KMJ account and revoke refresh access at any time.';
const NO_CONNECTED_CLIENTS =
    'No active CodeBridge OAuth client is connected to this account.';

export default function CodeBridgeService({
    organization,
    entitlement,
    service,
}: Props) {
    const [showProjectForm, setShowProjectForm] = useState(false);
    const defaultDevice = service.devices[0]?.id ?? '';
    const projectForm = useForm({
        tenant_id: organization.id,
        device_id: defaultDevice,
        project_id: '',
        project_name: '',
        repository: '',
        access_mode: 'write',
        gate_preset: 'standard',
    });

    const projectCounts = useMemo(
        () => ({
            authorized: service.projects.filter(
                (project) => project.status === 'authorized',
            ).length,
            pending: service.projects.filter(
                (project) => project.status !== 'authorized',
            ).length,
        }),
        [service.projects],
    );

    const submitProject = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        projectForm.post('/services/kmj-codebridge/projects', {
            preserveScroll: true,
            onSuccess: () => {
                projectForm.reset(
                    'project_id',
                    'project_name',
                    'repository',
                );
                setShowProjectForm(false);
            },
        });
    };

    const revokeClient = (clientId: string) => {
        router.post(
            `/services/kmj-codebridge/oauth-clients/${encodeURIComponent(clientId)}/revoke`,
            {},
            { preserveScroll: true },
        );
    };

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
                                href={CHATGPT_DESKTOP_SETUP_URL}
                                download
                                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-black text-white transition hover:bg-red-500"
                            >
                                <Link2 className="h-3.5 w-3.5" />
                                Set up ChatGPT Desktop
                            </a>
                            <button
                                type="button"
                                onClick={() => setShowProjectForm(true)}
                                disabled={service.devices.length === 0}
                                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-red-500/30 px-4 text-xs font-black text-red-500 transition hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                                <Plus className="h-3.5 w-3.5" />
                                Add project
                            </button>
                            <Link
                                href="/codebridge/pair"
                                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-bold transition hover:border-red-500/40 hover:text-red-500"
                            >
                                <Laptop2 className="h-3.5 w-3.5" />
                                Pair device
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
                                ? titleCase(service.plan) + ' plan'
                                : 'Setup required'
                        }
                    />
                    <Metric
                        label="OAuth"
                        value={service.oauth_ready ? 'Ready' : 'Unavailable'}
                        hint="Browser OAuth + Desktop bridge"
                    />
                    <Metric
                        label="Managed devices"
                        value={service.managed_devices}
                        hint={
                            service.device_limit
                                ? 'Limit ' + service.device_limit
                                : 'No plan limit reported'
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
                            <div className="text-muted-foreground text-[10px] font-bold tracking-wider uppercase">
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

                        <div className="mt-5 rounded-xl border border-red-500/20 bg-red-500/[0.03] p-4">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <div className="flex items-center gap-2 text-xs font-black">
                                        <Laptop2 className="h-3.5 w-3.5 text-red-500" />
                                        ChatGPT Desktop
                                    </div>
                                    <p className="text-muted-foreground mt-2 text-[11px] leading-5">
                                        {DESKTOP_INSTALL_DESCRIPTION}
                                    </p>
                                </div>
                                <a
                                    href={CHATGPT_DESKTOP_SETUP_URL}
                                    download
                                    className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-black text-white transition hover:bg-red-500"
                                >
                                    <Link2 className="h-3.5 w-3.5" />
                                    Download setup
                                </a>
                            </div>
                        </div>

                        <div className="mt-5 rounded-xl border border-emerald-500/15 bg-emerald-500/[0.03] p-4">
                            <div className="flex items-center gap-2 text-xs font-black">
                                <FolderGit2 className="h-3.5 w-3.5 text-emerald-500" />
                                Browser-managed projects
                            </div>
                            <p className="text-muted-foreground mt-2 text-[11px] leading-5">
                                After a device is enrolled, project access is
                                managed here. No JSON editing, token copying or
                                manual systemd configuration is part of the
                                normal project workflow.
                            </p>
                        </div>

                        <div className="mt-5">
                            <div className="text-xs font-black">
                                Connect from ChatGPT Desktop
                            </div>
                            <ol className="text-muted-foreground mt-3 space-y-3 text-xs leading-5">
                                <li className="flex gap-3">
                                    <StepNumber value="1" />
                                    Download and run the KMJ ChatGPT Desktop
                                    setup once.
                                </li>
                                <li className="flex gap-3">
                                    <StepNumber value="2" />
                                    Fully quit and reopen ChatGPT Desktop. KMJ
                                    CodeBridge is installed by default.
                                </li>
                                <li className="flex gap-3">
                                    <StepNumber value="3" />
                                    Use CodeBridge. Its local bridge opens KMJ
                                    browser OAuth automatically on first use.
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
                                    service.plan ? titleCase(service.plan) : '—'
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
                                    : ['read', 'write', 'execute']
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

                <section
                    id="projects"
                    className="border-sidebar-border/70 bg-card dark:border-sidebar-border scroll-mt-6 rounded-2xl border p-5 sm:p-6"
                >
                    <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
                        <div>
                            <div className="flex items-center gap-2">
                                <FolderGit2 className="h-5 w-5 text-red-500" />
                                <h2 className="font-black">Projects</h2>
                            </div>
                            <p className="text-muted-foreground mt-1 text-xs leading-5">
                                Manage project access from the browser. Device
                                credentials stay private and projects are only
                                exposed after secure device synchronization.
                            </p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-full border px-3 py-1 text-[10px] font-bold">
                                {projectCounts.authorized} authorized
                            </span>
                            {projectCounts.pending > 0 && (
                                <span className="rounded-full border border-amber-500/20 bg-amber-500/5 px-3 py-1 text-[10px] font-bold text-amber-600 dark:text-amber-400">
                                    {projectCounts.pending} pending
                                </span>
                            )}
                            <button
                                type="button"
                                onClick={() => setShowProjectForm((value) => !value)}
                                disabled={service.devices.length === 0}
                                className="inline-flex h-9 items-center justify-center gap-2 rounded-xl bg-red-600 px-3 text-[11px] font-black text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                                <Plus className="h-3.5 w-3.5" />
                                Add project
                            </button>
                        </div>
                    </div>

                    {showProjectForm && (
                        <form
                            onSubmit={submitProject}
                            className="mt-5 grid gap-4 rounded-2xl border border-red-500/15 bg-red-500/[0.02] p-4 lg:grid-cols-2"
                        >
                            <ProjectField label="Device">
                                <select
                                    value={projectForm.data.device_id}
                                    onChange={(event) =>
                                        projectForm.setData(
                                            'device_id',
                                            event.target.value,
                                        )
                                    }
                                    className="bg-background h-10 w-full rounded-xl border px-3 text-xs"
                                    required
                                >
                                    {service.devices.map((device) => (
                                        <option key={device.id} value={device.id}>
                                            {device.name} ({device.id})
                                        </option>
                                    ))}
                                </select>
                            </ProjectField>

                            <ProjectField label="Repository">
                                <input
                                    value={projectForm.data.repository}
                                    onChange={(event) =>
                                        projectForm.setData(
                                            'repository',
                                            event.target.value,
                                        )
                                    }
                                    placeholder="kmjtechno/kmj-main-platform"
                                    className="bg-background h-10 w-full rounded-xl border px-3 text-xs"
                                    required
                                />
                                {projectForm.errors.repository && (
                                    <FieldError text={projectForm.errors.repository} />
                                )}
                            </ProjectField>

                            <ProjectField label="Project ID">
                                <input
                                    value={projectForm.data.project_id}
                                    onChange={(event) =>
                                        projectForm.setData(
                                            'project_id',
                                            event.target.value,
                                        )
                                    }
                                    placeholder="kmj-main-platform"
                                    className="bg-background h-10 w-full rounded-xl border px-3 text-xs"
                                    required
                                />
                                {projectForm.errors.project_id && (
                                    <FieldError text={projectForm.errors.project_id} />
                                )}
                            </ProjectField>

                            <ProjectField label="Display name">
                                <input
                                    value={projectForm.data.project_name}
                                    onChange={(event) =>
                                        projectForm.setData(
                                            'project_name',
                                            event.target.value,
                                        )
                                    }
                                    placeholder="KMJ Main Platform"
                                    className="bg-background h-10 w-full rounded-xl border px-3 text-xs"
                                    required
                                />
                            </ProjectField>

                            <ProjectField label="Access">
                                <select
                                    value={projectForm.data.access_mode}
                                    onChange={(event) =>
                                        projectForm.setData(
                                            'access_mode',
                                            event.target.value,
                                        )
                                    }
                                    className="bg-background h-10 w-full rounded-xl border px-3 text-xs"
                                >
                                    <option value="write">Read + guarded write</option>
                                    <option value="read">Read only</option>
                                </select>
                            </ProjectField>

                            <ProjectField label="Quality gate preset">
                                <select
                                    value={projectForm.data.gate_preset}
                                    onChange={(event) =>
                                        projectForm.setData(
                                            'gate_preset',
                                            event.target.value,
                                        )
                                    }
                                    className="bg-background h-10 w-full rounded-xl border px-3 text-xs"
                                >
                                    <option value="standard">Standard</option>
                                    <option value="platform">Platform</option>
                                    <option value="full">Full</option>
                                </select>
                            </ProjectField>

                            <div className="flex flex-wrap justify-end gap-2 lg:col-span-2">
                                <button
                                    type="button"
                                    onClick={() => setShowProjectForm(false)}
                                    className="h-10 rounded-xl border px-4 text-xs font-bold"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={projectForm.processing}
                                    className="h-10 rounded-xl bg-red-600 px-4 text-xs font-black text-white transition hover:bg-red-500 disabled:opacity-50"
                                >
                                    {projectForm.processing
                                        ? 'Queuing…'
                                        : 'Install project'}
                                </button>
                            </div>
                        </form>
                    )}

                    {service.devices.length === 0 ? (
                        <div className="text-muted-foreground mt-5 rounded-xl border border-dashed p-5 text-xs">
                            Pair a device first. After enrollment, projects can
                            be added here without terminal configuration.
                        </div>
                    ) : service.projects.length === 0 ? (
                        <div className="text-muted-foreground mt-5 rounded-xl border border-dashed p-5 text-xs">
                            No projects are registered yet. Use Add project to
                            start the secure device-sync workflow.
                        </div>
                    ) : (
                        <div className="mt-5 grid gap-3">
                            {service.projects.map((project) => (
                                <div
                                    key={`${project.device_id}:${project.project_id}`}
                                    className="flex flex-col justify-between gap-4 rounded-xl border p-4 lg:flex-row lg:items-center"
                                >
                                    <div className="min-w-0">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <div className="text-sm font-black">
                                                {project.project_name}
                                            </div>
                                            <ProjectStatus status={project.status} />
                                        </div>
                                        <div className="text-muted-foreground mt-1 text-[11px]">
                                            {project.repository ?? project.project_id}
                                            {' · '}
                                            {project.device_id}
                                            {' · '}
                                            {titleCase(project.gate_preset)} gates
                                        </div>
                                        <div className="mt-2 flex flex-wrap gap-2">
                                            {project.permissions.map((permission) => (
                                                <span
                                                    key={permission}
                                                    className="rounded-lg border px-2 py-1 text-[9px] font-bold uppercase"
                                                >
                                                    {permission}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                    <span className="text-muted-foreground text-[10px]">
                                        {project.status === 'authorized'
                                            ? 'Available to authorized AI clients'
                                            : 'Waiting for secure device sync'}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </section>

                <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                        <div>
                            <h2 className="font-black">Connected AI clients</h2>
                            <p className="text-muted-foreground mt-1 text-xs leading-5">
                                {CONNECTED_CLIENTS_DESCRIPTION}
                            </p>
                        </div>
                        <span className="rounded-full border px-3 py-1 text-[10px] font-bold">
                            {service.connected_clients.length} active
                        </span>
                    </div>

                    {service.connected_clients.length === 0 ? (
                        <div className="text-muted-foreground mt-5 rounded-xl border border-dashed p-5 text-xs">
                            {NO_CONNECTED_CLIENTS}
                        </div>
                    ) : (
                        <div className="mt-5 grid gap-3">
                            {service.connected_clients.map((client) => (
                                <div
                                    key={client.client_id}
                                    className="flex flex-col justify-between gap-4 rounded-xl border p-4 lg:flex-row lg:items-center"
                                >
                                    <div className="min-w-0">
                                        <div className="text-sm font-black">
                                            {client.client_name}
                                        </div>
                                        <div className="text-muted-foreground mt-1 text-[11px]">
                                            {clientSummary(client)}
                                        </div>
                                        <div className="mt-2 flex flex-wrap gap-2">
                                            {client.scopes.map((scope) => (
                                                <span
                                                    key={scope}
                                                    className="rounded-lg border px-2 py-1 text-[9px] font-bold"
                                                >
                                                    {scope}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() =>
                                            revokeClient(client.client_id)
                                        }
                                        className="inline-flex h-9 shrink-0 items-center justify-center rounded-xl border border-red-500/30 px-3 text-[11px] font-black text-red-500 transition hover:bg-red-500/10"
                                    >
                                        Revoke access
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    <p className="text-muted-foreground mt-4 text-[10px] leading-4">
                        Refresh access stops immediately. Existing access tokens
                        expire within{' '}
                        {Math.max(
                            1,
                            Math.ceil(service.access_token_ttl_seconds / 60),
                        )}{' '}
                        minutes.
                    </p>
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

function ProjectField({
    label,
    children,
}: {
    label: string;
    children: ReactNode;
}) {
    return (
        <label className="grid gap-2">
            <span className="text-muted-foreground text-[10px] font-bold tracking-wider uppercase">
                {label}
            </span>
            {children}
        </label>
    );
}

function FieldError({ text }: { text: string }) {
    return <span className="text-[10px] font-bold text-red-500">{text}</span>;
}

function ProjectStatus({ status }: { status: string }) {
    const active = status === 'authorized';

    return (
        <span
            className={
                active
                    ? 'rounded-full border border-emerald-500/15 bg-emerald-500/5 px-2 py-1 text-[9px] font-black text-emerald-600 uppercase dark:text-emerald-400'
                    : 'rounded-full border border-amber-500/20 bg-amber-500/5 px-2 py-1 text-[9px] font-black text-amber-600 uppercase dark:text-amber-400'
            }
        >
            {active ? 'Authorized' : titleCase(status)}
        </span>
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
            <div className="text-muted-foreground text-[10px] font-bold tracking-wider uppercase">
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
        .join(' ');
}

function clientSummary(client: ConnectedClient): string {
    const sessions =
        client.sessions === 1
            ? '1 active session'
            : `${client.sessions} active sessions`;

    return `${sessions} · Last active ${formatDateTime(client.last_active_at)}`;
}

function formatDateTime(value?: string | null): string {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat('en', {
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    }).format(date);
}

function formatDate(value?: string | null): string {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat('en', {
        year: 'numeric',
        month: 'short',
        day: '2-digit',
    }).format(date);
}
