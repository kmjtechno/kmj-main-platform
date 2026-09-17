# KMJ Main Platform Product Hub V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the first evidence-backed KMJ product hub slice with a public product catalog, truthful lifecycle states, deterministic virtual-demo scaffolding, and reusable licensing/catalog foundations for KMJ CloudOS and KMJ Calibration Pro.

**Architecture:** Keep Main Platform as the commercial/licensing authority. Add a presentation projection layer over canonical catalog facts, public read-only product routes, and deterministic browser-only demo state machines. Reuse the existing entitlement and sandbox-license authority chain; do not introduce production signing keys or client-side authority.

**Tech Stack:** Laravel 13, PHP 8.3, Inertia, React 19, TypeScript 5.7, existing KMJ domain packages, existing Rust sandbox license core.

**Spec:** `docs/superpowers/specs/2026-09-17-product-hub-licensing-virtual-demos-design.md`

## Global Constraints

- Git is the source of truth; work in an isolated branch/worktree.
- TDD is mandatory: every production behavior starts with a failing test.
- Public copy must reflect verified repository/product lifecycle state; no fabricated accuracy, price, customer, deployment, or benchmark claims.
- KMJ Calibration Pro is listed as development/preview until its repository evidence changes.
- Production signing/key custody remains owner-gated and is out of scope.
- Virtual demos are deterministic simulations and must be visibly labeled as demo/simulation.
- Main Platform remains the sole commercial/licensing authority; product clients never get database access.
- Do not touch KMJ Cloud Nexus.
- Exact-head CI must be green before merge; staging promotion uses the existing verified chain.

---### Task 1: Canonical multi-product catalog projection

**Files:**
- Create: `apps/platform/app/Services/Commerce/KmjProductCatalog.php`
- Modify: `apps/platform/app/Services/Commerce/CloudOSProductCatalog.php`
- Test: `apps/platform/tests/Feature/KmjProductCatalogTest.php`

**Interfaces:**
- Produces: `KmjProductCatalog::syncAll(): array<string, Product>` and canonical product metadata for `kmj-cloudos` and `kmj-calibration-pro`.
- Consumes: existing `ProductCatalog` and `EntitlementPolicyRegistry` services.

- [ ] **Step 1: Write failing catalog tests** proving both products sync idempotently, CloudOS remains active/commercial, and Calibration is created with a non-purchasable preview lifecycle until explicitly promoted.
- [ ] **Step 2: Run RED** with `cd apps/platform && php artisan test tests/Feature/KmjProductCatalogTest.php`; expect missing service/class or missing second product behavior.
- [ ] **Step 3: Implement minimal catalog projection** using canonical slugs/names/capability codes and existing domain services; no duplicate product rows or conflicting policies.
- [ ] **Step 4: Run GREEN** for the new test plus `tests/Feature/CloudOSProductCatalogTest.php`.
- [ ] **Step 5: Run static checks** with `composer lint:check` and `composer types:check`.
- [ ] **Step 6: Commit** `feat(catalog): add canonical KMJ product catalog`.

### Task 2: Public product hub read model and routes

**Files:**
- Create: `apps/platform/app/Services/Commerce/PublicProductPresenter.php`
- Create: `apps/platform/tests/Feature/PublicProductHubTest.php`
- Modify: `apps/platform/routes/web.php`

**Interfaces:**
- Consumes: canonical products from Task 1.
- Produces: safe public arrays with slug, name, lifecycle, one-line outcome, verified capabilities, CTA state, and demo availability; no secret/internal authority data.- [ ] **Step 1: Write failing feature tests** for `GET /products` and `GET /products/{slug}`. Assert CloudOS exposes an active purchase/demo CTA, Calibration exposes preview/demo without purchase, unknown slug is 404, and no entitlement/license internals leak.
- [ ] **Step 2: Run RED** with `php artisan test tests/Feature/PublicProductHubTest.php` and confirm routes/presenter are missing.
- [ ] **Step 3: Implement presenter and read-only routes** rendering `products/index` and `products/show` via Inertia.
- [ ] **Step 4: Run GREEN** for `PublicProductHubTest.php` and relevant route tests.
- [ ] **Step 5: Commit** `feat(products): expose evidence-backed public product read model`.

### Task 3: Product hub UI and fast-understanding product cards

**Files:**
- Create: `apps/platform/resources/js/pages/products/index.tsx`
- Create: `apps/platform/resources/js/pages/products/show.tsx`
- Create: `apps/platform/resources/js/components/products/product-card.tsx`
- Create: `apps/platform/resources/js/components/products/product-proof-strip.tsx`
- Modify: `apps/platform/resources/js/pages/welcome.tsx`
- Test: `apps/platform/tests/Feature/PublicProductHubTest.php`

**Interfaces:**
- Consumes: Task 2 presenter props only.
- Produces: responsive product cards and detail surfaces with lifecycle badge, outcome-first copy, 3-4 proof-backed capabilities, primary CTA, and demo CTA.

- [ ] **Step 1: Extend failing feature assertions** for exact Inertia component names and required prop keys before creating React files.
- [ ] **Step 2: Run RED** and confirm missing components/props cause failure.
- [ ] **Step 3: Implement minimal React pages/components** using the existing KMJ visual system; keep first viewport outcome-first and avoid unsupported superlatives.
- [ ] **Step 4: Add Products entry point on `welcome.tsx`** without changing unrelated home-page architecture.
- [ ] **Step 5: Run GREEN** with `npm run check`, `npm run types:check`, and `php artisan test tests/Feature/PublicProductHubTest.php`.
- [ ] **Step 6: Commit** `feat(products): add public product hub experience`.

### Task 4: Deterministic virtual-demo scaffolding

**Files:**
- Create: `apps/platform/resources/js/components/products/virtual-demo-shell.tsx`
- Create: `apps/platform/resources/js/components/products/demos/cloudos-demo.tsx`
- Create: `apps/platform/resources/js/components/products/demos/calibration-demo.tsx`
- Modify: `apps/platform/resources/js/pages/products/show.tsx`
- Test: `apps/platform/tests/Feature/PublicProductHubTest.php`

**Interfaces:**
- Consumes: `demo.kind` and `demo.available` from Task 2.
- Produces: browser-only finite-state demos; no production APIs, device access, worker control, or fabricated measurement truth.- [ ] **Step 1: Add failing prop/contract assertions** requiring demo kind, explicit `simulation` label, and lifecycle-safe CTA behavior.
- [ ] **Step 2: Run RED** and verify missing demo contract fails.
- [ ] **Step 3: Implement CloudOS demo state machine** as `Monitor → Validate → Deploy → Verify` with deterministic sample events and a persistent simulation label.
- [ ] **Step 4: Implement Calibration demo state machine** as `Setup → Capture → Analyze → Results`, using clearly synthetic values and never presenting physical calibration as certified.
- [ ] **Step 5: Run GREEN** with frontend checks and focused feature tests.
- [ ] **Step 6: Commit** `feat(demo): add deterministic product virtual demos`.

### Task 5: Licensing foundation for product-specific capabilities

**Files:**
- Create: `apps/platform/app/Services/Licensing/ProductLicenseProfile.php`
- Create: `apps/platform/app/Services/Licensing/ProductLicenseProfileRegistry.php`
- Test: `apps/platform/tests/Feature/ProductLicenseProfileTest.php`
- Modify: `apps/platform/app/Services/Licensing/SandboxProductAuthorityValidator.php`

**Interfaces:**
- Consumes: canonical product slug/product id and authoritative entitlement state.
- Produces: product-specific capability profile and stable validation reason without exposing signing material.

- [ ] **Step 1: Write failing tests** proving CloudOS and Calibration map to distinct capability profiles, unknown products fail closed, inactive products fail closed, and revoked/mismatched entitlements remain rejected.
- [ ] **Step 2: Run RED** with `php artisan test tests/Feature/ProductLicenseProfileTest.php tests/Feature/SandboxProductAuthorityValidationTest.php`.
- [ ] **Step 3: Implement minimal registry/profile objects** and integrate them into the existing authority validator without changing cryptographic format.
- [ ] **Step 4: Run GREEN** for licensing feature/unit tests and Rust sandbox verifier tests.
- [ ] **Step 5: Commit** `feat(licensing): add product license capability profiles`.

### Task 6: Purchase/CTA integration and lifecycle safety

**Files:**
- Modify: `apps/platform/resources/js/pages/purchase.tsx`
- Modify: `apps/platform/routes/web.php`
- Test: `apps/platform/tests/Feature/CommercialPurchaseTest.php`
- Test: `apps/platform/tests/Feature/PublicProductHubTest.php`

**Interfaces:**
- Consumes: canonical lifecycle/purchasability facts from Tasks 1-2.
- Produces: purchase center that only offers purchase-enabled products; preview products route to demo/details instead of order creation.- [ ] **Step 1: Write failing tests** proving preview products cannot create commercial orders and active purchasable products still can.
- [ ] **Step 2: Run RED** for purchase and product-hub tests.
- [ ] **Step 3: Filter purchase options and order validation** by authoritative lifecycle/purchasability; do not trust client-submitted product ids.
- [ ] **Step 4: Run GREEN** for purchase, entitlement, licensing, and product-hub feature tests.
- [ ] **Step 5: Commit** `feat(commerce): enforce product lifecycle at purchase boundary`.

### Task 7: Integration verification, delivery evidence, and staging readiness

**Files:**
- Modify: `apps/platform/resources/js/data/delivery-progress.ts`
- Modify only if required by existing verification contracts: `docs/architecture/*` or focused evidence docs.

**Interfaces:**
- Consumes: completed Tasks 1-6.
- Produces: verified delivery evidence and an exact-head candidate for CI/staging promotion.

- [ ] **Step 1: Run focused backend suite** covering catalog, public hub, commerce, entitlement, license lifecycle, authority validation, and audit behavior.
- [ ] **Step 2: Run frontend verification** with `npm run check`, `npm run types:check`, and `npm run build`.
- [ ] **Step 3: Run PHP verification** with `composer lint:check`, `composer types:check`, and the relevant `php artisan test` suites.
- [ ] **Step 4: Run Rust license verification** with `cargo test --manifest-path ../../services/license-core/Cargo.toml --locked` from the platform/repository context as appropriate.
- [ ] **Step 5: Run repository gates** including `python scripts/verify_delivery_progress.py`, architecture/contracts checks used by Verify Foundation, and `git diff --check`.
- [ ] **Step 6: Update delivery progress only with verified evidence**; do not convert preview/product claims into verified milestones without proof.
- [ ] **Step 7: Commit** `chore(progress): record product hub verification evidence`.
- [ ] **Step 8: Push implementation branch and require exact-head CI green** before merge/staging promotion.

## Execution order and agent parallelism

- Task 1 must land before Tasks 2 and 5.
- After Task 1, Task 2 and Task 5 may run in parallel because they touch separate presentation/licensing surfaces.
- Task 3 depends on Task 2. Task 4 depends on Task 3's product-detail surface.
- Task 6 depends on Tasks 1-2 and can run in parallel with Task 4 after those prerequisites are complete.
- Task 7 is the integration gate and runs last.
- Maximum safe concurrency: 3 non-conflicting implementation tasks with 2 verification lanes; never allow concurrent writers to the same worktree or file set.
