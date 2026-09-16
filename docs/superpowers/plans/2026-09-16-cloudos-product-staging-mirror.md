# CloudOS Product + Staging Production Mirror Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make KMJ CloudOS a canonical commercial Main Platform product/licensing target and make the temporary staging homepage show the live production homepage while preserving `/info` and Main Platform controls.

**Architecture:** Main Platform remains the commercial/entitlement/license authority; CloudOS remains a separate runtime product and future hosting substrate. Staging mirrors only the exact homepage through an application service with host gating, direct production-origin TLS resolution, short caching and safe fallback; `/info` stays native Main Platform.

**Tech Stack:** Laravel/PHP 8.5, Inertia/React, PostgreSQL, Laravel HTTP client/cache, GitHub Actions, self-hosted Linux runners.

**Spec:** `docs/superpowers/specs/2026-09-16-cloudos-product-hosting-licensing-design.md`

## Global Constraints

- CloudOS repository remains separate; do not modify `kmjtechno/kmj-cloudos` from this plan.
- Production `kmjtechno.com` and production DNS remain untouched.
- `/info` and `/info/status` remain native staging Main Platform routes.
- Payment confirmation never grants access by itself; explicit fulfillment is required.
- Client/runtime state is never final license authority.
- Private signing keys are never stored in application database rows.
- Existing CloudOS workloads must survive central/license outage through bounded offline grace.
- Zero-cost cloud-only AI policy and existing owner gates remain unchanged.

---
### Task 1: Canonical CloudOS commercial product

**Files:**
- Create: `apps/platform/app/Services/Commerce/CloudOSProductCatalog.php`
- Create: `apps/platform/app/Console/Commands/SyncCanonicalProductsCommand.php`
- Create: `apps/platform/tests/Feature/CloudOSProductCatalogTest.php`

**Interfaces:**
- `CloudOSProductCatalog::sync(): Product`
- constants: slug `kmj-cloudos`, name `KMJ CloudOS`, policy `cloudos.platform.default`, capability `cloudos.platform.access`
- command: `kmj:catalog:sync`

- [ ] **Step 1: Write failing catalog tests**

Test that two sync calls produce exactly one active `products` row and one active `entitlement_policies` row with the canonical facts. Add a conflict test where `cloudos.platform.default` already belongs to another product and must throw `DomainException`.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `php artisan test tests/Feature/CloudOSProductCatalogTest.php`
Expected: FAIL because `CloudOSProductCatalog` and command do not exist.

- [ ] **Step 3: Implement minimal idempotent sync**

Use `ProductCatalog::ensureCommercialProduct()` and `EntitlementPolicyRegistry::ensure()` inside `DB::transaction()`, then explicitly compare returned policy product/capability/status to canonical values and throw `DomainException` on conflict.

- [ ] **Step 4: Run focused test and verify GREEN, then commit**

Run the same focused test; expected PASS. Commit product sync separately.

---
### Task 2: Temporary live production-home mirror on staging

**Files:**
- Create: `apps/platform/app/Services/Staging/ProductionHomeMirror.php`
- Create: `apps/platform/app/Http/Controllers/StagingProductionHomeController.php`
- Modify: `apps/platform/routes/web.php`
- Modify: `apps/platform/config/services.php`
- Create: `apps/platform/tests/Feature/StagingProductionHomeMirrorTest.php`

**Interfaces:**
- exact host gate: `staging.kmjtechno.com`
- config keys: `services.kmj_staging_home_mirror.enabled`, `origin`, `origin_ip`, `cache_seconds`
- mirror marker: `<meta name="kmj-staging-mirror" content="production-home">`

- [ ] **Step 1: Write failing route/mirror tests**

Cover enabled staging host returning fetched production HTML, injected `<base href="https://kmjtechno.com/">`, noindex header/meta and marker. Cover non-staging hosts retaining the normal Inertia welcome page. Cover cached last-known-good fallback after a simulated origin failure.

- [ ] **Step 2: Run focused test and verify RED**

Run: `php artisan test tests/Feature/StagingProductionHomeMirrorTest.php`
Expected: FAIL because the mirror service/controller do not exist and `/` still renders `welcome`.

- [ ] **Step 3: Implement minimal mirror service and controller**

Use Laravel HTTP client with TLS verification enabled and cURL `CURLOPT_RESOLVE` for `kmjtechno.com:443:<origin_ip>`. Cache successful source HTML briefly and retain a longer last-known-good copy. Return only the HTML body with staging noindex/marker injection; do not copy upstream cookies or headers.

- [ ] **Step 4: Verify GREEN and production-host isolation**

Run the focused feature test plus existing public/staging monitoring tests. Commit only after both pass.

---
### Task 3: Deploy and QA the staging mirror without losing `/info`

**Files:**
- Modify: `.github/workflows/staging-vps-deploy-fixed.yml`
- Modify: `ops/staging/browser-qa.mjs`
- Modify: `ops/staging/browser-qa.test.mjs`
- Modify: `tests/test_staging_monitor_contract.py` only if contract assertions require the new root marker.

**Interfaces:**
- staging `.env` gets `KMJ_STAGING_HOME_MIRROR=true`, `KMJ_PRODUCTION_WEB_ORIGIN=https://kmjtechno.com`, `KMJ_PRODUCTION_WEB_ORIGIN_IP=138.252.200.74`, and a bounded cache duration.
- deployment progress verification always targets `https://staging.kmjtechno.com/info`, never `/`.
- browser QA root marker becomes the deterministic staging mirror marker; `/info` retains `Staging live operations monitor`.

- [ ] **Step 1: Add/adjust QA tests first**

Update Node contract tests so root mirror marker is mandatory and redirected/blank/failed pages still fail. Keep `/info` marker checks unchanged.

- [ ] **Step 2: Run QA contract tests and verify RED before workflow wiring**

Run: `node --test ops/staging/browser-qa.test.mjs` plus the staging monitor Python contract test. Expected RED until `browser-qa.mjs` uses the new root marker.

- [ ] **Step 3: Wire deployment configuration and `/info` progress verification**

Persist the four non-secret staging mirror variables idempotently before Laravel config caching. Change the rendered progress UI check to fetch `/info`, while keeping the HTTP root health probe and authenticated smoke gates.

- [ ] **Step 4: Run action/workflow contracts and commit**

Run local syntax/contract checks available in the repository, then let self-hosted Linux CI be authoritative for Actions behavior.

---
### Task 4: CloudOS entitlement-backed licensing eligibility and Purchase Center presentation

**Files:**
- Create: `apps/platform/app/Services/Licensing/CloudOSLicenseEligibility.php`
- Modify: `apps/platform/tests/Feature/ManualSalesFlowTest.php`
- Modify: `apps/platform/resources/js/pages/purchase.tsx`
- Modify: `apps/platform/resources/js/data/delivery-progress.ts`
- Modify: `KMJ_TECHNO_MAIN_PLATFORM_MASTER_ROADMAP_BLUEPRINT_V1_0.md`

**Interfaces:**
- `CloudOSLicenseEligibility::eligibleEntitlement(string $organizationId): ?Entitlement`
- eligibility requires product slug `kmj-cloudos`, active product, active entitlement, and capability `cloudos.platform.access`.
- Purchase Center visually identifies KMJ CloudOS as the cloud operating platform and states that commercial access is licensed by KMJ Main Platform.

- [ ] **Step 1: Write failing commercial authority test**

Sync canonical products, request a CloudOS order, confirm payment, assert eligibility is still absent, explicitly fulfill the order, then assert `CloudOSLicenseEligibility` returns the resulting active entitlement. Also assert an unrelated product entitlement cannot satisfy CloudOS eligibility.

- [ ] **Step 2: Run focused sales test and verify RED**

Run: `php artisan test tests/Feature/ManualSalesFlowTest.php`
Expected: FAIL because `CloudOSLicenseEligibility` does not exist.

- [ ] **Step 3: Implement minimal eligibility service and branded Purchase Center copy**

Query canonical product by slug/status, then active entitlement by organization/product/capability. Do not issue a production signing credential in this task. Update the CloudOS product card copy without changing generic product behavior.

- [ ] **Step 4: Update roadmap/evidence and run the full required gates**

Record Main Platform -> CloudOS product/licensing authority and future hosting topology in the master blueprint snapshot. Update delivery evidence without claiming release completion. Run focused PHP/Node tests, Verify Foundation, Platform Runtime CI, then merge only after both required gates are green.

- [ ] **Step 5: Verify staging end-to-end after merge**

Require staging promotion, exact-SHA VPS deploy, root production-home mirror marker, `/info` operations monitor, `/info/status`, `/dashboard`, `/operator/ops`, and `/purchase` authenticated smoke to pass before marking this sprint complete.
