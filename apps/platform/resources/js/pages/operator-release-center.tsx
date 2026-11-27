import { Head } from '@inertiajs/react';
import OperatorModuleNavigation from '@/components/operator-module-navigation';
import { LockKeyhole, Rocket, ShieldCheck, TriangleAlert } from 'lucide-react';

type Contract = {
    project: string;
    kind: string;
    repository: string;
    required_checks: string[];
    stage_gate: string;
    smoke_probe: string;
    health_probe: string;
    rollback_strategy: string;
    staging_qa_probe: string | null;
    restore_probe: string | null;
    data_risk: string;
    approval: string;
    signing: string;
};

type Live = {
    deployed_sha: string | null;
    readiness_status: string;
    readiness_reason: string;
    approved_sha: string | null;
};

const readinessLabel: Record<string, string> = {
    preflight_ready_only: 'Approved release is ready for activation',
    already_live_observed: 'Approved release is already live',
    blocked: 'Blocked',
    unavailable: 'No fresh root receipt',
};

type Catalog = {
    status: string;
    contracts: Contract[];
    invalid: string[];
};

const riskTone: Record<string, string> = {
    none: 'text-emerald-600 dark:text-emerald-400',
    migrations: 'text-amber-600 dark:text-amber-400',
    destructive: 'text-red-600 dark:text-red-400',
};

type Migrations = {
    status: 'ok' | 'pending' | 'unavailable';
    pending_count: number;
    pending: string[];
    applied_count: number;
};

export default function OperatorReleaseCenter({
    catalog,
    live,
    migrations,
}: {
    catalog: Catalog;
    live: Record<string, Live>;
    migrations?: Migrations;
}) {
    return (
        <>
            <Head title="Release Center" />
            <div className="owner-admin-page kmj-admin-shell flex h-full min-w-0 flex-1 flex-col gap-6 overflow-x-auto p-4 sm:p-6 lg:p-8">
                <OperatorModuleNavigation active="operations" />
                <section className="owner-admin-hero kmj-admin-hero rounded-[1.65rem] p-6 sm:p-8">
                    <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/5 px-3 py-1 text-xs font-bold text-emerald-600 dark:text-emerald-400">
                        <ShieldCheck className="h-3.5 w-3.5" />
                        Platform Owner · read-only · owner approval stays the
                        only release gate
                    </div>
                    <h1 className="mt-4 flex items-center gap-3 text-3xl font-black tracking-tight sm:text-4xl">
                        <Rocket className="h-8 w-8 text-red-500" />
                        Release Center
                    </h1>
                    <p className="text-muted-foreground mt-3 max-w-2xl text-sm leading-6">
                        One release contract per project: named gates, the CI
                        checks that must be green on the exact commit, the data
                        risk and how it is signed. This page only lists the
                        checked-in contracts. It cannot stage, approve or
                        release anything yet.
                    </p>
                </section>

                {catalog.status !== 'ok' ? (
                    <p
                        className="flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/5 p-4 text-sm"
                        data-testid="release-center-unavailable"
                    >
                        <TriangleAlert className="h-4 w-4 text-amber-500" />
                        The release contracts are not available on this server,
                        so nothing is listed.
                    </p>
                ) : null}

                <section
                    className="grid gap-4 lg:grid-cols-2"
                    aria-label="Release contracts"
                >
                    {catalog.contracts.map((contract) => (
                        <article
                            key={contract.project}
                            className="owner-panel rounded-2xl border p-5"
                            data-testid="release-contract"
                        >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <h2 className="text-lg font-black">
                                    {contract.project}
                                </h2>
                                <span className="bg-muted rounded-full px-3 py-1 text-xs font-bold">
                                    {contract.kind}
                                </span>
                            </div>
                            <p className="text-muted-foreground mt-1 font-mono text-xs">
                                {contract.repository}
                            </p>
                            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                                <div>
                                    <dt className="text-muted-foreground text-xs">
                                        Stage gate
                                    </dt>
                                    <dd className="font-mono text-xs">
                                        {contract.stage_gate}
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-muted-foreground text-xs">
                                        Smoke test
                                    </dt>
                                    <dd className="font-mono text-xs">
                                        {contract.smoke_probe}
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-muted-foreground text-xs">
                                        Health check
                                    </dt>
                                    <dd className="font-mono text-xs">
                                        {contract.health_probe}
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-muted-foreground text-xs">
                                        Rollback
                                    </dt>
                                    <dd className="font-mono text-xs">
                                        {contract.rollback_strategy}
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-muted-foreground text-xs">
                                        Staging QA
                                    </dt>
                                    <dd className="font-mono text-xs">
                                        {contract.staging_qa_probe ??
                                            'not declared'}
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-muted-foreground text-xs">
                                        Restore proof
                                    </dt>
                                    <dd className="font-mono text-xs">
                                        {contract.restore_probe ??
                                            'not declared'}
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-muted-foreground text-xs">
                                        Data risk
                                    </dt>
                                    <dd
                                        className={`text-xs font-bold ${riskTone[contract.data_risk] ?? ''}`}
                                    >
                                        {contract.data_risk}
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-muted-foreground text-xs">
                                        Signing
                                    </dt>
                                    <dd className="font-mono text-xs">
                                        {contract.signing}
                                    </dd>
                                </div>
                            </dl>
                            <p className="mt-4 flex items-center gap-2 text-xs font-bold">
                                <LockKeyhole className="h-3.5 w-3.5 text-red-500" />
                                Approval: {contract.approval} (every release, no
                                exceptions)
                            </p>
                            <details className="mt-3 text-xs">
                                <summary className="cursor-pointer font-bold">
                                    {contract.required_checks.length} required
                                    CI checks on the exact commit
                                </summary>
                                <ul className="text-muted-foreground mt-2 list-disc space-y-1 pl-5">
                                    {contract.required_checks.map((check) => (
                                        <li key={check}>{check}</li>
                                    ))}
                                </ul>
                            </details>
                            {live[contract.project] ? (
                                <div
                                    className="bg-muted mt-3 rounded-xl p-3 text-xs"
                                    data-testid="release-live-status"
                                >
                                    <p className="font-bold">
                                        Live now:{' '}
                                        <span className="font-mono">
                                            {live[contract.project].deployed_sha
                                                ? live[
                                                      contract.project
                                                  ].deployed_sha!.slice(0, 12)
                                                : 'unknown'}
                                        </span>
                                    </p>
                                    <p className="text-muted-foreground mt-1">
                                        Preflight:{' '}
                                        {readinessLabel[
                                            live[contract.project]
                                                .readiness_status
                                        ] ?? 'Unknown'}{' '}
                                        (
                                        {
                                            live[contract.project]
                                                .readiness_reason
                                        }
                                        )
                                    </p>
                                    {contract.project === 'main-platform' &&
                                    migrations ? (
                                        <p
                                            className="mt-1"
                                            data-testid="release-migration-status"
                                        >
                                            Database migrations:{' '}
                                            {migrations.status === 'ok'
                                                ? `all applied (${migrations.applied_count})`
                                                : migrations.status ===
                                                    'pending'
                                                  ? `${migrations.pending_count} pending (${migrations.pending.join(', ')}). Post-activation has not been applied.`
                                                  : 'could not be read'}
                                        </p>
                                    ) : null}
                                    <p className="text-muted-foreground mt-1">
                                        Advisory view from this server&apos;s
                                        own state. It is not proof of a release
                                        and cannot start one.
                                    </p>
                                </div>
                            ) : (
                                <p className="text-muted-foreground mt-3 text-xs">
                                    Live status: not connected yet for this
                                    project.
                                </p>
                            )}
                        </article>
                    ))}
                </section>

                {catalog.invalid.length > 0 ? (
                    <p
                        className="flex items-center gap-2 rounded-xl border border-red-500/40 bg-red-500/5 p-4 text-sm"
                        data-testid="release-center-invalid"
                    >
                        <TriangleAlert className="h-4 w-4 text-red-500" />
                        Not shown because they failed the safety checks:{' '}
                        {catalog.invalid.join(', ')}
                    </p>
                ) : null}
            </div>
        </>
    );
}
