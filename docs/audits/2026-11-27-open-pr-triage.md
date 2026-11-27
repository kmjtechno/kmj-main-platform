# Open PR triage — 2026-11-27

Source: GitHub API at `main` after #1251. 157 open PRs: 118 draft, 39 non-draft. CI = conclusion of the check runs on each PR's own head (not on current main), so FAIL on an old head may only mean it is stale. This report recommends; it closes and merges nothing. Claude only merges PRs it opened itself.

## Counts by group

| Group | PRs | Draft | CI PASS | CI FAIL | none/pending |
|---|---|---|---|---|---|
| Release / Ops / Backup | 35 | 32 | 29 | 4 | 2 |
| CodeBridge | 29 | 19 | 8 | 19 | 2 |
| Other | 16 | 10 | 10 | 6 | 0 |
| Mail | 14 | 12 | 6 | 7 | 1 |
| OmniDesk | 14 | 13 | 11 | 3 | 0 |
| Licensing / KSLP | 13 | 10 | 2 | 10 | 1 |
| Payments | 12 | 7 | 7 | 5 | 0 |
| Owner/Admin UI | 11 | 8 | 2 | 8 | 1 |
| Public / SEO / Pricing | 7 | 3 | 1 | 6 | 0 |
| ModelFabric / AI | 6 | 4 | 5 | 1 | 0 |

## Stacked PRs (base is not main) — merge order matters

- #1158 base `feat/mail-inbound-text-inbox-pilot-20261124` CI PASS — feat(mail): default-off bounded multipart alternative text projection
- #1124 base `feat/mail-inbound-encrypted-pilot-20261124` CI PASS — feat(mail): restricted external plain-text Inbox pilot with real sender identity
- #1091 base `feat/omnidesk-verified-paid-auto-fulfillment-20261123` CI PASS — feat(M9): competitive OmniDesk freemium launch offers, 14-day trial and owner-gated payment-ready catalog
- #1075 base `feat/omnidesk-paid-plan-price-snapshot-20261123` CI PASS — feat(M9): guarded verified-LIVE payment to automatic KSLP paid entitlement/license fulfillment
- #1072 base `feat/licensing-hub-first-party-trial-self-service-20261123` CI PASS — feat(M9): bind OmniDesk paid checkout to immutable approved plan/price/term
- #1070 base `feat/omnidesk-trial-auto-expiry-ledger-20261123` CI PASS — feat(M9): one-click verified OmniDesk trial from the ONE customer Licensing Hub
- #1066 base `feat/omnidesk-one-hub-automatic-trial-provisioning-20261123` CI PASS — feat(M9): automatically reconcile expired OmniDesk trial rights into both audit ledgers
- #1057 base `feat/licensing-hub-automatic-verified-reconciliation-20261123` CI PASS — feat(M9): automatic one-time OmniDesk trial provisioning from verified Licensing Hub
- #1056 base `feat/omnidesk-single-licensing-hub-authorization-20261123` CI PASS — feat(Licensing Hub): automate verified Razorpay sandbox order reconciliation, fail-closed
- #1055 base `feat/omnidesk-protected-activation-lease-issuer-20261123` CI PASS — feat(OmniDesk M9): reuse single Licensing Hub verified-member authorization (source-only)
- #1052 base `fix/omnidesk-renewal-challenge-lock-order-20261123` CI PASS — feat(P0 OmniDesk): protected-signer gated transactional activation and renewal adapters
- #1051 base `fix/omnidesk-status-license-activation-gates-20261123` CI PASS — fix(P0 OmniDesk): renewal challenge license-first row locking and tenant policy recheck
- #1048 base `fix/omnidesk-activation-status-entitlement-window-20261122` CI PASS — fix(P0 OmniDesk): status refuses suspended, future-dated and unsigned activation bindings
- #1041 base `fix/omnidesk-signer-temporal-parity-20261122` CI PASS — fix(P0 OmniDesk): fail-closed entitlement status and deadlock-safe deactivation locks
- #897 base `feat/kslp-tenant-device-summary-20261118` CI PASS — feat(kslp): atomic, tenant-safe trial key batch workflow with quota rollback
- #896 base `security/kslp-v1-strict-signed-verifier-20261118` CI FAIL — feat(kslp): tenant-scoped device binding summary without hardware identifiers
- #895 base `feat/kslp-secure-app-lifecycle-20261118` CI FAIL — security(kslp): strict signed v1 PHP/Rust verifier and negative interop tests
- #894 base `feat/kslp-authsp-unified-workflow-20261118` CI FAIL — feat(kslp): guarded developer app lifecycle, issuer-serialized pause and modern trust boundary
- #874 base `fix/health-v3-dual-local-owner-onepass-20261115` CI PASS — security(backup): integrate full-file SHA manifest with verified 3-lineage Certbot V3 recovery
- #871 base `fix/health-v3-dual-local-owner-onepass-20261115` CI PASS — security(backup): require SHA-256 coverage of every V3 daily snapshot file
- #777 base `claude/materializer-fail-closed-rollback` CI PASS — security(materializer): root-protected same-filesystem rollback (review pending)
- #448 base `fix/locked-overview-dialog-a11y-20261017` CI PASS — fix(locked UI): truthful product artwork and authenticated owner identity
- #445 base `feat/locked-ui-browser-20261017` CI FAIL — fix(landing): accessible company overview dialog on locked UI
- #444 base `feat/admin-command-os-visual-lock-20261015` CI FAIL — Match locked KMJ landing and owner dashboard with recreated art and browser QA
- #441 base `fix/mail-pr439-production-mail-http-csrf-tests-20261016` CI FAIL — test(mail): exercise Laravel 13 CSRF with matching session/header in production simulations
- #440 base `fix/mail-pr438-contract-whitespace-20261016` CI FAIL — test(mail): preserve production mail HTTP checks while isolating PHPUnit CSRF
- #439 base `fix/mail-pr423-formatter-only-20261016` CI FAIL — test(mail): make reset email source contract resilient to Vite+ formatting
- #438 base `fix/kmj-mail-01-self-hosted-20261014` CI FAIL — style(mail): format four PR #423 auth and contract files (no behavior changes)
- #435 base `feat/authsp-simple-licensing-flow-20261016` CI FAIL — feat(licensing): AuthSP-style device center, secure seat recovery and first-use SDK
- #432 base `feat/admin-roadmap-command-center-20261015` CI FAIL — feat(super-admin): locked KMJ Command OS with Kristi text/voice and real data
- #431 base `feat/super-admin-premium-workspace-20261015` CI FAIL — feat(admin): roadmap-aligned task-first enterprise owner command center V2
- #386 base `fix/gemini-spark-oauth-on-control-center-hub` CI FAIL — feat(codebridge): replace long customer dashboard with compact accessible workspaces
- #382 base `feat/codebridge-control-center-hub-20261012` CI FAIL — fix(oauth): rebase Gemini Spark opaque-state fix onto control center hub (resolves #380 CircleCI gap)
- #381 base `integrate/codebridge-control-center-377-378` CI FAIL — feat(codebridge): modular customer hub for devices, usage, billing and security
- #373 base `feat/kslp-offline-lease-guard-authsp-adaptation-20261012` CI FAIL — feat(licensing): trial-safe Developer Console, Ed25519 onboarding and privacy controls
- #364 base `feat/payment-webhook-verified-envelope-20261012` CI FAIL — feat(payments): durable signed webhook inbox and GET-only sandbox reconciliation guards

## 39 non-draft PRs (closest to mergeable)

| # | CI | updated | title |
|---|---|---|---|
| #265 | FAIL | 2026-10-01 | feat: signature KMJ ecosystem landing experience |
| #270 | FAIL | 2026-10-01 | Focus customer dashboard on the registered service |
| #273 | FAIL | 2026-10-02 | Restore production compatibility with PHP 8.3 |
| #274 | FAIL | 2026-10-02 | Scope customer portal to authorized KMJ services |
| #282 | FAIL | 2026-10-03 | fix(brand): replace Laravel favicon with locked KMJ icon |
| #299 | PASS | 2026-10-04 | fix: return authoritative CodeBridge agent gateway on pairing redemption |
| #321 | FAIL | 2026-10-05 | feat: ship canonical verified CodeBridge Desktop one-click setup |
| #325 | FAIL | 2026-10-06 | feat: unified KMJ multi-product customer center, bundle requests and device onboarding |
| #359 | FAIL | 2026-10-12 | fix(codebridge): explain expired pairing codes on Check device |
| #362 | FAIL | 2026-10-11 | feat(payments): authenticated Razorpay/Cashfree webhook identity without side effects |
| #364 | FAIL | 2026-10-12 | feat(payments): durable signed webhook inbox and GET-only sandbox reconciliation guards |
| #367 | FAIL | 2026-10-12 | fix(public): merchant-ready contact, billing support and cancellation-policy URL |
| #368 | FAIL | 2026-10-12 | feat(admin): modular Super Admin, payment settings, service inventory and dashboard clarit |
| #370 | FAIL | 2026-10-12 | fix(UX): identify Super Admin and unblock empty sandbox license onboarding |
| #385 | FAIL | 2026-10-13 | fix(CodeBridge UX): compact searchable dashboard and safe client revocation |
| #401 | FAIL | 2026-10-13 | feat(admin): modular Super Admin registry drives owner navigation |
| #421 | FAIL | 2026-10-14 | licensing: production-safe OmniDesk verification key discovery |
| #429 | FAIL | 2026-10-15 | security(P0): block unauthenticated CodeBridge super-admin OAuth bypass routes |
| #443 | FAIL | 2026-10-16 | feat(memory): PostgreSQL-first curated Knowledge Memory foundation |
| #446 | FAIL | 2026-10-17 | fix(ci): resume private Main Platform development with guarded zero-cost exact-head local  |
| #601 | PASS | 2026-10-27 | P0: staged 7043ac release candidate real backup + isolated restore operator gate |
| #618 | PASS | 2026-10-27 | Guarded staging storage continuity and disposable DB restore safety (no live cutover) |
| #888 | PASS | 2026-11-20 | ops(P0): Google-independent P520 recovery evidence and signed offsite gate |
| #934 | PASS | 2026-11-21 | fix(p520): immutable nonroot PostgreSQL18 + AGE recovery image separate from OpenHands |
| #978 | none | 2026-11-22 | feat(kslp): tenant-safe Ed25519 customer device transfer API with 24h cooldown |
| #993 | PASS | 2026-11-22 | security(cleanup): fence PostgreSQL writers before protected purge |
| #1082 | none | 2026-11-23 | feat(revenue): current-main owner-only KMJ 15-product competitive pricebook |
| #1087 | PASS | 2026-11-23 | feat(codebridge): source-only atomic monthly hosted usage ledger and safety tests |
| #1092 | PASS | 2026-11-23 | feat(codebridge): source-only device job receipt consistency gate, never bill without atte |
| #1093 | PASS | 2026-11-23 | feat(codebridge): authenticated tenant-scoped usage read model, source only |
| #1117 | PASS | 2026-11-24 | fix(kslp): signed reversal correlation on current main |
| #1118 | PASS | 2026-11-24 | feat(kslp): exact reviewed commercial terms and sandbox checkout binding |
| #1120 | PASS | 2026-11-24 | feat(kslp): reviewed checkout and refund correlation on current main |
| #1123 | PASS | 2026-11-25 | feat(mail): default-off authenticated inbound email pilot and encrypted quarantine |
| #1125 | FAIL | 2026-11-24 | feat(pricing): Calibration Studio competitive trial and commercial plan proposal |
| #1177 | PASS | 2026-11-25 | Unify Main Platform and CodeBridge one-page Elite release guide |
| #1194 | PASS | 2026-11-25 | fix(mail): strict owner Inbox HTTP contract and private response regressions |
| #1213 | PASS | 2026-11-26 | fix: isolate damaged credentials during scheduled ModelFabric refresh |
| #1214 | PASS | 2026-11-26 | feat: verify replacement provider credentials in one action |

## Oldest 15 (staleness)

- #261 updated 2026-09-30 CI FAIL draft=true — feat: prepare Razorpay integration without live activation
- #270 updated 2026-10-01 CI FAIL draft=false — Focus customer dashboard on the registered service
- #265 updated 2026-10-01 CI FAIL draft=false — feat: signature KMJ ecosystem landing experience
- #274 updated 2026-10-02 CI FAIL draft=false — Scope customer portal to authorized KMJ services
- #273 updated 2026-10-02 CI FAIL draft=false — Restore production compatibility with PHP 8.3
- #282 updated 2026-10-03 CI FAIL draft=false — fix(brand): replace Laravel favicon with locked KMJ icon
- #299 updated 2026-10-04 CI PASS draft=false — fix: return authoritative CodeBridge agent gateway on pairing redemption
- #323 updated 2026-10-05 CI FAIL draft=true — feat: CodeBridge browser-managed projects
- #321 updated 2026-10-05 CI FAIL draft=false — feat: ship canonical verified CodeBridge Desktop one-click setup
- #330 updated 2026-10-06 CI FAIL draft=true — docs(architecture): propose KMJ unified autonomous ecosystem and Kristi multi-agent plan
- #325 updated 2026-10-06 CI FAIL draft=false — feat: unified KMJ multi-product customer center, bundle requests and device onboarding
- #331 updated 2026-10-07 CI FAIL draft=true — feat: durable cloud-only autonomy and public experience hardening
- #362 updated 2026-10-11 CI FAIL draft=false — feat(payments): authenticated Razorpay/Cashfree webhook identity without side effects
- #384 updated 2026-10-12 CI FAIL draft=true — docs(incident): review one-time CodeBridge production gateway cutover
- #382 updated 2026-10-12 CI FAIL draft=true — fix(oauth): rebase Gemini Spark opaque-state fix onto control center hub (resolves #380 Ci

## Owner decisions needed

1. Which Razorpay/payment stack wins; close the others as superseded.
2. Which OmniDesk M9 and KSLP PRs are superseded by the unified Licensing Hub.
3. Whether drafts older than 30 days with failing CI on a stale head may be closed (reopenable).
4. Which non-draft PRs with PASS to merge, in stacked order.

Claude will not close or merge PRs it did not open; the owner (or ChatGPT lane with owner approval) does that.
