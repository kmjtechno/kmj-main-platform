import { Link, usePage } from '@inertiajs/react';
import { dashboard } from '@/routes';
import { ArrowUpRight } from 'lucide-react';
import LockedBrand from '@/components/locked-brand';
import KristiSupport from '@/components/public/kristi-support';

export default function PublicSiteFooter() {
    const { auth } = usePage().props;

    return (
        <>
            <KristiSupport />
            <footer className="border-t border-white/[0.07] bg-[#05070a]">
                <div className="mx-auto grid max-w-[1440px] gap-12 px-5 py-14 sm:px-8 md:grid-cols-2 lg:grid-cols-[1.4fr_.7fr_.7fr_.8fr] lg:px-12">
                    <div>
                        <LockedBrand />
                        <p className="mt-5 max-w-md text-sm leading-7 text-white/65">
                            Software, cloud systems and intelligent products
                            designed around clear product boundaries, governed
                            access and verifiable delivery.
                        </p>
                    </div>

                    <div>
                        <div className="text-[11px] font-black tracking-[0.18em] text-white/65 uppercase">
                            Explore
                        </div>
                        <div className="mt-4 grid gap-3">
                            <Link
                                href="/company"
                                className="text-sm font-semibold text-white/78 transition hover:text-white"
                            >
                                Company
                            </Link>
                            <Link
                                href="/capabilities"
                                className="text-sm font-semibold text-white/78 transition hover:text-white"
                            >
                                Capabilities
                            </Link>
                            <Link
                                href="/products"
                                className="text-sm font-semibold text-white/78 transition hover:text-white"
                            >
                                Products
                            </Link>
                            <Link
                                href="/trust"
                                className="text-sm font-semibold text-white/78 transition hover:text-white"
                            >
                                Trust center
                            </Link>
                            <a
                                href="https://www.linkedin.com/company/kmj-techno/"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-2 text-sm font-semibold text-white/78 transition hover:text-white"
                            >
                                International B2B enquiries
                                <ArrowUpRight className="h-3.5 w-3.5" />
                            </a>
                        </div>
                    </div>

                    <div>
                        <div className="text-[11px] font-black tracking-[0.18em] text-white/65 uppercase">
                            Legal
                        </div>
                        <div className="mt-4 grid gap-3">
                            {[
                                ['/legal', 'Legal center'],
                                ['/terms', 'Terms & Conditions'],
                                ['/privacy', 'Privacy Policy'],
                                ['/refund-policy', 'Refund Policy'],
                                ['/acceptable-use', 'Acceptable Use'],
                                ['/cookie-policy', 'Cookie Policy'],
                            ].map(([href, label]) => (
                                <Link
                                    key={href}
                                    href={href}
                                    className="text-sm font-semibold text-white/78 transition hover:text-white"
                                >
                                    {label}
                                </Link>
                            ))}
                        </div>
                    </div>

                    <div>
                        <div className="text-[11px] font-black tracking-[0.18em] text-white/65 uppercase">
                            Customer access
                        </div>
                        <div className="mt-4 grid gap-3">
                            {auth.user ? (
                                <Link
                                    href={dashboard()}
                                    className="inline-flex items-center gap-2 text-sm font-semibold text-white/80 transition hover:text-white"
                                >
                                    Open dashboard
                                    <ArrowUpRight className="h-3.5 w-3.5" />
                                </Link>
                            ) : (
                                <>
                                    <Link
                                        href="/login"
                                        className="inline-flex items-center gap-2 text-sm font-semibold text-white/72 transition hover:text-white"
                                    >
                                        Sign in
                                        <ArrowUpRight className="h-3.5 w-3.5" />
                                    </Link>
                                    <Link
                                        href="/register"
                                        className="inline-flex items-center gap-2 text-sm font-semibold text-white/72 transition hover:text-white"
                                    >
                                        Create account
                                        <ArrowUpRight className="h-3.5 w-3.5" />
                                    </Link>
                                </>
                            )}
                        </div>
                    </div>
                </div>
                <div className="border-t border-white/[0.06]">
                    <div className="mx-auto flex max-w-[1440px] flex-col gap-2 px-5 py-5 text-[11px] text-white/58 sm:px-8 md:flex-row md:items-center md:justify-between lg:px-12">
                        <span>
                            © {new Date().getFullYear()} KMJ TECHNO. All rights
                            reserved.
                        </span>
                        <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
                            <span>
                                Public product claims remain bound to verified
                                platform authority.
                            </span>
                            <span className="font-semibold text-white/70">
                                Build &amp; Design by KMJ TECHNO
                            </span>
                        </span>
                    </div>
                </div>
            </footer>
        </>
    );
}
