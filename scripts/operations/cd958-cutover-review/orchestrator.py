#!/usr/bin/env python3
"""Reviewed-order storage transaction core. Native apply adapter is not authorized.

The executable entry point is read-only and deliberately cannot mutate a host.
The core is exercised with an explicit fake adapter; no receipt boolean is an
authorization to substitute shell commands for the still-unimplemented adapter.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import stat

LIVE = "/home/kmjprod/releases/platform-574e443a2c75"
CANDIDATE_SHA = "cd9580701d3cea19d7d4e4c96ebe70c0553fbf37"
CANDIDATE = "/home/kmjprod/releases/platform-cd9580701d3c"
SHARED = "/home/kmjprod/shared/storage"
RELEASE_LOCK = "/run/lock/kmj-main-platform-production-release.lock"
PINS = {
    "helper": "72fe5702c59599bd1b28b88dad808dda5d6be97b61f0db06dc3a7295258a51b6",
    "scanner": "f4d01f6e3b40c9ad774c8ada5129b241cee93dac782ce75bb0e229b26bbc95ba",
    "materializer": "fd29c4ebcf224c45786f8cedd0e0d42bbfd414d706678fe820e0ead4eea3984f",
}
UNITS = ("kmj-main-platform-queue.service", "kmj-main-platform-scheduler.service",
         "kmj-main-platform-scheduler.timer")


class Blocked(RuntimeError):
    pass


def require(value, reason):
    if not value:
        raise Blocked(reason)


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def protected_dir(path, owner=0, *, allow_sticky=False):
    """Open, bind and retain every root-owned non-writable ancestor."""
    path = Path(path)
    require(path.is_absolute() and str(path) == os.path.abspath(path), "DIRECTORY_NOT_CANONICAL")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                            dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            require(info.st_uid == owner and (info.st_mode & 0o022 == 0
                    or (allow_sticky and info.st_mode & stat.S_ISVTX)), "UNPROTECTED_DIRECTORY")
        return fd
    except BaseException:
        os.close(fd)
        raise


class Store:
    """One pre-provisioned protected directory; atomic fsync-before-action state.

    Directory creation is an operator/install responsibility. Never repair an
    unexpected file, truncate a receipt, or follow a writable ancestor.
    """
    def __init__(self, directory, owner=0):
        self.fd = protected_dir(directory, owner)
        self.owner = owner

    def close(self):
        os.close(self.fd)

    def read(self):
        try:
            fd = os.open("transaction.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=self.fd)
        except FileNotFoundError:
            return None
        try:
            st = os.fstat(fd)
            require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_uid == self.owner
                    and stat.S_IMODE(st.st_mode) == 0o600 and st.st_size <= 65536, "UNSAFE_STATE")
            raw = os.read(fd, 65537)
            require(raw.endswith(b"\n") and len(raw) <= 65536, "TORN_STATE")
            value = json.loads(raw, object_pairs_hook=no_duplicates)
            require(canonical_json(value) == raw, "NONCANONICAL_STATE")
            return value
        finally:
            os.close(fd)

    def write(self, state):
        raw = canonical_json(state)
        require(len(raw) <= 65536, "STATE_TOO_LARGE")
        # A left-over staging name is a crash artifact; do not unlink blindly.
        name = "pending-" + os.urandom(16).hex()
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=self.fd)
        try:
            offset = 0
            while offset < len(raw):
                count = os.write(fd, raw[offset:])
                require(count > 0, "STATE_SHORT_WRITE")
                offset += count
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(name, "transaction.json", src_dir_fd=self.fd, dst_dir_fd=self.fd)
        os.fsync(self.fd)


class ReleaseLock:
    def __init__(self, path=RELEASE_LOCK, owner=0):
        self.parent = protected_dir(Path(path).parent, owner, allow_sticky=True)
        self.name = Path(path).name
        self.fd = None
        try:
            self.fd = os.open(self.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                              dir_fd=self.parent)
            st = os.fstat(self.fd)
            require(stat.S_ISREG(st.st_mode) and st.st_uid == owner and st.st_nlink == 1
                    and stat.S_IMODE(st.st_mode) == 0o600, "UNSAFE_RELEASE_LOCK")
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.verify()
        except BaseException:
            self.close()
            raise

    def verify(self):
        st = os.stat(self.name, dir_fd=self.parent, follow_symlinks=False)
        fdst = os.fstat(self.fd)
        require((st.st_dev, st.st_ino) == (fdst.st_dev, fdst.st_ino), "RELEASE_LOCK_REPLACED")

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        if self.parent is not None:
            os.close(self.parent)
            self.parent = None


# Exact fresh observations required at each boundary, not cached preflight PASS.
PREFLIGHT = ("fixed_host_pointer_sha", "pinned_protected_dependencies", "scope_units_and_cgroups",
             "file_maintenance_driver", "queue_restart_cache_visible", "queue_no_force",
             "fpm_single_listener_ondemand", "all_writers_accounted", "same_network_namespace",
             "nft_output_priorities_complete", "original_states_recorded")
DRAIN = ("guard_identity_readback", "nginx_uid_syn_counter_advanced", "scheduler_cgroup_empty",
         "old_queue_generation_exited", "replacement_queue_maintenance_idle", "queue_cgroup_empty",
         "all_fpm_pidfds_exited", "no_untracked_fpm_descendants", "no_replacement_fpm_children",
         "fpm_master_listener_unchanged", "tcp_syn_established_empty", "listen_backlog_zero")
SWITCHED = ("v6_completed_receipt", "live_shared_identity", "preserved_original_frozen",
            "shared_fully_thawed", "candidate_snapshot_attested", "pointer_574_unchanged")


def proofs(result, keys):
    require(type(result) is dict and set(result) == set(keys)
            and all(type(result[key]) is bool and result[key] for key in keys), "FRESH_PROOF_MISSING")


class Transaction:
    """Crash-conservative protocol; adapter operations must be bounded/idempotent.

    Adapter is deliberately dependency injection, not import-from-candidate.
    write-ahead intent survives action-success/journal-write crashes. Recovery
    never infers success from the last recorded phase alone.
    """
    def __init__(self, store, adapter, release_lock):
        self.store, self.ops, self.lock = store, adapter, release_lock
        self.state = None

    def save(self, phase, **extra):
        self.state.update(extra, phase=phase)
        self.store.write(self.state)

    def step(self, name, action):
        self.lock.verify()
        self.save("intent_" + name)
        result = action()
        self.save("done_" + name)
        return result

    def apply(self, candidate_sha):
        require(candidate_sha == CANDIDATE_SHA, "EXACT_CANDIDATE_SHA_REQUIRED")
        require(self.store.read() is None, "EXISTING_TRANSACTION_RECOVER_ONLY")
        observed, original = self.ops.preflight()
        proofs(observed, PREFLIGHT)
        require(type(original) is dict and set(original) == set(UNITS)
                and all(v in ("active", "inactive") for v in original.values()), "UNIT_ORIGINAL_STATES_UNVERIFIED")
        evidence = self.ops.recovery_evidence()
        require(type(evidence) is dict and 0 < len(canonical_json(evidence)) <= 16384, "RECOVERY_EVIDENCE_REQUIRED")
        self.state = {"version": 1, "phase": "prepared", "candidate_sha": candidate_sha,
                      "original_units": original, "pins": PINS, "live": LIVE, "shared": SHARED,
                      "guard": self.ops.guard_identity(), "recovery_evidence": evidence}
        self.store.write(self.state)
        try:
            self.step("guard", self.ops.install_guard)
            self.step("timer_pause", self.ops.pause_timer)
            self.step("scheduler_drain", self.ops.drain_scheduler)
            self.step("maintenance", self.ops.maintenance_on)
            self.step("queue_restart", self.ops.queue_restart)
            self.step("queue_drain_stop", self.ops.drain_and_stop_queue)
            self.step("fpm_natural_idle", self.ops.drain_fpm)
            proofs(self.ops.drain_proofs(), DRAIN)
            # Maintenance file belongs to persistent storage: remove only our
            # verified file before fresh plan, while all admission remains shut.
            self.step("maintenance_remove", self.ops.maintenance_off)
            proofs(self.ops.drain_proofs(), DRAIN)
            plan = self.step("fresh_plan", self.ops.fresh_plan)
            require(type(plan) is dict and set(plan) == {"ready", "plan_id"} and plan["ready"] is True
                    and re.fullmatch(r"[0-9a-f]{16}", plan["plan_id"]) is not None, "FRESH_PLAN_BLOCKED")
            self.save("switch_intent", plan_id=plan["plan_id"])
            # From this write forward, errors retain admission guard and pauses.
            self.ops.switch(plan["plan_id"])
            proofs(self.ops.switched_proofs(), SWITCHED)
            self.save("switch_verified")
            materialize_request = self.resume()
        except Exception:
            if self.state["phase"] in {"switch_intent", "switch_verified"} or self.state.get("switch_verified"):
                self.save("recovery_required", switch_uncertain=True)
            else:
                self.save("recovery_required", switch_uncertain=False)
                # Reconcile actual storage before restoring runtime, even when
                # the last recorded action was before the switch invocation.
                self.recover()
            raise
        return materialize_request

    def resume(self):
        # This marker precedes any runtime restart and remains sticky on failures.
        self.save("switch_verified", switch_verified=True)
        proofs(self.ops.switched_proofs(), SWITCHED)
        self.step("runtime_restore", lambda: self.ops.restore_units(self.state["original_units"]))
        require(self.ops.runtime_restored(self.state["original_units"]) is True, "RUNTIME_RESTORE_NOT_VERIFIED")
        # Never delete our guard in finally, and never delete foreign tables.
        self.step("guard_remove", self.ops.remove_owned_guard)
        require(self.ops.guard_absent() is True, "GUARD_REMOVAL_NOT_VERIFIED")
        self.save("storage_complete_materializer_pending")
        # Materializer takes same lock: boundary is intentionally after unlock.
        self.lock.verify()
        self.lock.close()
        # Caller invokes the pinned root-private materializer with fresh pointer
        # checks outside this transaction's exception/recovery handler. Its
        # failure cannot undo safely resumed storage or reacquire a closed FD.
        return {"candidate_sha": self.state["candidate_sha"], "expected_live": LIVE,
                "materializer_sha256": PINS["materializer"]}

    def recover(self, *, allow_scanner_recovery=False):
        self.state = self.store.read()
        require(type(self.state) is dict and self.state.get("version") == 1
                and self.state.get("pins") == PINS and self.state.get("live") == LIVE
                and self.state.get("shared") == SHARED
                and self.state.get("candidate_sha") == CANDIDATE_SHA, "RECOVERY_STATE_INVALID")
        original = self.state.get("original_units")
        require(type(original) is dict and set(original) == set(UNITS)
                and all(v in ("active", "inactive") for v in original.values()), "RECOVERY_UNIT_STATES_INVALID")
        allowed = {"version", "phase", "candidate_sha", "original_units", "pins", "live", "shared", "guard",
                   "plan_id", "switch_verified", "switch_uncertain", "recovery_evidence"}
        require(set(self.state) <= allowed and type(self.state.get("guard")) is dict
                and type(self.state.get("phase")) is str
                and type(self.state.get("recovery_evidence")) is dict, "RECOVERY_SCHEMA_INVALID")
        for key in ("switch_verified", "switch_uncertain"):
            require(key not in self.state or type(self.state[key]) is bool, "RECOVERY_BOOLEAN_INVALID")
        require("plan_id" not in self.state or (type(self.state["plan_id"]) is str
                and re.fullmatch(r"[a-f0-9]{16}", self.state["plan_id"]) is not None), "RECOVERY_PLAN_ID_INVALID")
        self.lock.verify()
        require(self.ops.bind_recovery(self.state) is True, "RECOVERY_IDENTITY_UNVERIFIED")
        if self.state["phase"] == "aborted_original_restored":
            # A completed abort grants no permission to restart units again.
            # Administrators may have changed their states since that receipt.
            require(self.ops.reconcile_storage_readonly() == "verified_original"
                    and self.ops.original_storage_writable_and_unchanged() is True,
                    "COMPLETED_ABORT_STORAGE_CHANGED")
            require(self.ops.guard_absent() is True, "COMPLETED_ABORT_GUARD_CHANGED")
            self.lock.close()
            return None
        if self.state["phase"] == "storage_complete_materializer_pending":
            # A completed transaction is not permission to reset units again
            # after an administrator changed them. Materializer is independent.
            proofs(self.ops.switched_proofs(), SWITCHED)
            require(self.ops.guard_absent() is True, "COMPLETED_GUARD_STATE_CHANGED")
            self.lock.close()
            return {"candidate_sha": self.state["candidate_sha"], "expected_live": LIVE,
                    "materializer_sha256": PINS["materializer"]}
        # Inspect v6 receipts and actual inode/flag/runtime state even when crash
        # occurred after switch syscall but before its completion record.
        outcome = self.ops.reconcile_storage_readonly()
        if outcome == "uncertain" and allow_scanner_recovery and self.ops.recover_active_scanner(self.state):
            outcome = self.ops.reconcile_storage_readonly()
        if outcome == "verified_switched":
            return self.resume()
        elif outcome == "verified_original":
            require(self.ops.original_storage_writable_and_unchanged() is True, "ORIGINAL_NOT_SAFE")
            self.ops.restore_owned_maintenance(self.state)
            self.ops.restore_units(self.state["original_units"])
            require(self.ops.runtime_restored(self.state["original_units"]) is True, "RUNTIME_RESTORE_NOT_VERIFIED")
            self.ops.remove_owned_guard()
            require(self.ops.guard_absent() is True, "GUARD_REMOVAL_NOT_VERIFIED")
            self.save("aborted_original_restored")
        else:
            self.save("recovery_required", switch_uncertain=True)
            raise Blocked("STORAGE_UNCERTAIN_RETAIN_GUARD_AND_PAUSES")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--recover", action="store_true")
    args = parser.parse_args(argv)
    # No implicit state/lock creation, root imports, subprocesses or mutations.
    print(json.dumps({"status": "BLOCKED_NATIVE_ADAPTER_NOT_IMPLEMENTED",
                      "mode": "apply" if args.apply else "recover" if args.recover else "plan",
                      "mutated": False, "live": LIVE, "shared": SHARED, "pins": PINS}, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
