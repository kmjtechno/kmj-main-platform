import { Link, router } from '@inertiajs/react';
import { KeyRound, Pencil } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';

// An owner-only view delegates authorization to the Laravel PATCH endpoints.
// Never send email, owner flags, permissions or license changes from here.
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

    useEffect(() => {
        if (!editing) setValue(name);
    }, [editing, name]);

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
        router.patch('/operator/directory/' + segment + '/' + encodeURIComponent(String(id)), {
            name: updated,
        }, {
            preserveScroll: true,
            onStart: () => setSaving(true),
            onSuccess: () => {
                setMessage('Saved');
                setEditing(false);
            },
            onError: (errors) => setMessage(errors.name ?? 'Update was not saved.'),
            onFinish: () => setSaving(false),
        });
    };

    return (
        <div className="mt-2 flex flex-wrap items-center gap-2">
            {editing ? (
                <form onSubmit={save} className="flex flex-wrap items-center gap-2">
                    <label className="sr-only" htmlFor={'edit-' + kind + '-' + id}>Display name</label>
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
                    <button type="submit" disabled={saving || value.trim().length < 2}
                        className="min-h-9 rounded-lg bg-red-600 px-3 py-1 text-xs font-semibold disabled:opacity-50">
                        {saving ? 'Saving…' : 'Save'}
                    </button>
                    <button type="button" onClick={cancel} disabled={saving}
                        className="min-h-9 rounded-lg border border-white/20 px-3 py-1 text-xs font-semibold">
                        Cancel
                    </button>
                </form>
            ) : (
                <button type="button" onClick={() => { setMessage(''); setEditing(true); }}
                    aria-label={'Edit ' + kind + ' ' + name}
                    className="inline-flex min-h-9 items-center gap-1 rounded-lg border border-white/20 px-2.5 py-1 text-xs font-semibold text-slate-200 hover:bg-white/10">
                    <Pencil className="size-3.5" aria-hidden="true" /> Edit
                </button>
            )}
            {kind === 'organization' && (
                <Link href={'/operator/kslp?customer_id=' + encodeURIComponent(String(id))}
                    className="inline-flex min-h-9 items-center gap-1 rounded-lg border border-amber-500/30 px-2.5 py-1 text-xs font-semibold text-amber-100 hover:bg-amber-500/10">
                    <KeyRound className="size-3.5" aria-hidden="true" /> CloudOS licenses
                </Link>
            )}
            {message && <span role="status" className="text-xs text-blue-200">{message}</span>}
        </div>
    );
}
