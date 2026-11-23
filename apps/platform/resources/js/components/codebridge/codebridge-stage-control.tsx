import { router } from '@inertiajs/react';
import { CheckCircle2, GitBranch, LockKeyhole, Play } from 'lucide-react';
import { useState } from 'react';

type Stage = {
    status: string;
    configured: boolean;
    workflow_url: string;
};

export default function CodeBridgeStageControl({
    stage,
}: {
    stage?: Stage | null;
}) {
    // Synthetic previews and partial server responses may omit this optional
    // protected capability. Fail closed instead of crashing the Ops console.
    const configured = stage?.configured === true;
    const workflowUrl =
        stage?.workflow_url ??
        'https://github.com/kmjtechno/kmj-codebridge/actions/workflows/oneclick-stage.yml';
    const [requesting, setRequesting] = useState(false);
    const [notice, setNotice] = useState('');

    const requestStage = () => {
        if (requesting || !configured) return;
        setRequesting(true);
        setNotice('Requesting one exact-main isolated staging run...');
        router.post(
            '/operator/ops/actions/codebridge-stage',
            { confirmation: 'STAGE_CODEBRIDGE_MAIN' },
            {
                preserveScroll: true,
                onSuccess: () =>
                    setNotice(
                        'Request accepted, not staged yet. Verify exact SHA, GitHub CI and the unsigned archive receipt.',
                    ),
                onError: () =>
                    setNotice(
                        'Stage request not verified. Review the owner action audit before retrying.',
                    ),
                onFinish: () => setRequesting(false),
            },
        );
    };

    return (
        <section
            id="codebridge-release-center"
            className="bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
        >
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h2 className="flex items-center gap-2 font-bold">
                        <GitBranch className="size-4 text-red-500" />
                        CodeBridge Release Center
                    </h2>
                    <p className="text-muted-foreground mt-1 text-xs">
                        One-click source staging. Owner signing and Elite
                        release remain protected.
                    </p>
                </div>
                <span className="rounded-full border px-3 py-1 text-xs font-bold">
                    {configured
                        ? 'Stage connector available'
                        : 'Stage connector not configured'}
                </span>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border p-4">
                    <strong className="block text-sm">1. Stage & QA</strong>
                    <span className="text-muted-foreground mt-2 block text-xs">
                        Exact main SHA, isolated CI, archive hash and receipt
                    </span>
                </div>
                <div className="rounded-xl border p-4">
                    <strong className="block text-sm">
                        2. Owner signature
                    </strong>
                    <span className="text-muted-foreground mt-2 block text-xs">
                        Independent owner-held Ed25519 approval required
                    </span>
                </div>
                <div className="rounded-xl border p-4">
                    <strong className="block text-sm">3. Elite LIVE</strong>
                    <span className="text-muted-foreground mt-2 block text-xs">
                        Signed gateway canary, health and rollback proof
                    </span>
                </div>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3">
                <button
                    type="button"
                    onClick={requestStage}
                    disabled={!configured || requesting}
                    className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-red-600 px-5 py-3 text-xs font-black text-white disabled:cursor-not-allowed disabled:opacity-40"
                >
                    <Play className="size-4" aria-hidden="true" />
                    {requesting ? 'Requesting stage...' : 'Stage CodeBridge'}
                </button>
                <a
                    href={workflowUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground text-xs underline"
                >
                    View official GitHub staging runs
                </a>
                <span className="text-muted-foreground inline-flex items-center gap-2 text-xs">
                    <LockKeyhole className="size-4" />
                    No signing key or production command in browser
                </span>
            </div>
            <p className="text-muted-foreground mt-3 text-xs" role="status">
                {notice ||
                    (configured
                        ? 'Ready to request staging. A click is not a completed stage.'
                        : 'A restricted server-side GitHub Actions connector must be installed by the owner first.')}
            </p>
            <p className="text-muted-foreground mt-3 flex items-center gap-2 text-xs">
                <CheckCircle2 className="size-4" />
                Existing CodeBridge signed release is unchanged by this action.
            </p>
        </section>
    );
}
