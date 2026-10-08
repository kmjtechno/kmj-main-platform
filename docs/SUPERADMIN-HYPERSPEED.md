# KMJ Super Admin HyperSpeed — protected implementation contract

## Identity and authority

The intended Super Admin account email was confirmed as **`kmjtechno.net@gmail.com`** on 8 Oct 2026; the owner states this is currently the sole Main Platform account. The server-controlled `KMJ_SUPER_ADMIN_EMAIL` configuration defaults to this email solely as an **identity allowlist**, not an authentication method or privilege grant. Live account ownership and database state have **not** been independently verified. The subject must still be an **already-provisioned Platform Owner**, with a verified email, enrolled passkey and fresh password-confirmed operator session. Never silently grant `is_platform_owner` based only on an email string.

`GET /operator/super-admin/development-profile` is authenticated readback of this management policy, **not** an entitlement issuer. It cannot make a Professional license Owner, enable paid model APIs, grant roles, or override signatures.

All KMJ-owned canonical products can be managed through existing operator authorization; individually licensed executables still require their proper product entitlement and signed renewal. Access to third-party providers, ChatGPT plugins or GitHub Actions is controlled separately by those services.

## Unlimited goal vs. actual physical limits

- **No commercial cap on planning/logical tasks** for the verified internal development owner.
- **Not unlimited simultaneous execution.** Current CodeBridge Owner license schema has a signed maximum of 16 jobs *per authorized device*, and runtime admission additionally checks real CPU, RAM, disk, journal/queue pressure, access grants and safe worktree locks. Current live Professional license has only one effective slot. Never patch the client to pretend otherwise.
- Horizontal scaling requires each node and repo to be separately enrolled and legitimately licensed. Worktrees cannot have concurrent writers over overlapping paths.
- Signed production release, rollbacks, provenance, tenant binding, passkey, independent verification, audit and CI gates remain mandatory.

## Cost safety

- Default **new paid-provider spend is ₹0** until an authenticated owner explicitly approves a monthly rupee cap. The existing VPS's subscription is separate.
- Default provider order: authenticated legal free quota, other free cloud providers with approved data-handling terms, already-included allowances, then metered models **only if** monthly budget has been explicitly set; no unknown-cost fallbacks.
- Persist model request reservations and spent budgets across restarts. Alert at 50/80/100% and stop at 100%, including concurrent-flight reservations.
- Do not configure unlimited credit card spending or assume unlimited provider quota. Do not buy GitHub plans or register GitHub Actions runners without separate owner approval.

## HyperSpeed delivery critical path

1. Finish authorized signed Owner tier activation from the existing PR with legitimate green/approved CI and live signed readback. Do **not** bypass GitHub account restrictions.
2. Finish KMJ Agent P1 source-verified per-hunk review, and independently verified Rust/Node CI for its separately approved CodeBridge project.
3. Connect existing ModelFabric/KMJ Agent free-model router and durable quota ledger to CodeBridge jobs, one writer per isolated worktree, with 3–5 specialist logical roles initially.
4. Admit actual parallelism from signed entitlement + per-node resources + free provider quota. Separate research/review/test roles from write locks, preserve context at failovers, checkpoint every change and require exact-head CI.
5. Benchmark a representative set of independent development tasks against a one-agent baseline: median end-to-end minutes, P95, dollars/rupees spent, calls, test retries, regressions. Increase workers only when observed quality and throughput improve.

**No guarantee that months of arbitrary engineering can be completed in minutes**; a multi-worker pool accelerates independent tasks, while complex dependent tasks and compilation still take real time.
