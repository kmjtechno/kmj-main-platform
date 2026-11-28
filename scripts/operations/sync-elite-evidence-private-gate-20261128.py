#!/usr/bin/env python3
"""Owner-only synchronization of the installed evidence private gate copy.

Pins the previously reviewed install source and the merged compatibility fix.
Changes only the evidence private copy and creates one root-owned rollback copy.
Never creates approval/admission, starts services, migrates or switches releases.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import tempfile

OLD_COMMIT = "7d12e10e1eebfce779ce62a1a044528e2dad4fb6"
NEW_COMMIT = "299706fddcc6a5eb057a6c1a5b3c3228db0e3d7a"
OLD_BLOB = "f2f03f35947288ea1f11bb2a1f043b65973d8c4a"
NEW_BLOB = "6eab33bdf49d28cce74c5df01db4dbdbdd9e8b31"
LIVE_SHA = "72e7c9ada19077549e96946087a373249cbd4eb2"
SOURCE = "scripts/operations/main_platform_autopublish_gate.py"
REMOTE = "https://github.com/kmjtechno/kmj-main-platform.git"
PRIMARY = Path("/opt/kmj-main-platform-autopublish/main_platform_autopublish_gate.py")
GATE = Path("/opt/kmj-main-platform-release-evidence/main_platform_autopublish_gate.py")
BACKUP = GATE.with_name(GATE.name + ".pre-shared-storage-" + OLD_BLOB[:12])
LOCK = Path("/run/lock/kmj-main-platform-autopublish.lock")
APPROVAL = Path("/etc/kmj-codebridge/main-platform-production-release.json")
LIVE = Path("/home/kmjprod/current")
EXPECTED_LIVE = Path("/home/kmjprod/releases/platform-" + LIVE_SHA[:12])
UNITS = (
    (Path("/etc/systemd/system/kmj-main-platform-autopublish.service"),
     "c83744915e8e102f87503e37deabf7495310f205"),
    (Path("/etc/systemd/system/kmj-main-platform-autopublish.timer"),
     "32cd3c6be7377d12a1c177339a8bbf287599ccff"),
)
CONFIRM = "OWNER_APPROVES_EVIDENCE_PRIVATE_GATE_PIN_SYNC"
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/root", "LANG": "C",
       "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
       "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_NO_REPLACE_OBJECTS": "1"}


class Blocked(Exception):
    pass


def require(ok, code):
    if not ok:
        raise Blocked(code)


def protected_dir(path):
    if not path.is_absolute() or ".." in path.parts:
        return False
    try:
        for parent in (path, *path.parents):
            info = parent.lstat()
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                    or info.st_mode & 0o022):
                return False
        return True
    except OSError:
        return False


def stable_read(path, mode, limit=30000):
    require(protected_dir(path.parent), "UNTRUSTED_PARENT")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == 0
                and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == mode
                and 0 < before.st_size <= limit, "UNTRUSTED_ARTIFACT")
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                and len(data) == before.st_size, "ARTIFACT_READ_RACE")
        return data


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def git(args, timeout=100):
    p = subprocess.run(["/usr/bin/git", *args], cwd="/", env=ENV,
                       stdin=subprocess.DEVNULL, capture_output=True,
                       timeout=timeout, check=False)
    require(p.returncode == 0 and len(p.stdout) <= 30000, "GIT_READ_FAILED")
    return p.stdout


def reviewed_bytes():
    require(protected_dir(Path("/root")), "ROOT_PARENT_UNTRUSTED")
    with tempfile.TemporaryDirectory(prefix="kmj-gate-upgrade-", dir="/root") as temp:
        repo = str(Path(temp) / "objects.git")
        git(["init", "--bare", "--quiet", repo])
        data = []
        for commit, expected_blob in ((OLD_COMMIT, OLD_BLOB), (NEW_COMMIT, NEW_BLOB)):
            git(["-c", "credential.helper=", "-c", "core.hooksPath=/dev/null",
                 "-C", repo, "fetch", "--no-tags", "--depth=1", REMOTE, commit])
            actual = git(["-C", repo, "rev-parse", "--verify", "FETCH_HEAD^{commit}"])
            require(actual.decode("ascii").strip() == commit, "COMMIT_PIN_MISMATCH")
            raw = git(["-C", repo, "show", commit + ":" + SOURCE])
            require(blob(raw) == expected_blob and b"\0" not in raw,
                    "BLOB_PIN_MISMATCH")
            compile(raw, SOURCE, "exec")
            data.append(raw)
        return tuple(data)


def exact_approval(raw):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            require(k not in result, "DUPLICATE_APPROVAL_KEY")
            result[k] = v
        return result
    approval = json.loads(raw, object_pairs_hook=unique)
    require(isinstance(approval, dict) and set(approval) ==
            {"approvedSha", "expectedCurrentRelease", "backupVerified", "rollbackVerified"},
            "APPROVAL_SCHEMA")
    require(approval["approvedSha"] == LIVE_SHA and
            approval["backupVerified"] is True and approval["rollbackVerified"] is True,
            "APPROVAL_NOT_CURRENT_LIVE")
    require(LIVE.is_symlink() and LIVE.resolve(strict=True) == EXPECTED_LIVE,
            "LIVE_POINTER_DRIFT")


def sync_dir():
    fd = os.open(GATE.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def stage(data):
    fd, name = tempfile.mkstemp(prefix=".gate-upgrade-", dir=GATE.parent)
    path = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o500)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        require(stable_read(path, 0o500) == data, "STAGED_BYTES_MISMATCH")
        return path
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def ensure_backup(old):
    if BACKUP.exists() or BACKUP.is_symlink():
        require(stable_read(BACKUP, 0o500) == old, "BACKUP_PIN_MISMATCH")
        return
    temp = stage(old)
    try:
        os.link(temp, BACKUP, follow_symlinks=False)
        temp.unlink()
        require(stable_read(BACKUP, 0o500) == old, "BACKUP_PIN_MISMATCH")
        sync_dir()
    finally:
        temp.unlink(missing_ok=True)


def run(apply):
    require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite",
            "ROOT_ELITE_ONLY")
    old, new = reviewed_bytes()
    require(stable_read(PRIMARY, 0o500) == new, "PRIMARY_GATE_PIN_MISMATCH")
    for path, pin in UNITS:
        require(blob(stable_read(path, 0o644, 10000)) == pin, "UNIT_PIN_MISMATCH")
    # Existing gate lock is shared with the autopublisher. Never create or
    # replace that lock; if absent/untrusted, stop for owner review.
    fd = os.open(LOCK, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "r+b") as lock:
        info = os.fstat(lock.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0
                and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600,
                "LOCK_UNTRUSTED")
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        approval = stable_read(APPROVAL, 0o600, 4096)
        exact_approval(approval)
        current = stable_read(GATE, 0o500)
        require(current in (old, new), "INSTALLED_GATE_UNKNOWN")
        if current == new:
            require(stable_read(BACKUP, 0o500) == old, "BACKUP_PIN_MISMATCH")
            print("GATE_UPGRADE=ALREADY_INSTALLED_PIN_MATCH")
            return
        if not apply:
            print("GATE_UPGRADE=OLD_PIN_MATCH_NEW_PIN_VERIFIED_INSPECT_ONLY")
            return
        ensure_backup(old)
        temp = stage(new)
        try:
            require(stable_read(GATE, 0o500) == old, "GATE_CHANGED")
            require(stable_read(APPROVAL, 0o600, 4096) == approval, "APPROVAL_CHANGED")
            exact_approval(approval)
            require(stable_read(PRIMARY, 0o500) == new, "PRIMARY_GATE_PIN_CHANGED")
            os.replace(temp, GATE)
            sync_dir()
            require(stable_read(GATE, 0o500) == new, "INSTALLED_NEW_PIN_MISMATCH")
            require(stable_read(BACKUP, 0o500) == old, "BACKUP_PIN_MISMATCH")
            require(stable_read(PRIMARY, 0o500) == new, "PRIMARY_GATE_PIN_CHANGED")
            print("EVIDENCE_PRIVATE_GATE=PASS_PRIMARY_PIN_MATCH")
            print("GATE_UPGRADE=PASS_NEW_PIN_AND_ROLLBACK_COPY")
        finally:
            temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    try:
        require(not args.apply or args.confirm == CONFIRM, "OWNER_CONFIRMATION_REQUIRED")
        run(args.apply)
        return 0
    except Blocked as exc:
        print("GATE_UPGRADE=BLOCKED_" + str(exc))
        return 2
    except Exception:
        print("GATE_UPGRADE=BLOCKED_HOST_IO_OR_LOCK")
        return 2
    finally:
        print("RELEASE_SWITCH_REQUESTED=NO")
        print("APPROVAL_WRITE_REQUESTED=NO")


if __name__ == "__main__":
    raise SystemExit(main())
