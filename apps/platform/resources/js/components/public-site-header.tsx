import { Link, usePage } from '@inertiajs/react';
import { Menu, Search, X, ArrowRight } from 'lucide-react';
import { useState } from 'react';
import LockedBrand from '@/components/locked-brand';
import PublicLanguageSwitch from '@/components/public-language-switch';
import '../../css/locked-landing.css';
import '../../css/public-theme.css';

const navigation = [
    ['Home', '/'],
    ['Company', '/company'],
    ['Products', '/products'],
    ['Solutions', '/capabilities'],
    ['Industries', '/#industries'],
    ['Resources', '/products'],
    ['Support', '/#contact'],
];

export default function PublicSiteHeader() {
    const { auth, publicSite, operator } = usePage().props;
    const { url } = usePage();
    const [open, setOpen] = useState(false);
    const ownerEnabled = (operator as { enabled?: boolean })?.enabled === true;
    const registrationAvailable = publicSite?.registration_available === true;
    const dashboardHref = ownerEnabled ? '/super-admin' : '/dashboard';
    const currentPath = url.split('?')[0].split('#')[0];
    return (
        <>
            <a className="lock-skip" href="#main-content">
                Skip to main content
            </a>
            <header className="lock-header kmj-public-header">
                <Link href="/" aria-label="KMJ TECHNO home">
                    <LockedBrand compact />
                </Link>
                <nav
                    id="public-mobile-nav"
                    aria-label="Primary navigation"
                    className={open ? 'is-open' : ''}
                >
                    {navigation.map(([label, href]) => (
                        <Link
                            key={label}
                            href={href}
                            onClick={() => setOpen(false)}
                            className={
                                currentPath === href && label !== 'Resources'
                                    ? 'active'
                                    : ''
                            }
                        >
                            {label}
                        </Link>
                    ))}
                    <div className="lock-mobile-account">
                        {auth.user ? (
                            <Link
                                href={dashboardHref}
                                onClick={() => setOpen(false)}
                            >
                                My dashboard
                            </Link>
                        ) : (
                            <>
                                <Link
                                    href="/login"
                                    onClick={() => setOpen(false)}
                                >
                                    Sign in
                                </Link>
                                <Link
                                    href="/register"
                                    onClick={() => setOpen(false)}
                                >
                                    {registrationAvailable
                                        ? 'Create account'
                                        : 'Registration paused — details'}
                                </Link>
                            </>
                        )}
                    </div>
                </nav>
                <Link
                    className="lock-search"
                    href="/products#product-search"
                    aria-label="Search products and solutions"
                >
                    <Search size={18} />
                </Link>
                <PublicLanguageSwitch className="lock-language" />
                <Link href="/#contact" className="lock-primary lock-contact">
                    Contact Us <ArrowRight size={13} />
                </Link>
                <div className="lock-auth" aria-label="Account access">
                    {auth.user ? (
                        <Link href={dashboardHref} className="lock-auth-login">
                            Dashboard
                        </Link>
                    ) : (
                        <>
                            <Link href="/login" className="lock-auth-login">
                                Sign in
                            </Link>
                            <Link
                                href="/register"
                                className="lock-auth-register"
                                aria-label={
                                    registrationAvailable
                                        ? 'Create KMJ TECHNO account'
                                        : 'Register account — registration currently paused'
                                }
                            >
                                {registrationAvailable
                                    ? 'Create account'
                                    : 'Register'}
                            </Link>
                        </>
                    )}
                </div>
                <button
                    className="lock-menu"
                    aria-label={open ? 'Close navigation' : 'Open navigation'}
                    aria-controls={open ? 'public-mobile-nav' : undefined}
                    aria-expanded={open}
                    onClick={() => setOpen(!open)}
                >
                    {open ? <X /> : <Menu />}
                </button>
            </header>
        </>
    );
}
