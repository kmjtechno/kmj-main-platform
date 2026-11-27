# KMJ TECHNO Unified Autonomous Ecosystem — Architecture Proposal v1.0

**Status:** PROPOSED / REVIEW REQUIRED — does not supersede any accepted product ADR, signed contract, released architecture or current operational policy.
**Date:** 2026-10-06
**Home:** `kmjtechno/kmj-main-platform`
**Purpose:** Record the owner's self-reliance, maximum-safe-automation and multi-agent product direction across the KMJ portfolio. This is an architecture/ownership proposal, not evidence of implementation or production readiness.

## 0. Executive decision

Build **KMJ-owned orchestration, data, business authority, security, evaluation, governance and infrastructure management**, with portable interfaces and replaceable external dependencies. The owner should be able to tell Kristi the desired outcome and let multiple specialized agents carry out independent parts of a project concurrently, with test-backed completion and policy-based approval.

**Do not interpret "KMJ-owned" as permission to copy third-party copyrighted code or ignore software licenses.** Maintain provenance, SPDX/SBOM records, reproducible builds, compatibility suites and an exit plan for non-KMJ technologies.

**Existing lock remains:** the Main Platform and Cloud Nexus are separate. Cloud-only generative inference, strict verified-free policy, `NO_FREE_ROUTE_AVAILABLE`, no unapproved paid fallback, single authoritative writer per protected worktree, and owner approval for production/DNS/billing/destructive changes. A proposed KMJ-hosted cloud inference cluster requires its own technical, legal and economic ADR before use and must not silently enable local inference.

## 1. Product ownership map — one capability, one authority

| Component | Owns | Must not own |
|---|---|---|
| **KMJ Main Platform** | Customers, organizations, IAM, billing, catalog, product entitlement, licensing, releases, approvals, audit policy, public/customer/operator portals | Engineering IDE, AI model implementation, machine shell, live remote-desktop data plane |
| **KMJ ModelFabric** (proposed independently deployable service) | Provider/model registry, discovery, qualification, unified inference contract, prompt/capability routing, pricing/quota evidence, cost controls, failover, context handoff envelopes, model telemetry | Software engineering plans, business entitlements, unrestricted execution, hidden paid activation |
| **Kristi** (governed operator experience) | User intent and conversation, outcome specification, planning/delegation to domain engines, progress/approvals, notifications, accessibility/mobile/voice | Direct privileged shell, unverifiable completion, bypass of Main Platform risk tiers |
| **KMJ Forge** | Reusable software-engineering workflow engine, task DAGs, specialist-agent work allocation, patch/review/test policies, quality/evaluation harness, portable skills | Provider price authority, corporate licensing, direct infrastructure admin |
| **KMJ Agent** | Bounded agent worker runtime, context/session persistence, tool-turn execution, attempts/checkpoints, agent status | Second independent provider/router source of truth, direct production deployment |
| **KMJ Cloud Nexus** (`kmj-autonomous-cloud-ide`) | Independent Code-OSS IDE, project/session UX, debugger, developer review, interaction with Forge/Agent/CodeBridge via versioned contracts | Main Platform business backend, another enterprise model registry or business database |
| **KMJ CodeBridge** | Authorized remote project/device connectors, scoped Git/file/test/command capabilities, agent enrollment, execution audit and policy enforcement | AI model selection, billing ledger, unrestricted shell |
| **KMJ Desktop Commander** | Desktop/VPS operator UI and authorized admin workflows atop shared execution interfaces | Duplicate remote-execution gateway or ad-hoc privileged bypass |
| **KMJ CloudOS** | KMJ-controlled provisioning, compute/VM/storage/network, backup/restore, deployment, fleet health, observability and infrastructure policy | Commerce/product licensing authority, autonomous production bypass |
| **KMJ OmniDesk** | Direct-first secure remote sessions, screen/audio/input/file transport and client behavior | Main Platform's billing authority or shared AI router |
| **KMJ CineCore** | Deterministic cinema playback, sync, stereo, digital twin, motion safety, show automation | AI-controlled safety-critical motion without deterministic interlocks |
| **KMJ Calibration Pro** | Structured-light measurement, geometry, warping/blending, calibration provenance and hardware qualification | Fabricated physical-calibration PASS from AI text |
| **KMJ MotionDirector** (product; repo not found in inspected account inventory) | Motion extraction/editing, interpolation, timeline/export; interface contracts with CineCore | CineCore safety kernel |
| **Company profile/website** | Public approved claims, branding, published documentation | The source of technical PASS claims |

The existence of a repository/module is not proof of product completion. Proposed components without repositories require a separate repo/ownership ADR before code migration.

## 2. Audit snapshot and outstanding work (GitHub, 2026-10-06)

Repositories visible in connected account: 11:
`kmj-main-platform`, `kmj-autonomous-cloud-ide`, `kmj-agent`, `kmj-cloudos`, `kmj-calibration-pro`, `kmj-forge`, `kmj-desktop-commander`, `kmj-omnidesk`, `kmj-codebridge`, `kmj-cinecore`, `kmjtechno`.

- **Main Platform:** existing modular-monolith boundaries, Kristi risk-tier ADR and organization → entitlement → signed sandbox licensing foundation. A current customer-control-center PR (#325) had queued workflows; not PASS. Its `controller/model_router.py` independently implements cloud routing and is a planned adapter-extraction seam, not an immediately removable module. Other open PRs are not assumed merged.
- **Cloud Nexus:** `rust-core` exists. Its roadmap already defines autonomous missions, persistent sessions and cloud router. Root README is still upstream Code-OSS text; product branding/deployment evidence needs review. One visible workflow run is a dependency-graph success, not end-to-end IDE CI certification.
- **KMJ Agent:** dedicated Rust router, context, quota, session, lease and tool crates exist, but recent CI runs failed. `kmj-router` currently hardcodes OpenRouter URLs and a Gemini route: portability/registry integration should be redesigned safely; do not introduce a third router.
- **Forge:** reusable Python engine and tests; recent CI/CodeQL green, explicitly early-development. Its roadmap calls for local-first models whereas Main Platform/Cloud Nexus lock *no local generative inference*. Resolve by scoped product policy ADR, not silent reinterpretation of existing roadmap.
- **CodeBridge:** scope-aware gateway, autopilot and execution files exist; 2026-10-06 icon branch #140 had recent successful CI. UI appearance/production plugin branding is not proven by CI alone. Main Platform CodeBridge pairing/installer PRs remain open.
- **CloudOS:** broad infrastructure source modules and engineering queue; its status file explicitly says production readiness BLOCKED. Older security verification workflow failures are visible; latest dependency-graph success does not clear them.
- **Desktop Commander:** CI green on several dependency branches but some cross-platform installer jobs failed. No signed cross-OS stable release asserted.
- **OmniDesk:** main CI green, pre-alpha; REALNET-60 external-network evidence and production signer integration gated.
- **CineCore:** actual C++/Qt6 engines and measured software checkpoints; multiple newer PR workflows failed; software/hardware verification must be separated, current-head CI cannot be called green.
- **Calibration Pro:** buildable C++ foundation, not a verified working calibration product; zero visible Actions runs and hardware execution unknown.
- **Profile:** public presentation, not a software service.

This is repository/docs/workflow inspection, not a host penetration test, deployment validation, hardware test or complete line-by-line code audit.

## 3. Canonical request and execution flow

```text
Owner / customer / IDE / mobile / voice
  -> Kristi intent + constraints + identity
  -> Main Platform authorization / approval policy / spending rules
  -> Domain router:
       Engineering -> Forge task DAG + specialist workers (KMJ Agent)
       Infrastructure -> CloudOS plan
       Remote operation -> Desktop Commander / OmniDesk
       Business support -> Main Platform scoped domain APIs
       Cinema / calibration -> each product's deterministic engine
  -> ModelFabric cloud inference (replaceable provider adapters)
  -> CodeBridge scoped execution for approved dev tools or CloudOS scoped ops
  -> deterministic build/tests/security/hardware evidence
  -> independent verifier + status ledger
  -> owner-visible result / gated release / audit
```

No data-plane request should need the Main Platform database directly. Communication occurs through versioned REST/RPC/events and signed, scoped work tokens. The Main Platform retains policy authority, not operational monopoly over every data packet.

## 4. Kristi mission contract

Minimum durable fields: mission_id, tenant_id, principal, objective, constraints, product/repo scope, canonical branch + base commit, permitted tools, data classification, approved spend (default zero), model policy, acceptance tests, risk tier, rollback plan, deadlines (if set), dependency DAG, agent leases, checkpoints, tool audit refs, result artifacts, user approval refs and final verification evidence.

Lifecycle: `CREATED -> POLICY_CHECKED -> PLANNED -> READY -> RUNNING -> VERIFYING -> {DONE | BLOCKED | PAUSED | FAILED | CANCELLED}`.

- Kristi may decompose work and schedule agents, not invent permissions.
- Specialists include architect, implementation, UI/UX, testing, security, performance, compatibility, documentation, independent reviewer and release operator.
- Use independent **worktrees/branches per writer**; one authoritative writer per protected worktree. Parallelize reads, research, planning, testing and separate work packages, not conflicting writes to the same files.
- Every assignment has a bounded time/token/tool budget, cancellation, retry ceiling, deterministic verification and an immutable checkpoint.
- Final `DONE` requires exact-head checks and evidence; no evidence = not done.
- Resume idempotently after crash/outage/restart; expired leases should be requeued without duplicate side effects.
- Existing accepted Main Platform ADR-005 risk policy controls actions: Tier A reversible autonomous; Tier B bounded/guarded; Tier C owner approval for public/financial; Tier D critical/destructive owner plus second control.
- When cloud inference has no eligible free route, report `NO_FREE_ROUTE_AVAILABLE` and perform only safe deterministic tasks.

## 5. ModelFabric: automatic model discovery and switching

Pipelines:
1. **Discover:** official provider catalogs/metadata, licensed public sources and versioned adapters. Poll on a resource budget, with exponential backoff; no invasive scraping.
2. **Normalize:** model identity, provider, region, context, tool calling, vision/audio/streaming/structured outputs, public pricing and timestamps; mark unknown as unknown.
3. **Qualify:** API/contract/schema, toxicity/abuse/privacy policy, prompt-injection resilience, tool-call fidelity, long context, coding tests, performance, provider health and reproducibility.
4. **Certify free status:** independently verify actual route, billing-account conditions, input/output/tool fees, free-tier caps and expiration. Require fresh provenance; unknown cost is NOT zero.
5. **Canary:** isolate and replay representative tasks; compare against current stable, reject regressions and unauthorized model/data handling.
6. **Activate:** promote only if eligible, under workload/tenant policy; maintain previous known-good routing until new route qualifies.
7. **Operate:** quota reservations; forecast depletion before execution; bounded retries, context checkpoints, warm standby, circuit breaker, health-weighted routing.
8. **Decommission:** revoke credentials, quarantine failing routes, expire unsafe attestations, retain versioned audit.

**Cost policy:** Verified zero-cost cloud route first. No paid automatic fallback, no paid inference, no silent new billable services. An owner-approved paid mode would require a separate future ADR, explicit authorization, accounting and billing limits.

**Ownership strategy:** KMJ owns registry, adapter API, qualification and telemetry. Individual cloud model providers remain replaceable third-party dependencies. If full inference sovereignty is later required, evaluate a KMJ-controlled remote/cloud GPU inference plane as a *new and separately costed/approved proposal*; do not imply that operating a GPU/model is free or compatible with current locks without review.

## 6. Engineering speed: pipeline, not agent count

Independent work packages should be parallelized only after a task DAG identifies non-overlapping ownership; otherwise use sequential integration. Prefer cached toolchains and deterministic code analysis before token-heavy reasoning. Run targeted tests per patch, full CI at integration. Enforce secure sandbox and provenance before model-generated code runs. Use blue/green/canary deployment, exact-SHA release artifacts, rollback and signed attestations. Never merge just because an AI model or a single green check says PASS.

Key measurable KPIs: verified mission success rate; exact-head CI pass rate; lead time to PR and to audited release; effective cost per independently verified task; retry/rollback rate; unauthorized action count (target zero); quota outage recovery; resume-after-crash fidelity; security vulnerabilities; real hardware/real-network pass coverage. Benchmark against a held-out, rotating set of real KMJ repos/tasks, not only public contaminated benchmarks.

## 7. Shared standards and anti-lock-in

- All product integrations through owned, versioned contracts; generated clients/conformance tests; no implicit shared database or hardcoded provider authority.
- Adopt interoperable transport/API conventions (e.g. REST, OpenAPI, MCP where useful) without making any third-party hosted endpoint mandatory.
- Maintain self-controlled, tested backups of Git, releases, CI logs, design decisions, registries, identity recovery and artifacts, including restore drills; GitHub may remain collaboration interface, not sole survivability boundary.
- Pin dependencies with SBOMs, license attribution, vulnerability review and reproducible builds; support transparent upgrades and exit plans.
- Own domain event and audit schema, tenant isolation, secrets vault, scoped device identities, release certificates and evidence retention.
- Full local/offline *deterministic tools* are permitted; prior prohibition applies to local generative model inference in the locked Main Platform/Nexus scope. The Forge local-model roadmap conflict remains unresolved until a dedicated ADR settles policy per product.

## 8. Work packages, dependency order and gates

**F0 — Stabilize current foundations:** inventory/open PR triage; main branch/CI permission gate, CodeBridge VPS enrollment/reliability/branding verification, KMJ Agent CI failures, CloudOS security CI, exact-head CineCore failures, desktop packaging failures and baseline visibility. Do not call external/hardware tests complete.

**F1 — Freeze cross-product contracts:** authoritative `MissionV1`, `AgentAssignmentV1`, `ModelRouteV1`, `ToolGrantV1`, `EvidenceV1`, `ApprovalV1`, `ReleaseIntentV1`. Add contract conformance CI in the existing product repos before moving code.

**F2 — Consolidate router:** extract duplicated Main Platform and Agent model-route behavior behind a versioned ModelFabric client/service without disrupting known-good flows. Establish free-route firewall, capability tests, catalog, quota forecast and fallback. Decide repository location and custody via ADR; do not opportunistically migrate production.

**F3 — Unify autonomous engineering:** Forge is the canonical reusable engineering engine; KMJ Agent is bounded worker runtime; Cloud Nexus is IDE and session interface. Add task-DAG lease scheduling, worktree isolation, evidence ledger, retry policy and resumable multi-agent milestones; reuse CodeBridge tools.

**F4 — Kristi Universal Operator:** identity-linked mobile/web/voice assistant using Main Platform ADR-005. Support natural-language project creation, status, error reports, approvals and multi-project concurrency. No unrestricted machine control.

**F5 — CloudOS independence:** secure service operations, isolated staging environments, backups/recovery, self-controlled CI/runner/artifact mirrors, and optional independently approved KMJ cloud inference proposal.

**F6 — Product integrations:** OmniDesk, CineCore, Calibration Pro, MotionDirector, Desktop Commander and future products consume entitlements, SDK contracts, observability, support/agent operations, and certified model capabilities without importing ModelFabric internals.

**F7 — External-quality qualification:** real-device trials, real network tests, publishable security/performance metrics, accessibility, multilingual UX, installer signing, rollback drills, customer support and release readiness.

Gates for every phase: owner-approved scope where necessary, contract tests, exact-head CI, security/privacy review, deterministic rollback, evidence artifact, no unresolved P0 and no fabricated production completion.

## 9. Explicit decisions requiring review

1. **Product naming/repository location:** new dedicated `kmj-modelfabric` and `kmj-kristi` repos versus extracting from existing modules. Proposed: separate deployable services with independent repos after interface freezes; no duplicate implementation.
2. **Local model conflict:** Forge roadmap says local models are first class, while Main Platform/Nexus prohibit local LLM inference. Proposed: retain previous Main Platform/Nexus prohibition; resolve Forge scope through separate reviewed ADR; KMJ-hosted *remote cloud* inference is only a possible later proposal.
3. **Financial independence:** owner-funded hosting is not equivalent to verified-zero inference. Any billable GPU/provider/CI/commercial action remains approval-gated.
4. **Existing router migration:** staged, compatibility-checked extraction; no delete/rewrite of verified existing production path before cutover gates.
5. **Public claims:** no "world number one" marketing until controlled, published comparative evidence exists.

## 10. Non-goals of this proposal

No code migration, no creation of live autonomous workers, no production deployment, no permission change, no network/DNS/billing changes, no merge, no change to Main Platform master blueprint or Cloud Nexus's locked boundaries. Future acceptance requires an ADR, reviewed PRs and passing gates per repository.
