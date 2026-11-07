"""Root entry point for the fixed KMJ-elite storage transaction.

Operations (each requires the exact CD958 candidate SHA):
  inventory    read-only fixed-scope native inventory; no lock, no state, no mutation
  preflight    read-only adapter preflight under the global release lock; writes nothing
  apply        guarded storage cutover; ends at storage_complete_materializer_pending
  recover      reconcile an interrupted transaction from actual storage/runtime state
  rollback     ONLY from a paused, verified switch whose resume failed: pinned v6
               rollback to the original inode, then restore runtime and admission
  materialize  ONLY after storage_complete_materializer_pending: pinned materializer,
               run without holding the release lock (it takes that lock itself)
"""

import argparse
from contextlib import ExitStack
import json
import os
import signal
import socket

import native_ops as native
import native_plan as plan
import orchestrator as core

TERMINAL = {"storage_complete_materializer_pending", "aborted_original_restored"}


def install_signal_guard():
    """A hangup/terminate becomes an ordinary failure so the transaction's own
    recovery runs; further signals are ignored so that recovery is not cut short."""
    def handler(signum, _frame):
        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            signal.signal(sig, signal.SIG_IGN)
        raise core.Blocked("TERMINATED_BY_SIGNAL_" + str(signum))
    for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(sig, handler)


def require_host():
    core.require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite", "ROOT_ELITE_ONLY")
    os.umask(0o077)


def run(operation):
    if operation == "inventory":
        return {"operation": operation, "inventory": plan.inventory()}, 0
    if operation == "materialize":
        store = core.Store(native.STATE)
        try:
            receipt = store.read()
        finally:
            store.close()
        core.require(receipt is not None and receipt.get("phase") == "storage_complete_materializer_pending"
                     and receipt.get("candidate_sha") == core.CANDIDATE_SHA, "MATERIALIZE_REQUIRES_COMPLETED_STORAGE")
        request = {"candidate_sha": core.CANDIDATE_SHA, "expected_live": core.LIVE,
                   "materializer_sha256": core.PINS["materializer"]}
        return {"operation": operation, "result": native.materialize(request)}, 0
    with ExitStack() as resources:
        lock = core.ReleaseLock()
        resources.callback(lock.close)
        store = core.Store(native.STATE)
        resources.callback(store.close)
        adapter = native.NativeOps(store, lock)
        resources.callback(adapter.close)
        if operation == "preflight":
            core.require(store.read() is None, "EXISTING_TRANSACTION_RECOVER_ONLY")
            proofs, original = adapter.preflight()
            lock.verify()
            return {"operation": operation, "preflight": proofs, "unit_states": original, "mutated": False}, 0
        transaction = core.Transaction(store, adapter, lock)
        if operation == "apply":
            transaction.apply(core.CANDIDATE_SHA)
        elif operation == "recover":
            transaction.recover(allow_scanner_recovery=True)
        else:
            transaction.rollback_paused()
        receipt = store.read()
        phase = receipt.get("phase") if receipt else None
        core.require(phase in TERMINAL, "TRANSACTION_TERMINAL_RECEIPT_MISSING")
    return {"operation": operation, "phase": phase}, 0 if phase == "storage_complete_materializer_pending" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("operation", choices=("inventory", "preflight", "apply", "recover", "rollback", "materialize"))
    parser.add_argument("candidate_sha", choices=(core.CANDIDATE_SHA,))
    args = parser.parse_args(argv)
    try:
        require_host()
        install_signal_guard()
        result, code = run(args.operation)
        print(json.dumps(result, sort_keys=True))
        return code
    except Exception as exc:
        reason = str(exc) if isinstance(exc, core.Blocked) else type(exc).__name__
        print(json.dumps({"status": "CUTOVER_BLOCKED", "operation": args.operation, "reason": reason}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
