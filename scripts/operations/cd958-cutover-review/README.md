# CD958 storage cutover review

This directory contains an executable storage transaction under review. It is not a production deployment or an approved installer.

## Entry points

- `orchestrator.py` exposes the transaction model. Its standalone CLI does not apply changes.
- `cutover_runner.py` wires `NativeOps` to the transaction. Every operation requires the exact CD958 candidate SHA:
  - `inventory`: read-only fixed-scope inventory. No lock, no state, no mutation.
  - `preflight`: read-only adapter preflight under the global release lock. Writes nothing. Refuses if a transaction receipt already exists.
  - `apply`: guarded storage cutover. Executing it as root on KMJ-elite mutates production storage, maintenance admission, the scheduler/queue and the transaction-owned firewall guard.
  - `recover`: reconciles an interrupted transaction from actual storage/runtime state.
  - `rollback`: only from `recovery_required` with a verified switch, while the transaction still owns the guard and every writer is still paused. It runs the pinned v6 rollback (which refuses if any persistent file changed in shared since the switch), then restores runtime and admission on the original inode.
  - `materialize`: only after `storage_complete_materializer_pending`. Runs the pinned materializer without holding the release lock.
- SIGTERM, SIGHUP and SIGINT become an ordinary failure once, so the transaction's own recovery runs; later signals are ignored so that recovery is not cut short.
- Preflight refuses a queue unit without `Restart=always` before any mutation, because only that policy brings the maintenance-idle replacement worker the drain waits for.
- `build_cutover_bundle.py` creates a standalone artifact from the four fixed modules. A root process must not import adjacent project-writable modules.
- The runner requires an independently provisioned root-owned 0700 state directory and the protected dependencies. It does not install them.

## Completion boundary

A successful storage transaction returns `storage_complete_materializer_pending`. `apply` does not call `native_ops.materialize`; that is the separate `materialize` operation. The runner never updates protected approval, changes the production pointer or activates a release. Those remain separate operations after the global lock is released. Recovery can instead return `aborted_original_restored`; this is not deployment success.

The fixed current release is platform-574e443a2c75; the candidate is cd9580701d3cea19d7d4e4c96ebe70c0553fbf37. Original storage is preserved for recovery. Do not delete preserved directories or relax attestation to make readiness pass.

## Evidence and limits

Earlier code head c6d33e0c2e7933fb131ecc35ef7deede8f626195 passed Verify Foundation (42365807157), CD958 cutover review (42365807313) and KMJ Main Platform CI (42365807223). These results belong to that head and are not evidence for later code changes. Every later head needs its own exact-head CI.

The recovery workflow exercises disposable filesystem transactions including real immutable flags. Its production service, network and FPM observations are mocked. It does not prove the integrated adapter has run safely on ELITE. Previously supplied host preflight results do not establish current writer quiescence.

A rollback is impossible while restored units are running: stop the timer and queue first (the queue worker exits after its current job; systemd may SIGKILL it after the unit stop timeout, and the job is then retried). The rollback refuses rather than overwrites if shared data changed.

## Remaining operator workflow

1. Review the integrated native adapter and recovery paths, including interruption during admission changes and storage exchange.
2. Use an authorized operator installation workflow for the reviewed pinned artifact and protected state. Earlier privileged staging rejection must not be bypassed through another transport.
3. Execute guarded storage cutover with fresh locked checks and retain recovery evidence.
4. Materialize the exact candidate and verify environment privacy, public ACL and unchanged production pointer.
5. Complete exact-candidate migration/rollback rehearsal and authenticated CodeBridge UI/Workspace QA.
6. Reconcile the protected manifest to the actual current release and verified candidate only after its evidence requirements pass, then activate only when readyToActivate=true.
7. Verify deployed SHA, HTTPS, authenticated functionality and rollback health.

This document supplies no root execution approval and no claim that production has changed.
