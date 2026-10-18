# KMJ TECHNO — locked Landing & Owner Command OS production acceptance

This checklist is for the end-to-end integration review [PR #449](https://github.com/kmjtechno/kmj-main-platform/pull/449), including stacked design PRs #432, #444, #445 and #448. **Passing a synthetic preview is not deployment.**

## User-approved visual references (17 October 2026)

1. **Public landing:** KMJ TECHNO logo + tagline; full-width dramatic city/technology hero; dark charcoal/navy with controlled red accents; flagship products presented as 5×2 illustrated cards; eight capabilities; connected ecosystem visual; industry cards; roadmap; responsive accessible header/footer; public Kristi panel.
2. **Super Admin:** charcoal/red enterprise shell; left owner workspace navigation; Earth/globe hero; factual KPI cards; product suite carousel; revenue, orders, system health, activity and quick tools; right Kristi assistant; search and keyboard/mobile access.
3. Use original official branding. Artwork rendered in source is recreated and **not certified pixel-identical**. Mock figures, mock payments, green/healthy states and AI-online flags **must not be copied into production**; derive truthful status from real authority, or show unavailable/unknown.
4. The demo Company Video dialog explicitly states that no real company video is available; Kristi is a guided assistant, not proven generative/live voice functionality. Treat these as remaining product completeness gaps, not implemented claims.

## Verified candidate evidence (before additional smoke-coverage changes)

Exact isolated code HEAD `1025c7957fac0f390f9185dc8ab003e794acd674` passed Composer/npm, Wayfinder, frontend check, TypeScript, production build, PHP formatting/static analysis/Laravel tests and synthetic Chrome UI for both views at 1536, 768 and 390 px. Evidence directory on KMJ-elite:
`work/qa/locked448-1025c7957fac0f390f9185dc8ab003e794acd674-20261017T141345Z`

The current integration branch includes **new changes** to staging authenticated route smoke that must be retested on its new exact SHA. Previous PASS must not be transferred to a newer head.

## Mandatory promotion gates

- [x] Original design images located and reviewed for intended content hierarchy.
- [x] Earlier exact-head local isolated full QA and 6/6 synthetic browser cases PASS.
- [ ] New exact-head local QA including updated staging owner `/operator` route smoke PASS.
- [ ] Test real authenticated Platform Owner role and owner-only actions using isolated **staging** data, plus non-owner access denial and password-confirm policy. No backdoor, no real credentials exposed.
- [ ] Render candidate screenshots at desktop/tablet/mobile and compare with both approved locked references; log meaningful differences, correct before visual sign-off. The preview is not currently pixel-identical.
- [ ] Verify catalog product actions and owner product-management create/edit, lifecycle, show/hide and ordering; no false production states.
- [ ] Resolve GitHub private-repo zero-step hosted Actions (#437), obtain required exact-head policy acceptance without bypassing required rules.
- [ ] Require current protected deployment approval manifest for **this exact merged release SHA** and the **actual** current production release (not a stale prior release).
- [ ] Complete release rollback plan / DB backups / service health / zero-secrets receipt, with tested restore path.
- [ ] Controlled production activation followed by real browser guest + authenticated smoke, core-services health, release SHA and rollback receipt.

## Snapshot of existing deployment blocker

At last read, Main Platform `/home/kmjprod/current` resolved to `platform-54142f844c0b`. The guarded CodeBridge release status returned `readyToActivate=false` because protected approved SHA `58cfdf06e6abbb47e0330c70b551679dafe4d3c2` and expected current release `platform-1cbd35b77301` do **not** match either the candidate or live pointer. Do not bypass these guards.

Do not deploy by merely copying Vite build files while the related backend, routes, owner guard, and public layout remain in an earlier release. Production billing, licensing, secrets, DNS and database must be unchanged until separately approved, backed up and validated.
