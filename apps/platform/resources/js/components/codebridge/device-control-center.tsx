import { Link, router } from '@inertiajs/react';
import {
    ArrowRight,
    Cable,
    CheckCircle2,
    Clipboard,
    FolderPlus,
    HardDrive,
    Laptop2,
    LockKeyhole,
    MonitorSmartphone,
    RefreshCw,
    Search,
    ShieldAlert,
    ShieldCheck,
    Unplug,
} from 'lucide-react';
import { useMemo, useState } from 'react';

export type CodeBridgeDevice = {
    id: string;
    name: string;
    platform: string | null;
    arch: string | null;
    projects: Array<{ id: string; name: string }>;
    registration: 'registered';
    connection_status: 'not_verified';
    registered_at?: string | null;
};

type Props = {
    tenantId: string;
    devices: CodeBridgeDevice[];
    managedCount: number;
    deviceLimit: number | null;
    canManage: boolean;
    endpoint: string;
};

type View = 'all' | 'with-projects' | 'needs-projects';

export default function DeviceControlCenter({
    tenantId,
    devices,
    managedCount,
    deviceLimit,
    canManage,
    endpoint,
}: Props) {
    const [search, setSearch] = useState('');
    const [showProjectSetup, setShowProjectSetup] = useState(false);
    const [view, setView] = useState<View>('all');
    const [details, setDetails] = useState<string | null>(null);
    const [confirmId, setConfirmId] = useState<string | null>(null);
    const [confirmation, setConfirmation] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [feedback, setFeedback] = useState('');

    const visibleDevices = useMemo(() => {
        const query = search.trim().toLowerCase();
        return devices.filter((device) => {
            if (view === 'with-projects' && device.projects.length === 0)
                return false;
            if (view === 'needs-projects' && device.projects.length > 0)
                return false;
            return (
                query === '' ||
                [
                    device.name,
                    device.id,
                    device.platform ?? '',
                    device.arch ?? '',
                ].some((value) => value.toLowerCase().includes(query)) ||
                device.projects.some((project) =>
                    [project.id, project.name].some((value) =>
                        value.toLowerCase().includes(query),
                    ),
                )
            );
        });
    }, [devices, search, view]);

    const startDisconnect = (device: CodeBridgeDevice) => {
        if (!canManage) return;
        setDetails(device.id);
        setConfirmId(device.id);
        setConfirmation('');
        setFeedback('');
    };

    const cancelDisconnect = () => {
        if (submitting) return;
        setConfirmId(null);
        setConfirmation('');
    };

    const disconnect = (device: CodeBridgeDevice) => {
        if (
            !canManage ||
            submitting ||
            confirmId !== device.id ||
            confirmation !== device.id
        )
            return;
        setSubmitting(true);
        router.post(
            `/services/kmj-codebridge/organizations/${encodeURIComponent(tenantId)}/devices/${encodeURIComponent(device.id)}/disconnect`,
            { confirm_device_id: confirmation },
            {
                preserveScroll: true,
                onSuccess: () => {
                    setConfirmId(null);
                    setConfirmation('');
                    setFeedback(
                        'Authorization revoked. A new pairing code is required to reconnect.',
                    );
                },
                onError: () =>
                    setFeedback(
                        'Disconnect was not completed. Check your account confirmation and retry.',
                    ),
                onFinish: () => setSubmitting(false),
            },
        );
    };

    const copy = async (value: string, label: string) => {
        try {
            await navigator.clipboard.writeText(value);
            setFeedback(`${label} copied.`);
        } catch {
            setFeedback('Copy unavailable. Select the visible value manually.');
        }
    };

    return (
        <section
            id="codebridge-device-control"
            aria-labelledby="codebridge-control-title"
            className="border-sidebar-border/70 bg-card rounded-2xl border p-5 sm:p-6"
        >
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <div className="flex items-center gap-2">
                        <MonitorSmartphone className="h-5 w-5 text-red-500" />
                        <h2
                            id="codebridge-control-title"
                            className="text-lg font-black"
                        >
                            Device Control Center
                        </h2>
                    </div>
                    <p className="text-muted-foreground mt-2 max-w-2xl text-xs leading-5">
                        Pair computers and VPSs, review approved projects and
                        disconnect credentials. Registered devices are not
                        necessarily online: Main Platform does not receive live
                        gateway heartbeats.
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
                <div className="flex flex-wrap gap-2">
                    <button
                        type="button"
                        onClick={() => router.reload({ only: ['service'] })}
                        className="inline-flex h-10 items-center gap-2 rounded-xl border px-3 text-xs font-bold hover:border-red-500/40"
                    >
                        <RefreshCw className="h-4 w-4" /> Refresh
                    </button>
                    {canManage && (
                        <button
                            type="button"
                            aria-expanded={showProjectSetup}
                            aria-controls="codebridge-add-project"
                            onClick={() => setShowProjectSetup((current) => !current)}
                            className="inline-flex h-10 items-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-black text-white hover:bg-red-500"
                        >
                            <FolderPlus className="h-4 w-4" /> Add project
                        </button>
                    )}
                    <Link
                        href="/codebridge/pair"
                        className="inline-flex h-10 items-center gap-2 rounded-xl border px-4 text-xs font-black hover:border-red-500/40"
                    >
                        <Cable className="h-4 w-4" /> Connect device
                    </Link>
                </div>
            </div>

            {canManage && showProjectSetup && (
                <section
                    id="codebridge-add-project"
                    aria-label="Add a CodeBridge project"
                    className="mt-5 space-y-4 rounded-xl border border-red-500/25 p-4"
                >
                    <div>
                        <h3 className="text-sm font-black">
                            Add project — KMJ OmniDesk first
                        </h3>
                        <p className="text-muted-foreground mt-2 text-xs leading-5">
                            Target repository: kmjtechno/kmj-omnidesk · Host:
                            Lenovo P720 Windows. The current free agent is
                            single-project, so setup uses a separate device
                            identity. It never replaces CodeBridge or CineCore.
                        </p>
                    </div>
                    {devices.some((device) =>
                        device.projects.some(
                            (project) => project.id === 'kmj-omnidesk',
                        ),
                    ) ? (
                        <p role="status" className="text-xs font-bold text-emerald-600">
                            OmniDesk grant is registered. Live agent status
                            still requires a verified CodeBridge gateway check.
                        </p>
                    ) : (
                        <p role="status" className="text-xs font-semibold text-amber-600">
                            OmniDesk is not registered in this account yet.
                            Download the scoped installer, run it once on the
                            P720, and approve the short-lived KMJ pairing.
                        </p>
                    )}
                    <div className="flex flex-wrap gap-2">
                        <a
                            href="https://raw.githubusercontent.com/kmjtechno/kmj-codebridge/main/scripts/enroll-p720-omnidesk.ps1"
                            download="KMJ-CodeBridge-Add-OmniDesk.ps1"
                            rel="noopener noreferrer"
                            className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-black text-white hover:bg-red-500"
                        >
                            <FolderPlus className="h-4 w-4" /> Download OmniDesk setup
                        </a>
                        <Link
                            href="/codebridge/pair"
                            className="inline-flex min-h-10 items-center gap-2 rounded-xl border px-4 text-xs font-bold"
                        >
                            Approve project pairing
                        </Link>
                        <button
                            type="button"
                            onClick={() => router.reload({ only: ['service'] })}
                            className="inline-flex min-h-10 items-center gap-2 rounded-xl border px-4 text-xs font-bold"
                        >
                            <RefreshCw className="h-4 w-4" /> Check registration
                        </button>
                    </div>
                    <p className="text-muted-foreground text-xs leading-5">
                        A browser cannot install software silently. Pairing
                        requires the device owner's consent. Project status
                        changes only after a real enrollment, never when the
                        installer is merely downloaded. More repository presets
                        need separate scoped installers or signed host grants.
                    </p>
                </section>
            )}

            <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <Stat
                    label="Authorized devices"
                    value={managedCount}
                    hint={
                        deviceLimit !== null
                            ? `Plan limit: ${deviceLimit}`
                            : 'Plan limit not reported'
                    }
                />
                <Stat
                    label="Known project grants"
                    value={devices.reduce(
                        (count, device) => count + device.projects.length,
                        0,
                    )}
                    hint="From saved pairing records"
                />
                <Stat
                    label="Live status"
                    value="Not verified"
                    hint="Use gateway connection overview"
                />
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border bg-black/[0.02] px-4 py-3 dark:bg-white/[0.02]">
                <p className="text-muted-foreground text-xs leading-5">
                    Registration is verified by Main Platform. Live connectivity
                    requires an authenticated gateway heartbeat and is not
                    available in this view.
                </p>
                <span className="inline-flex w-fit rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-1.5 text-xs font-semibold text-amber-600 dark:text-amber-400">
                    Online status: Not verified
                </span>
            </div>

            <div className="mt-5 flex flex-col gap-3 sm:flex-row">
                <label className="relative flex-1">
                    <Search className="text-muted-foreground pointer-events-none absolute top-3.5 left-3 h-4 w-4" />
                    <span className="sr-only">Search devices and projects</span>
                    <input
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                        maxLength={120}
                        placeholder="Search device, OS, project or ID"
                        className="bg-background h-11 w-full rounded-xl border py-2 pr-3 pl-10 text-sm outline-none focus:border-red-500/60"
                    />
                </label>
                <label>
                    <span className="sr-only">Filter devices</span>
                    <select
                        value={view}
                        onChange={(event) =>
                            setView(event.target.value as View)
                        }
                        className="bg-background h-11 w-full rounded-xl border px-3 text-xs font-bold sm:w-48"
                    >
                        <option value="all">All registered</option>
                        <option value="with-projects">With projects</option>
                        <option value="needs-projects">
                            Needs project grant
                        </option>
                    </select>
                </label>
            </div>

            {feedback && (
                <p
                    role="status"
                    className="mt-3 rounded-xl border px-3 py-2 text-xs"
                >
                    {feedback}
                </p>
            )}

            {devices.length === 0 ? (
                <div className="mt-5 rounded-xl border border-dashed p-6">
                    <div className="flex items-center gap-2 text-sm font-black">
                        <Laptop2 className="h-4 w-4 text-red-500" /> No device
                        registered yet
                    </div>
                    <p className="text-muted-foreground mt-2 text-xs leading-5">
                        Install the CodeBridge agent on your computer or VPS,
                        then approve its short-lived code with your KMJ account.
                        No device password, GitHub login or token paste is
                        needed.
                    </p>
                    <Link
                        href="/install"
                        className="mt-4 inline-flex rounded-lg border px-3 py-2 text-xs font-bold"
                    >
                        Download VPS installer{' '}
                        <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                </div>
            ) : visibleDevices.length === 0 ? (
                <div className="text-muted-foreground mt-5 rounded-xl border border-dashed p-5 text-xs">
                    No devices match these filters.
                </div>
            ) : (
                <div className="mt-5 grid gap-3 lg:grid-cols-2">
                    {visibleDevices.map((device) => (
                        <article
                            key={device.id}
                            className="min-w-0 rounded-xl border p-4"
                        >
                            <div className="flex items-start justify-between gap-3">
                                <div className="flex min-w-0 items-start gap-3">
                                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-red-500/10 text-red-500">
                                        <HardDrive className="h-5 w-5" />
                                    </span>
                                    <div className="min-w-0">
                                        <h3 className="truncate text-sm font-black">
                                            {device.name}
                                        </h3>
                                        <p className="text-muted-foreground mt-1 text-xs">
                                            {[device.platform, device.arch]
                                                .filter(Boolean)
                                                .join(' / ') ||
                                                'Platform not reported'}
                                        </p>
                                    </div>
                                </div>
                                <span className="shrink-0 rounded-lg border px-2 py-1 text-xs font-bold">
                                    Registered · Live status unknown
                                </span>
                            </div>

                            <div className="text-muted-foreground mt-4 flex items-center gap-2 text-xs">
                                <ShieldAlert className="h-4 w-4 text-amber-500" />
                                Live connection has not been verified
                            </div>
                            {device.registered_at && (
                                <p className="text-muted-foreground mt-1 text-xs">
                                    Registered{' '}
                                    {formatRegisteredAt(device.registered_at)}
                                </p>
                            )}
                            <p className="mt-3 text-xs font-semibold">
                                {device.projects.length} authorized project
                                {device.projects.length === 1 ? '' : 's'}
                            </p>
                            <div className="mt-2 flex flex-wrap gap-1.5">
                                {device.projects.map((project) => (
                                    <span
                                        key={project.id}
                                        title={project.id}
                                        className="max-w-full truncate rounded-lg border px-2.5 py-1 text-xs"
                                    >
                                        {project.name}
                                    </span>
                                ))}
                                {device.projects.length === 0 && (
                                    <span className="text-muted-foreground text-xs">
                                        No saved project grant
                                    </span>
                                )}
                            </div>

                            <div className="mt-4 flex flex-wrap gap-2 border-t pt-3">
                                <button
                                    type="button"
                                    onClick={() =>
                                        setDetails(
                                            details === device.id
                                                ? null
                                                : device.id,
                                        )
                                    }
                                    aria-expanded={details === device.id}
                                    className="rounded-lg border px-3 py-2 text-xs font-bold"
                                >
                                    {details === device.id
                                        ? 'Hide details'
                                        : 'Details & diagnose'}
                                </button>
                                <Link
                                    href="/codebridge/pair"
                                    className="rounded-lg border px-3 py-2 text-xs font-bold"
                                >
                                    Reconnect guide
                                </Link>
                                {canManage && (
                                    <button
                                        type="button"
                                        onClick={() => startDisconnect(device)}
                                        disabled={submitting}
                                        className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/30 px-3 py-2 text-xs font-bold text-red-500 disabled:opacity-50"
                                    >
                                        <Unplug className="h-3.5 w-3.5" />{' '}
                                        Disconnect
                                    </button>
                                )}
                            </div>

                            {details === device.id && (
                                <div className="mt-3 rounded-xl border bg-black/[0.02] p-3 text-xs dark:bg-white/[0.02]">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <div>
                                            <p className="text-muted-foreground text-xs">
                                                Device ID
                                            </p>
                                            <code className="break-all">
                                                {device.id}
                                            </code>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() =>
                                                void copy(
                                                    device.id,
                                                    'Device ID',
                                                )
                                            }
                                            className="inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs"
                                        >
                                            <Clipboard className="h-3.5 w-3.5" />{' '}
                                            Copy
                                        </button>
                                    </div>
                                    <p className="text-muted-foreground mt-3 leading-5">
                                        In your connected AI chat, run{' '}
                                        <strong>connection_overview</strong> for
                                        this device and project. This page only
                                        verifies stored registration; it cannot
                                        start or stop a remote process.
                                    </p>
                                </div>
                            )}

                            {confirmId === device.id && canManage && (
                                <div className="mt-3 rounded-xl border border-red-500/35 bg-red-500/[0.04] p-3">
                                    <p className="flex items-center gap-2 text-xs font-black">
                                        <LockKeyhole className="h-4 w-4 text-red-500" />
                                        Confirm device disconnect
                                    </p>
                                    <p className="text-muted-foreground mt-2 text-xs leading-5">
                                        This revokes the stored device
                                        credential; it does not erase local
                                        files or shut down the machine. New
                                        pairing is required to reconnect.
                                        Gateway status may lag until
                                        revalidation.
                                    </p>
                                    <label className="mt-3 block text-xs font-semibold">
                                        Type exact device ID to confirm:
                                        <code className="ml-1 break-all">
                                            {device.id}
                                        </code>
                                        <input
                                            value={confirmation}
                                            onChange={(event) =>
                                                setConfirmation(
                                                    event.target.value,
                                                )
                                            }
                                            autoComplete="off"
                                            spellCheck={false}
                                            maxLength={64}
                                            className="bg-background mt-2 h-10 w-full rounded-lg border px-3 font-mono text-xs outline-none focus:border-red-500/60"
                                        />
                                    </label>
                                    <div className="mt-3 flex flex-wrap gap-2">
                                        <button
                                            type="button"
                                            onClick={() => disconnect(device)}
                                            disabled={
                                                submitting ||
                                                confirmation !== device.id
                                            }
                                            className="rounded-lg bg-red-600 px-3 py-2 text-xs font-bold text-white disabled:cursor-not-allowed disabled:opacity-40"
                                        >
                                            {submitting
                                                ? 'Disconnecting…'
                                                : 'Revoke device access'}
                                        </button>
                                        <button
                                            type="button"
                                            onClick={cancelDisconnect}
                                            disabled={submitting}
                                            className="rounded-lg border px-3 py-2 text-xs font-bold"
                                        >
                                            Cancel
                                        </button>
                                    </div>
                                </div>
                            )}
                        </article>
                    ))}
                </div>
            )}
            {managedCount > devices.length && (
                <p className="text-muted-foreground mt-3 text-xs">
                    Showing the first {devices.length} registrations; this list
                    is bounded to protect account performance.
                </p>
            )}

            <div className="mt-5 grid gap-3 lg:grid-cols-3">
                <QuickAction
                    icon={Cable}
                    title="Connect / reconnect"
                    description="Install the agent, then approve a new five-minute pairing code."
                    href="/codebridge/pair"
                    label="Approve pairing"
                />
                <QuickAction
                    icon={ShieldCheck}
                    title="Review permissions"
                    description="Manage account security and authorized client sessions."
                    href="/settings/security"
                    label="Account security"
                />
                <div className="rounded-xl border p-4">
                    <div className="flex items-center gap-2 text-xs font-black">
                        <CheckCircle2 className="h-4 w-4 text-red-500" /> MCP
                        endpoint
                    </div>
                    <code className="mt-3 block text-xs break-all">
                        {endpoint}
                    </code>
                    <button
                        type="button"
                        onClick={() => void copy(endpoint, 'MCP endpoint')}
                        className="mt-3 inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-bold"
                    >
                        <Clipboard className="h-3.5 w-3.5" /> Copy endpoint
                    </button>
                </div>
            </div>
            {!canManage && (
                <p className="text-muted-foreground mt-4 rounded-lg border p-3 text-xs">
                    Disconnect requires organization-management permission and
                    recent password confirmation. Contact your organization
                    administrator.
                </p>
            )}
        </section>
    );
}

function Stat({
    label,
    value,
    hint,
}: {
    label: string;
    value: string | number;
    hint: string;
}) {
    return (
        <div className="bg-background rounded-xl border p-4">
            <p className="text-muted-foreground text-xs font-bold uppercase">
                {label}
            </p>
            <p className="mt-1 text-lg font-black">{value}</p>
            <p className="text-muted-foreground mt-1 text-xs">{hint}</p>
        </div>
    );
}

function QuickAction({
    icon: Icon,
    title,
    description,
    href,
    label,
}: {
    icon: typeof Cable;
    title: string;
    description: string;
    href: string;
    label: string;
}) {
    return (
        <div className="rounded-xl border p-4">
            <Icon className="h-4 w-4 text-red-500" />
            <p className="mt-2 text-xs font-black">{title}</p>
            <p className="text-muted-foreground mt-1 text-xs leading-5">
                {description}
            </p>
            <Link
                href={href}
                className="mt-3 inline-flex items-center gap-1.5 text-xs font-bold text-red-500"
            >
                {label} <ArrowRight className="h-3.5 w-3.5" />
            </Link>
        </div>
    );
}

function formatRegisteredAt(value: string): string {
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? 'at an unknown time'
        : date.toLocaleString(undefined, {
              dateStyle: 'medium',
              timeStyle: 'short',
          });
}
