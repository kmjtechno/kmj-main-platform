#!/usr/bin/env python3
"""Owner-reviewed, opt-in reconciliation of the Elite local health timer policy.

--inspect is read-only. --apply changes only the exact owner-disabled offsite
timer requirement in the root-owned health script, with an exclusive backup.
This is never a release approval, a timer start, or DR/restore attestation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import socket
import stat
import subprocess
import tempfile

HEALTH = Path("/usr/local/sbin/kmj-elite-health-check")
OLD = b"systemctl is-active --quiet kmj-elite-offsite-backup.timer\n"
NEW = b"""if systemctl is-active --quiet kmj-elite-offsite-backup.timer; then
  echo "KMJ_OFFSITE_TIMER=ACTIVE; DR=NOT_VERIFIED"
elif [[ "$(systemctl is-active kmj-elite-offsite-backup.timer 2>/dev/null || true)" == "inactive" && "$(systemctl is-enabled kmj-elite-offsite-backup.timer 2>/dev/null || true)" == "disabled" ]]; then
  echo "KMJ_OFFSITE_TIMER=DISABLED_BY_OWNER; DR=NOT_VERIFIED"
else
  echo "UNHEALTHY_OFFSITE_TIMER_STATE"
  exit 8
fi
"""
ANCHORS = (
    b"set -Eeuo pipefail\n",
    b"systemctl is-active --quiet kmj-main-platform-scheduler.timer\n",
    b"find /var/backups/kmj-elite-daily -mindepth 2 -maxdepth 2 -name platform.dump -type f -mtime -2 | grep -q .\n",
    b"test -s /root/kmj-bootstrap/offsite-age-recipients.txt\n",
    b"find /var/backups/kmj-elite-offsite-encrypted -mindepth 1 -maxdepth 1 -name '20*.tar.age' -type f -mtime -2 | grep -q .\n",
    b"echo KMJ_ELITE_HEALTH_PASS\n",
)


def transform(source: bytes) -> tuple[bytes, str]:
    """Change only the failed owner-disabled timer gate; reject script drift."""
    if b"\r" in source or not source.startswith(b"#!/usr/bin/env bash\n"):
        raise ValueError("BLOCKED_SCRIPT_FORMAT")
    lines = source.splitlines(keepends=True)
    for anchor in ANCHORS:
        if lines.count(anchor) != 1:
            raise ValueError("BLOCKED_REQUIRED_LOCAL_HEALTH_ANCHOR")
    original = lines.count(OLD)
    patched = source.count(NEW)
    if original == 1 and patched == 0:
        transformed = source.replace(OLD, NEW, 1)
        state = "READY_FOR_OWNER_APPLY"
    elif original == 0 and patched == 1:
        transformed, state = source, "ALREADY_APPLIED"
    else:
        raise ValueError("BLOCKED_UNKNOWN_OFFSITE_POLICY")

    markers = (
        ANCHORS[1], ANCHORS[2], NEW if state == "ALREADY_APPLIED" else NEW,
        ANCHORS[3], ANCHORS[4], ANCHORS[5],
    )
    indexes = [transformed.find(marker) for marker in markers]
    if any(i < 0 for i in indexes) or indexes != sorted(indexes) or len(set(indexes)) != len(indexes):
        raise ValueError("BLOCKED_HEALTH_CHECK_ORDER")
    if transformed.count(b"KMJ_ELITE_HEALTH_PASS") != 1:
        raise ValueError("BLOCKED_PASS_MARKER_DRIFT")
    return transformed, state


def read_verified(path: Path) -> tuple[bytes, os.stat_result]:
    parent = path.parent.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0 or parent.st_mode & 0o022:
        raise ValueError("BLOCKED_PARENT_IDENTITY")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != 0
                or before.st_nlink != 1 or before.st_mode & 0o022
                or not 32 <= before.st_size <= 65536):
            raise ValueError("BLOCKED_SCRIPT_IDENTITY")
        data = os.read(fd, 65537)
        after = os.fstat(fd)
        if (len(data) != before.st_size or after.st_size != before.st_size
                or after.st_mtime_ns != before.st_mtime_ns):
            raise ValueError("BLOCKED_SCRIPT_CHANGED_WHILE_READING")
        return data, before
    finally:
        os.close(fd)


def exact_timer_state(unit: str, verb: str) -> str:
    result = subprocess.run(
        ["/usr/bin/systemctl", verb, unit],
        check=False, capture_output=True, text=True, timeout=10,
    )
    return result.stdout.strip() if result.returncode in (0, 3, 1) else ""


def require_owner_selected_state() -> None:
    scheduler = exact_timer_state("kmj-main-platform-scheduler.timer", "is-active")
    offsite = exact_timer_state("kmj-elite-offsite-backup.timer", "is-active")
    enabled = exact_timer_state("kmj-elite-offsite-backup.timer", "is-enabled")
    if (scheduler, offsite, enabled) != ("active", "inactive", "disabled"):
        raise ValueError("BLOCKED_UNEXPECTED_TIMER_STATE")


def durable_write(fd: int, data: bytes, info: os.stat_result) -> None:
    os.fchown(fd, info.st_uid, info.st_gid)
    os.fchmod(fd, stat.S_IMODE(info.st_mode))
    with os.fdopen(fd, "wb") as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())


def apply(path: Path, source: bytes, updated: bytes, info: os.stat_result) -> str:
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        raise ValueError("BLOCKED_OWNER_ROOT_ELITE_REQUIRED")
    require_owner_selected_state()
    current = path.lstat()
    if (current.st_ino, current.st_dev, current.st_size, current.st_mtime_ns) != (
        info.st_ino, info.st_dev, info.st_size, info.st_mtime_ns
    ):
        raise ValueError("BLOCKED_SOURCE_CHANGED")
    backup = path.with_name(path.name + ".bak." + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    bfd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    durable_write(bfd, source, info)
    fd, tmp = tempfile.mkstemp(prefix=".kmj-health-policy-", dir=str(path.parent))
    try:
        durable_write(fd, updated, info)
        syntax = subprocess.run(["/usr/bin/bash", "-n", tmp], check=False, timeout=10)
        if syntax.returncode != 0:
            raise ValueError("BLOCKED_BASH_SYNTAX")
        latest = path.lstat()
        if (latest.st_ino, latest.st_dev, latest.st_size, latest.st_mtime_ns) != (
            info.st_ino, info.st_dev, info.st_size, info.st_mtime_ns
        ):
            raise ValueError("BLOCKED_SOURCE_RACE")
        os.replace(tmp, path)
        dirfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
        return str(backup)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        source, info = read_verified(HEALTH)
        updated, state = transform(source)
        if args.inspect or state == "ALREADY_APPLIED":
            print("KMJ_HEALTH_POLICY=" + state)
            print("DR=NOT_VERIFIED")
            return 0
        backup = apply(HEALTH, source, updated, info)
        print("KMJ_HEALTH_POLICY=APPLIED")
        print("BACKUP=" + backup)
        print("DR=NOT_VERIFIED")
        print("HEALTH_UNIT_INVOCATION=NOT_EXECUTED")
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print("KMJ_HEALTH_POLICY=" + str(exc)[:120])
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
