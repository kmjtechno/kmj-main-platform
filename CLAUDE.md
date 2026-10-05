# KMJ Main Platform — Claude / CodeBridge Operating Contract

## Scope
Work only in `kmjtechno/kmj-main-platform`. This repository is the central KMJ TECHNO business, customer, commerce, entitlement, licensing, release and governed automation authority. Do not collapse KMJ CloudOS, KMJ Cloud Nexus, KMJ CineCore, KMJ OmniDesk or other product runtimes into this repository.

## Read order
Before changing code, read:
1. `KMJ_TECHNO_MAIN_PLATFORM_MASTER_ROADMAP_BLUEPRINT_V1_0.md`
2. `THEME_LOCK.md`
3. `RELEASE_GATE.md`
4. `docs/CODEBRIDGE_PROJECT_SETUP.md`
5. current Git status, latest commits and the files relevant to the task

Newer explicit owner instructions override older roadmap wording only where they directly conflict.

## CodeBridge-first workflow
Use KMJ CodeBridge for real project operations whenever its tools are available.

1. Verify the connected device/project with `connection_doctor` or `inspect_project`.
2. Confirm the project is this repository before writing: inspect `README.md`, `apps/platform/composer.json` and Git status.
3. Inspect narrowly with `repo_map`, `search_code`, `read_file_range` and `git_diff`.
4. Make minimal scoped edits with guarded CodeBridge write/edit tools.
5. Run the smallest relevant configured quality gate first, then the broader gate when the slice is complete.
6. Re-read the resulting diff and exact test output before claiming PASS.
7. Never claim CodeBridge work occurred if the connector/device is unavailable.

Do not request or expose a generic shell through CodeBridge. Use only administrator-configured gates.

## Project identity
Preferred CodeBridge project id: `kmj-main-platform`.

The production checkout is known as `/home/kmjprod/current`, but production must not be used as an unrestricted development scratch tree. If the authorized CodeBridge project points there, preserve production safety: no destructive database actions, no secret rotation, no live deployment, no DNS/billing/signing-key mutation, and no destructive migration without explicit owner approval.

## Locked architecture
- Laravel application: `apps/platform`.
- Main Platform owns organization/account/business authority, subscriptions/orders, entitlement, licensing, releases/downloads, audit, support and governed automation.
- Payment state is not a license.
- Client software is never final licensing authority.
- Private signing keys must not be stored in application data or committed.
- Product clients consume versioned contracts/APIs; they do not get direct database access.
- KMJ Cloud Nexus remains a separate engineering IDE.
- Prefer modular-monolith boundaries unless an evidence-backed need justifies a service split.

## Branding / UI
Follow `THEME_LOCK.md`.
- Premium black/graphite foundation with controlled KMJ red.
- Preserve the canonical KMJ brand assets under `apps/platform/public/assets/brand/`.
- Do not invent customer counts, uptime, revenue, testimonials, compliance or release-readiness claims.
- Public/mobile/accessibility/performance truth matters more than decorative effects.

## Development discipline
- Preserve unrelated user work and uncommitted changes.
- Fix root causes, not screenshots or symptoms.
- Do not weaken validation, authorization, tenant isolation, licensing or release gates to make tests green.
- No paid-model fallback and no local-LLM dependency should be added to product architecture unless the owner explicitly changes that rule.
- Keep secrets, credentials, tokens, private keys and customer data out of source, logs and chat.
- Do not deploy to production merely because local tests pass.
- Exact-head evidence is required for release claims.

## CodeBridge quality gates
The repository provides `scripts/codebridge-quality-gate.sh` for administrator-configured CodeBridge gates:
- `fast`: repository/runtime/contract checks plus diff validation.
- `platform`: Laravel + frontend static/test checks, no production deployment.
- `full`: fast + platform + production frontend build.

Use a stable unique `requestKey` when calling `run_quality_gate` so retries are idempotent.

## Priority
Work in dependency order:
P0 security/data/licensing correctness → failing tests/CI → business authority and entitlement correctness → release/deployment safety → customer/admin workflows → public product experience → polish.

Prefer one complete, tested slice over many half-finished changes.

## Completion report
For every meaningful slice report:
- exact commit / current HEAD;
- files changed;
- gate(s) executed;
- exact PASS/FAIL result;
- remaining blocker;
- next dependency-ready task.

Do not state “complete”, “production ready”, “secure”, or “release ready” without the evidence required by `RELEASE_GATE.md`.
