import { Link } from '@inertiajs/react';
import { ArrowRight, CheckCircle2 } from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';

type PageSection = {
    title: string;
    body: string;
    items?: string[];
};

type PublicPageProps = {
    eyebrow: string;
    title: string;
    description: string;
    path: string;
    sections: PageSection[];
    primaryCta?: { label: string; href: string };
    secondaryCta?: { label: string; href: string };
};

export default function PublicPage({
    eyebrow,
    title,
    description,
    path,
    sections,
    primaryCta,
    secondaryCta,
}: PublicPageProps) {
    return (
        <div className="min-h-screen bg-[#06080b] text-white">
            <PublicSeo
                title={title + ' | KMJ TECHNO'}
                description={description}
                path={path}
            />
            <PublicSiteHeader />

            <main id="main-content">
                <section className="relative overflow-hidden border-b border-white/[0.07]">
                    <div className="pointer-events-none absolute top-0 -right-24 h-96 w-96 rounded-full bg-[#e21b23]/10 blur-[120px]" />
                    <div className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 lg:px-12 lg:py-28">
                        <div className="max-w-4xl">
                            <div className="text-[10px] font-black tracking-[0.2em] text-[#ee3942] uppercase">
                                {eyebrow}
                            </div>
                            <h1 className="mt-5 text-5xl leading-[0.98] font-black tracking-[-0.055em] sm:text-6xl lg:text-7xl">
                                {title}
                            </h1>
                            <p className="mt-7 max-w-3xl text-base leading-8 text-white/62 sm:text-lg">
                                {description}
                            </p>
                            {(primaryCta || secondaryCta) && (
                                <div className="mt-9 flex flex-wrap gap-3">
                                    {primaryCta && (
                                        <Link
                                            href={primaryCta.href}
                                            className="inline-flex h-12 items-center gap-2 rounded-xl bg-[#e21b23] px-6 text-sm font-black transition hover:-translate-y-0.5 hover:bg-[#f22b34]"
                                        >
                                            {primaryCta.label}
                                            <ArrowRight className="h-4 w-4" />
                                        </Link>
                                    )}
                                    {secondaryCta && (
                                        <Link
                                            href={secondaryCta.href}
                                            className="inline-flex h-12 items-center rounded-xl border border-white/12 bg-white/[0.035] px-6 text-sm font-bold text-white/76 transition hover:border-white/22 hover:bg-white/[0.07] hover:text-white"
                                        >
                                            {secondaryCta.label}
                                        </Link>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </section>

                <section className="mx-auto max-w-[1440px] px-5 py-16 sm:px-8 lg:px-12 lg:py-24">
                    <div className="grid gap-5 lg:grid-cols-2">
                        {sections.map((section) => (
                            <article
                                key={section.title}
                                className="rounded-[1.5rem] border border-white/[0.075] bg-[#0a0d12] p-6 sm:p-7"
                            >
                                <h2 className="text-2xl font-black tracking-[-0.035em]">
                                    {section.title}
                                </h2>
                                <p className="mt-4 text-sm leading-7 text-white/52 sm:text-base">
                                    {section.body}
                                </p>
                                {section.items && (
                                    <ul className="mt-5 grid gap-3">
                                        {section.items.map((item) => (
                                            <li
                                                key={item}
                                                className="flex gap-3 text-sm leading-6 text-white/64"
                                            >
                                                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#ff4c55]" />
                                                <span>{item}</span>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </article>
                        ))}
                    </div>
                </section>
            </main>

            <PublicSiteFooter />
        </div>
    );
}
