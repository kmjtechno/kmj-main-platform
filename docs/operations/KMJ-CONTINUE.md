# KMJ: start here to continue without the old chat

Updated 2026-10-07. Owner: Narendra Singh Kushwah / KMJ TECHNO. Reply Hindi or English. User authorizes lawful reversible development and existing VPS operations; do not repeatedly request already-given permission. No paid inference, new spending, quota evasion, secret disclosure or uncontrolled production promotion. Explicit current authorization permits CPU-only emergency fallback; older cloud-only memory does not override it.

## Authoritative source and runtime

Repository: https://github.com/kmjtechno/kmj-main-platform
Branch: feat/modelfabric-autonomy-20261007 (pushed, NOT merged into main).
Deployed code SHA: 28b7eb078e358c6c371acd3792ed04b599dc39a4.
Later branch commits may be control-manifest or documentation-only; compare code before redeploying.
Google source worktree: /home/info/.kmj-worktrees/modelfabric-autonomy-20261007.
Live immutable runtime: /home/info/.local/lib/kmj-autonomy/releases/28b7eb078e35.
Python: /home/info/.kmj-python313/bin/python3.
Original /home/info/work/kmj-main-platform has pre-existing dirty apps/platform/resources/js/app.tsx; preserve it. Never reset/clean live or dirty checkouts.

## What is actually operational

- Google user services kmj-autonomy-worker.service, kmj-github-control.service and kmj-model-fabric-cpu.service are active/running. kmj-backlog-coordinator.path is also active and reacts to validated CodeBridge status refreshes. The GitHub bridge remains outbound-only; no self-hosted Actions runner is used.
- Two asynchronous inference lanes; one running task per canonical project; SQLite atomic claims, leases, fencing, checkpoints, bounded retry. Outage/timeouts defer300seconds without spending generation attempts.
- Strict-zero cloud routing with operator-controlled confidentiality. Built-in public providers cannot grant themselves private-code access. CPU fallback is authenticated127.0.0.1:18766, one inference slot, Qwen2.5-Coder1.5B Q4. No paid fallback. Free availability and small-model quality remain finite.
- Stateful provider/model cooldown, recent HTTP-success preference, bounded failover, token-budget validation. Recent HTTP success is NOT proven engineering quality.
- Artifact tasks plan/review/text/patch. Patch artifact is NOT applied/tested/deployed code.
- Declarative JSON validation remains isolated. In addition, the separately vetted python-cli-v1 executor accepts only exact-scope .py patches with external declarative cases and Bubblewrap isolation. Arbitrary Python/JS execution is still NOT approved.
- Durable JSON workflow does generate -> test -> feedback -> repair, max3iterations, spec/test/base/content binding, crash recovery. No autonomous merge/deploy.

## Verified results and exact failures

196 Python tests PASS; separate3 acceptance tests PASS for committed contracts/kmj-autonomy-task.schema.json. Independent reviews completed. Router fixtures now isolate SQLite and lock paths;29router tests repeated3times without pollution.
Real private/local and public/9router inference succeeded. Synthetic generated-checkpoint recovery succeeded after stopping/starting worker (attempt2); this was not a full VPS reboot test.
Human-orchestrated real model loop: initial CPU JSON failed; feedback to free cloud produced corrected JSON; isolated3tests passed; accepted source commit70dc4f354632f2bff72273f999b7ba9f4ac5aae6.
IMPORTANT: fully automatic live workflow KMJ-schema-autonomous-proof FAILED after3iterations. It ran and repaired automatically, but models kept omitting properties.payload.properties.prompt.description and incorrectly adding max_attempts/data_classification to payload.required or nesting max_attempts inside payload. Do not hide this or claim whole-project autonomy is complete.
Live workflow state: /home/info/.local/state/kmj-autonomy/workflows/KMJ-schema-autonomous-proof/state.json (history, candidates, failures, report).
Service kmj-json-contract@KMJ-schema-autonomous-proof.service is inactive/dead after bounded terminal failure; that is expected. Main worker and CPU service remain active, awaiting tasks.
Queue at final KMJ-GH-001 health check:10completed tasks,1failed task,0running; control paused=false. Completed artifacts are not completed products.

## Safe first commands (Google info account)

Read this file and docs/KMJ-AUTONOMY.md first; do NOT rediscover the entire architecture.

    git -C /home/info/.kmj-worktrees/modelfabric-autonomy-20261007 status --short --branch
    git -C /home/info/.kmj-worktrees/modelfabric-autonomy-20261007 log -5 --oneline
    XDG_RUNTIME_DIR=/run/user/1001 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus systemctl --user status kmj-autonomy-worker.service kmj-github-control.service kmj-model-fabric-cpu.service --no-pager

From live runtime:

    /home/info/.kmj-python313/bin/python3 -m scripts.kmj_autonomy_queue --db /home/info/.local/state/kmj-autonomy/queue.sqlite status

Inspect workflow state through Python, initially print phase/attempt/history only. Do not print credentials or full private prompts.
From source worktree, when needed for a changed code snapshot:

    /home/info/.kmj-python313/bin/python3 -m unittest discover -s tests
    /usr/bin/python3 -m unittest discover -s acceptance/autonomy-schema
    git diff --check

## GitHub control status

KMJ-GH-001 is complete and deployed. GitHub is now the versioned control source for bounded enqueue, pause, resume and sanitized status requests through the outbound-only bridge. Legacy autonomous Actions remain excluded: do not activate the self-hosted/auto-merge workflows as a substitute.

## Next autonomy work, acceptance-defined

Read KMJ-NEXT-TASKS.json as the ordered source of truth. KMJ-AUTO-001 is complete with the preserved failed v1 evidence and a fresh v2 workflow reaching json_candidate_tested without manual candidate edits. KMJ-AUTO-002 and KMJ-AUTO-003 are dependency-ready. Preserve free-only/confidentiality rules, trusted external assertions, bounded retries and the distinction between artifact/tested candidate/product release. Do not overwrite concurrent work already present in the source worktree.

## State, secrets and rollback

State root /home/info/.local/state/kmj-autonomy, queue.sqlite, router-cooldowns.sqlite, artifacts/worker-status.json, github-control-status.json and isolated github-control.git. Specs ~/.config/kmj-autonomy/workflows; proof input /home/info/.local/state/kmj-autonomy/workflow-input pinned3f87cf9d1312ac50e7a678ab33d9ae3eb22f545f; trustedtests acceptance/schema-v2 outside repository. Do not move its HEAD while validating an existing spec.
Secrets only in ~/.kmj/9router-client.env and ~/.config/kmj-model-fabric/local.env plus local-api-key (0600); read into process environment without printing. Keep KMJ_OPENCODE_FREE_ENABLED=false: legacy blocking thread subprocess is not cancellable. Do not enable paid/unknown-cost routes.
Rollback runtime: prior release archives and timestamped backups of kmj-autonomy-worker.service / kmj-github-control.service are retained under the user systemd directory. Restore the chosen unit backups, daemon-reload/restart and verify; preserve all queue/state/artifacts. No production database migrations or main-branch merges were performed.

## Access and other infrastructure

Prefer CodeBridge project tools where sufficient. Remote Desktop Commander currently offers VPS process access: Google device7e86f116-c16c-4aa7-bc06-08c5807ebe1e (info), Main devicecbe1c3e2-c299-4851-9d11-9fafa86b4357 (existing root authority). Google blocked sudo/su must not be bypassed. Tools may differ in a new chat: do a read-only connectivity check; never invent access or ask to expose passwords.
Main CodeBridge agent main-platform-kmjtechnonetgmailcom/project kmj-main-platform was repaired and readiness runtime6202db57e36d deployed; fast gate passed, full gate correctly blocked missing actual checkout dependencies. This ModelFabric change does not complete those gates or CineCore/OmniDesk/Calibration.

## Low-credit operating rules

Work one dependency-ready task at a time; at most two useful implementation agents plus one review, no repeated whole-repo audits. Read this concise handover before long historical reports. Run focused tests during edits and full gate once per final snapshot. Commit/push each verified slice; append evidence here and change task state with explicit SHA/test/live result. Never replace failed evidence with an optimistic percentage. Service operation after chat ends is real; this ChatGPT session itself does not continue thinking after it ends.


## 2026-10-07 KMJ-GH-001 completion evidence

KMJ-GH-001 is implemented and live on the VPS without activating the legacy self-hosted or auto-merge workflows. Implementation commit `552059d157f22fe1f80ef79130f1ce140701b574` added the outbound isolated Git mirror control bridge, durable SQLite pause/idempotency state, strict manifest admission, sanitized status, systemd service, and replay/confidentiality tests. Follow-up `eafcb7f8a3098750eae0830c6db794598791aebe` retains the verified writeback capability state across duplicate polls.

Live control proof used GitHub commits `20df34a` (enqueue + pause), `e6bc76c` (resume), `aaea639` (pause while the proof task was already running), and `e2c9074` (final resume). The proof task was imported once, bridge restart retained idempotency, the running task survived pause and reached artifact-ready, and the worker finished resumed. Status writeback is honestly `read_only` because no separately scoped GitHub status credential is configured; no provider credential was reused.

Verified gates: 171 Python regression tests PASS, 3 schema acceptance tests PASS, and `git diff --check` PASS. Runtime release is `~/.local/lib/kmj-autonomy/releases/eafcb7f8a309`; the queue DB and artifacts remain outside the immutable release. Rollback copy of the previous worker unit was preserved during deployment.

Final sanitized-status request commit `91b78df2082a6a0f0735a9effd7cbd10b6692f1a` was applied live; duplicate polling preserved `writeback=read_only`, `stale=false` and `paused=false`. KMJ-AUTO-001 was subsequently completed by the preserved v2 workflow evidence below.


## 2026-10-07 KMJ-AUTO-001 completion evidence

The preserved original workflow `KMJ-schema-autonomous-proof` remains failed after three trusted-test iterations. A fresh workflow `KMJ-schema-autonomous-proof-v2` was started with a more precise operator prompt but the same immutable trusted validation digest `09ebd57ed0d2e8a685aee80109bd19f0c3437071534e0ef666bd19df0a07e766`. No candidate file was manually changed.

The fresh run reached `json_candidate_tested` on attempt 1. The sandbox report binds the candidate to base SHA `3f87cf9d1312ac50e7a678ab33d9ae3eb22f545f`, reports the candidate unchanged during validation and the base still current, and keeps `product_complete=false` and `deployed=false`. Final branch gates after the GitHub-control follow-up are 171 Python regression tests PASS, 3 schema acceptance tests PASS, and diff check PASS. KMJ-AUTO-002 and KMJ-AUTO-003 are now dependency-ready.


## 2026-10-07 KMJ-AUTO-002 completion evidence

KMJ-AUTO-002 is implemented in commit `3a323068d7a50c1bc8ab337671549262ed33961b` and deployed as immutable runtime `~/.local/lib/kmj-autonomy/releases/3a323068d7a5`. The router now records bounded, idempotent semantic acceptance evidence by provider/model and ranks tested semantic quality before transient HTTP-success recency. Tested failures demote a route; tested successes promote it. Privacy eligibility and free/known-cost policy are still applied before quality ranking and cannot be overridden by semantic score.

Focused semantic-quality tests: 4 PASS. Full branch gates: 175 Python regression tests PASS, 3 schema acceptance tests PASS, and diff check PASS. Worker, GitHub bridge and CPU fallback were active after rollout; queue was idle and control resumed before the switch. Rollback unit backups were preserved with timestamp `20261007-142703`.

Next active task is KMJ-AUTO-003: one general code executor with trusted out-of-process acceptance. Keep it narrowly scoped: pinned source/project, OS sandbox, no secrets/network/production writes, immutable external assertions, and one real isolated small-code-fix acceptance proof.


## 2026-10-07 KMJ-AUTO-002 completion evidence

Commit `3a323068d7a50c1bc8ab337671549262ed33961b` adds bounded tested semantic-quality routing. Trusted JSON workflow outcomes now record exactly-once evidence under hashed provider/model identity only; no prompt, response, credential or base URL is persisted in the quality table. Counts saturate at 8. A tested failure ranks below an otherwise equivalent untested route, while a tested pass ranks above it. Cost/free eligibility and confidentiality filtering happen before this score and remain authoritative.

Focused semantic/workflow/router tests passed, then the full gate passed 175 Python tests plus 3 schema acceptance tests and diff check. The immutable release `3a323068d7a5` is live. Fresh workflow `KMJ-schema-quality-route-proof-v1` reached `json_candidate_tested` on attempt 1 and wrote one live semantic-quality evidence record for its actual route. Product completion and deployment remain false.


## 2026-10-07 KMJ-AUTO-003 completion evidence

KMJ-AUTO-003 base implementation is `b1d316830aab1f635c103bff00b5e9bf572126db`; validation-digest hardening is `e4dbb633ded18cd2af111f1020d83a005cc177f4`, now deployed as immutable runtime `~/.local/lib/kmj-autonomy/releases/e4dbb633ded1`. The first vetted non-JSON executor is `python-cli-v1`: exact base SHA, exact operator allowlist, Git project lock, external pinned `cases.json`, read-only candidate, no candidate access to the validation tree, no inherited secrets/home, and Bubblewrap network isolation. Assertions are compared by the trusted parent process, so candidate output cannot manufacture the acceptance result.

A real temporary Git project was patched and executed in Bubblewrap; the small Python CLI fix passed two external behavior cases while the original repository remained unchanged. Adversarial and isolation tests cover forged success text, denied paths, validation digest mismatch, extra executable validation files, entrypoint scope, moved base, simultaneous project writer, host-secret absence, network denial and read-only workspace. Focused executor tests: 11 PASS. Exact-head gates: 187 Python regression tests PASS, 3 schema acceptance tests PASS and diff check PASS. Runtime services remained active after the hardened rollout; latest rollback backup stamp `20261007-143429`.

Next active task is KMJ-AUTO-004: connect a curated backlog and CodeBridge status to persistent workflows without collapsing artifact/tested-candidate/release states or claiming product completion.


## 2026-10-07 KMJ-AUTO-004 completion evidence and remaining transport blocker

KMJ-AUTO-004 is implemented in commit `28b7eb078e358c6c371acd3792ed04b599dc39a4` and deployed as `~/.local/lib/kmj-autonomy/releases/28b7eb078e35`. The versioned curated backlog is `ops/autonomy-backlog.json`; the coordinator validates exact repository/device/project/branch identity before admitting any auto-enqueued work. Queue completion maps only to `artifact_ready`; separately validated evidence is required for `candidate_tested`; release requires explicit deployed + health-verified release evidence. Every report keeps `product_complete=false`.

Live CodeBridge identity was independently verified as device `main-platform-kmjtechnonetgmailcom`, project `kmj-main-platform`, branch `main`, version `0.2.3`, gates fast/full/platform, writable and connected. Main VPS now has a root-owned sanitizer timer that refreshes a secret-free status JSON every 60 seconds after an authenticated local gateway health probe. A dedicated `kmjstatus` SSH key is forced to cat only that sanitized file with OpenSSH `restrict`; the Google side pins the Main VPS ED25519 host fingerprint. A real restricted read succeeded and the backlog coordinator persisted repository/project/connection plus task stage `ready` with `product_complete=false`.

Focused backlog tests: 9 PASS. Exact slice gates: 196 Python regression tests PASS, 3 schema acceptance tests PASS, backlog JSON validation PASS and diff check PASS. Runtime services and `kmj-backlog-coordinator.path` are active; rollback backup stamp is `20261007-144002`.

Remaining KMJ-AUTO-005 blocker: automatic cross-VPS fetching of the already-restricted status file was not installed because the current tool safety layer blocked creation of that fetcher. Do not bypass that block. Until an approved transport is available, refresh is manual over the pinned restricted SSH path; stale CodeBridge status fails closed and prevents new backlog admission.
