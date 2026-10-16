# KMJ TECHNO — Enterprise Command OS Visual Lock V1

**Status:** User-approved visual lock, first source implementation; NOT yet a production release.

**Reference:** user-approved 1536×1024 generated admin dashboard image in the 15 October 2026 conversation (red-black KMJ corporate command center; left sidebar, Earth hero, compact 6-metric strip, product suite carousel, categorized workspace, attention/revenue/system panels, right-side Kristi portrait/text/voice dock). The approved image is a **design reference**, not production proof of the figures, status labels or links depicted.

## Locked visual contract

1. Official existing KMJ TECHNO logo retained in the platform sidebar. Red-black brand with graphite/satin/blue shadows; signature globe header and white enterprise typography.
2. Left navigation stays owner-gated; top toolbar has command search with `Ctrl/Cmd + K`, real owner access and real Operations destination.
3. Exactly six compact KPI cards: users, organizations, orders, entitlements, public products and confirmed orders, all supplied by the authenticated owner backend. Financial revenue and percentages are **not** interpolated from order records. No fabricated health.
4. Horizontally scrollable Product Suite Overview uses real canonical catalog names, lifecycle and available first-party product artwork; cards link to existing owner product controls. Missing artwork gets a neutral icon, **not a counterfeit logo**. Product count is from the backend catalog.
5. The four verified categories remain People & access, Products & lifecycle, Revenue & entitlements, Systems & developers, with 11 real links and roadmap-only sections explicitly labelled Planned.
6. Attention & Review derives only from the bounded recentOrders and missingCanonicalSlugs arrays; finance charts show **Analytics not connected** until verified aggregate reports exist; System Health must link to its real owner Operations page without claiming green status from route availability.
7. Right dock **Kristi** has visual portrait, conversation history, text box, suggested read-only destinations, opt-in browser dictation, English/Hindi voice selection, and spoken reply controls. Browser speech engines may use third-party services; never start microphone automatically. Until KMJ ModelFabric inference and authorized tool lease are verified, show **Guided mode**, not online/AI connected.
8. At widths under 1170px, Kristi becomes a full-width panel; under 720px, 2-column KPIs, 1-column insight/workspace cards. Accessible focus, readable content, keyboard dismissal, reduced-motion preference required.
9. The existing server gate (PlatformOwnerAccess + passkey/password confirmation) remains the authority. Payment evidence confirmation, entitlement fulfillment, license issuance and protected customer data continue through existing backend controls. UI must never perform privileged action by chat message alone.
10. No new third-party paid design/CDN/runtime dependencies, no production database or mail/DNS changes.

## Implementation and source paths

- `apps/platform/resources/js/components/operator-command-os.tsx` — composition, evidence-based data, product rail, action center and command palette
- `apps/platform/resources/js/components/kristi-owner-assistant.tsx` — right-side assistant in guided mode, text input, voluntary voice
- `apps/platform/resources/css/command-os.css` — locked scoped styling and responsiveness
- `apps/platform/public/assets/admin/earth-orbit.svg`, `kristi-neon.svg` — local original SVG decorative assets, **not a pixel-identical crop of the reference** (requires visual QA against the generated image)
- `apps/platform/resources/js/pages/operator.tsx` — owner route, preserves guarded order actions/legacy owner tools
- `apps/platform/scripts/check-command-os-visual-lock.test.mjs` — source security and layout assertions integrated into `npm run check`.

## Completion gates

- `npm run check`, `npm run types:check`, `npm run build` at the **exact candidate SHA** in isolated source; Vite manifest and official logo request valid.
- Existing `check-operator-command-center`, `check-admin-premium`, `check-admin-roadmap-navigation`, `check-owner-dashboard` regressions and protected owner/order/payment/license Laravel HTTP feature tests.
- Visual comparison to reference at 320/390/768/1170/1440/1536px; 100% page-width no overflow, text readable; desktop Kristi right dock; mobile stacked.
- A11y: keyboard-only command modal focus/cancel, no visible search controls without actual result routes, opt-in microphone with browser permission disclosure, Hindi/English voice fallback.
- Validate actual server deployment with SHA-pinned backup and rollback, HTTP status and **owner authenticated visual acceptance**. No forcing red/zero-step GitHub CI or changing unrelated shared VPS files.
- CodeBridge mission/queue is tracked independently; queued status is not a 24×7 executing worker or deploy authorization.
