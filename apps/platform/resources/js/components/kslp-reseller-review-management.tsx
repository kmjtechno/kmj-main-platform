import { useForm } from '@inertiajs/react';

type Candidate = {
    organization_id: string;
    organization_name: string;
    product_id: string;
    product_code: string;
    product_name: string;
    reseller_user_id: string;
    reseller_name: string;
};

type Grant = {
    id: string;
    organization_name: string;
    product_code: string;
    product_name: string;
    reseller_user_id: string;
    reseller_name: string;
    expires_at: string;
    revoked_at: string | null;
};

export type ResellerReviewDirectory = {
    schema_ready: boolean;
    grant_enabled: boolean;
    candidates: Candidate[];
    grants: Grant[];
    candidates_truncated: boolean;
    grants_truncated: boolean;
};

export default function KslpResellerReviewManagement({
    directory,
}: {
    directory: ResellerReviewDirectory;
}) {
    const grantForm = useForm({
        organization_id: '',
        product_id: '',
        reseller_user_id: '',
        days: 30,
        reason: '',
    });
    const revokeForm = useForm({ grant_id: '', reason: '' });
    const selectedPair =
        grantForm.data.product_id + ':' + grantForm.data.reseller_user_id;

    return (
        <>
            <h2 className="text-lg font-black">Reseller review permissions</h2>
            <p className="text-muted-foreground mt-2 text-sm leading-6">
                Assign funding-evidence review to an eligible verified member
                for one application. This never grants license management,
                payment access, wallet credits or paid issuance.
            </p>
            {!directory.schema_ready ? (
                <p className="text-muted-foreground mt-4 text-sm">
                    Review permission storage is unavailable.
                </p>
            ) : (
                <>
                    <div className="mt-4 rounded-xl border p-4">
                        <h3 className="font-semibold">Grant product review</h3>
                        {!directory.grant_enabled ? (
                            <p className="text-muted-foreground mt-2 text-sm">
                                New grants are protected by a disabled rollout
                                gate. Existing permissions can still be revoked.
                            </p>
                        ) : (
                            <form
                                className="mt-3 space-y-3"
                                onSubmit={(event) => {
                                    event.preventDefault();
                                    grantForm.post(
                                        '/operator/kslp/reseller-review/grants',
                                        {
                                            preserveScroll: true,
                                            onSuccess: () => grantForm.reset(),
                                        },
                                    );
                                }}
                            >
                                <label className="block text-sm font-semibold">
                                    Eligible application and member
                                    <select
                                        className="bg-background mt-1 min-h-11 w-full rounded-lg border px-3 text-sm"
                                        value={selectedPair}
                                        onChange={(event) => {
                                            const candidate =
                                                directory.candidates.find(
                                                    (item) =>
                                                        item.product_id +
                                                            ':' +
                                                            item.reseller_user_id ===
                                                        event.target.value,
                                                );
                                            grantForm.setData({
                                                ...grantForm.data,
                                                organization_id:
                                                    candidate?.organization_id ??
                                                    '',
                                                product_id:
                                                    candidate?.product_id ?? '',
                                                reseller_user_id:
                                                    candidate?.reseller_user_id ??
                                                    '',
                                            });
                                        }}
                                    >
                                        <option value=":">
                                            Select a verified member and product
                                        </option>
                                        {directory.candidates.map(
                                            (candidate) => (
                                                <option
                                                    key={
                                                        candidate.product_id +
                                                        ':' +
                                                        candidate.reseller_user_id
                                                    }
                                                    value={
                                                        candidate.product_id +
                                                        ':' +
                                                        candidate.reseller_user_id
                                                    }
                                                >
                                                    {
                                                        candidate.organization_name
                                                    }{' '}
                                                    · {candidate.product_code} ·{' '}
                                                    {candidate.reseller_name} (#
                                                    {candidate.reseller_user_id}
                                                    )
                                                </option>
                                            ),
                                        )}
                                    </select>
                                </label>
                                <label className="block text-sm font-semibold">
                                    Validity in days (1–90)
                                    <input
                                        type="number"
                                        min={1}
                                        max={90}
                                        required
                                        value={grantForm.data.days}
                                        onChange={(event) =>
                                            grantForm.setData(
                                                'days',
                                                Number(event.target.value),
                                            )
                                        }
                                        className="bg-background mt-1 min-h-11 w-full rounded-lg border px-3 text-sm"
                                    />
                                </label>
                                <label className="block text-sm font-semibold">
                                    Reason for authorization
                                    <textarea
                                        required
                                        minLength={8}
                                        maxLength={240}
                                        value={grantForm.data.reason}
                                        onChange={(event) =>
                                            grantForm.setData(
                                                'reason',
                                                event.target.value,
                                            )
                                        }
                                        className="bg-background mt-1 w-full rounded-lg border p-3 text-sm"
                                    />
                                </label>
                                {Object.values(grantForm.errors).map(
                                    (error, index) => (
                                        <p
                                            key={index}
                                            className="text-xs text-red-500"
                                        >
                                            {error}
                                        </p>
                                    ),
                                )}
                                <button
                                    type="submit"
                                    disabled={
                                        grantForm.processing ||
                                        !grantForm.data.product_id ||
                                        grantForm.data.reason.trim().length < 8
                                    }
                                    className="min-h-11 rounded-lg bg-red-600 px-4 text-sm font-bold text-white disabled:opacity-40"
                                >
                                    Grant evidence review only
                                </button>
                            </form>
                        )}
                        {directory.candidates_truncated && (
                            <p className="text-muted-foreground mt-2 text-xs">
                                Only the first 100 eligible pairs are listed.
                            </p>
                        )}
                    </div>
                    <div className="mt-4 space-y-3">
                        <h3 className="font-semibold">Recorded permissions</h3>
                        {directory.grants.length === 0 && (
                            <p className="text-muted-foreground text-sm">
                                No reseller review grants recorded.
                            </p>
                        )}
                        {directory.grants.map((grant) => (
                            <article
                                key={grant.id}
                                className="rounded-xl border p-4"
                            >
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div>
                                        <p className="font-semibold">
                                            {grant.product_name} ·{' '}
                                            {grant.reseller_name}
                                        </p>
                                        <p className="text-muted-foreground mt-1 text-xs">
                                            {grant.organization_name} ·{' '}
                                            {grant.product_code} · member #
                                            {grant.reseller_user_id}
                                        </p>
                                        <p className="text-muted-foreground mt-2 text-xs">
                                            Expires: {grant.expires_at}
                                        </p>
                                        <p className="text-muted-foreground mt-1 text-xs">
                                            {grant.revoked_at
                                                ? 'Revoked: ' + grant.revoked_at
                                                : 'Recorded grant; eligibility is rechecked on every review.'}
                                        </p>
                                    </div>
                                    {!grant.revoked_at && (
                                        <button
                                            type="button"
                                            className="min-h-10 rounded-lg border px-3 text-xs font-bold"
                                            onClick={() => {
                                                revokeForm.clearErrors();
                                                revokeForm.setData({
                                                    grant_id: grant.id,
                                                    reason: '',
                                                });
                                            }}
                                        >
                                            Revoke review
                                        </button>
                                    )}
                                </div>
                                {!grant.revoked_at &&
                                    revokeForm.data.grant_id === grant.id && (
                                        <form
                                            className="mt-3 space-y-3 border-t pt-3"
                                            onSubmit={(event) => {
                                                event.preventDefault();
                                                revokeForm.post(
                                                    '/operator/kslp/reseller-review/grants/' +
                                                        grant.id +
                                                        '/revoke',
                                                    {
                                                        preserveScroll: true,
                                                        onSuccess: () =>
                                                            revokeForm.reset(),
                                                    },
                                                );
                                            }}
                                        >
                                            <label className="block text-sm font-semibold">
                                                Revocation reason
                                                <textarea
                                                    required
                                                    minLength={8}
                                                    maxLength={240}
                                                    value={
                                                        revokeForm.data.reason
                                                    }
                                                    onChange={(event) =>
                                                        revokeForm.setData(
                                                            'reason',
                                                            event.target.value,
                                                        )
                                                    }
                                                    className="bg-background mt-1 w-full rounded-lg border p-3 text-sm"
                                                />
                                            </label>
                                            {revokeForm.errors.reason && (
                                                <p className="text-xs text-red-500">
                                                    {revokeForm.errors.reason}
                                                </p>
                                            )}
                                            <button
                                                type="submit"
                                                disabled={
                                                    revokeForm.processing ||
                                                    revokeForm.data.reason.trim()
                                                        .length < 8
                                                }
                                                className="min-h-11 rounded-lg bg-red-600 px-4 text-sm font-bold text-white disabled:opacity-40"
                                            >
                                                Confirm review revocation
                                            </button>
                                        </form>
                                    )}
                            </article>
                        ))}
                        {directory.grants_truncated && (
                            <p className="text-muted-foreground text-xs">
                                Showing the latest 100 recorded permissions.
                            </p>
                        )}
                    </div>
                </>
            )}
        </>
    );
}
