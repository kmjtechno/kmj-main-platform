# KMJ ModelFabric durable development workers

This worker runs bounded inference tasks from a persistent SQLite queue. It can keep two distinct projects active at once. The queue admits one active task per project and fences heartbeat, checkpoint, failure and completion writes with an expiring claim token. A stopped process can resume generated checkpoints after lease recovery. This is **artifact generation**, not a claim that software projects have been implemented, tested or deployed.

## Supported task contract

Payload:

```json
{"kind":"plan","prompt":"Describe a bounded implementation plan.","data_classification":"confidential"}
```

Kinds: `plan`, `review`, `text`, `patch`. Classification defaults to confidential; only explicit `public` tasks may use public providers. The worker never reads repository files itself. Whoever enqueues task context must classify it accurately. Unknown classifications and kinds fail closed. Prompt size is limited to 65,536 bytes, output to 100,000 bytes. Patch artifacts additionally use the existing `persistent_worker.validate_patch` allowlists and size limits. A patch artifact is not an applied or tested patch.

Private source files or credentials must never be copied into a public task. Free inference availability is finite; provider quotas and outages can delay tasks. The configured strict-zero ModelFabric router decides eligible routes, including an explicitly configured emergency local CPU route when cloud routes fail. No paid fallback is enabled by this worker.

## Run

From the repository using its dependency-installed Python:

```sh
python -m controller.autonomy_worker --db /private/state/tasks.sqlite --artifacts /private/state/artifacts --concurrency 2
```

`--once` drains currently claimable work and exits; it does not wait for delayed retries. Normal mode remains alive, polling every two seconds. `--request-timeout` defaults to 180 seconds per overall inference await. Heartbeats renew the 120-second claim every 40 seconds. A request timeout cancels the asynchronous request; a provider adapter using an external process/thread must enforce its own process timeout as well.

Submit through the trusted local queue API (no public unauthenticated ingress):

```python
from controller.task_queue import TaskQueue
queue = TaskQueue('/private/state/tasks.sqlite', max_concurrency=2)
queue.enqueue('unique-task-id', 'KMJ-project-name', {
    'kind': 'review',
    'prompt': 'Review this explicitly supplied, non-secret specification...',
    'data_classification': 'confidential',
}, max_attempts=3)
```

Use the same concurrency setting for the service and administrative queue connections. Duplicate IDs must follow the queue's idempotency contract. A project identifier controls serialization; assign the same identifier to tasks that touch the same logical project.

## Results and recovery

Successful completion means a private JSON artifact exists, with `stage=artifact_ready`, `product_complete=false`, `tests_executed=false` and `deployed=false`. The queue result contains its path. Model/provider identifiers are provenance claims from the router, not independent vendor certification. Output remains untrusted content.

`worker-status.json` reports the current process state, instance identity, active count and artifact/failure counts. It contains no prompts or API credentials. Counters restart with the process; inspect queue records for durable history. Status alone proves neither provider health nor project completion.

The worker writes an owner-only generated checkpoint before the artifact. If interrupted after generation, the next attempt reuses that result. Artifacts are atomically written mode 0600 in a mode 0700 directory, named from task and attempt token hashes. An interrupted attempt can leave an orphan artifact; only a successful fenced queue result is authoritative. No shared repository writes occur. SQLite claim fencing alone would not be sufficient for future filesystem patch writers: those need process-level project locks and isolated worktrees.

When all eligible model routes are unavailable or the overall inference deadline expires, the worker defers the task for five minutes without consuming its generation retry budget. It keeps trying through provider outages instead of terminally failing after three unavailable-route checks or model timeouts. Timeout deferrals store `MODEL_TIMEOUT`; unavailable-route deferrals store `NO_MODEL_AVAILABLE`. Other failures store only the exception class, not potentially secret error text. Retry delays grow from 30 seconds up to one hour and stop at the task attempt limit. Failed terminal tasks need diagnosis and deliberate replacement/requeue; they are not silently reported as completed. SIGINT/SIGTERM cancels active inference and returns valid claims to the retry queue. Hard crashes recover by lease expiration.

A user systemd service with restart policy and enabled user lingering is required for operation independent of an SSH terminal. The worker does not install or enable a service itself. Use a private environment file for router credentials; do not place keys in command arguments or task payloads.

## Verification and remaining scope

Run `python -m unittest tests.test_task_queue tests.test_autonomy_worker` for durable claims and worker behavior. Worker tests verify two-project parallelism, one-project serialization, timeouts, sanitized errors, invalid tasks/patches, lease renewal, graceful shutdown and checkpoint reuse.

Still separate from this worker: isolated patch application, meaningful project-specific tests, independent review gates, pull requests, release promotion, rollout and rollback. Do not point older destructive checkout/reset/clean workflows at a dirty checkout. Do not interpret these artifact tasks as end-to-end autonomous project completion.
