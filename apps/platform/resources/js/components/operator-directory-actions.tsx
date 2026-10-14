import { Link, router } from '@inertiajs/react';
import { KeyRound, Pencil } from 'lucide-react';
import { useState, type FormEvent } from 'react';

// The Laravel PATCH endpoint enforces passkey ownership, password step-up,
// accepted fields and the audit trail. This UI does not issue any license.
export function DirectoryEditActions({
    kind,
    id,
    name,
}: {
    kind: 'user' | 'organization';
    id: string | number;
    name: string;
}) {
    const [editing, setEditing] = useState(false);
    const [value, setValue] = useState(name);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState('');

    const cancel = () => {
        setValue(name);
        setEditing(false);
        setMessage('');
    };

    const save = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        const updated = value.trim();
        if (saving || updated.length < 2) return;

        const segment = kind === 'user' ? 'users' : 'organizations';
        const url =
            '/operator/directory/' +
            segment +
            '/' +
            encodeURIComponent(String(id));

        router.patch(
            url,
            { name: updated },
            {
                preserveScroll: true,
                onStart: () => setSaving(true),
                onSuccess: () => {
                    setMessage('Saved');
                    setEditing(false);
                },
                onError: (errors) =>
                    setMessage(errors.name ?? 'Update was not saved.'),
                onFinish: () => setSaving(false),
            },
        );
    };

    return (
        <div className="mt-2 flex flex-wrap items-center gap-2">
            {editing ? (
                <form
                    onSubmit={save}
                    className="flex flex-wrap items-center gap-2"
                >
                    <label
                        className="sr-only"
                        htmlFor={'edit-' + kind + '-' + id}
                    >
                        Display name
                    </label>
                    <input
                        id={'edit-' + kind + '-' + id}
                        autoFocus
                        required
                        minLength={2}
                        maxLength={kind === 'user' ? 120 : 160}
                        value={value}
                        onChange={(event) => setValue(event.target.value)}
                        className="min-h-10 min-w-36 rounded-lg border border-white/25 bg-[#080b10] px-3 text-sm text-white"
                    />
                    <button
                        type="submit"
                        disabled={saving || value.trim().length < 2}
                        className="min-h-9 rounded-lg bg-red-600 px-3 py-1 text-xs font-semibold disabled:opacity-50"
                    >
                        {saving ? 'Saving…' : 'Save'}
                    </button>
                    <button
                        type="button"
                        onClick={cancel}
                        disabled={saving}
                        className="min-h-9 rounded-lg border border-white/20 px-3 py-1 text-xs font-semibold"
                    >
                        Cancel
                    </button>
                </form>
            ) : (
                <button
                    type="button"
                    onClick={() => {
                        setValue(name);
                        setMessage('');
                        setEditing(true);
                    }}
                    aria-label={'Edit ' + kind + ' ' + name}
                    className="inline-flex min-h-9 items-center gap-1 rounded-lg border border-white/20 px-2.5 py-1 text-xs font-semibold text-slate-200 hover:bg-white/10"
                >
                    <Pencil className="size-3.5" aria-hidden="true" /> Edit
                </button>
            )}
            {kind === 'organization' && (
                <>
                    <Link
                        href={
                            '/operator/kslp?customer_id=' +
                            encodeURIComponent(String(id))
                        }
                        className="inline-flex min-h-9 items-center gap-1 rounded-lg border border-amber-500/30 px-2.5 py-1 text-xs font-semibold text-amber-100 hover:bg-amber-500/10"
                    >
                        <KeyRound className="size-3.5" aria-hidden="true" />{' '}
                        CloudOS licenses
                    </Link>
                    <Link
                        href="/operator"
                        className="inline-flex min-h-9 items-center rounded-lg border border-white/20 px-2.5 py-1 text-xs font-semibold text-slate-200 hover:bg-white/10"
                    >
                        Products &amp; access
                    </Link>
                </>
            )}
            {message && (
                <span role="status" className="text-xs text-blue-200">
                    {message}
                </span>
            )}
        </div>
    );
}
