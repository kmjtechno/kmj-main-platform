import DeviceControlCenter, {
    type CodeBridgeDevice,
} from '@/components/codebridge/device-control-center';
import OperatorModuleNavigation from '@/components/operator-module-navigation';
import { Head, Link, router, usePage } from '@inertiajs/react';
import { useState } from 'react';
import { ShieldCheck, Server, LockKeyhole } from 'lucide-react';

type License = {
    id: string;
    customer_id: string;
    plan: string;
    status: string;
    expires_at: string;
    revoked_at: string | null;
};

type ManagedOrganization = {
    id: string;
    name: string;
    plan: string | null;
    deviceLimit: number | null;
    managedCount: number;
    canManage: boolean;
    devices: CodeBridgeDevice[];
};

type Props = {
    organizations: ManagedOrganization[];
    endpoint: string;
    licenses: License[];
    limits: { devices: number; concurrent_jobs: number };
    errors?: Record<string, string>;
};

const CONFIRM = 'UPGRADE_CODEBRIDGE_OWNER';

export default function OperatorCodeBridgeOwner({
    licenses,
    limits,
    organizations,
    endpoint,
}: Props) {
    const [confirmation, setConfirmation] = useState('');
    const [processing, setProcessing] = useState<string | null>(null);
    const { errors } = usePage<{ errors?: Record<string, string> }>().props;

    const upgrade = (license: License) => {
        if (confirmation !== CONFIRM || processing !== null) return;
        setProcessing(license.id);
        router.post(
            '/operator/codebridge/licenses/owner-tier',
            {
                license_id: license.id,
                tenant_id: license.customer_id,
                confirm: confirmation,
            },
            {
                preserveScroll: true,
                onFinish: () => setProcessing(null),
                onSuccess: () => setConfirmation(''),
            },
        );
    };

    return (
        <>
            <Head title="KMJ CodeBridge Control Center" />
            <main className="kmj-admin-shell flex min-w-0 flex-1 flex-col gap-6 p-4 sm:p-6 lg:p-8">
                <OperatorModuleNavigation active="codebridge" />
                <section className="kmj-admin-hero rounded-xl p-4">
                    <h1 className="text-2xl font-bold">
                        CodeBridge Control Center
                    </h1>
                    <p className="text-muted-foreground mt-2 text-sm">
                        Connect a computer, approve pairing, manage registered
                        devices and assign projects.
                    </p>
                    <div className="mt-4 flex flex-wrap gap-2">
                        <a
                            href="/install-codebridge-windows.cmd"
                            download
                            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white"
                        >
                            Connect Windows PC
                        </a>
                        <a
                            href="/install"
                            download="KMJ-CodeBridge-Connect-Linux.sh"
                            className="rounded-lg border px-4 py-2 text-sm"
                        >
                            Connect Linux / VPS
                        </a>
                        <Link
                            href="/codebridge/pair"
                            className="rounded-lg border px-4 py-2 text-sm"
                        >
                            Approve pairing code
                        </Link>
                        <a
                            href="/install-chatgpt-desktop.ps1"
                            download
                            className="rounded-lg border px-4 py-2 text-sm"
                        >
                            Set up ChatGPT Desktop
                        </a>
                        <button
                            type="button"
                            onClick={() =>
                                router.reload({ only: ['organizations'] })
                            }
                            className="rounded-lg border px-4 py-2 text-sm"
                        >
                            Refresh devices
                        </button>
                    </div>
                </section>
                {organizations.length === 0 && (
                    <section className="bg-card rounded-xl border p-4">
                        <h2 className="font-bold">
                            No managed organization yet
                        </h2>
                        <p className="text-muted-foreground mt-2 text-sm">
                            This account has no organization it can manage.
                            Device controls appear here after an authorized
                            organization and CodeBridge license are associated
                            with the account. Pairing does not create a license
                            automatically.
                        </p>
                    </section>
                )}
                {organizations.map((organization) => (
                    <section
                        key={organization.id}
                        className="min-w-0 space-y-3"
                    >
                        <h2 className="text-lg font-bold">
                            {organization.name}
                        </h2>
                        {!organization.canManage && (
                            <p role="status" className="text-sm text-amber-300">
                                An active CodeBridge license is required to
                                manage devices in this organization.
                            </p>
                        )}
                        <DeviceControlCenter
                            tenantId={organization.id}
                            plan={organization.plan}
                            devices={organization.devices}
                            managedCount={organization.managedCount}
                            deviceLimit={organization.deviceLimit}
                            canManage={organization.canManage}
                            endpoint={endpoint}
                        />
                    </section>
                ))}
                <details className="bg-card rounded-xl border p-4">
                    <summary className="cursor-pointer font-bold">
                        Owner license settings
                    </summary>
                    <div className="mt-4 space-y-4">
                        <section className="kmj-admin-hero rounded-[1.65rem] p-6 sm:p-8">
                            <div className="flex items-center gap-3">
                                <ShieldCheck className="h-8 w-8 text-red-500" />
                                <div>
                                    <h1 className="text-2xl font-bold">
                                        KMJ CodeBridge — Internal Owner Plan
                                    </h1>
                                    <p className="text-muted-foreground mt-1 text-sm">
                                        Verified KMJ Platform Owner only. This
                                        is an internal, non-billable license
                                        tier — not a public customer
                                        subscription or a payment.
                                    </p>
                                </div>
                            </div>
                            <div className="mt-5 flex flex-wrap gap-3 text-sm">
                                <span className="rounded-lg border px-3 py-2">
                                    <Server className="mr-2 inline h-4 w-4" />
                                    Owner-tier device policy
                                </span>
                                <span className="rounded-lg border px-3 py-2">
                                    Up to {limits.concurrent_jobs} concurrent
                                    jobs
                                </span>
                                <span className="rounded-lg border px-3 py-2">
                                    Read, write and approved execution
                                </span>
                            </div>
                            <p className="text-muted-foreground mt-4 text-sm">
                                Resource-aware execution, approved project
                                roots, audit records and existing license expiry
                                remain enforced. Actual job capacity also
                                requires signed entitlement renewal on the
                                connected device. No unrestricted shell or
                                automatic payment is enabled.
                            </p>
                        </section>

                        <section className="bg-card rounded-2xl border p-6">
                            <div className="flex items-center gap-2">
                                <LockKeyhole className="h-5 w-5 text-red-500" />
                                <h2 className="font-bold">
                                    Explicit owner confirmation
                                </h2>
                            </div>
                            <p className="text-muted-foreground mt-2 text-sm">
                                Your account must have verified platform-owner
                                access, a registered passkey and recent password
                                confirmation. Enter the phrase below to upgrade
                                one of your own organization&apos;s active
                                CodeBridge licenses.
                            </p>
                            <label
                                htmlFor="owner-confirmation"
                                className="mt-4 block text-sm font-medium"
                            >
                                Type {CONFIRM}
                            </label>
                            <input
                                id="owner-confirmation"
                                autoComplete="off"
                                spellCheck={false}
                                value={confirmation}
                                onChange={(e) =>
                                    setConfirmation(e.target.value)
                                }
                                className="bg-background mt-2 w-full max-w-lg rounded-lg border p-3 font-mono text-sm"
                            />
                            {errors?.license_id && (
                                <p
                                    role="alert"
                                    className="mt-2 text-sm text-red-500"
                                >
                                    {errors.license_id}
                                </p>
                            )}
                        </section>

                        <section className="bg-card rounded-2xl border p-6">
                            <h2 className="font-bold">
                                Your authorized CodeBridge licenses
                            </h2>
                            {licenses.length === 0 ? (
                                <p className="text-muted-foreground mt-3 text-sm">
                                    No CodeBridge license is associated with an
                                    organization owned by this account. Nothing
                                    has been changed.
                                </p>
                            ) : (
                                <div className="mt-4 space-y-3">
                                    {licenses.map((license) => {
                                        const eligible =
                                            license.status === 'active' &&
                                            license.revoked_at === null &&
                                            new Date(
                                                license.expires_at,
                                            ).getTime() > Date.now() &&
                                            license.plan !== 'owner';
                                        return (
                                            <div
                                                key={license.id}
                                                className="flex flex-wrap items-center justify-between gap-4 rounded-xl border p-4"
                                            >
                                                <div className="min-w-0">
                                                    <div className="font-mono text-xs break-all">
                                                        {license.id}
                                                    </div>
                                                    <p className="text-muted-foreground mt-1 text-xs break-all">
                                                        Organization:{' '}
                                                        {license.customer_id}
                                                    </p>
                                                    <p className="mt-1 text-sm">
                                                        Plan:{' '}
                                                        <b>{license.plan}</b> ·
                                                        Status: {license.status}{' '}
                                                        · Expires:{' '}
                                                        {license.expires_at}
                                                    </p>
                                                </div>
                                                {license.plan === 'owner' ? (
                                                    <span className="text-sm font-semibold">
                                                        {license.status ===
                                                            'active' &&
                                                        license.revoked_at ===
                                                            null &&
                                                        new Date(
                                                            license.expires_at,
                                                        ).getTime() > Date.now()
                                                            ? 'Owner Plan Active'
                                                            : 'Owner Plan Inactive'}
                                                    </span>
                                                ) : (
                                                    <button
                                                        type="button"
                                                        disabled={
                                                            !eligible ||
                                                            confirmation !==
                                                                CONFIRM ||
                                                            processing !== null
                                                        }
                                                        onClick={() =>
                                                            upgrade(license)
                                                        }
                                                        className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
                                                    >
                                                        {processing ===
                                                        license.id
                                                            ? 'Activating…'
                                                            : 'Activate Owner Plan'}
                                                    </button>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </section>
                    </div>
                </details>
            </main>
        </>
    );
}
