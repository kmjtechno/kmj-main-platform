# KMJ Knowledge Memory — PostgreSQL-first safe integration

## Baseline and provenance

Research source: [Gentleman-Programming/engram](https://github.com/Gentleman-Programming/engram), source reviewed at `8828249aa5abad414644c11bdf44665a4e18b3c9`; code MIT (retain notices if copying). This implementation is independently authored for KMJ's existing Laravel/PostgreSQL stack; no Engram code, binary, trademark or server is embedded.

Engram's valuable ideas are **curated agent memory**, topic-key revisions, progressive retrieval, project-scoped decisions and lessons, conflict surfacing, session handoffs and replay-safe saves. CodeBridge already owns operational checkpoint truth, Git SHA, CI evidence, file reservations and autonomous leases. Knowledge Memory never replaces or grants those authorities.

## Safety contract

- **PostgreSQL-first**, using the Main Platform's already-configured database connection. No new database, server, extension, API model or paid service.
- Organization + project are part of *every* read/write predicate. Authentication, active entitlement and membership must be verified by a separate owner/tenant-scoped controller **before** accessing this internal service. Do not expose this service over a public route as part of the first implementation.
- Project keys are explicit, bounded and immutable. No cwd, Git folder-name or ambient-project guessing. No cross-project reads (including aliases/dependency projects) without a separately reviewed allowlist.
- Only deliberate, sanitized, bounded **non-sensitive curated** observations may be stored. Deny obvious key, credential and raw prompt/transcript patterns. A denylist cannot prove absence of secrets; callers must review content before save.
- A stable topic key may be revised with a strict expected revision. Every mutation requires a unique idempotency key scoped to its organization+project. Changed-payload replay must fail. Concurrent same-topic creation must be serialized by DB constraints.
- Database transactions cover memory writes and replay receipts atomically. No network call in a write transaction.
- Search is bounded and read-only. Where PostgreSQL is available, use its native `simple` full-text search with a GIN index; use the SQLite LIKE test fallback solely for CI portability.
- No prompt copying, personal-scope sync, automatic cloud replication, auto-hydration into prompts, autonomous instruction execution, or implicit memory sharing.
- Query results are **untrusted context** and may be stale or wrong. Live GitHub, CI, task, policy and device evidence stay authoritative. Cap output sizes so memory retrieval does not overflow chat context.
- Schema migration is additive and inert. Never run a production migration, enable HTTP/MCP tools, or deploy without an independent backup/rollback review and release gate.

## Planned source slice on this branch

1. Add isolated additive `knowledge_observations` and `knowledge_write_receipts` tables with composite ownership and indexes.
2. Add a bounded Laravel service for atomic topic-revision saves, idempotent retries and read-only search.
3. Add SQLite-testable cross-organization/project safety, stale revision, replay conflict and secret rejection regressions.
4. Verify Laravel CI and syntax. Keep functionality internal until the production authorization and connector contract is separately reviewed.

## Future optional features — not activated by this PR

- Scoping via existing CodeBridge entitlement + real organization membership, explicit consent-gated API, read-only MCP bridge, compact context injection with token budget, conflict review, freshness/retention workflow, governed inter-project dependency retrieval, migration/restore rehearsals, metrics and operator UI.
- PostgreSQL has no dependency on Engram Cloud's separate Postgres server. In particular do **not** copy Engram's `personal` scope sync behavior; upstream documents that this does not constitute a privacy boundary.
- Windows P720 rollout, active client tools and performance improvements require independent live tests, not just merged code.

Acceptance: no billing or existing production route changes; no cross-tenant leakage, unauthorized writes, duplicate operations, silently truncated inputs or implied autonomous execution.


## Implemented behind default-off flag (PR #443)

The main-platform feature now includes:
- `apps/platform/config/knowledge_memory.php`: `KMJ_KNOWLEDGE_MEMORY_ENABLED=false` by default.
- `apps/platform/routes/knowledge-memory.php`: three **browser-session web routes** under `auth` + `verified`: `GET /services/kmj-codebridge/knowledge-memory?query=...`, `GET /services/kmj-codebridge/knowledge-memory/{observation}`, `POST /services/kmj-codebridge/knowledge-memory`.
- `KnowledgeMemoryController` derives organization only through the existing membership-backed active CodeBridge entitlement resolver; members may read their own organization's `kmj-codebridge` knowledge, owner/managers may explicitly write only after recent password confirmation and CSRF protection. Read/write throttles and private/no-store cache policy are used.
- Project is **hard-pinned** to `kmj-codebridge`; no request, header, session or model field can expand that grant. This implementation is not yet an OAuth/machine-to-machine endpoint.
- Bounded memory writes, scoped uniqueness, replay-safe write receipts, strict revision conditions and compact scoped searches live in the internal PostgreSQL store.
- No automatic capture, ChatGPT history import, sync, P720 deployment, network inference or data migration at source import.
- `scripts/ci/verify-postgres-staging.sh <exact-git-sha>` was extended to require both memory tables, native GIN index, focused memory tests and clean rollback against a disposable UNIX-socket PostgreSQL cluster.

**Activation block:** Unless this exact candidate has executable GitHub Actions PASS, isolated real PostgreSQL verification PASS and a backup/rollback rehearsal, leave the feature flag `false`. Do not flip it through CodeBridge or an AI request. A signed, authenticating CodeBridge API adapter requires separate authorization and deployment gates.

## Evidence status

GitHub run scheduling can fail independently of source tests. Do not label any job that failed before a test step as an application regression without a runnable stack trace, and do not treat it as PASS. A running/green CodeBridge hosted smoke does not prove this Main Platform database feature is deployed.
