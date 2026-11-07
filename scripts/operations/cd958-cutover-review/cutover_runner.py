"""Root entry point for the fixed KMJ-elite storage transaction."""

import argparse
from contextlib import ExitStack
import json
import os
import socket

import native_ops as native
import orchestrator as core


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("apply", "recover"))
    parser.add_argument("candidate_sha", choices=(core.CANDIDATE_SHA,))
    args = parser.parse_args(argv)

    try:
        core.require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite",
                     "ROOT_ELITE_ONLY")
        os.umask(0o077)
        with ExitStack() as resources:
            lock = core.ReleaseLock()
            resources.callback(lock.close)
            store = core.Store(native.STATE)
            resources.callback(store.close)
            adapter = native.NativeOps(store, lock)
            resources.callback(adapter.close)
            transaction = core.Transaction(store, adapter, lock)
            if args.operation == "apply":
                transaction.apply(args.candidate_sha)
            else:
                transaction.recover(allow_scanner_recovery=True)
            receipt = store.read()
            phase = receipt.get("phase") if receipt else None
            core.require(phase in {"storage_complete_materializer_pending", "aborted_original_restored"},
                         "TRANSACTION_TERMINAL_RECEIPT_MISSING")
        print(json.dumps({"phase": phase, "operation": args.operation}, sort_keys=True))
        return 0 if phase == "storage_complete_materializer_pending" else 2
    except Exception as exc:
        reason = str(exc) if isinstance(exc, core.Blocked) else type(exc).__name__
        print(json.dumps({"status": "CUTOVER_BLOCKED", "reason": reason}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
