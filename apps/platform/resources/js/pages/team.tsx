import { Link } from '@inertiajs/react';
import { ArrowRight, Linkedin, Users } from 'lucide-react';
import PublicSeo from '@/components/public-seo';
import PublicSiteFooter from '@/components/public-site-footer';
import PublicSiteHeader from '@/components/public-site-header';

export type TeamMember = {
    name: string;
    role: string;
    bio: string | null;
    photo: string | null;
    linkedin: string | null;
};

const initials = (name: string): string =>
    name
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase())
        .join('');

export default function Team({
    intro,
    members,
    preview = false,
}: {
    intro: string;
    members: TeamMember[];
    preview?: boolean;
}) {
    return (
        <>
            <PublicSeo
                title="Team Members — KMJ TECHNO"
                description="Meet the people building KMJ TECHNO software, cloud, AI and immersive technology."
                path="/team"
                structuredData={{
                    '@context': 'https://schema.org',
                    '@type': 'AboutPage',
                    name: 'KMJ TECHNO team',
                }}
            />
            <div className="kmj-public-page kmj-catalog min-h-screen overflow-clip bg-[#06080b] text-white">
                <PublicSiteHeader />
                <main id="main-content" tabIndex={-1}>
                    <section className="kmj-hero relative border-b border-white/10 px-5 py-20 text-center sm:py-28">
                        <div
                            aria-hidden="true"
                            className="kmj-hero-glow pointer-events-none absolute inset-0"
                        />
                        <div className="kmj-rise relative mx-auto max-w-4xl">
                            <p className="inline-flex items-center gap-2 rounded-full border border-[#ff3a4c]/40 bg-[#e21b23]/10 px-4 py-2 text-xs font-black tracking-[0.2em] text-[#ff8a91] uppercase">
                                <Users aria-hidden="true" size={15} />
                                KMJ TECHNO · Team
                            </p>
                            <h1 className="mt-7 font-black">
                                Team <span className="kmj-shine">Members</span>
                            </h1>
                            {intro && (
                                <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-white/70">
                                    {intro}
                                </p>
                            )}
                        </div>
                    </section>
                    <section
                        aria-label="Team profiles"
                        className="mx-auto max-w-[1440px] px-5 py-16 sm:px-8 sm:py-20 lg:px-12"
                    >
                        {preview && (
                            <p
                                role="status"
                                className="mb-10 rounded-2xl border border-amber-400/40 bg-amber-400/10 p-4 text-center text-sm text-amber-100"
                            >
                                Preview only. This page is hidden from the
                                public until you publish it.{' '}
                                <Link
                                    href="/operator/website"
                                    className="font-bold underline"
                                >
                                    Edit in the admin panel
                                </Link>
                            </p>
                        )}
                        {members.length === 0 ? (
                            <p className="text-center text-white/70">
                                Team profiles will appear here soon.
                            </p>
                        ) : (
                            <ul className="flex flex-wrap justify-center gap-6">
                                {members.map((member, index) => (
                                    <li
                                        key={`${member.name}-${index}`}
                                        className="kmj-card relative flex w-full flex-col items-center overflow-hidden rounded-3xl px-7 pt-12 pb-9 text-center sm:w-[calc(50%-0.75rem)] lg:w-[calc(25%-1.125rem)]"
                                    >
                                        <span
                                            aria-hidden="true"
                                            className="absolute inset-x-10 top-0 h-px bg-gradient-to-r from-transparent via-[#ff3a4c] to-transparent"
                                        />
                                        <span className="rounded-full bg-gradient-to-br from-[#ff5964] via-[#7a0c15] to-white/20 p-[3px] shadow-[0_18px_50px_-16px_rgba(226,27,35,0.75)]">
                                            {member.photo ? (
                                                <img
                                                    src={member.photo}
                                                    alt={member.name}
                                                    loading="lazy"
                                                    width="128"
                                                    height="128"
                                                    className="block h-32 w-32 rounded-full bg-[#10080a] object-cover"
                                                />
                                            ) : (
                                                <span
                                                    aria-hidden="true"
                                                    className="grid h-32 w-32 place-items-center rounded-full bg-[radial-gradient(circle_at_50%_25%,#3a1016,#0b0709_75%)] text-4xl font-black tracking-tight"
                                                >
                                                    {initials(member.name)}
                                                </span>
                                            )}
                                        </span>
                                        <h2 className="mt-7 text-xl font-extrabold tracking-tight break-words">
                                            {member.name}
                                        </h2>
                                        <p className="mt-2 text-xs font-black tracking-[0.14em] text-[#ff6a72] uppercase">
                                            {member.role}
                                        </p>
                                        {member.bio && (
                                            <p className="mt-5 border-t border-white/10 pt-5 text-sm leading-6 break-words text-white/70">
                                                {member.bio}
                                            </p>
                                        )}
                                        {member.linkedin && (
                                            <a
                                                href={member.linkedin}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                aria-label={`${member.name} on LinkedIn`}
                                                className="relative z-10 mt-6 grid h-11 w-11 place-items-center rounded-full border border-white/15 hover:border-[#ff3a4c] hover:bg-[#c1121f]"
                                            >
                                                <Linkedin
                                                    aria-hidden="true"
                                                    size={18}
                                                />
                                            </a>
                                        )}
                                    </li>
                                ))}
                            </ul>
                        )}
                        <div className="kmj-card relative mt-16 flex flex-col items-center gap-5 overflow-hidden rounded-3xl px-6 py-12 text-center">
                            <h2 className="text-2xl font-black tracking-tight sm:text-3xl">
                                Have a project in mind?
                            </h2>
                            <div className="relative z-10 flex flex-wrap justify-center gap-3">
                                <Link
                                    href="/#contact"
                                    className="inline-flex min-h-12 items-center gap-2 rounded-full bg-[#c1121f] px-7 text-sm font-bold hover:bg-[#a30f19]"
                                >
                                    Contact us
                                    <ArrowRight aria-hidden="true" size={16} />
                                </Link>
                                <Link
                                    href="/company"
                                    className="inline-flex min-h-12 items-center gap-2 rounded-full border border-white/20 px-7 text-sm font-bold hover:border-[#ff3a4c]"
                                >
                                    About the company
                                </Link>
                            </div>
                        </div>
                    </section>
                </main>
                <PublicSiteFooter />
            </div>
        </>
    );
}
