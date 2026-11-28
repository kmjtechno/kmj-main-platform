#!/usr/bin/env python3
"""Publish *read-only* exact-approval Elite release preflight for owner Ops UI.

This is NOT a deploy broker. It never creates approval, stages, deploys,
starts a release unit, or treats a GH branch as a verified staging origin.
The fixed gate may use a bounded unprivileged transient unit for local Git
verification under systemd hardening; this is read-only, not deployment.
Install only as an independently reviewed, root-owned fixed executable.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket
import stat
import sys
import tempfile
import time

HOST = "KMJ-elite"
GATE = Path("/opt/kmj-main-platform-autopublish/main_platform_autopublish_gate.py")
OUTPUT_DIR = Path("/run/kmj-main-platform")
OUTPUT = OUTPUT_DIR / "release-readiness.json"
BLOCKED = "BLOCKED_GATE_UNAVAILABLE"


def verified_gate():
    # Never write a .pyc into the signed, root-owned installed gate directory.
    sys.dont_write_bytecode = True
    # The only imported preflight is the operator-installed fixed root script.
    parent = GATE.parent.lstat()
    root = GATE.lstat()
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0
            or parent.st_mode & 0o022 or not stat.S_ISREG(root.st_mode)
            or root.st_uid != 0 or root.st_mode & 0o022 or root.st_nlink != 1
            or not 1000 <= root.st_size <= 30000):
        raise ValueError("BLOCKED_GATE_IDENTITY")
    spec = importlib.util.spec_from_file_location("kmj_fixed_release_gate", GATE)
    if spec is None or spec.loader is None:
        raise ValueError(BLOCKED)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    return gate


def snapshot(gate, clock: int) -> dict:
    approval = gate.protected_json(gate.APPROVAL)
    approved = approval.get("approvedSha") if isinstance(approval, dict) else None
    expected = approval.get("expectedCurrentRelease") if isinstance(approval, dict) else None
    valid_sha = isinstance(approved, str) and gate.SHA_RE.fullmatch(approved)
    admission = gate.protected_json(
        gate.ADMISSION_DIR / ("main-platform-autopublish-" + approved[:12] + ".json")
    ) if valid_sha else None
    current = gate.live_release()
    promoted = gate.remote_sha() if valid_sha else ""
    candidate = gate.candidate_sha(approved) if valid_sha else ""
    decision = gate.decision(approval, admission, current, promoted, candidate)
    if decision == "ALREADY_LIVE" and not gate.exact_https_sha_ok(
        gate.public_https_response(), approved
    ):
        decision = "BLOCKED_ALREADY_LIVE_HEALTH"

    return {
        "schema": "kmj.elite.release-readiness.v1",
        "host": HOST,
        "captured_at_unix": clock,
        "source": "fixed_root_preflight",
        "decision": decision,
        "current_release": current if gate.RELEASE_RE.fullmatch(current) else None,
        "approved_sha": approved if valid_sha else None,
        "expected_current_release": expected
        if isinstance(expected, str) and gate.RELEASE_RE.fullmatch(expected) else None,
        "promoted_sha": promoted if gate.SHA_RE.fullmatch(promoted) else None,
        "candidate_sha": candidate if gate.SHA_RE.fullmatch(candidate) else None,
        "staging_origin_verified": False,
        "scheduled_run_proven": False,
        "independent_dr_verified": False,
        "deploy_triggered": False,
    }


def publish(payload: dict) -> None:
    # Never put privileged health evidence in a user-writable directory.
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(mode=0o755)
    parent = OUTPUT_DIR.lstat()
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0
            or parent.st_mode & 0o022):
        raise ValueError("BLOCKED_OUTPUT_PARENT")
    if OUTPUT.exists() or OUTPUT.is_symlink():
        old = OUTPUT.lstat()
        if (not stat.S_ISREG(old.st_mode) or old.st_uid != 0
                or old.st_nlink != 1 or old.st_mode & 0o022):
            raise ValueError("BLOCKED_OUTPUT_IDENTITY")
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(data) > 4096:
        raise ValueError("BLOCKED_OVERSIZED_RECEIPT")

    fd, tmp = tempfile.mkstemp(prefix=".readiness-", dir=OUTPUT_DIR)
    try:
        with os.fdopen(fd, "wb") as file:
            os.fchmod(file.fileno(), 0o644)
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, OUTPUT)
        dirfd = os.open(OUTPUT_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != HOST:
        print("KMJ_RELEASE_READINESS=BLOCKED_HOST_ROOT")
        return 2
    try:
        result = snapshot(verified_gate(), int(time.time()))
        if args.publish:
            publish(result)
        print("KMJ_RELEASE_READINESS=" + result["decision"])
        print("MODE=" + ("PUBLISHED_READONLY" if args.publish else "INSPECT_ONLY"))
        print("PRODUCTION_MUTATION=NONE")
        return 0 if result["decision"] in ("READY_APPROVED_RELEASE", "ALREADY_LIVE") else 2
    except (OSError, ValueError, ImportError, AttributeError) as exc:
        print("KMJ_RELEASE_READINESS=BLOCKED_FIXED_PREFLIGHT")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
