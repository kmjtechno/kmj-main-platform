import { Head, Link, router } from '@inertiajs/react';
import { useState } from 'react';
import {
    ArrowLeft,
    Cable,
    CheckCircle2,
    KeyRound,
    Laptop2,
    Link2,
    Search,
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

type RegisteredDevice = {
    id: string;
    name: string;
    platform: string | null;
    arch: string | null;
    projects: Array<{ id: string; name: string }>;
    registration: 'registered';
    connection_status: 'not_verified';
    registered_at?: string | null;
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
    devices: RegisteredDevice[];
    pending_pairings: number;
    connected_clients: ConnectedClient[];
    access_token_ttl_seconds: number;
};

type Props = {
    organization: Organization;
    entitlement: Entitlement;
    service: Service;
    canManageOwnerPlan: boolean;
};

const CHATGPT_DESKTOP_SETUP_URL = '/install-chatgpt-desktop.ps1';
const VSCODE_COPILOT_SETUP_URL =
    'https://raw.githubusercontent.com/kmjtechno/kmj-codebridge/dbac6b574500804fea9ff493f27b84f2a5d73efa/scripts/install-vscode-copilot.cmd';
const DESKTOP_INSTALL_DESCRIPTION =
    'Download the KMJ Desktop setup once. It adds the official KMJ marketplace; CodeBridge is installed by default and opens browser OAuth on first use.';
const CONNECTED_CLIENTS_DESCRIPTION =
    'Review authorized OAuth refresh grants. An authorization does not confirm a live IDE session; revoke unused clients at any time.';
const NO_CONNECTED_CLIENTS =
    'No unexpired CodeBridge OAuth refresh grants are registered for this account.';

// VS Code expects exactly one percent-encoded MCP server configuration in
// its registered URI handler; do not include tokens or the whole mcp.json.
function vscodeInstallUrl(endpoint: string, insiders = false): string {
    const scheme = insiders ? 'vscode-insiders' : 'vscode';
    const server = { name: 'kmj-codebridge', type: 'http', url: endpoint };
    return `${scheme}:mcp/install?${encodeURIComponent(JSON.stringify(server))}`;
}

export default function CodeBridgeService({
    organization,
    entitlement,
    service,
    canManageOwnerPlan,
}: Props) {
    const [deviceSearch, setDeviceSearch] = useState('');
    const [clientSearch, setClientSearch] = useState('');
    const [showAllClients, setShowAllClients] = useState(false);
    const [copyStatus, setCopyStatus] = useState('');
    const [revokingClient, setRevokingClient] = useState<string | null>(null);
    const filteredDevices = service.devices.filter((device) => {
        const text = [
            device.name,
            device.id,
            device.platform ?? '',
            ...device.projects.flatMap((project) => [project.name, project.id]),
        ]
            .join(' ')
            .toLocaleLowerCase();
        return text.includes(deviceSearch.trim().toLocaleLowerCase());
    });

    const matchingClients = service.connected_clients.filter((client) =>
        [client.client_name, client.client_id, ...client.scopes]
            .join(' ')
            .toLocaleLowerCase()
            .includes(clientSearch.trim().toLocaleLowerCase()),
    );
    const visibleClients =
        clientSearch.trim() || showAllClients
            ? matchingClients
            : matchingClients.slice(0, 5);

    const copyEndpoint = async () => {
        try {
            await navigator.clipboard.writeText(service.endpoint);
            setCopyStatus('MCP endpoint copied.');
        } catch {
            setCopyStatus('Copy unavailable. Select the endpoint above.');
        }
    };

    const revokeClient = (clientId: string, clientName: string) => {
        if (
            revokingClient !== null ||
            !window.confirm(
                `Revoke future CodeBridge refresh access for "${clientName}"? Existing access tokens can work until expiry.`,
            )
        ) {
            return;
        }
        setRevokingClient(clientId);
        router.post(
            `/services/kmj-codebridge/oauth-clients/${encodeURIComponent(clientId)}/revoke`,
            {},
            {
                preserveScroll: true,
                onFinish: () => setRevokingClient(null),
            },
        );
    };

    return (
        <>
            <Head title="KMJ CodeBridge" />

            <div className="flex h-full min-w-0 flex-1 flex-col gap-6 overflow-x-hidden p-4 sm:p-6">
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
                                href={vscodeInstallUrl(service.endpoint)}
                                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-black text-white transition hover:bg-red-500"
                            >
                                <Laptop2 className="h-3.5 w-3.5" />
                                Open in VS Code / Copilot
                            </a>
                            <a
                                href={CHATGPT_DESKTOP_SETUP_URL}
                                download
                                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-black text-white transition hover:bg-red-500"
                            >
                                <Link2 className="h-3.5 w-3.5" />
                                Set up ChatGPT Desktop
                            </a>
                            <Link
                                href="/codebridge/pair"
                                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-bold transition hover:border-red-500/40 hover:text-red-500"
                            >
                                <Laptop2 className="h-3.5 w-3.5" />
                                Approve pairing
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
                        hint="OAuth authorization configuration"
                    />
                    <Metric
                        label="Registered devices"
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

                        <div className="mt-5 rounded-xl border p-4">
                            <div className="flex items-center gap-2 text-xs font-black">
                                <TerminalSquare className="h-3.5 w-3.5 text-red-500" />
                                Install on Linux / VPS
                            </div>
                            <p className="text-muted-foreground mt-2 text-[11px] leading-5">
                                Download and inspect the pinned bootstrap first,
                                then run the saved script in its folder. Pairing
                                still requires browser approval; no agent token
                                is entered manually.
                            </p>
                            <a
                                href="/install"
                                download="KMJ-CodeBridge-VPS.sh"
                                className="mt-4 inline-flex h-9 items-center rounded-xl border border-red-500/30 px-3 text-xs font-bold text-red-500"
                            >
                                Download Linux / VPS bootstrap
                            </a>
                            <code className="mt-3 block overflow-x-auto rounded-lg bg-black/5 px-3 py-2 text-[11px] dark:bg-white/[0.03]">
                                sudo bash KMJ-CodeBridge-VPS.sh
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
                                {service.permissions.length === 0 && (
                                    <span className="text-muted-foreground text-[11px]">
                                        No permissions reported. Ask an
                                        administrator to verify your grant.
                                    </span>
                                )}
                                {service.permissions.map((permission) => (
                                    <span
                                        key={permission}
                                        className="rounded-lg border px-2.5 py-1 text-[10px] font-bold uppercase"
                                    >
                                        {permission}
                                    </span>
                                ))}
                            </div>
                        </div>

                        {canManageOwnerPlan && service.plan !== 'owner' && (
                            <Link
                                href="/operator/codebridge/owner-plan"
                                className="mt-5 inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-red-500/30 px-4 text-xs font-bold text-red-500 transition hover:border-red-500"
                            >
                                <ShieldCheck className="h-3.5 w-3.5" />
                                Manage internal Owner Plan
                            </Link>
                        )}

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
                    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                        <div>
                            <h2 className="font-black">
                                Your devices & projects
                            </h2>
                            <p className="text-muted-foreground mt-1 text-xs leading-5">
                                Main Platform handles registration and access.
                                For actual online/offline health, run
                                connection_overview from an authorized
                                CodeBridge client. No repeated GitHub or ChatGPT
                                OAuth login is required.
                            </p>
                            <a
                                href="https://github.com/kmjtechno/kmj-codebridge/blob/main/docs/CONNECTION-DOCTOR.md"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="mt-2 inline-flex min-h-9 items-center text-xs font-bold text-red-500 underline underline-offset-4"
                            >
                                Open Connection Doctor guide
                            </a>
                        </div>
                        <button
                            type="button"
                            onClick={() => router.reload({ only: ['service'] })}
                            className="inline-flex min-h-10 items-center justify-center rounded-xl border px-3 text-[11px] font-bold transition hover:border-red-500/40"
                        >
                            Refresh registered devices
                        </button>
                    </div>

                    <div className="mt-4 grid gap-3 rounded-xl border bg-black/[0.02] p-4 sm:grid-cols-[1fr_auto] sm:items-center dark:bg-white/[0.02]">
                        <div>
                            <p className="text-sm font-bold">
                                {service.managed_devices} registered device
                                {service.managed_devices === 1 ? '' : 's'}
                            </p>
                            <p className="text-muted-foreground mt-1 text-xs leading-5">
                                Registration is verified by Main Platform. Live
                                connectivity requires a gateway heartbeat and is
                                not available in this view.
                            </p>
                        </div>
                        <span className="inline-flex w-fit rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-1.5 text-xs font-semibold text-amber-600 dark:text-amber-400">
                            Online status: Not verified
                        </span>
                    </div>

                    {service.devices.length > 0 && (
                        <label className="relative mt-4 block">
                            <span className="sr-only">
                                Search registered devices and projects
                            </span>
                            <Search className="text-muted-foreground pointer-events-none absolute top-3 left-3 h-4 w-4" />
                            <input
                                type="search"
                                value={deviceSearch}
                                onChange={(event) =>
                                    setDeviceSearch(event.target.value)
                                }
                                placeholder="Search device, platform or project"
                                className="bg-background min-h-10 w-full rounded-xl border pr-4 pl-10 text-sm outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                            />
                        </label>
                    )}

                    {service.devices.length === 0 ? (
                        <div className="mt-5 rounded-xl border border-dashed p-5">
                            <div className="text-sm font-bold">
                                No devices paired yet
                            </div>
                            <p className="text-muted-foreground mt-2 text-xs leading-5">
                                Install the CodeBridge device agent, then
                                approve the short-lived pairing code using your
                                KMJ account. No GitHub OAuth or manual device
                                token is needed.
                            </p>
                            <Link
                                href="/codebridge/pair"
                                className="mt-4 inline-flex h-9 items-center rounded-xl border border-red-500/30 px-3 text-xs font-bold text-red-500"
                            >
                                Approve a pairing code
                            </Link>
                        </div>
                    ) : (
                        <div className="mt-4 grid gap-3 md:grid-cols-2">
                            {filteredDevices.map((device) => (
                                <div
                                    key={device.id}
                                    className="min-w-0 rounded-xl border p-4"
                                >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <div className="min-w-0">
                                            <div className="truncate text-sm font-bold">
                                                {device.name}
                                            </div>
                                            <div className="text-muted-foreground mt-1 truncate text-[11px]">
                                                {device.id}
                                            </div>
                                        </div>
                                        <span className="rounded-lg border px-2 py-1 text-[10px] font-semibold">
                                            Registered · Live status unknown
                                        </span>
                                    </div>
                                    <div className="text-muted-foreground mt-3 text-xs">
                                        {[device.platform, device.arch]
                                            .filter(Boolean)
                                            .join(' / ') ||
                                            'Device type not reported'}
                                    </div>
                                    <div className="mt-3 text-xs font-semibold">
                                        {device.projects.length
                                            ? 'Authorized projects'
                                            : 'No project grant reported'}
                                    </div>
                                    {device.projects.map((project) => (
                                        <div
                                            key={project.id}
                                            className="mt-2 rounded-lg border bg-black/5 px-3 py-2 text-xs dark:bg-white/[0.03]"
                                        >
                                            {project.name}
                                            <span className="text-muted-foreground ml-2">
                                                {project.id}
                                            </span>
                                        </div>
                                    ))}
                                    <p className="text-muted-foreground mt-3 text-[11px] leading-5">
                                        {device.registered_at
                                            ? `Registered ${formatDateTime(device.registered_at)}. `
                                            : ''}
                                        Live connection has not been verified.
                                        Use connection_overview in the
                                        authorized CodeBridge client to check
                                        agent health.
                                    </p>
                                </div>
                            ))}
                        </div>
                    )}
                    {service.devices.length > 0 &&
                        filteredDevices.length === 0 && (
                            <p className="text-muted-foreground mt-3 text-xs">
                                No registered device or project matches your
                                search.
                            </p>
                        )}
                    {service.managed_devices > service.devices.length && (
                        <p className="text-muted-foreground mt-3 text-xs">
                            Showing the first {service.devices.length}{' '}
                            registered devices. The list is intentionally
                            bounded.
                        </p>
                    )}
                </section>

                <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                    <h2 className="font-black">Connect your AI workspace</h2>
                    <p className="text-muted-foreground mt-1 text-xs leading-5">
                        Connect the same authorized projects to ChatGPT, VS Code
                        / GitHub Copilot, Claude, Cursor or another
                        OAuth-capable MCP client. You do not need a GitHub
                        account for CodeBridge authorization.
                    </p>
                    <div className="mt-4 flex flex-wrap gap-3">
                        <a
                            href={vscodeInstallUrl(service.endpoint)}
                            className="inline-flex h-10 items-center rounded-xl bg-red-600 px-4 text-xs font-bold text-white hover:bg-red-500"
                        >
                            One-click VS Code / Copilot
                        </a>
                        <a
                            href={vscodeInstallUrl(service.endpoint, true)}
                            className="inline-flex h-10 items-center rounded-xl border px-4 text-xs font-bold"
                        >
                            VS Code Insiders
                        </a>
                        <a
                            href={VSCODE_COPILOT_SETUP_URL}
                            className="inline-flex h-10 items-center rounded-xl border px-4 text-xs font-bold"
                        >
                            Windows setup fallback
                        </a>
                        <a
                            href={CHATGPT_DESKTOP_SETUP_URL}
                            download
                            className="inline-flex h-10 items-center rounded-xl border px-4 text-xs font-bold"
                        >
                            Install ChatGPT Desktop
                        </a>
                        <button
                            type="button"
                            onClick={() => {
                                void copyEndpoint();
                            }}
                            className="inline-flex h-10 items-center rounded-xl border px-4 text-xs font-bold"
                        >
                            Copy MCP endpoint for other IDEs
                        </button>
                    </div>
                    {copyStatus && (
                        <p
                            role="status"
                            className="text-muted-foreground mt-2 text-xs"
                        >
                            {copyStatus}
                        </p>
                    )}
                    <p className="text-muted-foreground mt-3 text-[11px]">
                        VS Code opens a confirmation dialog before adding the
                        MCP server. Complete KMJ browser OAuth when prompted. If
                        your system does not handle VS Code install links, use
                        the Windows fallback or copy the MCP endpoint. No GitHub
                        login is required for device authorization.
                    </p>
                </section>

                <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                        <div>
                            <h2 className="font-black">
                                Authorized AI clients
                            </h2>
                            <p className="text-muted-foreground mt-1 text-xs leading-5">
                                {CONNECTED_CLIENTS_DESCRIPTION}
                            </p>
                        </div>
                        <span className="rounded-full border px-3 py-1 text-[10px] font-bold">
                            {service.connected_clients.length} authorized
                        </span>
                    </div>

                    {service.connected_clients.length > 0 && (
                        <label className="relative mt-4 block">
                            <span className="sr-only">
                                Search authorized AI clients
                            </span>
                            <Search className="text-muted-foreground pointer-events-none absolute top-3 left-3 h-4 w-4" />
                            <input
                                type="search"
                                value={clientSearch}
                                onChange={(event) =>
                                    setClientSearch(event.target.value)
                                }
                                placeholder="Search client name or scope"
                                className="bg-background min-h-10 w-full rounded-xl border pr-4 pl-10 text-sm outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                            />
                        </label>
                    )}

                    {service.connected_clients.length === 0 ? (
                        <div className="text-muted-foreground mt-5 rounded-xl border border-dashed p-5 text-xs">
                            {NO_CONNECTED_CLIENTS}
                        </div>
                    ) : (
                        <div className="mt-5 grid gap-3">
                            {visibleClients.map((client) => (
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
                                        <div className="text-muted-foreground mt-1 font-mono text-[10px]">
                                            Client ID · …
                                            {client.client_id.slice(-10)}
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
                                        aria-label={`Revoke ${client.client_name}, client ending ${client.client_id.slice(-10)}`}
                                        onClick={() =>
                                            revokeClient(
                                                client.client_id,
                                                client.client_name,
                                            )
                                        }
                                        disabled={revokingClient !== null}
                                        className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-xl border border-red-500/30 px-3 text-[11px] font-black text-red-500 transition hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                        {revokingClient === client.client_id
                                            ? 'Revoking...'
                                            : 'Revoke access'}
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    {service.connected_clients.length > 0 &&
                        matchingClients.length === 0 && (
                            <p className="text-muted-foreground mt-3 text-xs">
                                No authorized AI client matches your search.
                            </p>
                        )}
                    {!clientSearch.trim() && matchingClients.length > 5 && (
                        <button
                            type="button"
                            onClick={() =>
                                setShowAllClients((current) => !current)
                            }
                            className="mt-3 min-h-10 rounded-xl border px-4 text-xs font-bold hover:border-red-500/40"
                        >
                            {showAllClients
                                ? 'Show fewer clients'
                                : `Show all ${matchingClients.length} clients`}
                        </button>
                    )}
                    <p className="text-muted-foreground mt-4 text-[10px] leading-4">
                        Revoking stops future OAuth refresh grants. Existing
                        access tokens may remain valid for up to{' '}
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
            ? '1 authorized refresh session'
            : `${client.sessions} authorized refresh sessions`;

    return `${sessions} · Last token activity ${formatDateTime(client.last_active_at)}`;
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
