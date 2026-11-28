#!/usr/bin/env python3
"""Owner-invoked root runner: collect every non-owner evidence receipt for the
CURRENT protected approval, in a fixed order, via fixed argv (source only until installed).

It reads the approved SHA and predecessor ONLY from the root-protected approval file,
never from arguments. It writes receipts and nothing else: no admission, no approval
change, no unit start, no pointer change. Independent steps continue after failure;
dependent rehearsal and derived evidence steps fail closed;
the exit code is 0 only when every step passed.
"""
import os
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import main_platform_autopublish_gate as gate  # noqa: E402
import release_admission_receipts as ra  # noqa: E402

STEPS = (
    ("STAGING_ORIGIN", "elite_collect_staging_origin_receipt.py", "--write"),
    ("PUBLIC_QA", "elite_collect_public_qa_receipt.py", "--write"),
    ("BACKUP_AND_RESTORE", "elite_collect_backup_receipts.py", "--write"),
    ("REHEARSAL_WORKSPACE", "elite_prepare_rehearsal.py", "--write"),
    ("ROLLBACK_REHEARSAL", "elite_collect_rollback_rehearsal_receipt.py", "--write"),
    ("REHEARSAL_CLEANUP", "elite_prepare_rehearsal.py", "--cleanup"),
    ("MIGRATION_STORAGE", "elite_derive_migration_storage_receipt.py", "--write"),
)


def identity(approval):
    if not isinstance(approval, dict) or set(approval) != gate.APPROVAL_KEYS:
        raise ValueError("BLOCKED_APPROVAL_SCHEMA")
    sha, expected = approval.get("approvedSha"), approval.get("expectedCurrentRelease")
    if (not isinstance(sha, str) or not ra.SHA_RE.fullmatch(sha)
            or not isinstance(expected, str) or not ra.RELEASE_RE.fullmatch(expected)
            or approval.get("backupVerified") is not True
            or approval.get("rollbackVerified") is not True):
        raise ValueError("BLOCKED_PROTECTED_APPROVAL")
    return sha, expected


def run_step(script, mode, sha, expected):
    proc = subprocess.run(
        ["/usr/bin/python3", "-I", "-B", str(HERE / script), mode, sha, expected],
        cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C"}, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, check=False, timeout=7200)
    return proc.returncode == 0


def main(runner=run_step, approval=None):
    if approval is None:
        if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
            print("KMJ_COLLECT_ALL=BLOCKED_HOST_ROOT")
            return 2
        approval = gate.protected_json(gate.APPROVAL)
    try:
        sha, expected = identity(approval)
    except ValueError as exc:
        print("KMJ_COLLECT_ALL=" + str(exc))
        return 2
    failed = []
    passed = set()
    dependencies = {
        'ROLLBACK_REHEARSAL': {'REHEARSAL_WORKSPACE'},
        'REHEARSAL_CLEANUP': {'REHEARSAL_WORKSPACE'},
        'MIGRATION_STORAGE': {'BACKUP_AND_RESTORE', 'ROLLBACK_REHEARSAL', 'REHEARSAL_CLEANUP'},
    }
    for label, script, mode in STEPS:
        if not dependencies.get(label, set()) <= passed:
            print('KMJ_COLLECT_{}=BLOCKED_DEPENDENCY'.format(label))
            failed.append(label)
            continue
        ok = False
        try:
            ok = runner(script, mode, sha, expected)
        except (OSError, subprocess.SubprocessError):
            ok = False
        print("KMJ_COLLECT_{}={}".format(label, "PASS" if ok else "FAIL"))
        if ok:
            passed.add(label)
        else:
            failed.append(label)
    print("KMJ_COLLECT_ALL=" + ("PASS" if not failed else "INCOMPLETE"))
    print("AUTHENTICATED_QA=OWNER_CLICK_REQUIRED ADMISSION_WRITTEN=NO PRODUCTION_RELEASE=NOT_ATTEMPTED")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
