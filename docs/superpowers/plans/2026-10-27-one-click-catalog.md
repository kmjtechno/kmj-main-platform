# One-click AI catalog draft implementation plan

> **For agentic workers:** Use superpowers:executing-plans in this session.

**Goal:** One click fills and adds a private product/service draft with existing automatic SEO/GEO.

**Architecture:** Existing Laravel catalog manager and cloud adapter; React quick-create view; current server/React metadata pipeline.

**Tech Stack:** PHP 8.4, Laravel, React, TypeScript.

**Spec:** docs/superpowers/specs/2026-10-27-one-click-catalog-design.md

## Global Constraints
Zero additional cost; cloud-only inference; preserve owner/passkey gates and locked branding; no production activation or migration; no invented commerce/release claims.

## Review Focus
Concurrent/duplicate create; provider failure; guest access; service metadata parity; uploaded artwork continuity. Cover through Feature tests and staging deployment guards.

### Task 1: One-click creation and metadata
- [ ] Add failing Feature tests in OwnerProductDraftWorkflowTest.php for owner-only ai-create, complete hidden planned save, duplicate prevention, provider failure, service/FAQ metadata.
- [ ] Verify red in hosted CI.
- [ ] Add ai-create action to OwnerProductStudioController and route; serialize slug and reuse current generator/manager, force hidden planned non-commercial defaults.
- [ ] Add QuickProductCreator.tsx with title/type/category/public facts and one AI fill & add button; show saved fields, manual editing and truthful artwork fallback.
- [ ] Add offering_type validation and existing metadata Service/FAQ/custom-image parity in PublicInitialMetadata.php and products/show.tsx.
- [ ] Run full CI, fresh code review, merge and staging promotion.
- [ ] Prepare hash-pinned staging-only updater preserving env/uploads; user executes root step; real generation remains to be verified after deployment.
