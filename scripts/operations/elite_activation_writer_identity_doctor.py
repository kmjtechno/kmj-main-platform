#!/usr/bin/env python3
"""Read-only owner review gate for KMJ-elite activation-intent writer identity.

Never installs broker, creates directories, reads request contents, changes
permissions, starts units, approves a release or claims PHP-FPM pool routing.
The preflight intentionally blocks if any worker under the fixed PHP-FPM master
could write the queue with an unexpected identity.
"""
from __future__ import annotations

import argparse
import errno
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import subprocess

HOST = "KMJ-elite"
OWNER = "kmjprod"
UNIT = "php8.4-fpm.service"
MASTER_EXE = "/usr/sbin/php-fpm8.4"
INBOX_DIR = Path("/home/kmjprod/shared/storage/app/private/ops")
INBOX = INBOX_DIR / "production-activation-request.json"
WORKER_PREFIX = "php-fpm: pool "
ACL_KEYS = ("system.posix_acl_access", "system.posix_acl_default")


class Blocked(Exception):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise Blocked(code)


def no_extended_acl(path: Path) -> None:
    """Unrecognized discretionary ACLs fail closed; no ACL content is printed."""
    for key in ACL_KEYS:
        try:
            os.getxattr(path, key, follow_symlinks=False)
        except OSError as exc:
            if exc.errno == errno.ENODATA:
                continue
            raise Blocked("BLOCKED_ACL_UNVERIFIED") from None
        raise Blocked("BLOCKED_EXTENDED_ACL_PRESENT")


def directory_identity(path: Path, uid: int) -> None:
    info = path.lstat()  # Never let symlinked ancestors redirect the inbox.
    require(stat.S_ISDIR(info.st_mode), "BLOCKED_DIRECTORY_SYMLINK_OR_TYPE")
    require(info.st_uid in (0, uid), "BLOCKED_DIRECTORY_OWNER")
    require(info.st_mode & 0o022 == 0, "BLOCKED_DIRECTORY_WRITABLE_BY_NONOWNER")
    no_extended_acl(path)


def fixed_parent_chain(uid: int) -> None:
    path = INBOX_DIR
    directories = []
    while path != Path("/"):
        directories.append(path)
        path = path.parent
    for item in reversed(directories):
        directory_identity(item, uid)
    parent = INBOX_DIR.lstat()
    require(parent.st_uid == uid, "BLOCKED_INBOX_NOT_OWNER_UID")
    require((parent.st_mode & 0o300) == 0o300, "BLOCKED_INBOX_NOT_WRITABLE_BY_OWNER")
    try:
        info = INBOX.lstat()
    except FileNotFoundError:
        return
    require(stat.S_ISREG(info.st_mode), "BLOCKED_EXISTING_REQUEST_SYMLINK_OR_TYPE")
    require(info.st_uid == uid and info.st_nlink == 1 and not (info.st_mode & 0o027),
            "BLOCKED_EXISTING_REQUEST_IDENTITY")
    no_extended_acl(INBOX)
    # Do not read a queued request or claim it can be safely replaced.
    raise Blocked("BLOCKED_EXISTING_REQUEST_REQUIRES_RECONCILIATION")


def parse_status(raw: bytes) -> tuple[int, tuple[int, int, int, int]]:
    lines = raw.decode("ascii", errors="strict").splitlines()
    matches = {}
    for line in lines:
        if line.startswith(("PPid:", "Uid:")):
            key, value = line.split(":", 1)
            require(key not in matches, "BLOCKED_PROC_DUPLICATE")
            matches[key] = value.strip()
    require(set(matches) == {"PPid", "Uid"}, "BLOCKED_PROC_SCHEMA")
    parent = matches["PPid"]
    ids = matches["Uid"].split()
    require(re.fullmatch(r"[0-9]{1,12}", parent) is not None
            and len(ids) == 4
            and all(re.fullmatch(r"[0-9]{1,12}", i) is not None for i in ids),
            "BLOCKED_PROC_SCHEMA")
    return int(parent), tuple(int(i) for i in ids)


def process_identity(pid: int) -> dict:
    require(isinstance(pid, int) and 1 <= pid <= 4194304, "BLOCKED_PROC_PID")
    base = Path("/proc") / str(pid)
    with (base / "status").open("rb") as f:
        status = f.read(16385)
    require(len(status) < 16385, "BLOCKED_PROC_OVERSIZE")
    parent, ids = parse_status(status)
    with (base / "cmdline").open("rb") as f:
        cmdline = f.read(513)
    require(len(cmdline) < 513, "BLOCKED_PROC_CMD_OVERSIZE")
    return {
        "pid": pid,
        "parent": parent,
        "uids": ids,
        "cmd": cmdline.partition(b"\x00")[0].decode("utf-8", errors="replace"),
        "exe": os.readlink(base / "exe"),
    }


def pool_identity(master_pid: int, master: dict, children: list[dict], uid: int) -> int:
    require(master["pid"] == master_pid and master["uids"] == (0, 0, 0, 0)
            and master["exe"] == MASTER_EXE, "BLOCKED_FPM_MASTER_IDENTITY")
    require(len(children) > 0, "BLOCKED_NO_LIVE_FPM_WORKER")
    require(len({w["pid"] for w in children}) == len(children),
            "BLOCKED_DUPLICATE_WORKER_SNAPSHOT")
    # Validate the shape of ALL children before classifying any UID mismatch.
    # Only emit a bounded count of known pool categories, never raw process
    # titles, UID numbers, paths, command lines or environment.
    for worker in children:
        require(worker["parent"] == master_pid
                and worker["exe"] == MASTER_EXE
                and worker["cmd"].startswith(WORKER_PREFIX)
                and len(worker["cmd"]) <= 100, "BLOCKED_UNKNOWN_FPM_CHILD")
    if any(worker["uids"] != (uid, uid, uid, uid) for worker in children):
        digest = {category: [0, 0] for category in ("KMJPROD", "WWW", "STAGING", "OTHER")}
        for worker in children:
            title = worker["cmd"][len(WORKER_PREFIX):]
            category = (
                "KMJPROD" if title == "kmjprod" else
                "WWW" if title == "www" else
                "STAGING" if title in ("kmjstage", "kmjstage-a979") else
                "OTHER"
            )
            own = worker["uids"] == (uid, uid, uid, uid)
            digest[category][0 if own else 1] += 1
        for category in ("KMJPROD", "WWW", "STAGING", "OTHER"):
            own_count, other_count = digest[category]
            print(f"KMJ_FPM_POOL_{category}_OWNER_UID_COUNT={own_count}")
            print(f"KMJ_FPM_POOL_{category}_OTHER_UID_COUNT={other_count}")
        raise Blocked("BLOCKED_FPM_WRITER_UID_MISMATCH")
    # Deliberately conservative: all direct master children must use kmjprod.
    # It does not prove Nginx's selected FastCGI listener or worker quiescence.
    return len(children)


def fixed_master_pid() -> int:
    p = subprocess.run(
        ["/usr/bin/systemctl", "show", "--no-pager", UNIT,
         "-p", "ActiveState", "-p", "MainPID"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        check=False, timeout=10,
    )
    require(p.returncode == 0, "BLOCKED_FPM_UNIT_NOT_READABLE")
    entries = p.stdout.splitlines()
    require(len(entries) == 2
            and set(x.partition("=")[0] for x in entries) == {"ActiveState", "MainPID"},
            "BLOCKED_FPM_UNIT_SCHEMA")
    data = dict(x.split("=", 1) for x in entries)
    require(data["ActiveState"] == "active"
            and re.fullmatch(r"[0-9]{1,12}", data["MainPID"]) is not None
            and int(data["MainPID"]) > 1, "BLOCKED_FPM_UNIT_INACTIVE")
    return int(data["MainPID"])


def fixed_live_children(master_pid: int) -> list[dict]:
    children = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        selected = False
        try:
            # Cheap bounded status-only scan. Do not inspect command lines or
            # executable links of unrelated processes.
            with (entry / "status").open("rb") as f:
                status = f.read(16385)
            require(len(status) < 16385, "BLOCKED_PROC_OVERSIZE")
            parent, _ = parse_status(status)
            if parent != master_pid:
                continue
            selected = True
            identity = process_identity(int(entry.name))
            require(identity["parent"] == master_pid,
                    "BLOCKED_FPM_WORKER_PARENT_RACE")
            children.append(identity)
        except (FileNotFoundError, ProcessLookupError):
            if selected:
                raise Blocked("BLOCKED_FPM_WORKER_DISAPPEARED") from None
            continue
        except (PermissionError, OSError, UnicodeError):
            raise Blocked("BLOCKED_PROC_SNAPSHOT_UNVERIFIED") from None
    return children


def inspect() -> int:
    # Classify *only* the fixed read-only phase on unexpected OS/parse errors.
    # Never return exception text, private paths, request bytes or process data.
    phase = "HOST"
    try:
        require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == HOST,
                "BLOCKED_WRONG_HOST_OR_UID")
        phase = "OWNER_UID"
        uid = pwd.getpwnam(OWNER).pw_uid
        require(uid > 0, "BLOCKED_OWNER_UID")
        # Check the filesystem before any success wording.
        phase = "PRIVATE_INBOX"
        fixed_parent_chain(uid)
        phase = "FPM_SYSTEMD_UNIT"
        master_pid = fixed_master_pid()
        phase = "FPM_MASTER_PROCESS"
        master = process_identity(master_pid)
        phase = "FPM_CHILD_PROCESSES"
        children = fixed_live_children(master_pid)
        phase = "FPM_CHILD_IDENTITY"
        count = pool_identity(master_pid, master, children, uid)
        # Ensure the master did not change underneath the read-only scan.
        phase = "FPM_MASTER_RECHECK"
        require(fixed_master_pid() == master_pid
                and process_identity(master_pid) == master,
                "BLOCKED_FPM_IDENTITY_RACE")
        phase = "PRIVATE_INBOX_RECHECK"
        fixed_parent_chain(uid)
        print("KMJ_ACTIVATION_WRITER_IDENTITY=READY_FOR_OWNER_REVIEW_NOT_INSTALLED")
        print("KMJ_FPM_WORKERS_AT_SNAPSHOT=" + str(count))
        print("ACTIVATION_REQUEST=NOT_CREATED")
        print("ROOT_BROKER=NOT_STARTED")
        print("PRODUCTION_MUTATION=NONE")
        return 0
    except Blocked as exc:
        print("KMJ_ACTIVATION_WRITER_IDENTITY=" + str(exc))
        return 2
    except (OSError, UnicodeError, ValueError, KeyError, subprocess.TimeoutExpired):
        print("KMJ_ACTIVATION_WRITER_IDENTITY=BLOCKED_READONLY_PROBE_UNVERIFIED")
        print("KMJ_ACTIVATION_PROBE_PHASE=" + phase)
        return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect", action="store_true", required=True)
    args = parser.parse_args()
    raise SystemExit(inspect())
