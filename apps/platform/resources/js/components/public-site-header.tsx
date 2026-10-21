import { Link, usePage } from '@inertiajs/react';
import { ArrowUpRight, Menu, Search, X } from 'lucide-react';
import { useState } from 'react';
import LockedBrand from '@/components/locked-brand';
import PublicLanguageSwitch from '@/components/public-language-switch';
import { dashboard, login, register } from '@/routes';

export default function PublicSiteHeader() {
    const { auth, publicSite, operator } = usePage().props;
    const ownerEnabled = (operator as { enabled?: boolean } | undefined)?.enabled === true;
    const registrationAvailable = publicSite?.registration_available === true;
    const [open, setOpen] = useState(false);

    return (
        <header className="sticky top-0 z-50 border-b border-white/[0.07] bg-[#06080b]/88 backdrop-blur-2xl">
            <a
                href="#main-content"
                className="absolute top-3 left-4 z-[70] -translate-y-20 rounded-lg bg-white px-4 py-2 text-sm font-black text-black shadow-xl transition focus:translate-y-0"
            >
                Skip to main content
            </a>
            <div className="mx-auto flex h-[76px] max-w-[1440px] items-center justify-between px-5 sm:px-8 lg:px-12">
                <Link
                    href="/"
                    className="group flex min-w-0 items-center"
                    aria-label="KMJ TECHNO home"
                >
                    <LockedBrand compact />
                </Link>

                <nav
                    className="hidden items-center gap-1 lg:flex"
                    aria-label="Primary navigation"
                >
                    <Link
                        href="/company"
                        className="rounded-lg px-4 py-2 text-sm font-semibold text-white/78 transition hover:bg-white/[0.05] hover:text-white"
                    >
                        Company
                    </Link>
                    <Link
                        href="/capabilities"
                        className="rounded-lg px-4 py-2 text-sm font-semibold text-white/78 transition hover:bg-white/[0.05] hover:text-white"
                    >
                        Capabilities
                    </Link>
                    <Link
                        href="/products"
                        className="rounded-lg px-4 py-2 text-sm font-semibold text-white/78 transition hover:bg-white/[0.05] hover:text-white"
                    >
                        Products
                    </Link>
                    <Link
                        href="/trust"
                        className="rounded-lg px-4 py-2 text-sm font-semibold text-white/78 transition hover:bg-white/[0.05] hover:text-white"
                    >
                        Trust
                    </Link>
                    <Link
                        href="/products#product-search"
                        aria-label="Search KMJ products"
                        className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white/78 transition hover:bg-white/[0.05] hover:text-white"
                    >
                        <Search className="h-3.5 w-3.5" />
                        Search
                    </Link>
                    <PublicLanguageSwitch className="rounded-lg px-4 py-2 text-sm font-semibold text-white/78 transition hover:bg-white/[0.05] hover:text-white" />
                </nav>

                <div className="hidden items-center gap-2 sm:flex">
                    {auth.user ? (
                        <Link
                            href={
                                ownerEnabled ? '/super-admin' : dashboard()
                            }
                            className="inline-flex h-10 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.035] px-4 text-sm font-bold text-white/84 transition hover:border-white/20 hover:bg-white/[0.07]"
                        >
                            Dashboard
                            <ArrowUpRight className="h-3.5 w-3.5" />
                        </Link>
                    ) : (
                        <>
                            <Link
                                href={login()}
                                className="hidden px-3 py-2 text-sm font-semibold text-white/74 transition hover:text-white md:inline-flex"
                            >
                                Sign in
                            </Link>
                            {registrationAvailable ? (
                                <Link
                                    href={register()}
                                    className="inline-flex h-10 items-center gap-2 rounded-lg bg-white px-4 text-sm font-black text-[#07090c] transition hover:bg-white/90"
                                >
                                    Create account
                                    <ArrowUpRight className="h-3.5 w-3.5" />
                                </Link>
                            ) : (
                                <span
                                    role="status"
                                    className="inline-flex h-10 items-center rounded-lg border border-amber-500/20 px-4 text-xs font-semibold text-amber-200"
                                >
                                    Registration paused
                                </span>
                            )}
                        </>
                    )}
                </div>

                <button
                    type="button"
                    aria-label={open ? 'Close navigation' : 'Open navigation'}
                    aria-expanded={open}
                    aria-controls={open ? 'public-mobile-nav' : undefined}
                    onClick={() => setOpen((value) => !value)}
                    className="grid h-10 w-10 place-items-center rounded-lg border border-white/10 bg-white/[0.03] text-white lg:hidden"
                >
                    {open ? (
                        <X className="h-4 w-4" />
                    ) : (
                        <Menu className="h-4 w-4" />
                    )}
                </button>
            </div>

            {open && (
                <div
                    id="public-mobile-nav"
                    role="navigation"
                    aria-label="Mobile primary navigation"
                    className="border-t border-white/[0.06] bg-[#07090c] px-5 py-5 lg:hidden"
                >
                    <div className="mx-auto grid max-w-[1440px] gap-2">
                        <Link
                            href="/company"
                            onClick={() => setOpen(false)}
                            className="rounded-xl px-4 py-3 text-sm font-bold text-white/75 hover:bg-white/[0.05]"
                        >
                            Company
                        </Link>
                        <Link
                            href="/capabilities"
                            onClick={() => setOpen(false)}
                            className="rounded-xl px-4 py-3 text-sm font-bold text-white/75 hover:bg-white/[0.05]"
                        >
                            Capabilities
                        </Link>
                        <Link
                            href="/products"
                            onClick={() => setOpen(false)}
                            className="rounded-xl px-4 py-3 text-sm font-bold text-white/75 hover:bg-white/[0.05]"
                        >
                            Products
                        </Link>
                        <Link
                            href="/trust"
                            onClick={() => setOpen(false)}
                            className="rounded-xl px-4 py-3 text-sm font-bold text-white/75 hover:bg-white/[0.05]"
                        >
                            Trust
                        </Link>
                        <Link
                            href="/products#product-search"
                            onClick={() => setOpen(false)}
                            className="flex items-center gap-2 rounded-xl px-4 py-3 text-sm font-bold text-white/75 hover:bg-white/[0.05]"
                        >
                            <Search className="h-4 w-4" />
                            Search products
                        </Link>
                        <PublicLanguageSwitch className="rounded-xl px-4 py-3 text-sm font-bold text-white/75 hover:bg-white/[0.05]" />
                        <div className="mt-2 border-t border-white/[0.07] pt-4">
                            {auth.user ? (
                                <Link
                                    href={
                                        ownerEnabled
                                            ? '/super-admin'
                                            : dashboard()
                                    }
                                    className="inline-flex h-11 w-full items-center justify-center rounded-xl bg-white text-sm font-black text-black"
                                >
                                    Open dashboard
                                </Link>
                            ) : (
                                <div className="grid grid-cols-2 gap-2">
                                    <Link
                                        href={login()}
                                        className="inline-flex h-11 items-center justify-center rounded-xl border border-white/10 text-sm font-bold text-white/72"
                                    >
                                        Sign in
                                    </Link>
                                    {registrationAvailable ? (
                                        <Link
                                            href={register()}
                                            className="inline-flex h-11 items-center justify-center rounded-xl bg-white text-sm font-black text-black"
                                        >
                                            Create account
                                        </Link>
                                    ) : (
                                        <span
                                            role="status"
                                            className="inline-flex h-11 items-center justify-center rounded-xl border border-amber-500/20 text-xs font-semibold text-amber-200"
                                        >
                                            Registration paused
                                        </span>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </header>
    );
}
