# KMJ TECHNO — Super Admin information architecture V2

Status: **Design source and draft implementation** (not declared released)
Source of truth: `KMJ_TECHNO_MAIN_PLATFORM_MASTER_ROADMAP_BLUEPRINT_V1_0.md`, `THEME_LOCK.md`, `RELEASE_GATE.md`, `architecture/modules.yaml`, and the current Laravel routes/components.

## Finding: why another dark mockup is insufficient

Main Platform is an enterprise operating system, not a single dashboard. A premium home page must first answer four questions: **what can I manage, what needs action, where do I go, and which facts are verified?** Decorative mockups must not invent customers, uptime, active licenses, payments, health or delivery successes.

The canonical roadmap's snapshot is dated **10 September 2026**. Its foundational architecture/authority rules remain normative; its old implementation statuses are not evidence of what was deployed in October. Route existence proves only a page is implemented, not that billing, mail or a release is production ready.

The repo tree was indexed (**930 Git tree entries: 754 tracked files plus 176 directory entries** on baseline `main` at `54142f844c0bb2721c98617d1c4dd026f36ce384`); the owner-relevant routes, security, components, README, blueprint, release gate and theme lock were reviewed. This is a scoped architecture/UI audit, not a claim that all 930 files were individually line-reviewed.

## Four everyday operator categories

| Owner question | Category | Linked real workspace | Source |
| --- | --- | --- | --- |
| Who has access? | People & access | Customers/Organizations; account Security | `operator-directory.php`, `settings.php` |
| What can we offer? | Products & lifecycle | Product Management; read-only public portfolio | `operator-products.tsx`, `web.php` |
| What has the customer bought and been granted? | Revenue & entitlements | Recent commercial orders, sandbox payment settings, KSLP Licensing | `web.php`, `payments-console.php`, `kslp-admin.php` |
| Is the system operated safely? | Systems & developers | Ops, CodeBridge Owner Controls, Developer Apps & Keys, Sandbox Token Lab | `operator-ops.php`, `codebridge-admin.php`, `developer-licenses.php`, `web.php` |

The same categories appear in the **owner-only sidebar** and on `/operator`; they are not mixed with the customer `/dashboard` entitlement view. A keyword task finder filters modules without server calls or privileged mutations. Routes are ordinary Inertia links; the existing owner/passkey/password-confirmation server policies remain authoritative.

### Roadmap queue — deliberately non-clickable

These are visible *as planned capability areas*, without fictitious action buttons or availability claims:
- KMJ Mail administration
- Support & Trust cases
- Content & SEO studio
- Release registry
- Reporting & analytics

Implement a real module, endpoint, owner policy, tests and data source **before** changing its label from Planned to live navigation. The independent future services (e.g. Kristi and external product runtimes) must be linked through narrow authorized contracts, not a shared database or unrestricted shell.

## Information hierarchy for `/operator`

1. **Identity & role:** KMJ TECHNO / Owner Workspace / passkey-gated scope. Avoid claims such as "server healthy" from successful login.
2. **Evidence-backed KPIs only:** the existing backend supplies users, organizations, entitlements, order counts and confirmed orders. All denominators and snapshots are named; no manufactured revenue/uptime.
3. **Needs attention:** counts are derived only from the current bounded order and catalog snapshots; link to the correct action. They are not a live provider inbox.
4. **Task-first workspace map:** four compact categories with accessible search; no duplicate modules visible by default. Legacy module directory remains under *Advanced module index* for feature parity during migration.
5. **Detailed tables:** catalog readiness and recent commercial orders remain available below, with explicit owner financial approvals and licensing authority checks.

## Visual and interaction rules

- Branding remains the locked official KMJ red/black logo and `INNOVATE | BUILD | SCALE` language; do not replace it with generated near-matches.
- Charcoal, graphite and satin layer contrast rather than pure black. Use KMJ red sparingly for primary actions, and semantic accents to distinguish domains. No neon overload or decorative false health indicators.
- Clear visual rhythm, one primary action per panel, 44px-or-better tap targets, readable text (avoid smaller-than-12px interactive labels), strong focus states, reduced motion and mobile-friendly stacking.
- Search, active links and disclosure work with keyboard/screen readers; avoid mobile horizontal overflow.
- Empty/restricted states must explain why an action is unavailable and never trick operators into bypassing confirmation.
- Never expose passwords/API keys on cards. Provider account-owner approval is **not** verified live billing.
- No new dependencies or paid services.

## Acceptance gates before release

- Exact-head source review + `git diff --check`; `npm ci --ignore-scripts`, `npm run check`, `npm run types:check`, `npm run build`.
- Check `scripts/check-admin-roadmap-navigation.test.mjs` and existing owner/codebridge/dashboard safety contracts.
- Owner-only access / non-owner denial tests, manual commercial order and KSLP authorization regression; product ordering and payments gates remain untouched.
- Browser visual and accessibility checks at **320, 390, 768 and 1440px**, light/dark, keyboard navigation, visible focus, reduced motion and no console errors.
- No fictional KPI, misleading status badge, broken link, placeholder licensed service or unreleased Mail route.
- The strictly approved release process from `RELEASE_GATE.md`: back up current release/assets, verify candidate, controlled activation, real owner login/visual acceptance, rollback drill, record deployed SHA.
- GitHub workflow jobs that fail **before any steps** cannot be counted as passing source tests.
- Main Platform frontend asset activation for older PR #430 is distinct from this new V2 branch; do not assert this V2 design is already live.

## Deferred engineering backlog

P1 — Mature navigation: keyboard command palette with authorization-aware search, breadcrumbs, pinned favorites and cross-module deep links. Avoid exposing unauthorized search results.

P1 — Strong owner action center: server-built typed task records from payments, license, product, support and mail modules; timestamps, authoritative source and approved action gate. No guessed counts.

P1 — Governed Release Console, KMJ Mail delivery/communication console and Support Inbox only as backend capabilities become verified.

P2 — Saved views, CSV exports with role/tenant filtering, audit timelines, dashboard widget configuration, collaboration and multilingual admin UI.

P2 — Responsive screenshot regression baselines, dark/light design tokens and reusable chart patterns backed by measured facts.

## System boundaries and change rule

No production billing/DNS/key/signing operations, new database writes or migrations are part of this UI work. Backend truth remains `Account → Organization → Subscription → Entitlement → License → Device Activation`. The repository's roadmap strictly prohibits merging independent Cloud Nexus into Main Platform or using the UI as final entitlement authority.
