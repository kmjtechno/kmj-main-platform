# KMJ GitHub control contract

Owner requirement2026-10-07: this project must be controlled from GitHub and resumed by another tool-enabled coding agent without the prior chat. GitHub is the authoritative task/configuration/review/evidence store; VPS services are the execution layer. This document is a locked requirement and implementation contract, NOT a claim that the command bridge is deployed.

## Current truth

Source, handover, ordered tasks and tested branch changes are pushed to kmjtechno/kmj-main-platform, feat/modelfabric-autonomy-20261007. Runtime0340c0b is deployed. Persistent workers and CPU fallback are active; queue/task control is currently local. GitHub issue-to-queue, pause/resume, status publication and exact-SHA release commands are NOT connected to this worker.

Existing autonomous-worker.yml and autonomous-cycle.yml require self-hosted runners and an older destructive checkout worker; the former enables auto-merge. Do not activate/reuse these as the new bridge. Do not change account/branch protection or enable unrestricted issue execution. Preserve unrelated product workflows. Reconcile legacy policy declarations before any eventual main merge.

## Required control model

1. GitHub owns a versioned control manifest and explicit task specifications. Issues/PRs provide the human interface; validated manifest records are the machine interface. Repo files offer a low-credit initial integration using existing git access without creating a new repo.
2. VPS reads approved control records using outbound authenticated access; no new public shell endpoint and no GitHub self-hosted runner. A read-only fetch must not checkout/reset/clean a developer repository. Use an isolated control mirror and pinned repository identity.
3. Initial supported commands: pause new claims, resume, enqueue bounded plan/review/text/patch artifact tasks, and request sanitized status. Pause allows active work to checkpoint; it is not an uncontrolled process kill. Deploy/merge/arbitrary shell are not initial commands.
4. Command IDs + repository/ref + exact commit SHA form durable idempotency keys. Validate the complete batch before admitting work. Reject unknown operations, unsafe project aliases, oversized payloads and stale/replayed conflicts. Private classification is default; public must be explicit. Existing free-only policy remains authoritative.
5. Incoming task status: queued -> running -> artifact_ready / candidate_tested / blocked / failed. Never translate completed artifact into completed product. Include source SHA, taskID, tests, attempts and sanitized failure code in reports; no secrets or private prompts in GitHub.
6. Status writeback requires a separately scoped repository credential/App installation (issues/status only as needed). Git push access alone does not establish that API permission. Verify access without printing credentials. Never reuse model provider keys for GitHub.
7. Final changes travel through branches/PRs with exact-head tests. Runtime updates use immutable releases with state preserved and rollback. Broad existing authorization does not justify claiming a failed gate passed.

## Acceptance gates for KMJ-GH-001

- Remote GitHub control change pauses and resumes the actual VPS worker; active task state survives.
- One approved GitHub task is imported exactly once across repeated polls and a service restart.
- Unsupported commands, unapproved repository/ref, malformed batches and private-to-public escalation fail closed.
- Loss of GitHub connectivity cannot corrupt local tasks; last validated control state remains explicit and health reports stale status honestly.
- Sanitized status reaches GitHub only after scoped write access is verified; read-only mode is reported when unavailable.
- Existing160 Python tests and3 schema acceptance tests remain green plus meaningful bridge/replay tests.
- No self-hosted Actions runner installed, no auto-merge enabled, no secrets printed, no dirty checkout reset.

## Low-credit handoff

Implement KMJ-GH-001 first as one bounded reviewed slice. Then KMJ-AUTO-001 addresses the failed live JSON repair quality. Do not spend remaining credits recreating architecture or another repository. Update KMJ-CONTINUE.md with exact code/runtime/command evidence after implementation, not before.
