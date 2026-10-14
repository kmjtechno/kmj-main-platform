import { router } from '@inertiajs/react';
import { KeyRound } from 'lucide-react';
import { useState, type FormEvent } from 'react';

export type GrantablePolicy = {
    id: string;
    product_id: string;
    product_name: string;
    capability: string;
};

export function DirectoryGrantAccess({
    organizationId,
    policies,
}: {
    organizationId: string;
    policies: GrantablePolicy[];
}) {
    const [open, setOpen] = useState(false);
    const [policyId, setPolicyId] = useState('');
    const [reason, setReason] = useState('');
    const [confirmation, setConfirmation] = useState('');
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState('');

    const submit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (
            saving ||
            !policyId ||
            reason.trim().length < 10 ||
            confirmation !== 'GRANT_PRODUCT_ACCESS'
        )
            return;

        router.post(
            '/operator/directory/organizations/' +
                encodeURIComponent(organizationId) +
                '/access',
            {
                policy_id: policyId,
                reason: reason.trim(),
                confirmation,
            },
            {
                preserveScroll: true,
                onStart: () => setSaving(true),
                onSuccess: () => {
                    setOpen(false);
                    setNotice(
                        'Entitlement issued; review native license requirements separately.',
                    );
                    setReason('');
                    setConfirmation('');
                    setPolicyId('');
                },
                onError: (errors) =>
                    setNotice(Object.values(errors)[0] ?? 'Grant blocked.'),
                onFinish: () => setSaving(false),
            },
        );
    };

    return (
        <div className="mt-2">
            <button
                type="button"
                disabled={policies.length === 0}
                onClick={() => {
                    setOpen(!open);
                    setNotice('');
                }}
                className="inline-flex min-h-9 items-center gap-1 rounded-lg border border-red-500/30 px-2.5 py-1 text-xs font-semibold text-red-200 hover:bg-red-500/10 disabled:opacity-50"
            >
                <KeyRound className="size-3.5" aria-hidden="true" /> Grant
                product access
            </button>
            {policies.length === 0 && (
                <span className="ml-2 text-xs text-slate-400">
                    No release-ready licensing policy available.
                </span>
            )}
            {open && (
                <form
                    onSubmit={submit}
                    className="mt-3 grid min-w-56 gap-2 rounded-xl border border-red-500/25 bg-[#090d14] p-3"
                >
                    <p className="text-xs leading-5 text-amber-100">
                        This manually issues an audited product entitlement, not
                        a signed desktop/device license. Do not use as payment
                        confirmation or bypass product-specific activation.
                    </p>
                    <label
                        className="text-xs font-semibold text-slate-300"
                        htmlFor={'policy-' + organizationId}
                    >
                        Eligible product and access policy
                    </label>
                    <select
                        id={'policy-' + organizationId}
                        required
                        value={policyId}
                        onChange={(event) => setPolicyId(event.target.value)}
                        className="min-h-10 w-full rounded-lg border border-white/20 bg-[#090d14] px-2 text-sm"
                    >
                        <option value="">Select product access…</option>
                        {policies.map((policy) => (
                            <option key={policy.id} value={policy.id}>
                                {policy.product_name} — {policy.capability}
                            </option>
                        ))}
                    </select>
                    <label
                        className="text-xs font-semibold text-slate-300"
                        htmlFor={'grant-reason-' + organizationId}
                    >
                        Reason (audit required)
                    </label>
                    <input
                        id={'grant-reason-' + organizationId}
                        required
                        minLength={10}
                        maxLength={500}
                        value={reason}
                        onChange={(event) => setReason(event.target.value)}
                        className="min-h-10 w-full rounded-lg border border-white/20 bg-[#090d14] px-3 text-sm"
                        placeholder="Approved complimentary access reason"
                    />
                    <label
                        className="text-xs font-semibold text-slate-300"
                        htmlFor={'grant-confirm-' + organizationId}
                    >
                        Type GRANT_PRODUCT_ACCESS to confirm
                    </label>
                    <input
                        id={'grant-confirm-' + organizationId}
                        required
                        value={confirmation}
                        onChange={(event) => setConfirmation(event.target.value)}
                        className="min-h-10 w-full rounded-lg border border-white/20 bg-[#090d14] px-3 text-sm"
                        autoComplete="off"
                    />
                    <div className="flex flex-wrap gap-2">
                        <button
                            type="submit"
                            disabled={
                                saving ||
                                !policyId ||
                                reason.trim().length < 10 ||
                                confirmation !== 'GRANT_PRODUCT_ACCESS'
                            }
                            className="min-h-10 rounded-lg bg-red-600 px-3 text-xs font-bold disabled:opacity-50"
                        >
                            {saving ? 'Applying…' : 'Confirm access grant'}
                        </button>
                        <button
                            type="button"
                            onClick={() => setOpen(false)}
                            disabled={saving}
                            className="min-h-10 rounded-lg border border-white/20 px-3 text-xs"
                        >
                            Cancel
                        </button>
                    </div>
                </form>
            )}
            {notice && (
                <p role="status" className="mt-2 text-xs text-blue-200">
                    {notice}
                </p>
            )}
        </div>
    );
}
