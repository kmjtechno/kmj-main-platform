import { Head, Link, router } from '@inertiajs/react';
import { Building2, Pencil, Search, ShieldCheck, Trash2, Users } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import OperatorModuleNavigation from '@/components/operator-module-navigation';

type PageLink = { url: string | null; label: string; active: boolean };
type Paginated<T> = {
    data: T[];
    current_page: number;
    last_page: number;
    total: number;
    from: number | null;
    to: number | null;
    links: PageLink[];
};
type CustomerContact = {
    account_type: 'individual' | 'business';
    phone: string;
    country: string;
    company_name: string | null;
    service_interest: string | null;
};

type DirectoryUser = {
    customer_profile: CustomerContact | null;
    id: number;
    name: string;
    email: string;
    email_verified_at: string | null;
    created_at: string | null;
    is_platform_owner: boolean;
};
type DirectoryOrganization = {
    id: string;
    name: string;
    memberships_count: number;
    created_at: string | null;
};
type Props = {
    users: Paginated<DirectoryUser>;
    organizations: Paginated<DirectoryOrganization>;
    filters: { users_q: string; orgs_q: string };
    read_only: boolean;
};

function Pager({ data }: { data: Paginated<unknown> }) {
    if (data.last_page <= 1) return null;
    return (
        <nav
            aria-label="Results pagination"
            className="mt-5 flex flex-wrap items-center gap-2"
        >
            {data.links.map((link, index) =>
                link.url ? (
                    <Link
                        key={index}
                        href={link.url}
                        preserveScroll
                        preserveState
                        aria-current={link.active ? 'page' : undefined}
                        className={[
                            'rounded-lg border px-3 py-2 text-xs font-semibold',
                            link.active
                                ? 'border-red-500/50 bg-red-500/10 text-red-300'
                                : 'border-border text-muted-foreground hover:bg-accent',
                        ].join(' ')}
                    >
                        {index === 0
                            ? 'Previous'
                            : index === data.links.length - 1
                              ? 'Next'
                              : link.label}
                    </Link>
                ) : (
                    <span
                        key={index}
                        className="border-border/50 text-muted-foreground rounded-lg border px-3 py-2 text-xs"
                    >
                        {index === 0
                            ? 'Previous'
                            : index === data.links.length - 1
                              ? 'Next'
                              : link.label}
                    </span>
                ),
            )}
        </nav>
    );
}

export default function OperatorDirectory({
    users,
    organizations,
    filters,
}: Props) {
    const [usersQuery, setUsersQuery] = useState(filters.users_q);
    const [orgsQuery, setOrgsQuery] = useState(filters.orgs_q);
    const [editing, setEditing] = useState<number | null>(null);
    const [deleting, setDeleting] = useState<number | null>(null);
    const [deletePhrase, setDeletePhrase] = useState('');
    const [actionError, setActionError] = useState('');
    const [saving, setSaving] = useState(false);
    const [form, setForm] = useState({
        name: '',
        phone: '',
        country: '',
        company_name: '',
        service_interest: '',
    });

    const editUser = (user: DirectoryUser) => {
        setEditing(user.id);
        setDeleting(null);
        setActionError('');
        setForm({
            name: user.name,
            phone: user.customer_profile?.phone ?? '',
            country: user.customer_profile?.country ?? '',
            company_name: user.customer_profile?.company_name ?? '',
            service_interest: user.customer_profile?.service_interest ?? '',
        });
    };

    const saveUser = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (editing === null) return;
        setSaving(true);
        setActionError('');
        router.patch('/operator/directory/users/' + editing + '/contact', form, {
            preserveScroll: true,
            onSuccess: () => setEditing(null),
            onError: (errors) => setActionError(Object.values(errors).join(' ')),
            onFinish: () => setSaving(false),
        });
    };

    const deleteUser = (user: DirectoryUser) => {
        if (deletePhrase !== 'DELETE ' + user.email || saving) return;
        setSaving(true);
        setActionError('');
        router.post(
            '/operator/directory/users/' + user.id + '/delete',
            { confirmation: 'DELETE_USER_' + user.id },
            {
                preserveScroll: true,
                onSuccess: () => { setDeleting(null); setDeletePhrase(''); },
                onError: (errors) => setActionError(Object.values(errors).join(' ')),
                onFinish: () => setSaving(false),
            },
        );
    };


    const search = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        router.get(
            '/operator/directory',
            { users_q: usersQuery.trim(), orgs_q: orgsQuery.trim() },
            { preserveState: true, preserveScroll: true, replace: true },
        );
    };

    return (
        <>
            <Head title="KMJ TECHNO — Customer Accounts & Organizations" />
            <main className="owner-admin-page kmj-admin-shell flex min-w-0 flex-1 flex-col gap-6 p-4 sm:p-6 lg:p-8">
                <div className="w-full">
                    <OperatorModuleNavigation active="customers" />
                </div>
                <header className="owner-admin-hero kmj-admin-hero w-full rounded-[1.65rem] p-6 sm:p-8">
                    <div className="flex flex-wrap items-center gap-3">
                        <Users
                            className="size-8 text-red-400"
                            aria-hidden="true"
                        />
                        <h1 className="text-2xl font-black sm:text-3xl">
                            Users & Organizations
                        </h1>
                    </div>
                    <p className="text-muted-foreground mt-3 max-w-3xl text-sm leading-7">
                        Review verified identities, signup contact details and
                        customer organizations from one owner-only workspace.
                        Contact fields appear only when customers supplied them.
                        Contact details can be updated by the passkey-verified owner.
                        Deletion is limited to standalone accounts; linked
                        organizations, licenses and audit history are protected.
                    </p>
                    <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-blue-500/20 px-3 py-1.5 text-xs font-bold text-blue-200">
                        <ShieldCheck className="size-4" aria-hidden="true" />
                        Owner only · Password-confirmed actions
                    </div>
                </header>

                <form
                    onSubmit={search}
                    className="bg-card grid w-full gap-3 rounded-2xl border border-white/10 p-5 md:grid-cols-[1fr_1fr_auto] md:items-end"
                >
                    <label className="text-muted-foreground space-y-2 text-xs font-semibold">
                        <span>
                            Search name, email, company, country or phone
                        </span>
                        <input
                            className="bg-background/50 w-full rounded-xl border border-white/20 px-4 py-3 text-sm text-white"
                            value={usersQuery}
                            onChange={(event) =>
                                setUsersQuery(event.target.value)
                            }
                            maxLength={80}
                            placeholder="Name, email, business, phone or country"
                        />
                    </label>
                    <label className="text-muted-foreground space-y-2 text-xs font-semibold">
                        <span>Search organizations</span>
                        <input
                            className="bg-background/50 w-full rounded-xl border border-white/20 px-4 py-3 text-sm text-white"
                            value={orgsQuery}
                            onChange={(event) =>
                                setOrgsQuery(event.target.value)
                            }
                            maxLength={80}
                            placeholder="Organization name"
                        />
                    </label>
                    <button className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-red-600 px-5 py-3 text-sm font-bold hover:bg-red-500">
                        <Search className="size-4" aria-hidden="true" />
                        Search
                    </button>
                </form>

                <div className="grid w-full gap-6 xl:grid-cols-2">
                    <section
                        aria-label="Platform users"
                        className="bg-card min-w-0 rounded-2xl border border-white/10 p-5"
                    >
                        <h2 className="flex items-center gap-2 text-xl font-bold">
                            <Users
                                className="size-5 text-red-400"
                                aria-hidden="true"
                            />
                            Users{' '}
                            <span className="text-muted-foreground text-sm font-normal">
                                ({users.total})
                            </span>
                        </h2>
                        {users.data.length === 0 ? (
                            <p className="text-muted-foreground mt-5 rounded-xl border border-dashed border-white/15 p-5 text-sm">
                                No users match this search.
                            </p>
                        ) : (
                            <div className="mt-4 divide-y divide-white/10">
                                {users.data.map((user) => (
                                    <div
                                        key={user.id}
                                        className="flex flex-wrap items-start justify-between gap-3 py-4"
                                    >
                                        <div className="min-w-0">
                                            <p className="font-semibold">
                                                {user.name}
                                            </p>
                                            <p className="text-muted-foreground mt-1 text-xs break-all">
                                                {user.email}
                                            </p>
                                            {user.customer_profile && (
                                                <dl className="mt-3 grid gap-x-5 gap-y-2 text-xs sm:grid-cols-2">
                                                    <div className="min-w-0">
                                                        <dt className="text-muted-foreground">
                                                            Account
                                                        </dt>
                                                        <dd className="mt-1 font-medium capitalize">
                                                            {
                                                                user
                                                                    .customer_profile
                                                                    .account_type
                                                            }
                                                        </dd>
                                                    </div>
                                                    <div className="min-w-0">
                                                        <dt className="text-muted-foreground">
                                                            Country
                                                        </dt>
                                                        <dd className="mt-1 break-words">
                                                            {
                                                                user
                                                                    .customer_profile
                                                                    .country
                                                            }
                                                        </dd>
                                                    </div>
                                                    <div className="min-w-0">
                                                        <dt className="text-muted-foreground">
                                                            Contact phone
                                                        </dt>
                                                        <dd className="mt-1 break-all">
                                                            {
                                                                user
                                                                    .customer_profile
                                                                    .phone
                                                            }
                                                        </dd>
                                                    </div>
                                                    {user.customer_profile
                                                        .company_name && (
                                                        <div className="min-w-0">
                                                            <dt className="text-muted-foreground">
                                                                Company
                                                            </dt>
                                                            <dd className="mt-1 break-words">
                                                                {
                                                                    user
                                                                        .customer_profile
                                                                        .company_name
                                                                }
                                                            </dd>
                                                        </div>
                                                    )}
                                                    {user.customer_profile
                                                        .service_interest && (
                                                        <div className="min-w-0">
                                                            <dt className="text-muted-foreground">
                                                                Service interest
                                                            </dt>
                                                            <dd className="mt-1 break-words">
                                                                {user.customer_profile.service_interest.replaceAll(
                                                                    '_',
                                                                    ' ',
                                                                )}
                                                            </dd>
                                                        </div>
                                                    )}
                                                </dl>
                                            )}
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className="text-muted-foreground rounded-full border border-white/15 px-2.5 py-1 text-[11px]">
                                                {user.is_platform_owner
                                                    ? 'Platform owner'
                                                    : user.email_verified_at
                                                      ? 'Verified user'
                                                      : 'Email unverified'}
                                            </span>
                                            {!user.is_platform_owner && (
                                                <>
                                                    <button
                                                        type="button"
                                                        onClick={() => editUser(user)}
                                                        className="inline-flex items-center gap-1 rounded-lg border border-white/20 px-3 py-1.5 text-xs hover:bg-white/10"
                                                        aria-label={'Edit ' + user.name}
                                                    >
                                                        <Pencil className="size-3.5" /> Edit
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            setDeleting(user.id);
                                                            setEditing(null);
                                                            setDeletePhrase('');
                                                            setActionError('');
                                                        }}
                                                        className="inline-flex items-center gap-1 rounded-lg border border-red-500/40 px-3 py-1.5 text-xs text-red-300 hover:bg-red-500/10"
                                                        aria-label={'Review deletion of ' + user.name}
                                                    >
                                                        <Trash2 className="size-3.5" /> Delete
                                                    </button>
                                                </>
                                            )}
                                        </div>
                                        {editing === user.id && (
                                            <form onSubmit={saveUser} className="w-full rounded-xl border border-white/15 p-4" aria-label="Edit account contact">
                                                <p className="mb-3 text-xs text-muted-foreground">Email and verified status are read-only. Identity changes require a separate verification workflow.</p>
                                                <div className="grid gap-3 sm:grid-cols-2">
                                                    <label className="text-xs">Name
                                                        <input required maxLength={120} minLength={2} value={form.name} onChange={(e) => setForm({...form, name:e.target.value})} className="mt-1 w-full rounded-lg border bg-background p-2" />
                                                    </label>
                                                    {user.customer_profile && (
                                                        <>
                                                            <label className="text-xs">Phone
                                                                <input maxLength={32} value={form.phone} onChange={(e) => setForm({...form, phone:e.target.value})} className="mt-1 w-full rounded-lg border bg-background p-2" />
                                                            </label>
                                                            <label className="text-xs">Country
                                                                <input maxLength={80} value={form.country} onChange={(e) => setForm({...form, country:e.target.value})} className="mt-1 w-full rounded-lg border bg-background p-2" />
                                                            </label>
                                                            <label className="text-xs">Company
                                                                <input maxLength={160} value={form.company_name} onChange={(e) => setForm({...form, company_name:e.target.value})} className="mt-1 w-full rounded-lg border bg-background p-2" />
                                                            </label>
                                                        </>
                                                    )}
                                                </div>
                                                <div className="mt-3 flex gap-2">
                                                    <button type="submit" disabled={saving} className="rounded-lg bg-red-600 px-4 py-2 text-xs font-bold disabled:opacity-50">Save changes</button>
                                                    <button type="button" onClick={() => setEditing(null)} className="rounded-lg border px-4 py-2 text-xs">Cancel</button>
                                                </div>
                                            </form>
                                        )}
                                        {deleting === user.id && (
                                            <div className="w-full rounded-xl border border-red-500/40 p-4" role="group" aria-label="Confirm account deletion">
                                                <p className="text-xs text-red-200">Permanent deletion requires a standalone account with no organization, license, purchase, identity grants or audit links. Linked accounts are blocked. Type <strong>DELETE {user.email}</strong> to confirm.</p>
                                                <input value={deletePhrase} onChange={(e) => setDeletePhrase(e.target.value)} aria-label="Type deletion confirmation" className="mt-3 w-full rounded-lg border bg-background p-2 text-xs" />
                                                <div className="mt-3 flex gap-2">
                                                    <button type="button" disabled={saving || deletePhrase !== 'DELETE ' + user.email} onClick={() => deleteUser(user)} className="rounded-lg bg-red-600 px-4 py-2 text-xs font-bold disabled:opacity-50">Delete standalone account</button>
                                                    <button type="button" onClick={() => setDeleting(null)} className="rounded-lg border px-4 py-2 text-xs">Cancel</button>
                                                </div>
                                            </div>
                                        )}
                                        {actionError && (editing === user.id || deleting === user.id) && (
                                            <p className="w-full text-xs text-red-300" role="alert">{actionError}</p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                        <Pager data={users} />
                    </section>
                    <section
                        aria-label="Customer organizations"
                        className="bg-card min-w-0 rounded-2xl border border-white/10 p-5"
                    >
                        <h2 className="flex items-center gap-2 text-xl font-bold">
                            <Building2
                                className="size-5 text-red-400"
                                aria-hidden="true"
                            />
                            Organizations{' '}
                            <span className="text-muted-foreground text-sm font-normal">
                                ({organizations.total})
                            </span>
                        </h2>
                        {organizations.data.length === 0 ? (
                            <p className="text-muted-foreground mt-5 rounded-xl border border-dashed border-white/15 p-5 text-sm">
                                No organizations match this search.
                            </p>
                        ) : (
                            <div className="mt-4 divide-y divide-white/10">
                                {organizations.data.map((org) => (
                                    <div
                                        key={org.id}
                                        className="flex flex-wrap items-start justify-between gap-3 py-4"
                                    >
                                        <div className="min-w-0">
                                            <p className="font-semibold">
                                                {org.name}
                                            </p>
                                            <p className="text-muted-foreground mt-1 font-mono text-[11px] break-all">
                                                {org.id}
                                            </p>
                                        </div>
                                        <span className="text-muted-foreground rounded-full border border-white/15 px-2.5 py-1 text-[11px]">
                                            {org.memberships_count} members
                                        </span>
                                    </div>
                                ))}
                            </div>
                        )}
                        <Pager data={organizations} />
                    </section>
                </div>
            </main>
        </>
    );
}
