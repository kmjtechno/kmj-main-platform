# KMJ TECHNO — SEO + GEO, evidence-first open-source baseline (2026-10-26)

## Scope and non-goals

This is a source-only, zero-paid-service reliability improvement for the locked public
Laravel 13 / Inertia React site, not a claim that Google, Bing, ChatGPT, Gemini, or
Perplexity has indexed, ranked, cited or recommended KMJ. Keep the locked homepage,
brand, official company identity, product availability truth, authenticated dashboard,
CodeBridge OAuth and checkout untouched. No paid SERP APIs, automated backlinks,
crawler impersonation, fake reviews, unverified customer statistics or spam publishing.

## Confirmed source baseline

- `PublicSeo` already emits canonical, description, robots, Open Graph, Twitter and
  JSON-LD metadata; product pages use real catalog lifecycle labels and breadcrumbs.
- `/sitemap.xml` is assembled from the canonical public routes and catalog, and is
  deliberately 404 when `PUBLIC_INDEXING_ENABLED=false`.
- `/llms.txt` is a **supplementary information page**, not a protocol guaranteeing
  AI search inclusion. It uses public product facts and lifecycle labels.
- The public web server has a separate HTML `noindex` fail-closed policy. It
  previously excluded /legal and five policy documents even though the XML sitemap
  included them. The accompanying change aligns that allowlist.
- `public/robots.txt` declares the canonical production sitemap. Staging must
  remain unindexable. **Do not enable indexing** until production origin, ownership
  and current release are positively verified.
- Source/CI does **not** confirm that deployed Laravel `PUBLIC_INDEXING_ENABLED`
  is true or that crawlers see current release metadata.

## Reviewed open-source options — selectively adopt, don't blindly copy

| Source | License | Use in KMJ |
| --- | --- | --- |
| googlechrome/lighthouse | Apache-2.0 | Lighthouse page SEO, accessibility, mobile & performance |
| GoogleChrome/lighthouse-ci | Apache-2.0 | Exact-build regression audit; separate workflow only after isolated baseline |
| harlan-zw/unlighthouse | MIT | Owner-operated bounded multi-page sampling; no high-load VPS crawl |
| JustinBeckwith/linkinator | MIT | Broken links in public pages, bounded rate and same origin |
| google/schema-dts | Apache-2.0 | Potential type-safe schema vocabulary; not installed until schema review |
| sitespeedio/sitespeed.io | MIT | Controlled p75 Core Web Vitals benchmarking on representative hardware |
| GoogleChrome/web-vitals | Apache-2.0 | Optional consent-aware RUM metrics; not installed for this PR |
| umami-software/umami | MIT | Optional private analytics only after privacy/resource evaluation |
| firecrawl/firecrawl | AGPL-3.0 | Research only: hosting, license and operational costs not justified |
| generic GEO agent bundles | varies | No bulk install; do not accept generated citations as real |

Primary search guidance: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
Search engines prioritize technical discoverability and helpful, original, verifiable
content over gratuitous `llms.txt` files or guaranteed "GEO hacks".

## Acceptance gates

1. Offline: `cd apps/platform && node --test scripts/check-public-discovery.test.mjs`.
   Contract confirms sitemap/robots/indexing relationship but is not a live crawl.
2. Laravel test: `php artisan test --filter=PublicSeoFoundationTest` and
   `--filter=PublicSitemapTest` in an isolated configured test database.
3. Existing pinned exact-head CI: PHP, TS, Vite, brand/UI lock, accessibility,
   browser preview, code owners and production release safeguards remain green.
4. Canary after independently authorized deploy: capture anonymous HTTP status,
   canonical, robots, JSON-LD, sitemap, noindex and link integrity at the exact
   production origin; no private dashboard/account pages may be indexable.
5. GSC and Bing Webmaster ownership must be verified by the operator (no private
   credentials in PR). Use real impressions, clicks and crawler logs as evidence;
   no made-up search rank, AI citations or conversions.
6. Lighthouse / Unlighthouse / Linkinator and schema validation are optional
   standalone **read-only** QA jobs with pinned versions, bounded URLs, timeouts
   and resource caps. Do not run broad scans against production traffic.

## Editorial GEO / AI discoverability

For each public product publish only *verified* current lifecycle, exact
capabilities, limitations, OS/platform support, product-specific evidence
and a canonical link. Add original architecture guides, benchmark methodology
and signed release notes when independently confirmed. Keep navigable human
HTML; optional machine-readable summaries must not diverge from source truth.
No fabricated case studies, awards, review schema, ratings, price or availability.

## Release boundary

Source PR != deployed website. No PHP config, Nginx, Cloudflare, DNS, Google/Bing
indexing or paid external analytics is modified by this change. If post-deploy
indexability disagrees with the approved policy, roll back the exact artifact
and preserve the live failure evidence.
