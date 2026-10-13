import { Head, Link } from '@inertiajs/react';
import { useMemo, useState } from 'react';
import { ArrowLeft, Boxes, Search, ShieldCheck, Plus, ListFilter } from 'lucide-react';
import OperatorModuleNavigation from '@/components/operator-module-navigation';
import {
    CommercialProductForm,
    ProductManager,
    productCategoryOptions,
    type ManagedProduct,
} from '@/components/operator-product-manager';

export default function OperatorProducts({ products }: { products: ManagedProduct[] }) {
    const [search, setSearch] = useState('');
    const [category, setCategory] = useState('all');
    const [lifecycle, setLifecycle] = useState('all');
    const [creating, setCreating] = useState(false);
    const totals = useMemo(() => ({
        public: products.filter((p) => p.is_public).length,
        purchasable: products.filter((p) => p.purchase_enabled).length,
        licensable: products.filter((p) => p.licensing_enabled).length,
    }), [products]);
    const shown = products.filter((product) =>
        (category === 'all' || product.category === category) &&
        (lifecycle === 'all' || product.lifecycle === lifecycle) &&
        `${product.name} ${product.slug} ${product.summary ?? ''}`
            .toLowerCase().includes(search.trim().toLowerCase()),
    ).length;

    return (
        <>
            <Head title="Product Management · Super Admin" />
            <main className="flex min-w-0 flex-1 flex-col gap-5 p-4 sm:p-6">
                <OperatorModuleNavigation active="products" />
                <header className="rounded-2xl border bg-card p-5 sm:p-7">
                    <Link href="/operator" className="inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground">
                        <ArrowLeft className="size-4" /> Back to Control Center
                    </Link>
                    <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
                        <div className="max-w-2xl">
                            <span className="inline-flex items-center gap-2 text-xs font-semibold text-red-500">
                                <ShieldCheck className="size-4" /> Owner-only · Governed catalog
                            </span>
                            <h1 className="mt-2 text-2xl font-black tracking-tight sm:text-3xl">Product Management</h1>
                            <p className="mt-2 text-sm leading-6 text-muted-foreground">
                                Create and edit your entire KMJ catalog in one workspace.
                                Publishing, purchasing and license entitlement are separate approvals.
                            </p>
                        </div>
                        <button type="button" onClick={() => setCreating((value) => !value)}
                            aria-expanded={creating} aria-controls="new-product"
                            className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-red-600 px-5 text-sm font-semibold text-white hover:bg-red-500">
                            <Plus className="size-4" /> {creating ? 'Close form' : 'New product'}
                        </button>
                    </div>
                    <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
                        {[
                            ['Total products', products.length],
                            ['Public', totals.public],
                            ['Purchase enabled', totals.purchasable],
                            ['Licensing enabled', totals.licensable],
                        ].map(([label, value]) => (
                            <div key={label} className="rounded-xl border bg-background/60 p-4">
                                <p className="text-xs text-muted-foreground">{label}</p>
                                <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
                            </div>
                        ))}
                    </div>
                </header>

                {creating && (
                    <section id="new-product" className="rounded-2xl border bg-card p-5 sm:p-6" aria-label="New product">
                        <h2 className="mb-4 flex items-center gap-2 text-lg font-bold"><Boxes className="size-5" /> New product</h2>
                        <CommercialProductForm />
                    </section>
                )}

                <section aria-label="Product inventory filters" className="rounded-2xl border bg-card p-4 sm:p-5">
                    <div className="flex items-center gap-2 font-semibold">
                        <ListFilter className="size-4 text-red-500" /> Catalog filters
                    </div>
                    <div className="mt-4 grid gap-3 md:grid-cols-[minmax(180px,1fr)_minmax(160px,.6fr)_minmax(160px,.6fr)]">
                        <label className="relative">
                            <span className="sr-only">Search products</span>
                            <Search className="absolute left-3 top-3.5 size-4 text-muted-foreground" />
                            <input className="h-11 w-full rounded-xl border bg-background pl-10 pr-3 text-sm"
                                placeholder="Search name, slug or summary" value={search}
                                onChange={(event) => setSearch(event.target.value)} />
                        </label>
                        <label>
                            <span className="sr-only">Category filter</span>
                            <select className="h-11 w-full rounded-xl border bg-background px-3 text-sm"
                                value={category} onChange={(event) => setCategory(event.target.value)}>
                                <option value="all">All categories</option>
                                {productCategoryOptions.map(([value, label]) => (
                                    <option key={value} value={value}>{label}</option>
                                ))}
                            </select>
                        </label>
                        <label>
                            <span className="sr-only">Lifecycle filter</span>
                            <select className="h-11 w-full rounded-xl border bg-background px-3 text-sm"
                                value={lifecycle} onChange={(event) => setLifecycle(event.target.value)}>
                                <option value="all">All lifecycles</option>
                                {['available', 'preview', 'public-beta', 'research', 'planned', 'retired'].map((value) => (
                                    <option key={value} value={value}>{value}</option>
                                ))}
                            </select>
                        </label>
                    </div>
                    <p role="status" className="mt-3 text-xs text-muted-foreground">
                        Showing {shown} of {products.length} products. Reordering always preserves the complete catalog.
                    </p>
                </section>
                <ProductManager products={products} search={search} category={category} lifecycle={lifecycle} />
            </main>
        </>
    );
}
