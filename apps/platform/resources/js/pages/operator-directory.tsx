import { Head, Link, router } from '@inertiajs/react';
import { Building2, Search, ShieldCheck, Users } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import OwnerDirectoryUserActions from '@/components/owner-directory-user-actions';
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
    filters: { users_q: string; users_status: string; orgs_q: string };
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
    const [usersStatus, setUsersStatus] = useState(
        filters.users_status ?? 'all',
    );
    const [orgsQuery, setOrgsQuery] = useState(filters.orgs_q);
    const [selectedIds, setSelectedIds] = useState<number[]>([]);
    const [bulkBusy, setBulkBusy] = useState(false);
    const [bulkError, setBulkError] = useState('');
    // Deliberately select visible page records only, never all filtered users.
    const visibleIds = users.data
        .filter((user) => !user.is_platform_owner)
        .map((user) => user.id);
    const selectedVisibleIds = selectedIds.filter((id) =>
        visibleIds.includes(id),
    );
    const everyVisibleSelected =
        visibleIds.length > 0 &&
        visibleIds.every((id) => selectedVisibleIds.includes(id));

    const togglePageSelection = (checked: boolean) => {
        setSelectedIds(checked ? visibleIds : []);
    };

    const toggleSelected = (id: number) => {
        setSelectedIds((current) => {
            const visible = current.filter((item) => visibleIds.includes(item));
            return visible.includes(id)
                ? visible.filter((item) => item !== id)
                : [...visible, id];
        });
    };

    const deleteSelected = () => {
        if (bulkBusy || selectedVisibleIds.length === 0) {
            return;
        }
        const ids = [...selectedVisibleIds].sort((a, b) => a - b);
        const prompt = [
            `Delete ${ids.length} selected customer(s) and their private signup data?`,
            'This cannot be undone. If any account is protected, no selected account is deleted.',
        ].join(' ');
        if (!window.confirm(prompt)) {
            return;
        }

        setBulkBusy(true);
        setBulkError('');
        const options = {
            preserveScroll: true,
            onSuccess: () => setSelectedIds([]),
            onError: (errors: Record<string, string>) =>
                setBulkError(Object.values(errors).join(' ')),
            onFinish: () => setBulkBusy(false),
        };
        if (ids.length === 1) {
            router.post(
                '/operator/directory/users/' + ids[0] + '/delete',
                { confirmation: 'DELETE_USER_' + ids[0] },
                options,
            );
        } else {
            router.post(
                '/operator/directory/users/bulk-delete',
                { user_ids: ids },
                options,
            );
        }
    };

    const search = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        router.get(
            '/operator/directory',
            {
                users_q: usersQuery.trim(),
                users_status: usersStatus,
                orgs_q: orgsQuery.trim(),
            },
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
                        Contact details can be updated by the passkey-verified
                        owner. Private signup accounts and their exclusive empty
                        organizations may be deleted; shared organizations,
                        licenses, payments and audit records are protected.
                    </p>
                    <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-blue-500/20 px-3 py-1.5 text-xs font-bold text-blue-200">
                        <ShieldCheck className="size-4" aria-hidden="true" />
                        Owner only · Password-confirmed actions
                    </div>
                </header>

                <form
                    onSubmit={search}
                    className="bg-card grid w-full gap-3 rounded-2xl border border-white/10 p-5 md:grid-cols-[1fr_1fr_12rem_auto] md:items-end"
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
                    <label className="text-muted-foreground space-y-2 text-xs font-semibold">
                        <span>Email verification</span>
                        <select
                            className="bg-background/50 w-full rounded-xl border border-white/20 px-4 py-3 text-sm text-white"
                            value={usersStatus}
                            onChange={(event) =>
                                setUsersStatus(event.target.value)
                            }
                            aria-label="Filter email verification"
                        >
                            <option value="all">All users</option>
                            <option value="verified">Verified</option>
                            <option value="unverified">Unverified</option>
                        </select>
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
                        <div className="bg-background/40 mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-white/10 p-3">
                            <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-semibold">
                                <input
                                    type="checkbox"
                                    checked={everyVisibleSelected}
                                    disabled={
                                        bulkBusy || visibleIds.length === 0
                                    }
                                    aria-label="Select all customers on this page"
                                    onChange={(event) =>
                                        togglePageSelection(
                                            event.target.checked,
                                        )
                                    }
                                    className="size-4 accent-red-500"
                                />
                                Select page ({visibleIds.length})
                            </label>
                            <span className="text-muted-foreground text-xs">
                                {selectedVisibleIds.length} selected
                            </span>
                            <button
                                type="button"
                                disabled={
                                    bulkBusy || selectedVisibleIds.length === 0
                                }
                                onClick={deleteSelected}
                                className="ml-auto min-h-10 rounded-lg bg-red-600 px-4 py-2 text-xs font-bold text-white hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                {bulkBusy
                                    ? 'Deleting...'
                                    : `Delete selected (${selectedVisibleIds.length})`}
                            </button>
                            <p className="text-muted-foreground w-full text-xs">
                                Only checked customers on this page. One
                                confirmation; protected accounts block the
                                entire selection.
                            </p>
                            {bulkError && (
                                <p
                                    role="alert"
                                    className="w-full text-xs text-red-300"
                                >
                                    {bulkError}
                                </p>
                            )}
                        </div>
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
                                        {!user.is_platform_owner && (
                                            <label className="inline-flex min-h-8 items-center gap-2 text-xs">
                                                <input
                                                    type="checkbox"
                                                    checked={selectedVisibleIds.includes(
                                                        user.id,
                                                    )}
                                                    disabled={bulkBusy}
                                                    onChange={() =>
                                                        toggleSelected(user.id)
                                                    }
                                                    aria-label={
                                                        'Select customer ' +
                                                        user.name
                                                    }
                                                    className="size-4 accent-red-500"
                                                />
                                                Select
                                            </label>
                                        )}
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
                                        </div>
                                        <OwnerDirectoryUserActions
                                            user={user}
                                        />
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
