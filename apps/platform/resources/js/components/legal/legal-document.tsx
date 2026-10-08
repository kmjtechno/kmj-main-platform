import { Link } from "@inertiajs/react";
import PublicSeo from "@/components/public-seo";
import PublicSiteFooter from "@/components/public-site-footer";
import PublicSiteHeader from "@/components/public-site-header";

export type LegalSection = {
  title: string;
  paragraphs?: string[];
  bullets?: string[];
};

export default function LegalDocument({
  title,
  description,
  path,
  eyebrow,
  intro,
  effectiveDate,
  sections,
}: {
  title: string;
  description: string;
  path: string;
  eyebrow: string;
  intro: string;
  effectiveDate: string;
  sections: LegalSection[];
}) {
  return (
    <>
      <PublicSeo
        title={title + " — KMJ TECHNO"}
        description={description}
        path={path}
        type="article"
        structuredData={{
          "@context": "https://schema.org",
          "@type": "WebPage",
          name: title,
          dateModified: effectiveDate,
          publisher: { "@type": "Organization", name: "KMJ TECHNO" },
        }}
      />
      <div className="min-h-screen bg-[#05070a] text-white">
        <PublicSiteHeader />
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto max-w-[1180px] px-5 py-14 sm:px-8 lg:px-10 lg:py-20"
        >
          <div className="grid gap-10 lg:grid-cols-[260px_1fr]">
            <aside className="lg:sticky lg:top-24 lg:self-start">
              <div className="text-[10px] font-black tracking-[0.2em] text-[#ef3941] uppercase">
                {eyebrow}
              </div>
              <div className="mt-5 grid gap-2 text-sm">
                {[
                  ["/legal", "Legal center"],
                  ["/terms", "Terms & Conditions"],
                  ["/privacy", "Privacy Policy"],
                  ["/refund-policy", "Refund Policy"],
                  ["/acceptable-use", "Acceptable Use"],
                  ["/cookie-policy", "Cookie Policy"],
                ].map(([href, label]) => (
                  <Link
                    key={href}
                    href={href}
                    className={
                      "rounded-lg px-3 py-2.5 transition " +
                      (href === path
                        ? "bg-white/[0.07] font-bold text-white"
                        : "text-white/45 hover:bg-white/[0.04] hover:text-white/75")
                    }
                  >
                    {label}
                  </Link>
                ))}
              </div>
            </aside>

            <article>
              <div className="rounded-[1.8rem] border border-white/[0.08] bg-[#0a0d12] p-6 sm:p-9 lg:p-11">
                <div className="text-[10px] font-black tracking-[0.2em] text-[#ef3941] uppercase">
                  KMJ TECHNO · Legal
                </div>
                <h1 className="mt-4 text-4xl font-black tracking-[-0.045em] sm:text-5xl">
                  {title}
                </h1>
                <p className="mt-5 max-w-3xl text-sm leading-7 text-white/52 sm:text-base">
                  {intro}
                </p>
                <div className="mt-5 text-xs font-semibold text-white/30">
                  Effective: {effectiveDate}
                </div>

                <div className="mt-10 grid gap-9 border-t border-white/[0.07] pt-9">
                  {sections.map((section, index) => (
                    <section key={section.title}>
                      <h2 className="text-xl font-black tracking-[-0.025em]">
                        {index + 1}. {section.title}
                      </h2>
                      {section.paragraphs?.map((paragraph) => (
                        <p key={paragraph} className="mt-3 text-sm leading-7 text-white/48">
                          {paragraph}
                        </p>
                      ))}
                      {section.bullets && (
                        <ul className="mt-4 grid gap-2.5">
                          {section.bullets.map((bullet) => (
                            <li key={bullet} className="flex gap-3 text-sm leading-7 text-white/48">
                              <span className="mt-3 h-1.5 w-1.5 shrink-0 rounded-full bg-[#ef3941]" />
                              <span>{bullet}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </section>
                  ))}
                </div>

                <div className="mt-11 rounded-2xl border border-white/[0.08] bg-white/[0.025] p-5 text-xs leading-6 text-white/38">
                  Mandatory rights under applicable consumer, privacy or other law are not excluded
                  by these terms. Where a local law gives you rights that cannot legally be waived,
                  that law prevails to the extent of the conflict.
                </div>
              </div>
            </article>
          </div>
        </main>
        <PublicSiteFooter />
      </div>
    </>
  );
}
