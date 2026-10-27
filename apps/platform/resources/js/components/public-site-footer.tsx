import { Link, usePage } from '@inertiajs/react';
import { ArrowRight } from 'lucide-react';
import LockedBrand from '@/components/locked-brand';
import KristiSupport from '@/components/public/kristi-support';
import '../../css/locked-landing.css';
import '../../css/public-theme.css';

type FooterProduct = { slug: string; name: string };
const sections = [
    [
        'Company',
        [
            ['About Us', '/company'],
            ['Our Capabilities', '/capabilities'],
            ['Industries', '/#industries'],
            ['Trust & Security', '/trust'],
        ],
    ],
    [
        'Resources',
        [
            ['Product catalogue', '/products'],
            ['Roadmap', '/#roadmap'],
            ['Support', '/#contact'],
        ],
    ],
    [
        'Legal',
        [
            ['Terms & Conditions', '/terms'],
            ['Privacy Policy', '/privacy'],
            ['Refund Policy', '/refund-policy'],
            ['Acceptable Use', '/acceptable-use'],
            ['Cookie Policy', '/cookie-policy'],
        ],
    ],
] as const;

export default function PublicSiteFooter({
    products = [],
    support = true,
}: {
    products?: FooterProduct[];
    support?: boolean;
}) {
    const { auth, operator } = usePage().props;
    const ownerEnabled = (operator as { enabled?: boolean })?.enabled === true;
    return (
        <>
            {support && <KristiSupport />}
            <footer className="lock-footer kmj-public-footer">
                <div className="lock-footer-main">
                    <div>
                        <LockedBrand compact />
                        <p>
                            AI-powered platforms, immersive systems and
                            intelligent solutions for a connected world.
                        </p>
                        <Link href="/#contact">
                            Connect with KMJ TECHNO <ArrowRight size={12} />
                        </Link>
                    </div>
                    <div>
                        <h3>Products</h3>
                        {products.slice(0, 10).map((product) => (
                            <Link
                                key={product.slug}
                                href={'/products/' + product.slug}
                            >
                                {product.name.replace('KMJ ', '')}
                            </Link>
                        ))}
                        <Link href="/products">
                            Explore all products <ArrowRight size={12} />
                        </Link>
                    </div>
                    {sections.map(([title, links]) => (
                        <div key={title}>
                            <h3>{title}</h3>
                            {links.map(([label, href]) => (
                                <Link key={label} href={href}>
                                    {label}
                                </Link>
                            ))}
                        </div>
                    ))}
                    <div>
                        <h3 id="contact">Stay Connected</h3>
                        <p>Discuss your project with KMJ TECHNO.</p>
                        <a
                            className="lock-outline"
                            href="https://www.linkedin.com/company/kmj-techno/"
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            Contact our team <ArrowRight size={12} />
                        </a>
                        <a
                            href="https://www.linkedin.com/company/kmj-techno/"
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            International B2B enquiries <ArrowRight size={12} />
                        </a>
                        {auth.user ? (
                            <Link
                                href={
                                    ownerEnabled ? '/super-admin' : '/dashboard'
                                }
                            >
                                Dashboard
                            </Link>
                        ) : (
                            <Link href="/login">Sign in</Link>
                        )}
                    </div>
                </div>
                <div className="lock-copyright">
                    <span>
                        © {new Date().getFullYear()} KMJ TECHNO. All rights
                        reserved.
                    </span>
                    <span>Engineered for a connected world.</span>
                </div>
            </footer>
        </>
    );
}
