# KMJ TECHNO — Super Admin Locked UI Fidelity Audit

Date: 15 November 2026. Scope: owner-facing `/super-admin`, `/operator` and owner subpages on the KMJ Main Platform. Production reference: actual `platform-e715829a56cc`, commit `e715829a56cc77e7aa63418ca1539635ae24e446`, reached after a real verified database/rollback-witness cutover.

## Source of design truth

Locked KMJ TECHNO Enterprise Command OS visuals previously approved by the owner: **KMJ TECHNO Super Admin Dashboard(2).png** and **KMJ TECHNO Super Admin Dashboard.png**. These establish dark graphite and KMJ red, locked Earth hero/artwork, product gallery, Business/Platform/Operations sidebar, readable KPI panels, Kristi right rail, visual hierarchy, and clear action affordances. Do not invent revenue, order, health or AI availability values to match example pictures; authoritative backend values win.

The owner supplied a **real authenticated CodeBridge Devices & Projects** screenshot on 15 Nov showing tiny type, dense device cards, repeated status unknown, crowded instructions/actions and inconsistent shell hierarchy. Screenshot alone cannot prove the other authenticated pages are visually correct or broken.

## Page-by-page source and functional route audit

| Protected page | Route | Source component | Verified scope / remaining gate |
|---|---|---|---|
| Super Admin Dashboard | `/super-admin` | `operator.tsx` + `operator-command-os.tsx` | Existing Earth/Kristi/product gallery and backend KPI data source found; full authenticated visual comparison still needed |
| Command Center | `/operator` | `operator.tsx` | Existing dashboard vs command-center ownerView routing; authenticated interactions still need proof |
| Product Management | `/operator/products` | `operator-products.tsx` | Search, lifecycle/category filter, protected product editor; authenticated creation/publishing decisions not run |
| Customers & Organizations | `/operator/directory` | `operator-directory.tsx` | Route exists; live owner pagination and protected mutations not tested |
| Orders & Payments | `/operator#commercial-orders`, `/operator/payments` | `operator.tsx`, `operator-payments.tsx` | Real route; payment settlement and entitlement safeguards must remain authoritative |
| Licensing | `/operator/kslp` | `operator-kslp.tsx` | Real protected route; no issuance can be inferred from browser QA alone |
| Operations & backups | `/operator/ops` | `operator-ops.tsx` | Real snapshot, readiness, backup evidence, action audit; new verified deep-link anchors map directly to these sections |
| Device control | `/services/kmj-codebridge#codebridge-device-control` | `services/codebridge.tsx`, `device-control-center.tsx` | Authenticated owner screenshot proves visual mismatch; PR fixes scoped layout, truthful status and active navigation |
| OAuth clients / AI | `/services/kmj-codebridge`, service tabs, `/services/kmj-codebridge/ai-providers` | service components | Real routes; live app grant does not prove a live CodeBridge heartbeat |
| Settings | `/settings/profile`, `/settings/security`, `/settings/appearance` | settings pages | Existing real authenticated routes; owner menu fixed to genuine settings instead of a generic Ops page |

## Confirmed failures corrected in this candidate

1. Shared owner shell hardcoded excessively small 11px/9px nav and subpage tabs. Scoped readable owner-only overrides added without altering customer/marketing pages.
2. CodeBridge 8-device cards displayed dense repeated unverified labels, wide prose and tiny buttons. Scoped premium CSS, progressive help and truthful filtered counts added; existing device-grant/confirm/disconnect behavior preserved.
3. CodeBridge hash anchor was compared as full href against pathname, preventing active navigation highlighting. URL/hash-aware owner-side highlight implemented.
4. Owner sidebar linked System Health, Backup, Audit and Monitoring to the top of generic Ops instead of real sections. Direct anchors now point to implemented sections; Settings points to the real account settings route.

## Important remaining blockers and policy

- **Live gateway heartbeat**: Main Platform has a stored registration/grant table but does not currently receive an authoritative authenticated per-device gateway connection feed. Never display "Online" based only on registration, license or agent existence in another connector.
- **Unverified modules**: some sidebar labels for model infrastructure, remote access, mail/SMS and task automation still lead to broad product/ops views rather than implemented dedicated workspaces. Do not create fake pages, pretend the feature exists or silently grant access.
- **Authenticated pixel acceptance**: public Chrome 9/9 pages is NOT protected owner acceptance. Compare the live private routes against approved locked screenshots at desktop/tablet/mobile, inspect spacing/font/card hierarchy, keyboard, overflow and every visible action. Do not expose personal device credentials in screenshots or public CI.
- **Release**: PR CI and synthetic owner browser tests do not deploy production. Require exact main SHA, existing customer data and uploads backup/restore evidence, source/build/runtime guards, protected release approval, controller own exit0, and post-cutover owner acceptance. Do not reuse stale `bce410` approval or claim a production update before this.
- **Zero extra cost / safe operation**: no local LLM or paid fallback, no git reset/clean, no unsafe symlinks, no unreviewed systemd production changes.

## Acceptance checklist

- [x] Real prior approved reference images located, current CodeBridge owner screenshot inspected
- [x] Shared owner shell and CodeBridge UI corrections implemented on isolated PR
- [x] Current routes for protected modules and deep-link anchors audited
- [x] 11+ static source/permission/branding/route assertions added
- [ ] Exact-head CI all-green including formatting, TypeScript and responsive checks
- [ ] Authenticated owner screenshots compared for every route at three viewport sizes
- [ ] Full navigation, search and protected action end-to-end tests with owner identity
- [ ] Verified new guarded production release and rollback
- [ ] Real gateway heartbeat sourced independently before displaying live status
