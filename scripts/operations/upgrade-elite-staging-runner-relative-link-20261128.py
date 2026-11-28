#!/usr/bin/env python3
"""Owner-only, pinned staging runner replacement. Never writes approval or starts a unit."""
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

SOURCE = "eb8e6c490e8f3ec837593141e8459e28cac4b3c9"
SOURCE_PATH = "deploy/staging/kmj-main-platform-staging-deploy.sh"
OLD = "39fd993d4bc2cd4427fc6d460073204a7e1f82e3"
NEW = "2fa8ef2631f48b4fd902e644cd2f7948615ffc55"
UNIT_PIN = "07d77b4e2ec9b2e3cd73d4a8aa4c4786e5927eb1"
RUNNER = Path("/usr/local/libexec/kmj-codebridge/kmj-main-platform-staging-deploy.sh")
UNIT = Path("/etc/systemd/system/kmj-main-platform-staging-deploy.service")
SERVICE = UNIT.name
ENV = {"PATH": "/usr/bin:/usr/sbin:/bin:/sbin", "LC_ALL": "C", "HOME": "/root"}


def check(ok, code):
    if not ok:
        raise ValueError(code)


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def protected(path):
    for parent in path.parents:
        s = parent.lstat()
        check(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
              "PARENT_IDENTITY")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        s = os.fstat(handle.fileno())
        check(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1
              and not s.st_mode & 0o022 and 0 < s.st_size <= 100000, "FILE_IDENTITY")
        raw = handle.read(100001)
        a = os.fstat(handle.fileno())
        check(len(raw) == s.st_size and (s.st_size, s.st_mtime_ns, s.st_ctime_ns) ==
              (a.st_size, a.st_mtime_ns, a.st_ctime_ns), "READ_RACE")
        return raw, stat.S_IMODE(s.st_mode), s.st_gid


def quiet():
    result = subprocess.run(["/usr/bin/systemctl", "show", SERVICE, "-p", "LoadState",
                             "-p", "ActiveState", "-p", "FragmentPath", "-p", "DropInPaths",
                             "-p", "NeedDaemonReload"], env=ENV, capture_output=True,
                            text=True, timeout=20, check=True)
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    check(fields.get("LoadState") == "loaded" and fields.get("ActiveState") in ("inactive", "failed")
          and fields.get("FragmentPath") == str(UNIT) and fields.get("DropInPaths") == ""
          and fields.get("NeedDaemonReload") == "no", "UNIT_NOT_QUIESCENT")
    check(blob(protected(UNIT)[0]) == UNIT_PIN, "UNIT_PIN")


def replace(path, raw, mode, gid):
    fd, name = tempfile.mkstemp(prefix=".kmj-staging-runner-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            os.fchown(f.fileno(), 0, gid)
            os.fchmod(f.fileno(), mode)
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.lexists(name):
            os.unlink(name)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--inspect", action="store_true")
    g.add_argument("--apply", action="store_true")
    p.add_argument("--confirm", default="")
    a = p.parse_args()
    try:
        check(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite", "HOST")
        check(not a.apply or a.confirm == "OWNER_APPROVES_STAGING_RUNNER_RELATIVE_LINK_UPGRADE",
              "CONFIRMATION")
        # Use a root-only persistent lock, not the staging RuntimeDirectory
        # (which systemd creates only while the existing unit runs).
        root = Path("/root")
        s = root.lstat()
        check(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o077, "ROOT_DIR")
        lock = os.open(root / ".kmj-staging-runner-upgrade.lock",
                       os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600)
        with os.fdopen(lock, "r+b") as f:
            s = os.fstat(f.fileno())
            check(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1
                  and stat.S_IMODE(s.st_mode) == 0o600, "LOCK_IDENTITY")
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            quiet()
            old, mode, gid = protected(RUNNER)
            check(blob(old) in (OLD, NEW), "INSTALLED_UNKNOWN_PIN")
            check(mode & 0o100 and not mode & 0o7022, "RUNNER_MODE")
            with urllib.request.urlopen("https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/"
                                        + SOURCE + "/" + SOURCE_PATH, timeout=30) as response:
                new = response.read(100001)
            check(len(new) <= 100000 and blob(new) == NEW, "SOURCE_PIN")
            subprocess.run(["/bin/bash", "-n"], input=new, env=ENV, check=True,
                           capture_output=True, timeout=15)
            if blob(old) == NEW:
                print("STAGING_RUNNER_UPGRADE=ALREADY_PINNED")
                return 0
            if a.inspect:
                print("STAGING_RUNNER_UPGRADE=INSPECT_PASS")
                return 0
            backup = Path(tempfile.mkdtemp(prefix="kmj-stage-runner-backup-", dir=root))
            replace(backup / "original", old, 0o400, 0)
            print("INSTALL_BACKUP=" + str(backup))
            quiet()
            check(protected(RUNNER) == (old, mode, gid), "INSTALL_DRIFT")
            try:
                replace(RUNNER, new, mode, gid)
                check(protected(RUNNER) == (new, mode, gid), "READBACK")
                quiet()
            except BaseException:
                replace(RUNNER, old, mode, gid)
                check(protected(RUNNER) == (old, mode, gid), "ROLLBACK_READBACK")
                print("STAGING_RUNNER_UPGRADE=ROLLBACK_COMPLETE")
                raise
            print("STAGING_RUNNER_UPGRADE=PASS_PINNED")
            return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print("STAGING_RUNNER_UPGRADE=BLOCKED:" +
              (str(exc) if isinstance(exc, ValueError) else type(exc).__name__))
        return 2
    finally:
        print("PRODUCTION_POINTER_CHANGED=NO STAGING_POINTER_CHANGED=NO APPROVAL_UPDATED=NO UNIT_STARTED=NO")


if __name__ == "__main__":
    raise SystemExit(main())
