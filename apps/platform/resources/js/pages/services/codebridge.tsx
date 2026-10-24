import { Head, Link, router } from '@inertiajs/react';
import { useState } from 'react';
import CodeBridgeControlCenterHub, {
    type CodeBridgeSection,
} from '@/components/codebridge/control-center-hub';
import DeviceControlCenter, {
    type CodeBridgeDevice,
} from '@/components/codebridge/device-control-center';
import {
    ArrowLeft,
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

type RegisteredDevice = CodeBridgeDevice;

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
    canManageDevices: boolean;
};

const CHATGPT_DESKTOP_SETUP_URL = '/install-chatgpt-desktop.ps1';
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
    canManageDevices,
}: Props) {
    const [activeSection, setActiveSection] =
        useState<CodeBridgeSection>('overview');
    const [clientSearch, setClientSearch] = useState('');
    const [showAllClients, setShowAllClients] = useState(false);
    const [copyStatus, setCopyStatus] = useState('');
    const [revokingClient, setRevokingClient] = useState<string | null>(null);

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
                                <img
                                    src="/assets/kmj-codebridge-icon.png"
                                    alt="Official KMJ CodeBridge icon"
                                    width={40}
                                    height={40}
                                    className="h-10 w-10 object-contain"
                                />
                            </span>
                            <div>
                                <div className="flex flex-wrap items-center gap-2">
                                    <h1 className="text-3xl font-black tracking-tight">
                                        KMJ CodeBridge
                                    </h1>
                                    <span className="rounded-full border border-emerald-500/15 bg-emerald-500/5 px-2 py-1 text-xs font-black text-emerald-600 uppercase dark:text-emerald-400">
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
                                href="/install-codebridge-windows.cmd"
                                download="KMJ-CodeBridge-Connect-Windows.cmd"
                                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-black text-white transition hover:bg-red-500"
                            >
                                <Laptop2 className="h-3.5 w-3.5" />
                                Connect Windows PC
                            </a>
                            <button
                                type="button"
                                onClick={() => setActiveSection('devices')}
                                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-bold transition hover:border-red-500/40 hover:text-red-500"
                            >
                                <Laptop2 className="h-3.5 w-3.5" />
                                Manage devices
                            </button>
                            <Link
                                href="/services/kmj-codebridge/ai-providers"
                                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-bold transition hover:border-red-500/40 hover:text-red-500"
                            >
                                <KeyRound className="h-3.5 w-3.5" />
                                AI Providers
                            </Link>
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

                <CodeBridgeControlCenterHub
                    organizationName={organization.name}
                    plan={service.plan}
                    licenseStatus={service.license_status}
                    licenseExpiresAt={service.license_expires_at}
                    managedDevices={service.managed_devices}
                    deviceLimit={service.device_limit}
                    pendingPairings={service.pending_pairings}
                    authorizedClientGrants={service.connected_clients.length}
                    oauthReady={service.oauth_ready}
                    canManageOwnerPlan={canManageOwnerPlan}
                    activeSection={activeSection}
                    onSectionChange={setActiveSection}
                >
                    {activeSection === 'overview' && (
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
                                value={
                                    service.oauth_ready
                                        ? 'Ready'
                                        : 'Unavailable'
                                }
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
                    )}

                    {activeSection === 'setup' && (
                        <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
                            <div className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                                <div className="flex items-center gap-2">
                                    <Server className="h-5 w-5 text-red-500" />
                                    <h2 className="font-black">Connection</h2>
                                </div>
                                <p className="text-muted-foreground mt-1 text-xs">
                                    Use this endpoint when connecting KMJ
                                    CodeBridge as an MCP service.
                                </p>

                                <div className="mt-5 rounded-xl border bg-black/5 p-4 dark:bg-white/[0.02]">
                                    <div className="text-muted-foreground text-xs font-bold tracking-wider uppercase">
                                        MCP endpoint
                                    </div>
                                    <code className="mt-2 block overflow-x-auto rounded-lg bg-black/5 px-3 py-2 text-xs dark:bg-white/[0.03]">
                                        {service.endpoint}
                                    </code>
                                    <div className="mt-3 inline-flex items-center gap-1.5 text-xs font-bold text-emerald-600 dark:text-emerald-400">
                                        <CheckCircle2 className="h-3.5 w-3.5" />
                                        Protected by OAuth 2.1 + PKCE
                                    </div>
                                </div>

                                <div className="mt-5 rounded-xl border border-red-500/20 bg-red-500/[0.03] p-4">
                                    <div className="flex flex-wrap items-center justify-between gap-3">
                                        <div>
                                            <div className="flex items-center gap-2 text-xs font-black">
                                                <Laptop2 className="h-3.5 w-3.5 text-red-500" />
                                                Windows PC / workstation
                                            </div>
                                            <p className="text-muted-foreground mt-2 text-xs leading-5">
                                                Download from this dashboard,
                                                then double-click on that PC.
                                                Already enrolled? Choose YES to
                                                reuse its private config. First
                                                connection? Choose NO and
                                                approve in your KMJ account. Git
                                                and Node.js 24 are required;
                                                missing prerequisites are
                                                reported safely, never installed
                                                without your approval.
                                            </p>
                                        </div>
                                        <a
                                            href="/install-codebridge-windows.cmd"
                                            download="KMJ-CodeBridge-Connect-Windows.cmd"
                                            className="inline-flex h-10 shrink-0 items-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-black text-white hover:bg-red-500"
                                        >
                                            <Laptop2 className="h-3.5 w-3.5" />
                                            Download Windows connector
                                        </a>
                                    </div>
                                </div>

                                <div className="mt-5 rounded-xl border border-red-500/20 bg-red-500/[0.03] p-4">
                                    <div className="flex items-center justify-between gap-3">
                                        <div>
                                            <div className="flex items-center gap-2 text-xs font-black">
                                                <Laptop2 className="h-3.5 w-3.5 text-red-500" />
                                                ChatGPT Desktop
                                            </div>
                                            <p className="text-muted-foreground mt-2 text-xs leading-5">
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
                                    <p className="text-muted-foreground mt-2 text-xs leading-5">
                                        Download and inspect the pinned
                                        bootstrap first, then run the saved
                                        script in its folder. Pairing still
                                        requires browser approval; no agent
                                        token is entered manually.
                                    </p>
                                    <a
                                        href="/install"
                                        download="KMJ-CodeBridge-VPS.sh"
                                        className="mt-4 inline-flex h-9 items-center rounded-xl border border-red-500/30 px-3 text-xs font-bold text-red-500"
                                    >
                                        Download Linux / VPS bootstrap
                                    </a>
                                    <code className="mt-3 block overflow-x-auto rounded-lg bg-black/5 px-3 py-2 text-xs dark:bg-white/[0.03]">
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
                                            Download and run the KMJ ChatGPT
                                            Desktop setup once.
                                        </li>
                                        <li className="flex gap-3">
                                            <StepNumber value="2" />
                                            Fully quit and reopen ChatGPT
                                            Desktop. KMJ CodeBridge is installed
                                            by default.
                                        </li>
                                        <li className="flex gap-3">
                                            <StepNumber value="3" />
                                            Use CodeBridge. Its local bridge
                                            opens KMJ browser OAuth
                                            automatically on first use.
                                        </li>
                                    </ol>
                                </div>
                            </div>

                            <div className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                                <div className="flex items-center gap-2">
                                    <ShieldCheck className="h-5 w-5 text-red-500" />
                                    <h2 className="font-black">
                                        Access & security
                                    </h2>
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
                                            service.plan
                                                ? titleCase(service.plan)
                                                : '—'
                                        }
                                    />
                                    <InfoRow
                                        label="Started"
                                        value={formatDate(
                                            service.license_starts_at,
                                        )}
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
                                            <span className="text-muted-foreground text-xs">
                                                No permissions reported. Ask an
                                                administrator to verify your
                                                grant.
                                            </span>
                                        )}
                                        {service.permissions.map(
                                            (permission) => (
                                                <span
                                                    key={permission}
                                                    className="rounded-lg border px-2.5 py-1 text-xs font-bold uppercase"
                                                >
                                                    {permission}
                                                </span>
                                            ),
                                        )}
                                    </div>
                                </div>

                                {canManageOwnerPlan &&
                                    service.plan !== 'owner' && (
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
                    )}

                    {activeSection === 'devices' && (
                        <DeviceControlCenter
                            tenantId={organization.id}
                            devices={service.devices}
                            managedCount={service.managed_devices}
                            deviceLimit={service.device_limit}
                            canManage={canManageDevices}
                            endpoint={service.endpoint}
                        />
                    )}

                    {activeSection === 'setup' && (
                        <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                            <h2 className="font-black">
                                Connect your AI workspace
                            </h2>
                            <p className="text-muted-foreground mt-1 text-xs leading-5">
                                Connect the same authorized projects to ChatGPT,
                                VS Code / GitHub Copilot, Claude, Cursor or
                                another OAuth-capable MCP client. You do not
                                need a GitHub account for CodeBridge
                                authorization.
                            </p>
                            <div className="mt-4 flex flex-wrap gap-3">
                                <a
                                    href={vscodeInstallUrl(service.endpoint)}
                                    className="inline-flex h-10 items-center rounded-xl bg-red-600 px-4 text-xs font-bold text-white hover:bg-red-500"
                                >
                                    One-click VS Code / Copilot
                                </a>
                                <a
                                    href={vscodeInstallUrl(
                                        service.endpoint,
                                        true,
                                    )}
                                    className="inline-flex h-10 items-center rounded-xl border px-4 text-xs font-bold"
                                >
                                    VS Code Insiders
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
                            <div className="mt-5 grid gap-3 lg:grid-cols-2">
                                <div className="rounded-xl border p-4">
                                    <h3 className="text-xs font-black">
                                        Claude Desktop / Claude web
                                    </h3>
                                    <p className="text-muted-foreground mt-2 text-xs leading-5">
                                        Open Claude Settings, then Connectors
                                        and Add custom connector. Use this
                                        hosted Streamable HTTP MCP URL and
                                        complete KMJ browser OAuth. Do not paste
                                        device tokens.
                                    </p>
                                    <code className="mt-3 block rounded-lg border px-3 py-2 text-xs break-all">
                                        {service.endpoint}
                                    </code>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            void copyEndpoint();
                                        }}
                                        className="mt-3 min-h-10 rounded-lg border px-3 py-2 text-xs font-bold"
                                    >
                                        Copy Claude MCP URL
                                    </button>
                                    <p className="text-muted-foreground mt-2 text-xs leading-5">
                                        For third-party inference Gateway mode
                                        in Claude Desktop, use Inference
                                        configuration, Connectors, Managed MCP
                                        servers, Add server, Streamable HTTP and
                                        OAuth auto-registration instead.
                                    </p>
                                </div>
                                <div className="rounded-xl border p-4">
                                    <h3 className="text-xs font-black">
                                        Multiple AI chats / automatic updates
                                    </h3>
                                    <p className="text-muted-foreground mt-2 text-xs leading-5">
                                        Multiple ChatGPT, Claude and IDE
                                        sessions can use the same authorized
                                        gateway. New CodeBridge work lanes
                                        protect reserved files from overlapping
                                        CodeBridge edits after the compatible
                                        gateway and device agent are deployed.
                                        Actual execution concurrency remains
                                        plan and hardware limited.
                                    </p>
                                    <p className="text-muted-foreground mt-3 text-xs leading-5">
                                        Verified hosted MCP updates are served
                                        centrally. Your AI desktop app may need
                                        to reconnect to refresh tools;
                                        third-party app binaries and marketplace
                                        icons cannot be silently updated by
                                        CodeBridge.
                                    </p>
                                </div>
                            </div>
                            <p className="text-muted-foreground mt-3 text-xs">
                                VS Code opens a confirmation dialog before
                                adding the MCP server. Complete KMJ browser
                                OAuth when prompted. If your system does not
                                handle VS Code install links, use the Windows
                                fallback or copy the MCP endpoint. No GitHub
                                login is required for device authorization.
                            </p>
                        </section>
                    )}

                    {activeSection === 'clients' && (
                        <section
                            id="codebridge-clients"
                            className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6"
                        >
                            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                                <div>
                                    <h2 className="font-black">
                                        Authorized AI clients
                                    </h2>
                                    <p className="text-muted-foreground mt-1 text-xs leading-5">
                                        {CONNECTED_CLIENTS_DESCRIPTION}
                                    </p>
                                </div>
                                <span className="rounded-full border px-3 py-1 text-xs font-bold">
                                    {service.connected_clients.length}{' '}
                                    authorized
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
                                                <div className="text-muted-foreground mt-1 text-xs">
                                                    {clientSummary(client)}
                                                </div>
                                                <div className="text-muted-foreground mt-1 font-mono text-xs">
                                                    Client ID · …
                                                    {client.client_id.slice(
                                                        -10,
                                                    )}
                                                </div>
                                                <div className="mt-2 flex flex-wrap gap-2">
                                                    {client.scopes.map(
                                                        (scope) => (
                                                            <span
                                                                key={scope}
                                                                className="rounded-lg border px-2 py-1 text-xs font-bold"
                                                            >
                                                                {scope}
                                                            </span>
                                                        ),
                                                    )}
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
                                                disabled={
                                                    revokingClient !== null
                                                }
                                                className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-xl border border-red-500/30 px-3 text-xs font-black text-red-500 transition hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-50"
                                            >
                                                {revokingClient ===
                                                client.client_id
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
                                        No authorized AI client matches your
                                        search.
                                    </p>
                                )}
                            {!clientSearch.trim() &&
                                matchingClients.length > 5 && (
                                    <button
                                        type="button"
                                        onClick={() =>
                                            setShowAllClients(
                                                (current) => !current,
                                            )
                                        }
                                        className="mt-3 min-h-10 rounded-xl border px-4 text-xs font-bold hover:border-red-500/40"
                                    >
                                        {showAllClients
                                            ? 'Show fewer clients'
                                            : `Show all ${matchingClients.length} clients`}
                                    </button>
                                )}
                            <p className="text-muted-foreground mt-4 text-xs leading-4">
                                Revoking stops future OAuth refresh grants.
                                Existing access tokens may remain valid for up
                                to{' '}
                                {Math.max(
                                    1,
                                    Math.ceil(
                                        service.access_token_ttl_seconds / 60,
                                    ),
                                )}{' '}
                                minutes.
                            </p>
                        </section>
                    )}

                    {activeSection === 'overview' && (
                        <section className="border-sidebar-border/70 bg-card dark:border-sidebar-border rounded-2xl border p-5 sm:p-6">
                            <div>
                                <h2 className="font-black">
                                    What CodeBridge can do
                                </h2>
                                <p className="text-muted-foreground mt-1 text-xs">
                                    Capabilities remain scoped to authorized
                                    projects and administrator-approved
                                    operations.
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
                    )}
                </CodeBridgeControlCenterHub>
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
            <div className="text-muted-foreground text-xs font-bold tracking-wider uppercase">
                {label}
            </div>
            <div className="mt-1 text-lg font-black">{value}</div>
            <div className="text-muted-foreground mt-1 text-xs">{hint}</div>
        </div>
    );
}

function InfoRow({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex items-start justify-between gap-4 rounded-xl border px-3 py-2.5">
            <span className="text-muted-foreground text-xs">{label}</span>
            <span className="max-w-[65%] text-right text-xs font-bold">
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
            <p className="text-muted-foreground mt-1 text-xs leading-5">
                {text}
            </p>
        </div>
    );
}

function StepNumber({ value }: { value: string }) {
    return (
        <span className="bg-muted text-foreground grid h-6 w-6 shrink-0 place-items-center rounded-lg text-xs font-black">
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
