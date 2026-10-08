# Customer-facing KMJ TECHNO website — release acceptance

## Problem reproduced

A logged-in customer visiting `/products` saw a Platform sidebar beside the public KMJ TECHNO header. The Inertia client in `resources/js/app.tsx` exempted only the homepage from `AppLayout`; public product, legal, trust and corporate pages inherited the authenticated dashboard shell. Marketing header mobile navigation was also hidden between the `sm` and `lg` breakpoints.

## Layout boundary

Marketing pages use their existing self-contained public header, footer, SEO and mobile navigation, without the Platform sidebar. The only standalone component names are explicitly allowlisted in `resources/js/lib/public-page-layout.ts` (welcome, company, capabilities, trust, public-page, product index/detail, CodeBridge legal/support, and the six legal documents). Do **not** wildcard `products/*`, `settings/*` or `services/*` because future authenticated product-management pages must retain their own protected layouts.

The authenticated Dashboard, Purchase Center, License Center, Security, Operator and services pages continue using `AppLayout`. Auth pages continue using `AuthLayout`, settings pages keep both required settings and application layouts.

The marketing header's menu toggle and expanded mobile menu must remain available on phones **and tablets** up to the desktop navigation breakpoint. Signed-in users see a Dashboard CTA in the footer rather than invitations to register again. The product hero copy and search hints must remain readable with the dark palette.

## Tests and launch checks

`npm run check` in `apps/platform` now includes `node scripts/check-public-layout.mjs` in addition to the existing `vp check`. Also require `npm run types:check`, `npm run build`, Laravel Pint, and public Inertia feature tests before merge/deploy.

After an approved production deployment, test **both guest and logged-in** sessions on desktop (1440 px), tablet (768 px), and phone (390 px):

- `/`, `/products`, `/products/kmj-cloudos`, `/products/kmj-codebridge`, `/company`, `/capabilities`, `/trust`, `/legal`, `/privacy`, `/terms`, and `/products/kmj-codebridge/support`: show only the public header and footer, full viewport width, no Platform sidebar or sidebar toggle, navigation and canonical SEO intact.
- Search and lifecycle filters yield meaningful results and an empty state; no nonavailable product displays a working purchase path, and demo labels distinguish simulations from production.
- Tablet hamburger menu opens, links navigate, and authenticated state shows Dashboard while guests see login/register.
- `/dashboard`, `/purchase`, `/sandbox-licenses`, `/operator` retain authenticated controls; a guest cannot access protected pages.
- Check image loading/alt text, contrast, horizontal overflow, keyboard focus/skip link, Kristi support, legal links, redirects, broken links and console errors.
- Confirm the deployed product catalog's count against the **actual current authority**. A previous user screenshot displayed **12**; the repository's newer public catalog test expects **15**. Do not assert deployed count equals source count until a live production check confirms the release SHA and canonical product sync.

## Release controls

This branch must stay separate from the draft Owner/Admin license PR #322. Do not modify DNS, production database, customer entitlements or signed licenses to fix public visuals. GitHub-hosted CI may be blocked by account restrictions (jobs starting zero steps). Never substitute a green marker for unrun CI. If runner access is unavailable, gather exact-head proof with an authorized isolated native CodeBridge job and the approved CI policy, or leave deployment blocked. Track branch head SHA, build hash and actual production screenshot after rollout; **merged code and live website are different states**.
