# KMJ ModelFabric and durable autonomy implementation plan

Goal: lawful zero-cost model routing and persistent two-lane engineering artifact workers.
Architecture: existing cloud router followed by explicitly private CPU emergency inference; SQLite leases fence workers and serialize writers per project. Systemd user services survive shell logout and reboot. Artifacts are not production deployments or completed products.
Tech stack: Python 3.13, httpx, SQLite, systemd, pinned llama.cpp and Qwen2.5-Coder-1.5B GGUF.

Constraints: paid and unknown-cost fallback prohibited; confidential prompts cannot use public-only routes; operator controls privacy permissions; never reset existing dirty repositories. No model-written shell commands execute. Two lanes, one running task per project; local inference one slot. Cloud quota exhaustion means retry/checkpoint, not quota evasion.

1. Router agent owns controller/model_router.py, controller/local_fallback.py, routing YAML and dedicated tests. Test privacy elevation rejection, cloud-first/local-last, disabled/invalid local endpoints, token budgeting, valid completion and fallback evidence.
2. Queue agent owns controller/task_queue.py and tests/test_task_queue.py. TaskQueue enqueue/claim/heartbeat/checkpoint/complete/fail use transactions, lease tokens, retry limits and idempotency. Tests prove stale tokens fail, leases recover, projects serialize, separate projects run concurrently.
3. Worker agent owns controller/autonomy_worker.py and tests/test_autonomy_worker.py. Two asynchronous lanes generate labeled private artifacts from bounded plan/review/text/patch tasks. Test concurrency, retries, signal recovery and rejection of invalid patch artifacts. Patch application and production promotion are separate unproven stages.
4. Root verifies checksums, local authentication and actual inference; tests combined code; installs immutable runtime user service with private env and persistent state; enqueues bounded public and confidential smoke tasks; proves recovery after restart.
5. Independent review before completion claims. Record exact commit, tests, service state, task evidence and remaining executor/promotion requirements.

Review focus: provider metadata cannot grant privacy permission; stale worker cannot publish completion; artifact file paths cannot escape private root; local endpoint cannot leak via proxies/redirects; idle service must never be described as completing whole products.
