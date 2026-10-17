# KMJ locked UI implementation and verification

Parent: `f9710e35def3d4105a65988108ea527a13feea2e` (PR #432).
Branch: `feat/locked-ui-browser-20261017`.
This is a stacked draft, not a production deployment.

## Implemented
Landing section order, dark/red visual system, 5×2 preview product grid, eight capabilities, ecosystem, industries, roadmap and public Kristi. Owner shell includes sidebar, Earth hero, five data cards, product carousel, revenue/orders/health panels, recent activity, quick actions and right Kristi panel. Existing guarded operator forms and backend authorization remain untouched. Shared KMJ logo and tagline remain; owner identity comes from authenticated props with the requested name as fallback.

25 recreated WebP assets are integrated in real components. Public metadata/structured data is retained. Owner search includes loaded catalog products and existing authorized workspace destinations. Carousel supports both directions and reduced motion.

## Verification
| Check | Result |
| --- | --- |
| Real-component Vite preview production bundle | PASS |
| Scoped type-aware lint of changed TSX components and preview | PASS |
| Targeted landing/owner/section contract tests | PASS, 14/14 |
| Full frontend check | PASS: formatting, lint, 71/71 tests and public-layout gate |
| Browser preview | PASS, 6/6: landing + owner at 1536, 768, 390 |
| Broken images / horizontal overflow / page JavaScript errors | None in those six cases |
| Laravel production build | BLOCKED: PHP absent; Wayfinder generation cannot run |
| Full TypeScript check | BLOCKED: generated Laravel routes/actions absent |
| Full application release check | BLOCKED: PHP/generated routes and authenticated runtime required |
| Authenticated owner / database smoke | NOT RUN |
| CodeBridge remote browser profile | NOT ACTIVATED |
| Merge / production deployment | NOT DONE |

Browser mode is `local-real-components-synthetic-data`, not an authenticated production session. Fixture products are Preview/nonpurchasable, all monetary/order values empty, and identity uses the requested display name with an invalid example email. Assertions cover ordered sections, image decoding, layout overflow, Kristi guidance/open/close, keyboard search and mobile navigation. Screenshots were visually inspected; the closing-search animation and narrow mobile assistant art were fixed.

## Screenshots
Paths relative to `apps/platform`:
- `visual-results/landing-1536.png`
- `visual-results/landing-768.png`
- `visual-results/landing-390.png`
- `visual-results/super-admin-1536.png`
- `visual-results/super-admin-768.png`
- `visual-results/super-admin-390.png`
- `visual-results/verification.json`

Generated output is provided separately as a review artifact; rerun `npm run visual:verify` to regenerate. Setup and the bounded CodeBridge profile proposal are in `apps/platform/visual/README.md`.

## Remaining mismatches and blockers
1. Recreated artwork is visually related but not pixel-identical to locked raster references; no exact image-diff score is claimed.
2. Real backend product counts/order/status and financial values are preserved. Reference mock money, customer names, activity and healthy-service claims are not fabricated; empty-data chart/order/health panels therefore differ.
3. Public overview video is unavailable; its modal states this. Kristi remains the existing guided assistant, not a newly connected live AI service.
4. Typography, cropping, content density and assistant consent controls differ from the mock; consent controls remain visible.
5. Responsive tablet/mobile arrangements are adaptations because only desktop/full-page locks were supplied.
6. The CodeBridge gateway exposes no browser tools or arbitrary command/profile-install capability. Repository automation is implemented, but administrator profile installation and exact-SHA remote execution are outstanding.
7. Full PHP build, generated-route type checks and authenticated functional release gates remain required before production.

Follow-up: exact upstream binary assets were retrieved through the base64 file API and verified against Git blob hashes. They are not changed by this patch. Removed three unused test variables, updated the public-layout guard to validate the locked home shell explicitly, and restored the verified LinkedIn enquiry link. `npm run check` now exits 0 (71 tests plus public layout). The earlier missing-binary and formatting findings are resolved. The remote CodeBridge build command was also exercised: it is pinned to old SHA eb6762533c3d86561780ca33e08aede40cef8d77 and fails with `vp: not found`; this is not evidence for this PR.

## Exact changed files (45)
- `apps/platform/package.json`
- `apps/platform/package-lock.json`
- `apps/platform/resources/js/pages/welcome.tsx`
- `apps/platform/resources/css/locked-landing.css`
- `apps/platform/resources/js/components/operator-command-os.tsx`
- `apps/platform/resources/css/owner-lock.css`
- `apps/platform/resources/js/components/kristi-owner-assistant.tsx`
- `apps/platform/resources/js/app.tsx`
- `apps/platform/resources/css/app.css`
- `apps/platform/visual/index.html`
- `apps/platform/visual/entry.tsx`
- `apps/platform/visual/vite.config.ts`
- `apps/platform/visual/README.md`
- `apps/platform/scripts/browser-preview-verify.mjs`
- `apps/platform/scripts/run-browser-preview.mjs`
- `scripts/check-locked-sections.test.mjs`
- `apps/platform/scripts/check-homepage-portfolio.test.mjs`
- `apps/platform/scripts/check-command-os-visual-lock.test.mjs`
- `apps/platform/public/assets/locked/agent.webp`
- `apps/platform/public/assets/locked/calibration.webp`
- `apps/platform/public/assets/locked/cinema.webp`
- `apps/platform/public/assets/locked/cloudos.webp`
- `apps/platform/public/assets/locked/codebridge.webp`
- `apps/platform/public/assets/locked/ecosystem.webp`
- `apps/platform/public/assets/locked/forge.webp`
- `apps/platform/public/assets/locked/industry-architecture.webp`
- `apps/platform/public/assets/locked/industry-corporate.webp`
- `apps/platform/public/assets/locked/industry-education.webp`
- `apps/platform/public/assets/locked/industry-entertainment.webp`
- `apps/platform/public/assets/locked/industry-healthcare.webp`
- `apps/platform/public/assets/locked/industry-industry.webp`
- `apps/platform/public/assets/locked/industry-museums.webp`
- `apps/platform/public/assets/locked/industry-research.webp`
- `apps/platform/public/assets/locked/kristi-owner.webp`
- `apps/platform/public/assets/locked/kristi-public.webp`
- `apps/platform/public/assets/locked/landing-hero.webp`
- `apps/platform/public/assets/locked/licensing.webp`
- `apps/platform/public/assets/locked/motion.webp`
- `apps/platform/public/assets/locked/nexus.webp`
- `apps/platform/public/assets/locked/omnidesk.webp`
- `apps/platform/public/assets/locked/owner-earth.webp`
- `apps/platform/public/assets/locked/roadmap.webp`
- `apps/platform/public/assets/locked/studio.webp`
- `docs/qa/locked-ui-browser-verification-20261017.md`

- `apps/platform/scripts/check-public-layout.mjs`
