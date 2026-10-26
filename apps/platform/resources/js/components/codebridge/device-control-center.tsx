import { Link, router } from '@inertiajs/react';
import { codeBridgeDeviceQuotaDisplay } from './device-policy-display';
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
    pending_projects?: Array<{
        id: string;
        name: string;
        repository: string;
        status: 'pending_local_setup';
    }>;
    registration: 'registered';
    pairing_state?: 'approved_unredeemed' | 'redeemed' | 'unknown';
    connection_status: 'not_verified';
    registered_at?: string | null;
};

type Props = {
    tenantId: string;
    plan: string | null;
    devices: CodeBridgeDevice[];
    managedCount: number;
    deviceLimit: number | null;
    canManage: boolean;
    endpoint: string;
};

type View = 'all' | 'with-projects' | 'needs-projects';

export default function DeviceControlCenter({
    tenantId,
    plan,
    devices,
    managedCount,
    deviceLimit,
    canManage,
    endpoint,
}: Props) {
    const [search, setSearch] = useState('');
    const [view, setView] = useState<View>('all');
    const [details, setDetails] = useState<string | null>(null);
    const [confirmId, setConfirmId] = useState<string | null>(null);
    const [confirmation, setConfirmation] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [assignDeviceId, setAssignDeviceId] = useState<string | null>(null);
    const [newProjectId, setNewProjectId] = useState('');
    const [newProjectName, setNewProjectName] = useState('');
    const [newRepositoryUrl, setNewRepositoryUrl] = useState('');
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

    const assignProject = (device: CodeBridgeDevice) => {
        if (!canManage || submitting || assignDeviceId !== device.id) return;
        setSubmitting(true);
        setFeedback('');
        router.post(
            `/services/kmj-codebridge/organizations/${encodeURIComponent(tenantId)}/devices/${encodeURIComponent(device.id)}/projects/assign`,
            {
                project_id: newProjectId.trim(),
                project_name: newProjectName.trim(),
                repository_url: newRepositoryUrl.trim(),
            },
            {
                preserveScroll: true,
                onSuccess: () => {
                    setAssignDeviceId(null);
                    setNewProjectId('');
                    setNewProjectName('');
                    setNewRepositoryUrl('');
                    setFeedback(
                        'Assignment saved; local agent setup and heartbeat verification remain pending.',
                    );
                },
                onError: () =>
                    setFeedback(
                        'Project assignment refused. Check ID, repository, permissions or existing request.',
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
                    <p className="text-muted-foreground mt-2 text-xs leading-5">
                        Download the official Windows connector and
                        double-click it on your computer. Home Office P520
                        automatically selects its approved Calibration Pro
                        device; other PCs use the guided device picker. Approve
                        new pairing once in your browser, then reconnect at
                        Windows sign-in. No GitHub visit or manual commands.
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <a
                        href="/install-codebridge-windows.cmd"
                        download="KMJ-CodeBridge-Connect-Windows.cmd"
                        className="inline-flex h-10 items-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-black text-white hover:bg-red-500"
                    >
                        <Laptop2 className="h-4 w-4" /> Connect this Windows PC
                    </a>
                    <button
                        type="button"
                        onClick={() => router.reload({ only: ['service'] })}
                        className="inline-flex h-10 items-center gap-2 rounded-xl border px-3 text-xs font-bold hover:border-red-500/40"
                    >
                        <RefreshCw className="h-4 w-4" /> Refresh
                    </button>
                    <Link
                        href="/codebridge/pair"
                        className="inline-flex h-10 items-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-black text-white hover:bg-red-500"
                    >
                        <Cable className="h-4 w-4" /> Connect device
                    </Link>
                </div>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <Stat
                    label="Authorized devices"
                    value={managedCount}
                    hint={
                        codeBridgeDeviceQuotaDisplay(
                            plan,
                            managedCount,
                            deviceLimit,
                        ).registrationHint
                    }
                />
                <Stat
                    label="Known project grants"
                    value={devices.reduce(
                        (count, device) => count + device.projects.length,
                        0,
                    )}
                    hint="Active grants from approved device pairings"
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
                                    {device.pairing_state ===
                                    'approved_unredeemed'
                                        ? 'Approved · Not redeemed'
                                        : 'Registered · Live status unknown'}
                                </span>
                            </div>

                            <div className="text-muted-foreground mt-4 flex items-center gap-2 text-xs">
                                <ShieldAlert className="h-4 w-4 text-amber-500" />
                                Live connection has not been verified
                            </div>
                            {device.pairing_state === 'approved_unredeemed' && (
                                <div className="mt-3 rounded-lg border border-amber-500/30 p-3 text-xs">
                                    <p className="font-black text-amber-600 dark:text-amber-400">
                                        Approval has not reached this computer
                                    </p>
                                    <p className="text-muted-foreground mt-1 leading-5">
                                        A server credential exists, but the
                                        agent never redeemed its one-time
                                        approval. First check whether this PC
                                        has a saved private agent enrollment. If
                                        it was lost, do not keep approving new
                                        codes. Once the public pairing endpoint
                                        is healthy, a manager can disconnect
                                        only this device (recent password
                                        confirmation required), then approve one
                                        new code using the first-party Windows
                                        installer. No files are deleted and no
                                        live connection is claimed until a
                                        gateway heartbeat is verified.
                                    </p>
                                </div>
                            )}
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

                            {(device.pending_projects ?? []).length > 0 && (
                                <div className="mt-3 rounded-lg border border-amber-500/30 p-3">
                                    <p className="text-xs font-black text-amber-600 dark:text-amber-400">
                                        Awaiting local project setup
                                    </p>
                                    <p className="text-muted-foreground mt-1 text-xs">
                                        Requests are not active agent grants.
                                        Verify device-side enrollment before
                                        using them.
                                    </p>
                                    <div className="mt-2 flex flex-wrap gap-1.5">
                                        {(device.pending_projects ?? []).map(
                                            (project) => (
                                                <span
                                                    key={project.id}
                                                    title={project.repository}
                                                    className="rounded-lg border border-amber-500/30 px-2.5 py-1 text-xs"
                                                >
                                                    {project.name} · Pending
                                                    setup
                                                </span>
                                            ),
                                        )}
                                    </div>
                                </div>
                            )}

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
                                <a
                                    href="/install-codebridge-windows.cmd"
                                    download="KMJ-CodeBridge-Connect-Windows.cmd"
                                    className="rounded-lg border px-3 py-2 text-xs font-bold"
                                >
                                    Reconnect on Windows
                                </a>
                                {canManage && (
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setAssignDeviceId(
                                                assignDeviceId === device.id
                                                    ? null
                                                    : device.id,
                                            );
                                            setConfirmId(null);
                                            setFeedback('');
                                        }}
                                        disabled={submitting}
                                        aria-expanded={
                                            assignDeviceId === device.id
                                        }
                                        className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-bold hover:border-red-500/40 disabled:opacity-50"
                                    >
                                        <FolderPlus className="h-3.5 w-3.5" />{' '}
                                        Assign project
                                    </button>
                                )}
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

                            {assignDeviceId === device.id && canManage && (
                                <form
                                    onSubmit={(event) => {
                                        event.preventDefault();
                                        assignProject(device);
                                    }}
                                    className="mt-3 grid gap-3 rounded-xl border p-4"
                                >
                                    <h4 className="text-sm font-black">
                                        Assign a new project
                                    </h4>
                                    <p className="text-muted-foreground text-xs leading-5">
                                        Save a project request for this device.
                                        This does not install code, authorize a
                                        local filesystem path or confirm the
                                        agent is online.
                                    </p>
                                    <label className="text-xs font-semibold">
                                        Project ID
                                        <input
                                            required
                                            pattern="[a-z0-9][a-z0-9_-]{0,63}"
                                            maxLength={64}
                                            value={newProjectId}
                                            onChange={(event) =>
                                                setNewProjectId(
                                                    event.target.value,
                                                )
                                            }
                                            placeholder="kmj-calibration-studio"
                                            className="bg-background mt-1 block h-10 w-full rounded-lg border px-3 text-sm"
                                        />
                                    </label>
                                    <label className="text-xs font-semibold">
                                        Display name
                                        <input
                                            required
                                            minLength={2}
                                            maxLength={100}
                                            value={newProjectName}
                                            onChange={(event) =>
                                                setNewProjectName(
                                                    event.target.value,
                                                )
                                            }
                                            placeholder="KMJ Calibration Studio"
                                            className="bg-background mt-1 block h-10 w-full rounded-lg border px-3 text-sm"
                                        />
                                    </label>
                                    <label className="text-xs font-semibold">
                                        GitHub repository URL
                                        <input
                                            required
                                            type="url"
                                            maxLength={255}
                                            value={newRepositoryUrl}
                                            onChange={(event) =>
                                                setNewRepositoryUrl(
                                                    event.target.value,
                                                )
                                            }
                                            placeholder="https://github.com/kmjtechno/kmj-calibration-pro"
                                            className="bg-background mt-1 block h-10 w-full rounded-lg border px-3 text-sm"
                                        />
                                    </label>
                                    <div className="flex flex-wrap gap-2">
                                        <button
                                            type="submit"
                                            disabled={submitting}
                                            className="rounded-lg bg-red-600 px-4 py-2 text-xs font-black text-white disabled:opacity-50"
                                        >
                                            {submitting
                                                ? 'Saving…'
                                                : 'Save assignment request'}
                                        </button>
                                        <button
                                            type="button"
                                            disabled={submitting}
                                            onClick={() =>
                                                setAssignDeviceId(null)
                                            }
                                            className="rounded-lg border px-4 py-2 text-xs font-bold"
                                        >
                                            Cancel
                                        </button>
                                    </div>
                                </form>
                            )}

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
                                        Existing device: use the Windows
                                        connector on this computer and choose
                                        YES to reuse its private approval. New
                                        device: choose NO and approve its
                                        short-lived code through your KMJ
                                        account. The browser cannot start an
                                        agent on a powered-off or unreachable
                                        machine. Registration alone is not an
                                        authenticated gateway heartbeat.
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
