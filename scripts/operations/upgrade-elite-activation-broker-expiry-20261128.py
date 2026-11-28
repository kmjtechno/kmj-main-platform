#!/usr/bin/env python3
"""Owner-only pinned upgrade of the existing Elite activation broker; no deployment."""
import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import socket
import stat
import subprocess
import tempfile
import urllib.request

SOURCE = "b0e4dfab4d11519d3788633e6be1c1c128354f46"
BASE = "https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/" + SOURCE + "/"
SERVICE = "kmj-elite-owner-activation-broker.service"
TIMER = "kmj-elite-owner-activation-broker.timer"
TARGETS = (
    ("scripts/operations/elite_owner_activation_broker.py",
     Path("/opt/kmj-main-platform-activation/elite_owner_activation_broker.py"),
     0o500, "19bb42da90e9e9c1c69781f616ae77fcc8b1c542", "7bed95c4d7d28f5a7580e8fef68d137ddfbda137"),
    ("infra/server/systemd/" + SERVICE, Path("/etc/systemd/system") / SERVICE,
     0o644, "a3c9ab93b299f955459c1a236656b785fd465721", "aabead68d757165140e7503646bd49b3df65de8f"),
    ("infra/server/systemd/" + TIMER, Path("/etc/systemd/system") / TIMER,
     0o644, "671814ae16d99391890f512b206b7ed8959779d0", "671814ae16d99391890f512b206b7ed8959779d0"),
)
INBOX = Path("/home/kmjprod/shared/storage/app/private/ops")
INTENTS = tuple(INBOX / name for name in ("production-activation-request.json",
                "release-admission-request.json", "release-prepare-request.json"))
CONFIRM = "OWNER_APPROVES_EXPIRED_ACTIVATION_BROKER_UPGRADE"
LOCK = Path("/run/lock/kmj-activation-broker-upgrade.lock")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "HOME": "/root"}


def require(ok, code):
    if not ok:
        raise ValueError(code)


def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def protected_dir(path):
    for parent in (path, *path.parents):
        s = parent.lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
                "BLOCKED_ROOT_PARENT")


def read_file(path, mode):
    protected_dir(path.parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        s = os.fstat(handle.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1
                and stat.S_IMODE(s.st_mode) == mode and 0 < s.st_size <= 30000,
                "BLOCKED_INSTALLED_IDENTITY")
        raw = handle.read(30001)
        a = os.fstat(handle.fileno())
        require(len(raw) == s.st_size and (s.st_size, s.st_mtime_ns, s.st_ctime_ns) ==
                (a.st_size, a.st_mtime_ns, a.st_ctime_ns), "BLOCKED_READ_RACE")
        return raw


def fetch(source, pin):
    with urllib.request.urlopen(BASE + source, timeout=30) as response:
        raw = response.read(30001)
    require(len(raw) <= 30000 and blob(raw) == pin, "BLOCKED_SOURCE_PIN")
    if source.endswith(".py"):
        compile(raw, source, "exec")
    return raw


def ctl(*args):
    result = subprocess.run(["/usr/bin/systemctl", *args], env=ENV,
                            capture_output=True, text=True, timeout=45, check=False)
    require(result.returncode == 0, "BLOCKED_SYSTEMD")
    return result.stdout


def unit_state(unit, expected):
    fields = dict(line.split("=", 1) for line in ctl(
        "show", unit, "-p", "LoadState", "-p", "ActiveState",
        "-p", "FragmentPath", "-p", "DropInPaths", "-p", "NeedDaemonReload"
    ).splitlines() if "=" in line)
    require(fields.get("LoadState") == "loaded" and fields.get("FragmentPath") == str(expected)
            and fields.get("DropInPaths") == "" and fields.get("NeedDaemonReload") == "no",
            "BLOCKED_UNIT_IDENTITY")
    return fields.get("ActiveState")


def quiet():
    require(unit_state(SERVICE, TARGETS[1][1]) in ("inactive", "failed"),
            "BLOCKED_BROKER_RUNNING")
    require(not any(os.path.lexists(p) for p in INTENTS), "BLOCKED_PENDING_INTENT")


def replace(path, mode, raw):
    protected_dir(path.parent)
    fd, name = tempfile.mkstemp(prefix=".kmj-activation-upgrade-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        dfd = os.open(path.parent, os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.lexists(name):
            os.unlink(name)


def installed():
    raws = tuple(read_file(path, mode) for _, path, mode, _, _ in TARGETS)
    pins = tuple(map(blob, raws))
    old = tuple(x[3] for x in TARGETS)
    new = tuple(x[4] for x in TARGETS)
    require(pins in (old, new), "BLOCKED_UNKNOWN_OR_MIXED_INSTALL")
    return raws, pins == new


def upgrade(apply):
    require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite",
            "BLOCKED_HOST")
    protected_dir(Path("/root"))
    # /run/lock can be world-writable on Ubuntu; the file itself is opened no-follow
    # and must be a private root-owned single-link regular inode.
    fd = os.open(LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, "r+b") as lock:
        s = os.fstat(lock.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1
                and stat.S_IMODE(s.st_mode) == 0o600, "BLOCKED_LOCK")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        old, already = installed()
        new = tuple(fetch(source, pin) for source, _, _, _, pin in TARGETS)
        quiet()
        state = unit_state(TIMER, TARGETS[2][1])
        require(state in ("active", "inactive"), "BLOCKED_TIMER_STATE")
        if not apply or already:
            print("ACTIVATION_BROKER_UPGRADE=" + ("ALREADY_PINNED" if already else "INSPECT_PASS"))
            return
        backup = Path(tempfile.mkdtemp(prefix="kmj-activation-broker-backup-", dir="/root"))
        for i, raw in enumerate(old):
            replace(backup / ("original-" + str(i)), 0o400, raw)
        print("INSTALL_BACKUP=" + str(backup))
        changed = []
        paused = False
        try:
            if state == "active":
                ctl("stop", TIMER)
                paused = True
            require(unit_state(TIMER, TARGETS[2][1]) == "inactive", "BLOCKED_TIMER_NOT_PAUSED")
            quiet()
            for i, (_, path, mode, _, _) in enumerate(TARGETS[:2]):
                require(read_file(path, mode) == old[i], "BLOCKED_INSTALL_DRIFT")
                changed.append(i)
                replace(path, mode, new[i])
                require(read_file(path, mode) == new[i], "BLOCKED_READBACK")
            ctl("daemon-reload")
            require(installed()[1], "BLOCKED_READBACK")
            quiet()
            require(unit_state(TIMER, TARGETS[2][1]) == "inactive", "BLOCKED_TIMER_DRIFT")
        except BaseException:
            for i in reversed(changed):
                _, path, mode, _, _ = TARGETS[i]
                replace(path, mode, old[i])
                require(read_file(path, mode) == old[i], "BLOCKED_ROLLBACK_READBACK")
            if changed:
                ctl("daemon-reload")
            print("ACTIVATION_BROKER_UPGRADE=ROLLBACK_COMPLETE")
            # Never restart a timer on a failed upgrade; surface pause explicitly.
            if paused:
                print("BROKER_TIMER=PAUSED_OWNER_REVIEW_REQUIRED")
            raise
        if paused:
            # A timer restart could run a newly submitted intent. Leave it paused
            # if one appeared; never discard an intent or start the release unit.
            quiet()
            ctl("start", TIMER)
            require(unit_state(TIMER, TARGETS[2][1]) == "active", "BLOCKED_TIMER_RESTORE")
        print("ACTIVATION_BROKER_UPGRADE=PASS_PINNED")
        print("BROKER_TIMER=" + ("RESTORED_ACTIVE" if paused else "PRESERVED_INACTIVE"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect", action="store_true")
    group.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    try:
        require(not args.apply or args.confirm == CONFIRM, "BLOCKED_OWNER_CONFIRMATION")
        upgrade(args.apply)
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        code = str(exc) if str(exc).startswith("BLOCKED_") else type(exc).__name__
        print("ACTIVATION_BROKER_UPGRADE=BLOCKED:" + code)
        return 2
    finally:
        print("PRODUCTION_UNIT_DIRECT_START=NO APPROVAL_UPDATED=NO ADMISSION_WRITTEN=NO")


if __name__ == "__main__":
    raise SystemExit(main())
