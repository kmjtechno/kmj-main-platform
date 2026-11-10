#!/usr/bin/env python3
"""09e8 candidate-only guarded storage transaction core. Native apply NOT authorized.

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

LIVE = "/home/kmjprod/releases/platform-bce4100d005e"
CANDIDATE_SHA = "09e8a224cd37445c42588a073a6b52d207475a09"
CANDIDATE = "/home/kmjprod/releases/platform-09e8a224cd37"
SHARED = "/home/kmjprod/shared/storage"
# Pinned to root's 2026-11-09T10:56:40Z independent candidate-only V6
# witness; a new valid-looking 16-hex ID is a DIFFERENT release geometry.
# This may never be inferred from an untrusted saved recovery journal.
OWNER_ATTESTED_CANDIDATE_PLAN = "c651c450b3941f3a"
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

    def _entries(self):
        """Never replay old state when a newer journal write was interrupted.

        Pending stages, unknown objects and surplus sidecars must remain
        untouched for explicit recovery. An original transaction receipt alone
        does not establish that the last attempted transaction write completed.
        """
        entries = os.listdir(self.fd)
        require(len(entries) <= 3, "STATE_DIRECTORY_UNREVIEWED_CONTENTS")
        allowed_env = re.compile(
            r"queue-environment-[0-9a-f]{32}(?:-replacement)?\.json\Z")
        for name in entries:
            require(name == "transaction.json"
                    or allowed_env.fullmatch(name) is not None,
                    "UNFINISHED_OR_UNKNOWN_JOURNAL_ARTIFACT")
        return set(entries)

    def read(self):
        entries = self._entries()
        if "transaction.json" not in entries:
            require(not entries, "ORPHANED_ENVIRONMENT_WITHOUT_TRANSACTION")
            return None
        fd = os.open("transaction.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=self.fd)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                    and before.st_uid == self.owner
                    and stat.S_IMODE(before.st_mode) == 0o600
                    and 0 < before.st_size <= 65536, "UNSAFE_STATE")
            raw = os.read(fd, 65537)
            require(raw.endswith(b"\n") and len(raw) <= 65536, "TORN_STATE")
            value = json.loads(raw, object_pairs_hook=no_duplicates)
            require(canonical_json(value) == raw, "NONCANONICAL_STATE")
            after = os.fstat(fd)
            named = os.stat("transaction.json", dir_fd=self.fd, follow_symlinks=False)
            require((before.st_dev, before.st_ino, before.st_mode,
                     before.st_uid, before.st_nlink, before.st_size)
                    == (after.st_dev, after.st_ino, after.st_mode,
                        after.st_uid, after.st_nlink, after.st_size)
                    == (named.st_dev, named.st_ino, named.st_mode,
                        named.st_uid, named.st_nlink, named.st_size),
                    "STATE_FILE_REPLACED_DURING_READ")
            sidecars = entries - {"transaction.json"}
            if sidecars:
                require(type(value) is dict and
                        type(value.get("recovery_evidence")) is dict,
                        "STATE_ENVIRONMENT_WITHOUT_RECOVERY_EVIDENCE")
                nonce = value["recovery_evidence"].get("nonce")
                require(type(nonce) is str and
                        re.fullmatch(r"[0-9a-f]{32}", nonce) is not None,
                        "STATE_ENVIRONMENT_NONCE_MISSING")
                require(all(name in {
                    "queue-environment-" + nonce + ".json",
                    "queue-environment-" + nonce + "-replacement.json",
                } for name in sidecars), "FOREIGN_QUEUE_ENVIRONMENT_ARTIFACT")
            return value
        finally:
            os.close(fd)

    def write(self, state):
        # Reject a prior torn pending write before any new staging file.
        # Never replace an untrusted journal or ignore foreign recovery data.
        self.read()
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
# The only journal phases the exact reviewed transaction can generate.
# Recovery must not treat arbitrary strings as permission to restore writers.
STEPS = (
    "guard", "timer_pause", "scheduler_drain", "maintenance",
    "queue_restart", "queue_drain_stop", "fpm_natural_idle",
    "maintenance_remove", "fresh_plan", "runtime_restore",
    "guard_remove", "rollback",
)
VALID_JOURNAL_PHASES = frozenset(
    ("prepared", "switch_intent", "switch_verified", "recovery_required",
     "storage_complete_materializer_pending", "aborted_original_restored")
) | frozenset(
    prefix + step for prefix in ("intent_", "done_") for step in STEPS
)
PHASES_REQUIRING_PLAN = frozenset({
    "switch_intent", "switch_verified",
    "intent_runtime_restore", "done_runtime_restore",
    "intent_guard_remove", "done_guard_remove",
    "storage_complete_materializer_pending",
    "intent_rollback", "done_rollback",
})

SWITCHED = ("v6_completed_receipt", "candidate_shared_identity", "live_shared_link_unchanged", "preserved_original_frozen",
            "shared_fully_thawed", "candidate_snapshot_attested", "pointer_bce_unchanged")


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
            require(type(plan) is dict and set(plan) == {"ready", "plan_id"}
                    and plan["ready"] is True
                    and type(plan["plan_id"]) is str
                    and plan["plan_id"] == OWNER_ATTESTED_CANDIDATE_PLAN,
                    "FRESH_PLAN_NOT_OWNER_ATTESTED")
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
        # A verified V6 receipt is STORAGE evidence, not proof that the
        # transaction still owns its nft admission guard and has drained all
        # queue/scheduler/FPM writers. Crashes or an external systemd/nft
        # change can invalidate a formerly good drain proof.
        #
        # Validate fresh kernel/runtime quiescence BEFORE marking the
        # transaction resumable or executing ANY original-unit restart.
        # If a crash occurs after runtime restore was partly attempted,
        # automatic recovery must fail closed for explicit operator review.
        self.lock.verify()
        require(self.ops.writers_still_paused() is True,
                "PRE_RESUME_WRITER_GUARD_OR_DRAIN_NOT_ATTESTED")
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

    def load_recovery_state(self):
        self.state = self.store.read()
        require(type(self.state) is dict and self.state.get("version") == 1
                and self.state.get("pins") == PINS and self.state.get("live") == LIVE
                and self.state.get("shared") == SHARED
                and self.state.get("candidate_sha") == CANDIDATE_SHA, "RECOVERY_STATE_INVALID")
        original = self.state.get("original_units")
        require(type(original) is dict and set(original) == set(UNITS)
                and all(v in ("active", "inactive") for v in original.values()), "RECOVERY_UNIT_STATES_INVALID")
        allowed = {"version", "phase", "candidate_sha", "original_units", "pins", "live", "shared", "guard",
                   "plan_id", "switch_verified", "switch_uncertain", "rollback_intent", "recovery_evidence"}
        require(set(self.state) <= allowed and type(self.state.get("guard")) is dict
                and self.state.get("phase") in VALID_JOURNAL_PHASES
                and type(self.state.get("recovery_evidence")) is dict,
                "RECOVERY_SCHEMA_INVALID")
        for key in ("switch_verified", "switch_uncertain", "rollback_intent"):
            require(key not in self.state or type(self.state[key]) is bool, "RECOVERY_BOOLEAN_INVALID")
        # A syntactically well-formed, foreign candidate plan is still
        # unreviewed. The same owner pin is required on initial apply and on
        # all recovery paths, including resumed and uncertain scanner journals.
        if "plan_id" in self.state:
            require(type(self.state["plan_id"]) is str
                    and self.state["plan_id"] == OWNER_ATTESTED_CANDIDATE_PLAN,
                    "RECOVERY_PLAN_NOT_OWNER_ATTESTED")
        require(self.state["phase"] not in PHASES_REQUIRING_PLAN
                or self.state.get("plan_id") == OWNER_ATTESTED_CANDIDATE_PLAN,
                "RECOVERY_PLAN_MISSING")
        require(not self.state.get("switch_verified") or
                self.state.get("plan_id") == OWNER_ATTESTED_CANDIDATE_PLAN,
                "RECOVERY_VERIFIED_SWITCH_WITHOUT_PLAN")
        require(not self.state.get("rollback_intent") or
                (self.state["phase"] in {"recovery_required", "intent_rollback", "done_rollback"}
                 and self.state.get("plan_id") == OWNER_ATTESTED_CANDIDATE_PLAN),
                "RECOVERY_ROLLBACK_PHASE_OR_PLAN_UNVERIFIED")
        self.lock.verify()
        require(self.ops.bind_recovery(self.state) is True, "RECOVERY_IDENTITY_UNVERIFIED")

    def finish_original(self):
        """Restore original only while the exact owned admission guard remains.

        Early failure before guard installation, lost nft state, or foreign
        firewall modification requires explicit operator recovery. A valid
        original inode alone never authorizes maintenance/queue/FPM changes.
        The guard check does not demand writers already drained: on an early
        pre-switch failure they may still be active on untouched LIVE storage.
        """
        self.lock.verify()
        require(self.ops.abort_admission_safe() is True, "ABORT_GUARD_NOT_ATTESTED")
        require(self.ops.original_storage_writable_and_unchanged() is True, "ORIGINAL_NOT_SAFE")
        self.ops.restore_owned_maintenance(self.state)
        self.ops.restore_units(self.state["original_units"])
        require(self.ops.runtime_restored(self.state["original_units"]) is True, "RUNTIME_RESTORE_NOT_VERIFIED")
        self.ops.remove_owned_guard()
        require(self.ops.guard_absent() is True, "GUARD_REMOVAL_NOT_VERIFIED")
        self.save("aborted_original_restored")

    def rollback_paused(self):
        """Explicit operator rollback after a VERIFIED switch whose resume failed.

        Only valid while the transaction still owns the admission guard and the
        paused writers (phase recovery_required + switch_verified). Live traffic
        is never drained a second time here. The pinned v6 rollback refuses if
        any persistent file was updated or deleted in shared since the switch.
        """
        self.load_recovery_state()
        require(self.state["phase"] == "recovery_required" and self.state.get("switch_verified") is True,
                "ROLLBACK_ONLY_FROM_PAUSED_VERIFIED_SWITCH")
        require(self.ops.writers_still_paused() is True, "ROLLBACK_WRITERS_NOT_PAUSED")
        require(self.ops.reconcile_storage_readonly() == "verified_switched", "ROLLBACK_REQUIRES_VERIFIED_SWITCH")
        self.save("recovery_required", rollback_intent=True)
        self.step("rollback", self.ops.rollback_storage)
        require(self.ops.reconcile_storage_readonly() == "verified_original", "ROLLBACK_NOT_VERIFIED")
        self.finish_original()
        self.lock.close()

    def recover(self, *, allow_scanner_recovery=False):
        self.load_recovery_state()
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
            self.finish_original()
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
    # Source-only: no implied root entry, state/lock creation or host mutation.
    print(json.dumps({"status": "BLOCKED_NATIVE_ADAPTER_NOT_IMPLEMENTED",
                      "mode": "apply" if args.apply else "recover" if args.recover else "plan",
                      "mutated": False, "live": LIVE, "shared": SHARED, "pins": PINS}, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
