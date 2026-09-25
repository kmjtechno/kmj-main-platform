import { Link } from '@inertiajs/react';
import { ArrowUpRight } from 'lucide-react';
import LockedBrand from '@/components/locked-brand';

export default function PublicSiteFooter() {
    return (
        <footer className="border-t border-white/[0.07] bg-[#05070a]">
            <div className="mx-auto grid max-w-[1440px] gap-12 px-5 py-14 sm:px-8 md:grid-cols-[1.3fr_.7fr_.7fr] lg:px-12">
                <div>
                    <LockedBrand />
                    <p className="mt-5 max-w-md text-sm leading-7 text-white/38">
                        Software, cloud systems and intelligent products
                        designed around clear product boundaries, governed
                        access and verifiable delivery.
                    </p>
                </div>

                <div>
                    <div className="text-[11px] font-black tracking-[0.18em] text-white/32 uppercase">
                        Explore
                    </div>
                    <div className="mt-4 grid gap-3">
                        <Link
                            href="/products"
                            className="text-sm font-semibold text-white/62 transition hover:text-white"
                        >
                            Products
                        </Link>
                        <Link
                            href="/trust"
                            className="text-sm font-semibold text-white/62 transition hover:text-white"
                        >
                            Trust center
                        </Link>
                        <Link
                            href="/"
                            className="text-sm font-semibold text-white/62 transition hover:text-white"
                        >
                            Company platform
                        </Link>
                    </div>
                </div>

                <div>
                    <div className="text-[11px] font-black tracking-[0.18em] text-white/32 uppercase">
                        Customer access
                    </div>
                    <div className="mt-4 grid gap-3">
                        <Link
                            href="/login"
                            className="inline-flex items-center gap-2 text-sm font-semibold text-white/62 transition hover:text-white"
                        >
                            Sign in <ArrowUpRight className="h-3.5 w-3.5" />
                        </Link>
                        <Link
                            href="/register"
                            className="inline-flex items-center gap-2 text-sm font-semibold text-white/62 transition hover:text-white"
                        >
                            Create account{' '}
                            <ArrowUpRight className="h-3.5 w-3.5" />
                        </Link>
                    </div>
                </div>
            </div>
            <div className="border-t border-white/[0.06]">
                <div className="mx-auto flex max-w-[1440px] flex-col gap-2 px-5 py-5 text-[11px] text-white/27 sm:px-8 md:flex-row md:items-center md:justify-between lg:px-12">
                    <span>
                        © {new Date().getFullYear()} KMJ TECHNO. All rights
                        reserved.
                    </span>
                    <span>
                        Public product claims remain bound to verified platform
                        authority.
                    </span>
                </div>
            </div>
        </footer>
    );
}
