import { Head, Link, router } from '@inertiajs/react';
import { useState } from 'react';
import {
    ArrowLeft,
    Cable,
    Copy,
    FolderKanban,
    Plus,
    RefreshCcw,
    CheckCircle2,
    KeyRound,
    Laptop2,
    Link2,
    Server,
    ShieldCheck,
    TerminalSquare,
    Wrench,
} from 'lucide-react';
import LockedBrand from '@/components/locked-brand';

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

type EnrolledDevice = {
    device_id: string;
    last_paired_project: string | null;
    last_paired_project_name: string | null;
    credential_expires_at_epoch: number;
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
    enrolled_devices: EnrolledDevice[];
    pending_pairings: number;
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
    'Download the official KMJ setup, then enable CodeBridge in ChatGPT Desktop and approve the requested connection. Installation alone does not grant access.';
const CONNECTED_CLIENTS_DESCRIPTION =
    'Review OAuth clients connected to this KMJ account and revoke refresh access at any time.';
const NO_CONNECTED_CLIENTS =
    'No active CodeBridge OAuth client is connected to this account.';

export default function CodeBridgeService({
    organization,
    entitlement,
    service,
}: Props) {
    const [showDeviceSetup, setShowDeviceSetup] = useState(false);
    const [copiedInstaller, setCopiedInstaller] = useState(false);
    const [newDeviceId, setNewDeviceId] = useState('');
    const [newProjectId, setNewProjectId] = useState('');
    const [newProjectPath, setNewProjectPath] = useState('');
    const safeProjectPath =
        /^\/[A-Za-z0-9._/-]+$/.test(newProjectPath) &&
        newProjectPath !== '/' &&
        !newProjectPath.split('/').some((segment) =>
            segment === '.' || segment === '..',
        );
    const validIdentity =
        /^[A-Za-z0-9_-]{1,64}$/.test(newDeviceId) &&
        /^[A-Za-z0-9_-]{1,64}$/.test(newProjectId) &&
        safeProjectPath;
    const installerCommand =
        'curl -fsSL --proto \'=https\' --tlsv1.2 https://kmjtechno.com/install | sudo bash -s -- --device ' +
        newDeviceId +
        ' --project-id ' +
        newProjectId +
        ' --project ' +
        newProjectPath;

    const suggestIdentity = () => {
        const suffix =
            typeof crypto !== 'undefined' && crypto.randomUUID
                ? crypto.randomUUID().slice(0, 8)
                : Date.now().toString(36).slice(-8);
        setNewDeviceId('device-' + suffix);
        setNewProjectId('project-' + suffix);
        setCopiedInstaller(false);
    };

    const copyInstaller = async () => {
        if (!validIdentity) return;
        try {
            await navigator.clipboard.writeText(installerCommand);
            setCopiedInstaller(true);
        } catch {
            setCopiedInstaller(false);
        }
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

                    <LockedBrand compact className="mt-5" />
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
                            <a
                                href="#device-center"
                                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-bold transition hover:border-red-500/40 hover:text-red-500"
                            >
                                <Laptop2 className="h-3.5 w-3.5" />
                                Devices & projects
                            </a>
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

                <section
                    id="device-center"
                    className="border-sidebar-border/70 bg-card dark:border-sidebar-border scroll-mt-6 rounded-2xl border p-5 sm:p-6"
                    aria-labelledby="device-center-title"
                >
                    <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                            <h2 id="device-center-title" className="flex items-center gap-2 text-lg font-black">
                                <FolderKanban className="h-5 w-5 text-red-500" />
                                Devices & projects
                            </h2>
                            <p className="text-muted-foreground mt-2 max-w-2xl text-xs leading-5">
                                Manage enrolled credentials and their last
                                approved projects in one place. Enrollment is
                                not proof of a live connection; check actual
                                gateway heartbeat from CodeBridge.
                            </p>
                        </div>
                        <button
                            type="button"
                            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-black text-white transition hover:bg-red-500"
                            onClick={() => setShowDeviceSetup((open) => !open)}
                            aria-expanded={showDeviceSetup}
                            aria-controls="codebridge-add-device-steps"
                        >
                            <Plus className="h-4 w-4" />
                            {showDeviceSetup ? 'Close setup' : 'Add device / project'}
                        </button>
                    </div>

                    <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        {service.enrolled_devices.length === 0 ? (
                            <div className="text-muted-foreground rounded-xl border border-dashed p-5 text-xs sm:col-span-2 xl:col-span-3">
                                No active device credential is enrolled for this
                                organization. Start the setup on the computer
                                or VPS you want to authorize.
                            </div>
                        ) : (
                            service.enrolled_devices.map((device) => (
                                <article
                                    key={device.device_id}
                                    className="rounded-xl border bg-background/50 p-4"
                                >
                                    <div className="flex flex-wrap items-start justify-between gap-2">
                                        <div className="min-w-0">
                                            <h3 className="break-all text-sm font-black">
                                                {device.device_id}
                                            </h3>
                                            <div className="text-muted-foreground mt-1 text-[11px]">
                                                Enrolled credential
                                            </div>
                                        </div>
                                        <span className="rounded-lg border border-sky-500/30 bg-sky-500/5 px-2 py-1 text-[10px] font-bold text-sky-600 dark:text-sky-300">
                                            Not live-verified
                                        </span>
                                    </div>
                                    <div className="mt-4 flex items-start gap-2 text-[11px]">
                                        <FolderKanban className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-500" />
                                        <span className="min-w-0 break-words">
                                            {device.last_paired_project
                                                ? 'Last paired project: ' +
                                                  (device.last_paired_project_name ||
                                                      device.last_paired_project)
                                                : 'Project pairing record unavailable'}
                                        </span>
                                    </div>
                                    <p className="text-muted-foreground mt-3 text-[11px]">
                                        Credential valid until{' '}
                                        {new Intl.DateTimeFormat('en', {
                                            year: 'numeric',
                                            month: 'short',
                                            day: '2-digit',
                                        }).format(
                                            new Date(
                                                device.credential_expires_at_epoch *
                                                    1000,
                                            ),
                                        )}
                                    </p>
                                </article>
                            ))
                        )}
                    </div>

                    <div
                        id="codebridge-add-device-steps"
                        hidden={!showDeviceSetup}
                        className="mt-5 space-y-4 rounded-xl border border-red-500/25 bg-red-500/[0.03] p-4"
                    >
                        <h3 className="text-sm font-black">
                            Set up a device or project
                        </h3>
                        <ol className="space-y-4 text-xs leading-5">
                            <li>
                                <div className="font-bold">
                                    1. Run the KMJ agent installer on the target
                                    Linux/VPS machine
                                </div>
                                <div className="mt-3 grid gap-3 md:grid-cols-2">
                                    <label className="text-xs font-semibold">
                                        Device ID
                                        <input
                                            type="text"
                                            value={newDeviceId}
                                            onChange={(event) => {
                                                setNewDeviceId(event.target.value);
                                                setCopiedInstaller(false);
                                            }}
                                            maxLength={64}
                                            placeholder="my-vps"
                                            autoComplete="off"
                                            className="bg-background mt-1 block h-10 w-full rounded-lg border px-3 font-mono text-xs"
                                        />
                                    </label>
                                    <label className="text-xs font-semibold">
                                        Project ID
                                        <input
                                            type="text"
                                            value={newProjectId}
                                            onChange={(event) => {
                                                setNewProjectId(event.target.value);
                                                setCopiedInstaller(false);
                                            }}
                                            maxLength={64}
                                            placeholder="my-application"
                                            autoComplete="off"
                                            className="bg-background mt-1 block h-10 w-full rounded-lg border px-3 font-mono text-xs"
                                        />
                                    </label>
                                </div>
                                <label className="mt-3 block text-xs font-semibold">
                                    Project folder on the target machine
                                    <input
                                        type="text"
                                        value={newProjectPath}
                                        onChange={(event) => {
                                            setNewProjectPath(event.target.value);
                                            setCopiedInstaller(false);
                                        }}
                                        maxLength={256}
                                        placeholder="/srv/my-application"
                                        autoComplete="off"
                                        className="bg-background mt-1 block h-10 w-full rounded-lg border px-3 font-mono text-xs"
                                    />
                                </label>
                                <button
                                    type="button"
                                    onClick={suggestIdentity}
                                    className="mt-3 rounded-lg border px-3 py-2 text-xs font-semibold hover:border-red-500/40"
                                >
                                    Suggest unique IDs
                                </button>
                                <p className="text-muted-foreground mt-2">
                                    Only letters, digits, hyphens and underscores
                                    are allowed. Use a new identity for each
                                    additional device or project. The folder must
                                    be an existing absolute Linux path with no
                                    spaces or traversal segments.
                                </p>
                                <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2">
                                    <code className="bg-background min-w-0 flex-1 overflow-x-auto rounded-lg border p-3 text-[11px]">
                                        {validIdentity
                                            ? installerCommand
                                            : 'Enter IDs and an existing absolute project path to prepare the installer.'}
                                    </code>
                                    <button
                                        type="button"
                                        onClick={copyInstaller}
                                        disabled={!validIdentity}
                                        className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-3 text-xs font-semibold hover:border-red-500/40 disabled:cursor-not-allowed disabled:opacity-40"
                                    >
                                        <Copy className="h-4 w-4" />
                                        {copiedInstaller ? 'Copied' : 'Copy command'}
                                    </button>
                                </div>
                                <p className="text-muted-foreground mt-2">
                                    Verify the exact project folder exists on the
                                    target machine and review the installer
                                    before running an administrative command.
                                    This creates a new identity; it does not
                                    repair or replace an old project.
                                </p>
                            </li>
                            <li>
                                <div className="font-bold">
                                    2. Approve the short pairing code with the
                                    correct organization
                                </div>
                                <p className="text-muted-foreground mt-1">
                                    The installer creates a project-scoped
                                    pairing request. Approval is explicit and
                                    uses your existing CodeBridge license.
                                </p>
                                <Link
                                    href="/codebridge/pair"
                                    className="mt-2 inline-flex items-center gap-2 text-xs font-bold text-red-500 hover:underline"
                                >
                                    Open secure pairing
                                    <KeyRound className="h-3.5 w-3.5" />
                                </Link>
                            </li>
                            <li>
                                <div className="font-bold">
                                    3. Verify authorization in ChatGPT
                                </div>
                                <p className="text-muted-foreground mt-1">
                                    Ask “KMJ CodeBridge, check my connections”.
                                    The connection doctor separates account
                                    grants, gateway registration and offline
                                    devices. Do not repeatedly reconnect OAuth
                                    or overwrite an existing project.
                                </p>
                                <button
                                    type="button"
                                    onClick={() => router.reload({ only: ['service'] })}
                                    className="mt-2 inline-flex items-center gap-2 text-xs font-bold text-red-500 hover:underline"
                                >
                                    <RefreshCcw className="h-3.5 w-3.5" />
                                    Refresh enrolled device list
                                </button>
                            </li>
                        </ol>
                    </div>
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

                        <div className="mt-5 rounded-xl border p-4">
                            <div className="flex items-center gap-2 text-xs font-black">
                                <TerminalSquare className="h-3.5 w-3.5 text-red-500" />
                                Install on Linux / VPS
                            </div>
                            <p className="text-muted-foreground mt-2 text-[11px] leading-5">
                                Run this from the project directory. The
                                installer opens a short-lived browser pairing
                                flow; no manual agent token is required.
                            </p>
                            <code className="mt-3 block overflow-x-auto rounded-lg bg-black/5 px-3 py-2 text-[11px] dark:bg-white/[0.03]">
                                curl -fsSL https://kmjtechno.com/install | sudo
                                bash
                            </code>
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
                                    Fully quit and reopen ChatGPT Desktop. Enable
                                    or install KMJ CodeBridge if prompted.
                                </li>
                                <li className="flex gap-3">
                                    <StepNumber value="3" />
                                    Connect the existing KMJ CodeBridge app and
                                    complete the browser OAuth approval when
                                    requested.
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
