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
            <div className="min-h-screen overflow-clip bg-[#06080b] text-white">
                <PublicSiteHeader />
                <main id="main-content" tabIndex={-1}>
                    <section className="mx-auto max-w-[1440px] px-5 pt-20 pb-24 sm:px-8 lg:px-12">
                        {preview && (
                            <p
                                role="status"
                                className="mb-10 rounded-2xl border border-amber-400/40 bg-amber-400/10 p-4 text-sm text-amber-100"
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
                        <div className="flex items-center gap-3 text-xs font-black tracking-[0.2em] text-[#ff5962] uppercase">
                            <Users aria-hidden="true" size={18} />
                            KMJ TECHNO · Team
                        </div>
                        <h1 className="mt-5 text-4xl font-black tracking-tight sm:text-6xl">
                            Team Members
                        </h1>
                        {intro && (
                            <p className="mt-5 max-w-2xl text-base leading-8 text-white/70">
                                {intro}
                            </p>
                        )}
                        {members.length === 0 ? (
                            <p className="mt-12 text-white/70">
                                Team profiles will appear here soon.
                            </p>
                        ) : (
                            <ul className="mt-12 flex flex-wrap justify-center gap-5">
                                {members.map((member, index) => (
                                    <li
                                        key={`${member.name}-${index}`}
                                        className="kmj-card flex w-full flex-col items-center rounded-3xl border border-white/10 bg-white/[0.04] p-8 text-center sm:w-[calc(50%-0.625rem)] lg:w-[calc(25%-0.9375rem)]"
                                    >
                                        {member.photo ? (
                                            <img
                                                src={member.photo}
                                                alt={member.name}
                                                loading="lazy"
                                                width="112"
                                                height="112"
                                                className="h-28 w-28 rounded-full border-2 border-[#e21b23] object-cover"
                                            />
                                        ) : (
                                            <span
                                                aria-hidden="true"
                                                className="grid h-28 w-28 place-items-center rounded-full border-2 border-[#e21b23] bg-[#e21b23]/15 text-3xl font-black"
                                            >
                                                {initials(member.name)}
                                            </span>
                                        )}
                                        <h2 className="mt-6 text-lg font-extrabold break-words">
                                            {member.name}
                                        </h2>
                                        <p className="mt-1 text-sm font-semibold text-[#ff6a72]">
                                            {member.role}
                                        </p>
                                        {member.bio && (
                                            <p className="mt-4 text-sm leading-6 break-words text-white/70">
                                                {member.bio}
                                            </p>
                                        )}
                                        {member.linkedin && (
                                            <a
                                                href={member.linkedin}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                aria-label={`${member.name} on LinkedIn`}
                                                className="mt-5 grid h-11 w-11 place-items-center rounded-full border border-white/15 hover:border-[#ff3a4c] hover:bg-[#c1121f]"
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
                        <Link
                            href="/company"
                            className="mt-14 inline-flex items-center gap-2 text-sm font-bold underline"
                        >
                            About the company
                            <ArrowRight aria-hidden="true" size={15} />
                        </Link>
                    </section>
                </main>
                <PublicSiteFooter />
            </div>
        </>
    );
}
