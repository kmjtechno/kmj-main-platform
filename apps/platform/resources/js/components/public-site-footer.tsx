import { Link, usePage } from '@inertiajs/react';
import { ArrowUpRight } from 'lucide-react';
import LockedBrand from '@/components/locked-brand';
import KristiSupport from '@/components/public/kristi-support';

export default function PublicSiteFooter() {
    const { localization } = usePage().props;
    const hi = localization.locale === 'hi';
    const explore = hi
        ? [
              ['/company', 'कंपनी'],
              ['/capabilities', 'क्षमताएँ'],
              ['/products', 'उत्पाद'],
              ['/trust', 'विश्वास केंद्र'],
              ['/docs', 'दस्तावेज़'],
              ['/insights', 'इनसाइट्स'],
              ['/support', 'सहायता'],
          ]
        : [
              ['/company', 'Company'],
              ['/capabilities', 'Capabilities'],
              ['/products', 'Products'],
              ['/trust', 'Trust center'],
              ['/docs', 'Documentation'],
              ['/insights', 'Insights'],
              ['/support', 'Support'],
          ];
    const legal = hi
        ? [
              ['/legal', 'कानूनी केंद्र'],
              ['/terms', 'नियम और शर्तें'],
              ['/privacy', 'गोपनीयता नीति'],
              ['/refund-policy', 'रिफंड नीति'],
              ['/acceptable-use', 'स्वीकार्य उपयोग'],
              ['/cookie-policy', 'कुकी नीति'],
          ]
        : [
              ['/legal', 'Legal center'],
              ['/terms', 'Terms & Conditions'],
              ['/privacy', 'Privacy Policy'],
              ['/refund-policy', 'Refund Policy'],
              ['/acceptable-use', 'Acceptable Use'],
              ['/cookie-policy', 'Cookie Policy'],
          ];

    return (
        <>
            <KristiSupport />
            <footer className="border-t border-white/[0.07] bg-[#05070a]">
                <div className="mx-auto grid max-w-[1440px] gap-12 px-5 py-14 sm:px-8 md:grid-cols-2 lg:grid-cols-[1.4fr_.7fr_.7fr_.8fr] lg:px-12">
                    <div>
                        <LockedBrand />
                        <p className="mt-5 max-w-md text-sm leading-7 text-white/38">
                            {hi
                                ? 'स्पष्ट product boundaries, governed access और verifiable delivery के लिए बनाए गए software, cloud systems और intelligent products।'
                                : 'Software, cloud systems and intelligent products designed around clear product boundaries, governed access and verifiable delivery.'}
                        </p>
                    </div>

                    <div>
                        <div className="text-[11px] font-black tracking-[0.18em] text-white/32 uppercase">
                            {hi ? 'एक्सप्लोर करें' : 'Explore'}
                        </div>
                        <div className="mt-4 grid gap-3">
                            {explore.map(([href, label]) => (
                                <Link
                                    key={href}
                                    href={href}
                                    className="text-sm font-semibold text-white/62 transition hover:text-white"
                                >
                                    {label}
                                </Link>
                            ))}
                        </div>
                    </div>

                    <div>
                        <div className="text-[11px] font-black tracking-[0.18em] text-white/32 uppercase">
                            {hi ? 'कानूनी' : 'Legal'}
                        </div>
                        <div className="mt-4 grid gap-3">
                            {legal.map(([href, label]) => (
                                <Link
                                    key={href}
                                    href={href}
                                    className="text-sm font-semibold text-white/62 transition hover:text-white"
                                >
                                    {label}
                                </Link>
                            ))}
                        </div>
                    </div>

                    <div>
                        <div className="text-[11px] font-black tracking-[0.18em] text-white/32 uppercase">
                            {hi ? 'ग्राहक पहुँच' : 'Customer access'}
                        </div>
                        <div className="mt-4 grid gap-3">
                            <Link
                                href="/login"
                                className="inline-flex items-center gap-2 text-sm font-semibold text-white/62 transition hover:text-white"
                            >
                                {hi ? 'साइन इन' : 'Sign in'}{' '}
                                <ArrowUpRight className="h-3.5 w-3.5" />
                            </Link>
                            <Link
                                href="/register"
                                className="inline-flex items-center gap-2 text-sm font-semibold text-white/62 transition hover:text-white"
                            >
                                {hi ? 'अकाउंट बनाएँ' : 'Create account'}{' '}
                                <ArrowUpRight className="h-3.5 w-3.5" />
                            </Link>
                        </div>
                    </div>
                </div>
                <div className="border-t border-white/[0.06]">
                    <div className="mx-auto flex max-w-[1440px] flex-col gap-2 px-5 py-5 text-[11px] text-white/27 sm:px-8 md:flex-row md:items-center md:justify-between lg:px-12">
                        <span>
                            © {new Date().getFullYear()} KMJ TECHNO.{' '}
                            {hi ? 'सर्वाधिकार सुरक्षित।' : 'All rights reserved.'}
                        </span>
                        <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
                            <span>
                                {hi
                                    ? 'सार्वजनिक product claims सत्यापित platform authority से बंधे रहते हैं।'
                                    : 'Public product claims remain bound to verified platform authority.'}
                            </span>
                            <span className="font-semibold text-white/45">
                                {hi
                                    ? 'निर्माण और डिज़ाइन: KMJ TECHNO'
                                    : 'Build & Design by KMJ TECHNO'}
                            </span>
                        </span>
                    </div>
                </div>
            </footer>
        </>
    );
}
