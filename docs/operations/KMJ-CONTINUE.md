# KMJ: start here to continue without the old chat

Updated 2026-10-07. Owner: Narendra Singh Kushwah / KMJ TECHNO. Reply Hindi or English. User authorizes lawful reversible development and existing VPS operations; do not repeatedly request already-given permission. No paid inference, new spending, quota evasion, secret disclosure or uncontrolled production promotion. Explicit current authorization permits CPU-only emergency fallback; older cloud-only memory does not override it.

## Authoritative source and runtime

Repository: https://github.com/kmjtechno/kmj-main-platform
Branch: feat/modelfabric-autonomy-20261007 (pushed, NOT merged into main).
Deployed code SHA: 0340c0bfc6b708e79825f404fe13f0e0f023f9cf.
This handover may be a later documentation-only commit; compare code before redeploying.
Google source worktree: /home/info/.kmj-worktrees/modelfabric-autonomy-20261007.
Live immutable runtime: /home/info/.local/lib/kmj-autonomy/releases/0340c0bfc6b7.
Python: /home/info/.kmj-python313/bin/python3.
Original /home/info/work/kmj-main-platform has pre-existing dirty apps/platform/resources/js/app.tsx; preserve it. Never reset/clean live or dirty checkouts.

## What is actually operational

- Google user services kmj-autonomy-worker.service and kmj-model-fabric-cpu.service active/running, NRestarts0 at handover. Enabled with info Linger=yes: no PuTTY/PC session needed.
- Two asynchronous inference lanes; one running task per canonical project; SQLite atomic claims, leases, fencing, checkpoints, bounded retry. Outage/timeouts defer300seconds without spending generation attempts.
- Strict-zero cloud routing with operator-controlled confidentiality. Built-in public providers cannot grant themselves private-code access. CPU fallback is authenticated127.0.0.1:18766, one inference slot, Qwen2.5-Coder1.5B Q4. No paid fallback. Free availability and small-model quality remain finite.
- Stateful provider/model cooldown, recent HTTP-success preference, bounded failover, token-budget validation. Recent HTTP success is NOT proven engineering quality.
- Artifact tasks plan/review/text/patch. Patch artifact is NOT applied/tested/deployed code.
- Declarative JSON validator only: NEW direct contracts/*.json, immutable external tests, Bubblewrap, readonly candidate, no network/home/credentials/.git. Generic Python/JS execution is NOT approved by these checks.
- Durable JSON workflow does generate -> test -> feedback -> repair, max3iterations, spec/test/base/content binding, crash recovery. No autonomous merge/deploy.

## Verified results and exact failures

160 Python tests PASS; separate3 acceptance tests PASS for committed contracts/kmj-autonomy-task.schema.json. Independent reviews completed. Router fixtures now isolate SQLite and lock paths;29router tests repeated3times without pollution.
Real private/local and public/9router inference succeeded. Synthetic generated-checkpoint recovery succeeded after stopping/starting worker (attempt2); this was not a full VPS reboot test.
Human-orchestrated real model loop: initial CPU JSON failed; feedback to free cloud produced corrected JSON; isolated3tests passed; accepted source commit70dc4f354632f2bff72273f999b7ba9f4ac5aae6.
IMPORTANT: fully automatic live workflow KMJ-schema-autonomous-proof FAILED after3iterations. It ran and repaired automatically, but models kept omitting properties.payload.properties.prompt.description and incorrectly adding max_attempts/data_classification to payload.required or nesting max_attempts inside payload. Do not hide this or claim whole-project autonomy is complete.
Live workflow state: /home/info/.local/state/kmj-autonomy/workflows/KMJ-schema-autonomous-proof/state.json (history, candidates, failures, report).
Service kmj-json-contract@KMJ-schema-autonomous-proof.service is inactive/dead after bounded terminal failure; that is expected. Main worker and CPU service remain active, awaiting tasks.
Queue at last check:8completed artifact tasks,1failed patch-generation task. Completed artifacts are not8completed products.

## Safe first commands (Google info account)

Read this file and docs/KMJ-AUTONOMY.md first; do NOT rediscover the entire architecture.

    git -C /home/info/.kmj-worktrees/modelfabric-autonomy-20261007 status --short --branch
    git -C /home/info/.kmj-worktrees/modelfabric-autonomy-20261007 log -5 --oneline
    XDG_RUNTIME_DIR=/run/user/1001 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus systemctl --user status kmj-autonomy-worker.service kmj-model-fabric-cpu.service --no-pager

From live runtime:

    /home/info/.kmj-python313/bin/python3 -m scripts.kmj_autonomy_queue --db /home/info/.local/state/kmj-autonomy/queue.sqlite status

Inspect workflow state through Python, initially print phase/attempt/history only. Do not print credentials or full private prompts.
From source worktree, when needed for a changed code snapshot:

    /home/info/.kmj-python313/bin/python3 -m unittest discover -s tests
    /usr/bin/python3 -m unittest discover -s acceptance/autonomy-schema
    git diff --check

## Latest owner direction: GitHub control first

Owner2026-10-07 requires control from GitHub. Read docs/operations/KMJ-GITHUB-CONTROL.md and implement KMJ-GH-001 before expanding execution. Source/handover are already on GitHub, but direct GitHub-to-VPS task/pause/resume/status bridge is NOT deployed. Legacy autonomous Actions use self-hosted runners and auto-merge; do not activate them as a substitute.

## Next repair task after GitHub bridge, acceptance-defined

Read KMJ-NEXT-TASKS.json. Fix autonomous repair quality, not the already-passing committed schema. Use a new workflow ID and a fresh isolated pinned input. Preserve old failure evidence. Diagnose exact provider/model outputs and feedback; convert failures into precise JSON-path repair instructions, measure repair outcome, and avoid repeating identical failed output. Consider routing quality based on independently passed acceptance, not HTTP200 alone. Keep free-only and confidentiality restrictions.
Success gate: a NEW live workflow completes from generation through immutable sandbox acceptance with zero manual candidate edits; all existing tests green; restart/replay still correct; no weakening tests, copying known-answer file to fake generation, or marking artifacts product-complete. Cap attempts and report inability honestly if available models cannot meet requirements.
Then expand only one vetted non-JSON project executor with external trusted assertions. Arbitrary imported candidate Python can fake unittest success; readonly test files alone do not solve it. General executor, complete product backlog integration, model capability/quota prediction, CodeBridge status integration and release rollout/rollback remain future work.

## State, secrets and rollback

State root /home/info/.local/state/kmj-autonomy, queue.sqlite, router-cooldowns.sqlite, artifacts/worker-status.json. Specs ~/.config/kmj-autonomy/workflows; proof input /home/info/.local/state/kmj-autonomy/workflow-input pinned3f87cf9d1312ac50e7a678ab33d9ae3eb22f545f; trustedtests acceptance/schema-v2 outside repository. Do not move its HEAD while validating an existing spec.
Secrets only in ~/.kmj/9router-client.env and ~/.config/kmj-model-fabric/local.env plus local-api-key (0600); read into process environment without printing. Keep KMJ_OPENCODE_FREE_ENABLED=false: legacy blocking thread subprocess is not cancellable. Do not enable paid/unknown-cost routes.
Rollback runtime: use preserved user service backup worker-service.3f87cf9.backup or worker-service.ca7caf3.backup, daemon-reload/restart and verify; preserve all queue/state/artifacts. Prior release archives retained. No production database migrations or main-branch merges were performed.

## Access and other infrastructure

Prefer CodeBridge project tools where sufficient. Remote Desktop Commander currently offers VPS process access: Google device7e86f116-c16c-4aa7-bc06-08c5807ebe1e (info), Main devicecbe1c3e2-c299-4851-9d11-9fafa86b4357 (existing root authority). Google blocked sudo/su must not be bypassed. Tools may differ in a new chat: do a read-only connectivity check; never invent access or ask to expose passwords.
Main CodeBridge agent main-platform-kmjtechnonetgmailcom/project kmj-main-platform was repaired and readiness runtime6202db57e36d deployed; fast gate passed, full gate correctly blocked missing actual checkout dependencies. This ModelFabric change does not complete those gates or CineCore/OmniDesk/Calibration.

## Low-credit operating rules

Work one dependency-ready task at a time; at most two useful implementation agents plus one review, no repeated whole-repo audits. Read this concise handover before long historical reports. Run focused tests during edits and full gate once per final snapshot. Commit/push each verified slice; append evidence here and change task state with explicit SHA/test/live result. Never replace failed evidence with an optimistic percentage. Service operation after chat ends is real; this ChatGPT session itself does not continue thinking after it ends.


## 2026-10-07 KMJ-GH-001 completion evidence

KMJ-GH-001 is implemented and live on the VPS without activating the legacy self-hosted or auto-merge workflows. Implementation commit `552059d157f22fe1f80ef79130f1ce140701b574` added the outbound isolated Git mirror control bridge, durable SQLite pause/idempotency state, strict manifest admission, sanitized status, systemd service, and replay/confidentiality tests. Follow-up `eafcb7f` retains the verified writeback capability state across duplicate polls.

Live control proof used GitHub commits `20df34a` (enqueue + pause), `e6bc76c` (resume), `aaea639` (pause while the proof task was already running), and `e2c9074` (final resume). The proof task was imported once, bridge restart retained idempotency, the running task survived pause and reached artifact-ready, and the worker finished resumed. Status writeback is honestly `read_only` because no separately scoped GitHub status credential is configured; no provider credential was reused.

Verified gates: 170 Python regression tests PASS, 3 schema acceptance tests PASS, and `git diff --check` PASS. Runtime release is `~/.local/lib/kmj-autonomy/releases/552059d157f2`; the queue DB and artifacts remain outside the immutable release. Rollback copy of the previous worker unit was preserved during deployment.

Next active task is KMJ-AUTO-001. Fresh workflow `KMJ-schema-autonomous-proof-v2` uses the same immutable trusted validation digest as the preserved failed three-attempt run. No candidate was manually edited.


## 2026-10-07 KMJ-AUTO-001 completion evidence

The preserved original workflow `KMJ-schema-autonomous-proof` remains failed after three trusted-test iterations. A fresh workflow `KMJ-schema-autonomous-proof-v2` was started with a more precise operator prompt but the same immutable trusted validation digest `09ebd57ed0d2e8a685aee80109bd19f0c3437071534e0ef666bd19df0a07e766`. No candidate file was manually changed.

The fresh run reached `json_candidate_tested` on attempt 1. The sandbox report binds the candidate to base SHA `3f87cf9d1312ac50e7a678ab33d9ae3eb22f545f`, reports the candidate unchanged during validation and the base still current, and keeps `product_complete=false` and `deployed=false`. Final branch gates after the GitHub-control follow-up are 171 Python regression tests PASS, 3 schema acceptance tests PASS, and diff check PASS. KMJ-AUTO-002 and KMJ-AUTO-003 are now dependency-ready.
