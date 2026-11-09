"""09e8 candidate-only storage cutover transaction contract -- SOURCE REVIEW ONLY.

This module has NO native host adapter, root entry point, service commands,
filesystem mutation primitives or production-approval writer. It is deliberately
not an executable release tool. Integration must be separately audited, tested
under real Linux immutable flags, and owner-installed as a root-protected fixed
artifact before any real transaction is considered.

Geometry at contract creation:
* CURRENT live release platform-bce4100d005e ALREADY uses shared storage.
* Candidate platform-09e8a224cd37 still has physical local storage.
* The existing CD958 transaction switches its OLD live release; invoking it
  for this candidate by changing a SHA or a path is NOT supported.
* The pinned v6 scanner momentarily freezes SHARED storage during switch.
  Fresh writer admission and bounded recovery are mandatory despite the
  candidate being non-live. Never mutate the LIVE storage link or DB.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

SOURCE_CANDIDATE_SHA = "09e8a224cd37445c42588a073a6b52d207475a09"
SOURCE_CURRENT_RELEASE = "platform-bce4100d005e"
LIVE_APP = "/home/kmjprod/releases/platform-bce4100d005e/apps/platform"
CANDIDATE_APP = "/home/kmjprod/releases/platform-09e8a224cd37/apps/platform"
SHARED_STORAGE = "/home/kmjprod/shared/storage"
SCANNER_SHA256 = "f4d01f6e3b40c9ad774c8ada5129b241cee93dac782ce75bb0e229b26bbc95ba"
MATERIALIZER_SHA256 = "fd29c4ebcf224c45786f8cedd0e0d42bbfd414d706678fe820e0ead4eea3984f"

# Every predicate is a FRESH attestation from a separately reviewed adapter.
# A CI fake returning True does not establish real-world worker quiescence.
PREFLIGHT = frozenset({
    "production_pointer_exact",
    "candidate_git_sha_exact",
    "live_storage_already_shared",
    "candidate_storage_physical",
    "candidate_to_shared_plan_ready",
    "no_persistent_storage_conflicts",
    "global_release_lock_held",
    "root_protected_scanner_sha",
    "root_protected_restore_journal",
    "queue_scheduler_scope_exact",
    "fpm_pool_listener_exact",
    "nginx_upstream_scope_exact",
    "nft_output_admission_supported",
    "rollback_admission_restoration_supported",
})
ADMISSION = frozenset({
    "guard_owned_and_verified", "fresh_netns_bound",
    "queue_restart_always_bound", "scheduler_timer_paused",
    "scheduler_cgroup_empty", "maintenance_worker_idle",
    "queue_cgroup_empty", "production_fpm_pidfds_exited",
    "production_listener_no_pending_connections",
    "no_untracked_writer_descendants",
    "recovery_evidence_durable",
})
SWITCH = frozenset({
    "candidate_v6_receipt_exact",
    "candidate_shared_link_exact",
    "candidate_original_storage_preserved_frozen",
    "live_storage_link_unchanged",
    "live_release_pointer_unchanged",
    "shared_storage_fully_thawed",
    "queue_scheduler_still_paused",
    "production_fpm_still_quiescent",
    "admission_guard_still_owned",
})
COMPLETED_PHASE = "candidate_storage_prepared_materializer_pending"


class Refused(RuntimeError):
    pass


def insist(ok: bool, reason: str) -> None:
    if not ok:
        raise Refused(reason)


def attest_exact(proof: dict, required: frozenset[str], label: str) -> None:
    """No missing, extra, non-boolean, inferred or grandfathered proof."""
    insist(type(proof) is dict and set(proof) == required
           and all(type(proof[k]) is bool and proof[k] is True for k in required),
           label + "_NOT_ATTESTED")


def candidate_binding(candidate_sha: str, expected_live: str) -> None:
    insist(candidate_sha == SOURCE_CANDIDATE_SHA and
           expected_live == SOURCE_CURRENT_RELEASE,
           "RELEASE_BINDING_NOT_EXACT")


@dataclass(frozen=True)
class Record:
    version: int
    phase: str
    candidate_sha: str
    expected_current: str
    plan_id: str | None = None
    guard_owned: bool = False
    switch_intent: bool = False
    switch_verified: bool = False
    # The actual journal/receipt must also bind scanned inode, lock, netns,
    # generation IDs, recovery evidence and service states. This abstract
    # record is NOT an on-disk production schema.


class TransactionStore(Protocol):
    def read(self) -> Record | None: ...
    def write_durable(self, record: Record) -> None: ...


class CandidateAdapter(Protocol):
    """REVIEW INTERFACE ONLY; no native adapter exists in this module."""
    def preflight_exact(self) -> dict: ...
    def install_admission_guard(self) -> None: ...
    def attest_admission_and_drain(self) -> dict: ...
    def fresh_candidate_v6_plan(self) -> dict: ...
    def v6_switch_candidate_storage(self, exact_plan_id: str) -> None: ...
    def attest_candidate_only_switch(self) -> dict: ...
    def resume_original_services(self) -> None: ...
    def attest_services_resumed(self) -> bool: ...
    def remove_only_owned_guard(self) -> None: ...
    def attest_guard_absent(self) -> bool: ...
    def attest_original_candidate_and_live_unchanged(self) -> bool: ...
    def recover_original_admission_without_switch(self) -> None: ...


def transition(store: TransactionStore, current: Record, phase: str, **changes) -> Record:
    """Write intent BEFORE any external action and require durable storage."""
    next_record = Record(**{**vars(current), "phase": phase, **changes})
    store.write_durable(next_record)
    insist(store.read() == next_record, "DURABLE_RECORD_MISMATCH")
    return next_record


def fresh_plan(plan: dict) -> str:
    insist(type(plan) is dict and set(plan) == {"ready", "plan_id", "target", "mutated",
           "persistent_conflicts", "to_copy"}, "PLAN_SCHEMA_INVALID")
    pid = plan["plan_id"]
    insist(plan["ready"] is True and plan["mutated"] is False
           and plan["target"] == CANDIDATE_APP
           and type(plan["persistent_conflicts"]) is list
           and plan["persistent_conflicts"] == []
           and type(plan["to_copy"]) is int and plan["to_copy"] >= 0
           and type(pid) is str and len(pid) == 16
           and all(char in "0123456789abcdef" for char in pid),
           "CANDIDATE_FRESH_PLAN_NOT_READY")
    return pid


def run_review_contract(
    store: TransactionStore, adapter: CandidateAdapter,
    candidate_sha: str, expected_current: str
) -> Record:
    """Model guarded ordering in fake-adapter tests, NEVER run on a host.

    An adapter failure once admission has been touched produces a durable
    'recovery_required' state. No unconditional finally block resumes writers
    or removes the owned firewall guard after uncertain switch intent.
    """
    candidate_binding(candidate_sha, expected_current)
    insist(store.read() is None, "EXISTING_TRANSACTION_REQUIRES_REVIEW")
    attest_exact(adapter.preflight_exact(), PREFLIGHT, "PREFLIGHT")
    record = Record(1, "preflight_proven", candidate_sha, expected_current)
    store.write_durable(record)
    insist(store.read() == record, "DURABLE_PREPARE_FAILED")
    try:
        record = transition(store, record, "admission_guard_intent")
        adapter.install_admission_guard()
        record = transition(store, record, "admission_guard_installed", guard_owned=True)
        attest_exact(adapter.attest_admission_and_drain(), ADMISSION, "WRITER_DRAIN")
        record = transition(store, record, "admission_and_drain_attested")
        plan_id = fresh_plan(adapter.fresh_candidate_v6_plan())
        record = transition(store, record, "candidate_switch_intent",
                            plan_id=plan_id, switch_intent=True)
        adapter.v6_switch_candidate_storage(plan_id)
        # Even return code 0 from v6 is not release success. Root receipts,
        # preserved candidate inode and STILL-PRESENT guard need fresh checks.
        attest_exact(adapter.attest_candidate_only_switch(), SWITCH, "CANDIDATE_SWITCH")
        record = transition(store, record, "candidate_switch_verified",
                            switch_verified=True)
        adapter.resume_original_services()
        insist(adapter.attest_services_resumed() is True, "SERVICES_NOT_RESTORED")
        record = transition(store, record, "services_restored")
        adapter.remove_only_owned_guard()
        insist(adapter.attest_guard_absent() is True, "OWNED_GUARD_NOT_REMOVED")
        record = transition(store, record, COMPLETED_PHASE)
        return record
    except Exception:
        # Scanner may have frozen shared inodes. Never infer that it reverted.
        # Do not resume services, drop guard or automatically retry switch.
        observed = store.read()
        if observed is not None and observed.phase != COMPLETED_PHASE:
            transition(store, observed, "recovery_required")
        raise


def review_pre_switch_abort(
    store: TransactionStore, adapter: CandidateAdapter
) -> Record:
    """Fail-closed recovery REVIEW: only if switch was provably NOT attempted.

    A native adapter needs an independent root journal proof for this; the
    abstract model intentionally has no recovery path after switch intent.
    """
    record = store.read()
    insist(record is not None and record.phase == "recovery_required",
           "NO_RECOVERY_RECORD")
    insist(record.switch_intent is False and record.switch_verified is False,
           "SCANNER_RECOVERY_AND_MANUAL_REVIEW_REQUIRED")
    insist(adapter.attest_original_candidate_and_live_unchanged() is True,
           "CANDIDATE_OR_LIVE_CHANGED")
    adapter.recover_original_admission_without_switch()
    insist(adapter.attest_services_resumed() is True and
           adapter.attest_guard_absent() is True, "ORIGINAL_ADMISSION_NOT_RESTORED")
    return transition(store, record, "aborted_original_preserved")


def release_gate(_record: Record) -> bool:
    """A storage-only review result must NEVER authorize production deploy."""
    return False


if __name__ == "__main__":
    raise SystemExit("REVIEW_ONLY_NO_NATIVE_ADAPTER_OR_HOST_ENTRYPOINT")
