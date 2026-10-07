# KMJ ModelFabric and durable autonomy implementation plan

Goal: lawful zero-cost cloud model routing and persistent two-lane engineering artifact workers.

Architecture: federated cloud-only routing with strict free/known-cost and confidentiality gates; SQLite leases fence workers and serialize writers per project. Systemd user services survive shell logout and reboot. Artifacts are not production deployments or completed products. Local LLM inference is prohibited.

Tech stack: Python 3.13, httpx, SQLite and systemd.

Constraints: paid and unknown-cost fallback prohibited; local LLM inference prohibited; confidential prompts cannot use public-only routes; operator controls privacy permissions; never reset existing dirty repositories. No model-written shell commands execute. Two lanes, one running task per project. Cloud quota exhaustion or route loss means defer/retry/checkpoint, never local inference or quota evasion.

1. Router agent owns controller/model_router.py, routing YAML and dedicated tests. Test privacy elevation rejection, cloud-only failover, bounded attempt budgets, valid completion, cooldown persistence and fail-closed no-route evidence.
2. Queue agent owns controller/task_queue.py and tests/test_task_queue.py. TaskQueue enqueue/claim/heartbeat/checkpoint/complete/fail use transactions, lease tokens, retry limits and idempotency. Tests prove stale tokens fail, leases recover, projects serialize and separate projects run concurrently.
3. Worker agent owns controller/autonomy_worker.py and tests/test_autonomy_worker.py. Two asynchronous lanes generate labeled private artifacts from bounded plan/review/text/patch tasks. Test concurrency, retries, signal recovery and rejection of invalid patch artifacts. Patch application and production promotion are separate evidence-gated stages.
4. Operations verifies exact cloud-routing policy and combined tests; installs immutable runtime user service with private cloud credentials and persistent state; enqueues bounded smoke tasks; proves recovery after restart. No local model daemon is a worker dependency.
5. Independent review precedes completion claims. Record exact commit, tests, service state, task evidence and remaining executor/promotion requirements.

Review focus: provider metadata cannot grant privacy permission; stale worker cannot publish completion; artifact file paths cannot escape private root; no local inference transport is reachable from ModelFabric routing; idle service must never be described as completing whole products.
