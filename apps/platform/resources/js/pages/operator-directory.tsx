import { Head, Link, router } from '@inertiajs/react';
import { Building2, Search, ShieldCheck, Users } from 'lucide-react';
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
    read_only: true;
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
            <main className="kmj-admin-shell min-h-screen space-y-6 p-4 sm:p-8">
                <div className="mx-auto max-w-7xl">
                    <OperatorModuleNavigation active="customers" />
                </div>
                <header className="kmj-admin-hero mx-auto max-w-7xl rounded-[1.65rem] p-6 sm:p-8">
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
                        This module cannot grant permissions, licenses or
                        account invitations.
                    </p>
                    <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-blue-500/20 px-3 py-1.5 text-xs font-bold text-blue-200">
                        <ShieldCheck className="size-4" aria-hidden="true" />
                        Owner only · Read-only
                    </div>
                </header>

                <form
                    onSubmit={search}
                    className="bg-card mx-auto grid max-w-7xl gap-3 rounded-2xl border border-white/10 p-5 md:grid-cols-[1fr_1fr_auto] md:items-end"
                >
                    <label className="text-muted-foreground space-y-2 text-xs font-semibold">
                        <span>Search name, email, company, country or phone</span>
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

                <div className="mx-auto grid max-w-7xl gap-6 xl:grid-cols-2">
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
                                                        <dt className="text-muted-foreground">Account</dt>
                                                        <dd className="mt-1 font-medium capitalize">
                                                            {user.customer_profile.account_type}
                                                        </dd>
                                                    </div>
                                                    <div className="min-w-0">
                                                        <dt className="text-muted-foreground">Country</dt>
                                                        <dd className="mt-1 break-words">
                                                            {user.customer_profile.country}
                                                        </dd>
                                                    </div>
                                                    <div className="min-w-0">
                                                        <dt className="text-muted-foreground">Contact phone</dt>
                                                        <dd className="mt-1 break-all">
                                                            {user.customer_profile.phone}
                                                        </dd>
                                                    </div>
                                                    {user.customer_profile.company_name && (
                                                        <div className="min-w-0">
                                                            <dt className="text-muted-foreground">Company</dt>
                                                            <dd className="mt-1 break-words">
                                                                {user.customer_profile.company_name}
                                                            </dd>
                                                        </div>
                                                    )}
                                                    {user.customer_profile.service_interest && (
                                                        <div className="min-w-0">
                                                            <dt className="text-muted-foreground">Service interest</dt>
                                                            <dd className="mt-1 break-words">
                                                                {user.customer_profile.service_interest.replaceAll('_', ' ')}
                                                            </dd>
                                                        </div>
                                                    )}
                                                </dl>
                                            )}
                                        </div>
                                        <span className="text-muted-foreground rounded-full border border-white/15 px-2.5 py-1 text-[11px]">
                                            {user.is_platform_owner
                                                ? 'Platform owner'
                                                : user.email_verified_at
                                                  ? 'Verified user'
                                                  : 'Email unverified'}
                                        </span>
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
