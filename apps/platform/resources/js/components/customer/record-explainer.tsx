import { Link } from '@inertiajs/react';

const records = [
    {
        title: 'Purchase request',
        detail: 'You asked to buy a product. It is not a license and it switches nothing on by itself.',
        href: '/purchase',
        action: 'Purchase Center',
    },
    {
        title: 'License',
        detail: 'A dated permission for one product, with a plan and an expiry date.',
        href: '/licensing#my-licenses',
        action: 'My licenses',
    },
    {
        title: 'Product access',
        detail: 'Features and downloads switched on for your organization. This is what appears under your products.',
        href: '/dashboard',
        action: 'My Services',
    },
] as const;

/** One shared explanation, so every customer page uses the same three words. */
export function RecordExplainer() {
    return (
        <section
            aria-labelledby="record-explainer-heading"
            className="bg-card rounded-2xl border p-5 sm:p-6"
        >
            <h2 id="record-explainer-heading" className="font-bold">
                Purchase, license and product access
            </h2>
            <p className="text-muted-foreground mt-1 text-sm">
                These are three separate records, so you can have one without
                the others.
            </p>
            <dl className="mt-4 grid gap-4 md:grid-cols-3">
                {records.map((record) => (
                    <div key={record.title} className="min-w-0">
                        <dt className="text-sm font-bold">{record.title}</dt>
                        <dd className="text-muted-foreground mt-1 text-sm leading-6">
                            {record.detail}
                            <Link
                                href={record.href}
                                className="mt-1 flex min-h-11 items-center font-semibold text-red-600 hover:underline dark:text-red-400"
                            >
                                {record.action}
                            </Link>
                        </dd>
                    </div>
                ))}
            </dl>
        </section>
    );
}
