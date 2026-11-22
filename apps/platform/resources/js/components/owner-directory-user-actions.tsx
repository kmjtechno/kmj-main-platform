import { router } from '@inertiajs/react';
import { Pencil, Trash2 } from 'lucide-react';
import { useState, type FormEvent } from 'react';

type ManagedUser = {
    id: number;
    name: string;
    email: string;
    is_platform_owner: boolean;
    customer_profile: {
        phone: string;
        country: string;
        company_name: string | null;
        service_interest: string | null;
    } | null;
};

export default function OwnerDirectoryUserActions({
    user,
}: {
    user: ManagedUser;
}) {
    const [name, setName] = useState(user.name);
    const [phone, setPhone] = useState(user.customer_profile?.phone ?? '');
    const [country, setCountry] = useState(
        user.customer_profile?.country ?? '',
    );
    const [company, setCompany] = useState(
        user.customer_profile?.company_name ?? '',
    );
    const [deletePhrase, setDeletePhrase] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    if (user.is_platform_owner) {
        return null;
    }

    const save = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setBusy(true);
        setError('');
        router.patch(
            '/operator/directory/users/' + user.id + '/contact',
            {
                name,
                ...(user.customer_profile
                    ? { phone, country, company_name: company }
                    : {}),
            },
            {
                preserveScroll: true,
                onError: (errors) => setError(Object.values(errors).join(' ')),
                onFinish: () => setBusy(false),
            },
        );
    };

    const remove = () => {
        if (busy || deletePhrase !== 'DELETE ' + user.email) return;
        setBusy(true);
        setError('');
        router.post(
            '/operator/directory/users/' + user.id + '/delete',
            { confirmation: 'DELETE_USER_' + user.id },
            {
                preserveScroll: true,
                onError: (errors) => setError(Object.values(errors).join(' ')),
                onFinish: () => setBusy(false),
            },
        );
    };

    return (
        <div className="w-full space-y-2">
            <details className="rounded-xl border border-white/15 p-3">
                <summary className="flex cursor-pointer items-center gap-2 text-xs font-semibold">
                    <Pencil className="size-4" aria-hidden="true" />
                    Edit contact
                </summary>
                <form
                    onSubmit={save}
                    aria-label="Edit account contact"
                    className="mt-3 grid gap-3 sm:grid-cols-2"
                >
                    <p className="text-muted-foreground text-xs sm:col-span-2">
                        Email, verification and privileges are not editable
                        here.
                    </p>
                    <label className="text-xs">
                        Name
                        <input
                            required
                            minLength={2}
                            maxLength={120}
                            value={name}
                            onChange={(event) => setName(event.target.value)}
                            className="bg-background mt-1 w-full rounded-lg border p-2"
                        />
                    </label>
                    {user.customer_profile && (
                        <>
                            <label className="text-xs">
                                Phone
                                <input
                                    required
                                    maxLength={32}
                                    value={phone}
                                    onChange={(event) =>
                                        setPhone(event.target.value)
                                    }
                                    className="bg-background mt-1 w-full rounded-lg border p-2"
                                />
                            </label>
                            <label className="text-xs">
                                Country
                                <input
                                    required
                                    maxLength={80}
                                    value={country}
                                    onChange={(event) =>
                                        setCountry(event.target.value)
                                    }
                                    className="bg-background mt-1 w-full rounded-lg border p-2"
                                />
                            </label>
                            <label className="text-xs">
                                Company
                                <input
                                    maxLength={160}
                                    value={company}
                                    onChange={(event) =>
                                        setCompany(event.target.value)
                                    }
                                    className="bg-background mt-1 w-full rounded-lg border p-2"
                                />
                            </label>
                        </>
                    )}
                    <button
                        type="submit"
                        disabled={busy}
                        className="rounded-lg bg-red-600 px-4 py-2 text-xs font-bold disabled:opacity-50 sm:col-span-2"
                    >
                        Save contact changes
                    </button>
                </form>
            </details>
            <details className="rounded-xl border border-red-500/30 p-3">
                <summary className="flex cursor-pointer items-center gap-2 text-xs text-red-300">
                    <Trash2 className="size-4" aria-hidden="true" />
                    Review deletion
                </summary>
                <p className="mt-3 text-xs text-red-200">
                    Linked organizations, purchases, licenses and audit records
                    block deletion. To delete a standalone account type
                    <strong> DELETE {user.email}</strong>.
                </p>
                <input
                    value={deletePhrase}
                    onChange={(event) => setDeletePhrase(event.target.value)}
                    aria-label="Type account deletion confirmation"
                    className="bg-background mt-3 w-full rounded-lg border p-2 text-xs"
                />
                <button
                    type="button"
                    disabled={busy || deletePhrase !== 'DELETE ' + user.email}
                    onClick={remove}
                    className="mt-3 rounded-lg bg-red-600 px-4 py-2 text-xs font-bold disabled:opacity-50"
                >
                    Permanently delete standalone account
                </button>
            </details>
            {error && (
                <p className="text-xs text-red-300" role="alert">
                    {error}
                </p>
            )}
        </div>
    );
}
