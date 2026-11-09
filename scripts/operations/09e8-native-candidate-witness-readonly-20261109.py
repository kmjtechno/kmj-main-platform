#!/usr/bin/env python3
"""Exact 09e8 candidate storage witness (READ ONLY, root KMJ-elite).

Modes:
  --pre: independently attest the exact candidate, installed root materializer,
         live shared storage and a fresh v6 storage plan.
  --post: after a separately owner-approved native switch, attest root-protected
          completed v6 scanner receipt, uniquely preserved candidate snapshot,
          unchanged live shared inode/pointer and unfrozen shared storage.

This does NOT stop writers, switch storage, run the materializer, modify the
database, change any systemd unit, approve or activate a production release.
Host mutation, cutover authorization and trust in an unverified receipt are
explicitly out of scope. All root-executed helper code is SHA-pinned.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import sys
import types

CANDIDATE_SHA = "09e8a224cd37445c42588a073a6b52d207475a09"
LIVE_RELEASE = "platform-bce4100d005e"
ROOT = Path("/home/kmjprod")
LIVE = ROOT / "releases" / LIVE_RELEASE
CANDIDATE = ROOT / "releases" / ("platform-" + CANDIDATE_SHA[:12])
CAND_APP = CANDIDATE / "apps/platform"
LIVE_APP = LIVE / "apps/platform"
CURRENT = ROOT / "current"
SHARED = ROOT / "shared/storage"
SCANNER = Path("/usr/local/libexec/kmj-codebridge/main-platform-storage-switch-v6.py")
HELPER = Path("/usr/local/libexec/kmj-codebridge/main-platform-storage-snapshot-attest.py")
MATERIALIZER = Path("/usr/local/libexec/kmj-codebridge/main-platform-candidate-materialize-v2.sh")
SCANNER_SHA = "f4d01f6e3b40c9ad774c8ada5129b241cee93dac782ce75bb0e229b26bbc95ba"
HELPER_SHA = "72fe5702c59599bd1b28b88dad808dda5d6be97b61f0db06dc3a7295258a51b6"
MATERIALIZER_SHA = "fd29c4ebcf224c45786f8cedd0e0d42bbfd414d706678fe820e0ead4eea3984f"
STATE = "/var/lib/kmj-main-platform-storage-switch"
MAX_BYTES = 1024 * 1024
SAFE_SNAPSHOT = re.compile(r"storage\.pre-shared-\d{8}T\d{6}Z\Z")
PLAN_ID = re.compile(r"[a-f0-9]{16}\Z")


class Refused(RuntimeError):
    pass


def require(test: bool, reason: str) -> None:
    if not test:
        raise Refused(reason)


def key_stat(s: os.stat_result) -> tuple:
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid,
            s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def verify_pinned(path: Path, sha: str) -> bytes:
    """No-follow protected read with stable root-owned ancestor chain."""
    require(str(path) == os.path.realpath(path), "DEPENDENCY_NONCANONICAL")
    for parent in path.parents:
        s = os.lstat(parent)
        require(stat.S_ISDIR(s.st_mode) and s.st_uid == 0
                and not s.st_mode & 0o022, "DEPENDENCY_ANCESTOR_UNTRUSTED")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == 0
                and stat.S_IMODE(before.st_mode) & 0o022 == 0
                and before.st_nlink == 1 and 0 < before.st_size <= MAX_BYTES,
                "DEPENDENCY_FILE_UNTRUSTED")
        chunks = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            require(bool(chunk), "DEPENDENCY_SHORT_READ")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(key_stat(before) == key_stat(os.fstat(fd))
                == key_stat(path.lstat()), "DEPENDENCY_CHANGED")
        raw = b"".join(chunks)
        require(hashlib.sha256(raw).hexdigest() == sha, "DEPENDENCY_SHA_MISMATCH")
        return raw
    finally:
        os.close(fd)


def load_helper() -> types.ModuleType:
    raw = verify_pinned(HELPER, HELPER_SHA)
    module = types.ModuleType("kmj_09e8_root_pinned_snapshot_attestor")
    module.__file__ = str(HELPER)
    exec(compile(raw, str(HELPER), "exec"), module.__dict__)
    return module


def live_identity() -> tuple:
    """Pointer and live storage are both already symlinks to exact roots."""
    require(CURRENT.is_symlink()
            and CURRENT.resolve(strict=True) == LIVE, "CURRENT_POINTER_NOT_EXACT")
    require((LIVE_APP / "storage").is_symlink()
            and (LIVE_APP / "storage").resolve(strict=True) == SHARED,
            "LIVE_STORAGE_NOT_APPROVED_SHARED")
    require(SHARED.is_dir() and not SHARED.is_symlink(),
            "SHARED_STORAGE_UNTRUSTED")
    live_stat = (LIVE_APP / "storage").stat()
    shared_stat = SHARED.stat()
    require((live_stat.st_dev, live_stat.st_ino) ==
            (shared_stat.st_dev, shared_stat.st_ino), "LIVE_SHARED_INODE_MISMATCH")
    return (key_stat(CURRENT.lstat()), key_stat((LIVE_APP / "storage").lstat()),
            (shared_stat.st_dev, shared_stat.st_ino))


def check_state_no_active_journal() -> None:
    """Read-only bound journal absence. No state-dir creation."""
    path = Path(STATE)
    if not path.exists():
        return
    require(path.is_dir() and not path.is_symlink(), "STATE_DIR_UNTRUSTED")
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        s = os.fstat(fd)
        require(s.st_uid == 0 and stat.S_IMODE(s.st_mode) == 0o700,
                "STATE_DIR_PERMISSIONS")
        key = hashlib.sha256(str(CAND_APP).encode()).hexdigest()[:12]
        require(key + ".journal" not in os.listdir(fd),
                "ACTIVE_CANDIDATE_JOURNAL_RUN_RECOVERY")
    finally:
        os.close(fd)


def sanitized_plan(value: dict) -> dict:
    require(type(value) is dict and value.get("command") == "plan"
            and value.get("mutated") is False
            and value.get("inventory_only_not_release_readiness") is True
            and value.get("persistent_only_plan_id") is True
            and value.get("ready") is True, "CANDIDATE_PLAN_NOT_READY")
    require(type(value.get("to_copy")) is int and value["to_copy"] == 0,
            "UNEXPECTED_ADDITIVE_COPY_REVIEW")
    require(type(value.get("persistent_conflicts")) is list
            and not value["persistent_conflicts"], "CANDIDATE_CONFLICTS")
    plan_id = value.get("plan_id")
    require(type(plan_id) is str and PLAN_ID.fullmatch(plan_id) is not None,
            "CANDIDATE_PLAN_ID_INVALID")
    require(value.get("top_dir_meta_live_mode_uid_gid") ==
            value.get("top_dir_meta_shared_mode_uid_gid"),
            "TOP_DIRECTORY_METADATA_MISMATCH")
    return {"STORAGE_PLAN_READY": "YES",
            "STORAGE_PLAN_ID": plan_id,
            "STORAGE_TO_COPY": "0",
            "STORAGE_PERSISTENT_CONFLICTS": "0"}


def pre(helper: types.ModuleType) -> dict:
    """Actual root read-only candidate geometry and scanner plan."""
    storage = CAND_APP / "storage"
    require(stat.S_ISDIR(storage.lstat().st_mode)
            and not storage.is_symlink(), "CANDIDATE_STORAGE_NOT_PHYSICAL")
    require(not (CAND_APP / ".env").exists()
            and not (CAND_APP / ".env").is_symlink(),
            "CANDIDATE_ALREADY_MATERIALIZED")
    helper.git_identity(CANDIDATE, CANDIDATE_SHA)
    check_state_no_active_journal()
    scanner = helper.load_scanner(str(SCANNER), CANDIDATE, SHARED, Path(STATE))
    values = scanner.cmd_plan(types.SimpleNamespace(
        app_dir=str(CAND_APP), shared=str(SHARED), allowed_root=str(ROOT),
        state_dir=STATE, proc_root="/proc", apply=False, plan_id=None
    ))
    return {"CANDIDATE_STORAGE": "PHYSICAL", **sanitized_plan(values)}


def post(helper: types.ModuleType) -> dict:
    """Actual root read-only scanner journal + snapshot attestation."""
    storage = CAND_APP / "storage"
    require(storage.is_symlink() and storage.resolve(strict=True) == SHARED,
            "CANDIDATE_SHARED_LINK_MISSING")
    check_state_no_active_journal()
    snapshots = sorted(x.name for x in CAND_APP.iterdir()
                       if x.name.startswith("storage.pre-shared-"))
    require(len(snapshots) == 1
            and SAFE_SNAPSHOT.fullmatch(snapshots[0]) is not None,
            "CANDIDATE_SNAPSHOT_NOT_UNIQUE")
    verified = helper.check_source(
        release_root=CANDIDATE, app_dir=str(CAND_APP),
        expected_sha=CANDIDATE_SHA, shared_dir=SHARED,
        snapshot_name=snapshots[0], state_dir=STATE, scanner_path=str(SCANNER)
    )
    require(verified == "apps/platform/" + snapshots[0] + "/",
            "CANDIDATE_ROOT_SNAPSHOT_NOT_ATTESTED")
    return {"CANDIDATE_STORAGE": "SHARED",
            "CANDIDATE_V6_CLOSED_RECEIPT": "ROOT_ATTESTED",
            "CANDIDATE_FROZEN_SNAPSHOT": "ROOT_ATTESTED",
            "SHARED_STORAGE_THAWED": "ROOT_ATTESTED"}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--pre", action="store_true")
    modes.add_argument("--post", action="store_true")
    flags = parser.parse_args(argv)
    print("SCHEMA=kmj.09e8.native-candidate-witness.readonly.v1")
    try:
        require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite",
                "ROOT_ELITE_ONLY")
        live = live_identity()
        verify_pinned(SCANNER, SCANNER_SHA)
        verify_pinned(MATERIALIZER, MATERIALIZER_SHA)
        helper = load_helper()
        result = pre(helper) if flags.pre else post(helper)
        require(live_identity() == live, "LIVE_POINTER_OR_SHARED_CHANGED")
        check_state_no_active_journal()
        print("LIVE_STORAGE_SWITCH_REQUIRED=NO")
        print("CANDIDATE_EXACT_GIT_SHA=YES")
        print("PINNED_ROOT_MATERIALIZER=YES")
        print("PINNED_ROOT_SCANNER_HELPER=YES")
        for key, value in result.items():
            print(key + "=" + value)
        print("WRITER_ADMISSION=NOT_ATTESTED")
        print("STORAGE_APPLY_ALLOWED=NO")
        print("PRODUCTION_MUTATION=NONE")
        print("NATIVE_CANDIDATE_WITNESS=READ_ONLY_COMPLETE")
        return 0
    except (Refused, OSError, ValueError, KeyError, TypeError,
            RuntimeError) as exc:
        # Fixed categorical output; no paths, current environment, customer
        # data, credentials, sensitive process lists or raw exception text.
        print("NATIVE_CANDIDATE_WITNESS=BLOCKED_UNVERIFIABLE")
        print("WRITER_ADMISSION=NOT_ATTESTED")
        print("STORAGE_APPLY_ALLOWED=NO")
        print("PRODUCTION_MUTATION=NONE")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
