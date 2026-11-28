#!/usr/bin/env python3
"""Owner-only upgrade of the four rehearsal helpers, preserving release identity.

No release pointer, approval, receipt, database, service or timer is modified.
--inspect verifies installed artifacts and immutable source; --apply requires
explicit owner confirmation. Review of the exact source remains a prerequisite.
"""
import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import socket
import stat
import subprocess
import tempfile

SOURCE = "5e356f95fc742812f4cad5746a940bc4e9fcb93b"
URL = "https://github.com/kmjtechno/kmj-main-platform.git"
DEST = Path("/opt/kmj-main-platform-release-evidence")
PINS = {
    "elite_prepare_rehearsal.py": ("81f0b8cf48ffc815ffca66daded8c936d7e27ff8", "dcc69911bab7a836c09ce5d5e292f9d238d5edf4"),
    "elite_collect_rollback_rehearsal_receipt.py": ("56ca8f9c41a34dd26185a5232ae66db5ce7192b1", "1f94752b8b7cd980a7b95ecda28eff084fee7b19"),
    "elite_collect_all_receipts.py": ("896d3c8c6b4557e38a4df10ca8ab28d2fe4ac281", "dc98197d8bf02be6342c621e595de788e2ca7fed"),
    "rehearse-app-http-db-rollback-20261029.py": ("8a81234e055ab0ac2b1efac73fa33864d911b16f", "859167bc6d9c712cc724e2de42ef8a718a4af87f"),
}
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/root", "LANG": "C",
       "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
       "GIT_TERMINAL_PROMPT": "0", "GIT_NO_REPLACE_OBJECTS": "1"}


def require(ok, code):
    if not ok:
        raise ValueError(code)


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def protected(path):
    return all(stat.S_ISDIR(p.lstat().st_mode) and p.lstat().st_uid == 0
               and not p.lstat().st_mode & 0o022 for p in (path, *path.parents))


def read_file(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as stream:
        s = os.fstat(stream.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1
                and stat.S_IMODE(s.st_mode) == 0o500 and 0 < s.st_size < 65536,
                "BLOCKED_INSTALLED_METADATA")
        data = stream.read(65536)
        require(len(data) == s.st_size, "BLOCKED_INSTALLED_SIZE")
        return data


def git(args):
    r = subprocess.run(["/usr/bin/git", *args], cwd="/", env=ENV,
                       capture_output=True, timeout=120, check=False)
    require(r.returncode == 0 and len(r.stdout) < 100000, "BLOCKED_GIT")
    return r.stdout


def get_source():
    with tempfile.TemporaryDirectory(prefix="kmj-rehearsal-source-", dir="/root") as temp:
        git(["init", "--bare", "--quiet", temp])
        git(["-C", temp, "-c", "credential.helper=", "-c", "core.hooksPath=/dev/null",
             "fetch", "--no-tags", "--depth=1", URL, SOURCE])
        require(git(["-C", temp, "rev-parse", "FETCH_HEAD^{commit}"]).decode().strip() == SOURCE,
                "BLOCKED_SOURCE_COMMIT")
        result = {}
        for name, (_, new) in PINS.items():
            data = git(["-C", temp, "show", SOURCE + ":scripts/operations/" + name])
            require(blob(data) == new, "BLOCKED_SOURCE_BLOB")
            compile(data, name, "exec")
            result[name] = data
        return result


def classify(dest=DEST):
    data = {name: read_file(dest / name) for name in PINS}
    current = {name: blob(value) for name, value in data.items()}
    if all(current[n] == PINS[n][0] for n in PINS):
        return "OLD", data
    if all(current[n] == PINS[n][1] for n in PINS):
        return "NEW", data
    raise ValueError("BLOCKED_MIXED_OR_UNKNOWN_INSTALLED_PINS")


def replace(path, data):
    fd, tmp = tempfile.mkstemp(prefix=".rehearsal-upgrade-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), 0o500)
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def apply(dest, old, new, backup):
    backup.mkdir(mode=0o700)
    for name, data in old.items():
        replace(backup / name, data)
    fsync_dir(backup)
    fsync_dir(backup.parent)
    changed = []
    try:
        for name in PINS:
            require(blob(read_file(dest / name)) == PINS[name][0], "BLOCKED_DRIFT")
            replace(dest / name, new[name])
            changed.append(name)
        fsync_dir(dest)
        require(classify(dest)[0] == "NEW", "BLOCKED_READBACK")
    except BaseException:
        for name in reversed(changed):
            replace(dest / name, old[name])
        fsync_dir(dest)
        raise


def idle_check():
    require(not os.path.lexists("/etc/kmj-codebridge/release-rehearsal.json"),
            "BLOCKED_EXISTING_REHEARSAL_CONFIG")
    for p in Path("/proc").iterdir():
        if p.name.isdigit() and p.name != str(os.getpid()):
            try:
                argv = (p / "cmdline").read_bytes().split(b"\0")
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            require(not any(Path(os.fsdecode(a)).name in PINS for a in argv if a),
                    "BLOCKED_ACTIVE_REHEARSAL")


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    try:
        require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite",
                "BLOCKED_HOST_ROOT")
        require(protected(DEST) and protected(Path("/root")), "BLOCKED_PARENT")
        state, old = classify()
        new = get_source()
        print("REHEARSAL_TOOLKIT_INSTALLED=" + state + " SOURCE_PINS=PASS")
        if args.apply and state == "OLD":
            require(args.confirm == "OWNER_APPROVES_REVIEWED_REHEARSAL_TOOLKIT",
                    "BLOCKED_OWNER_CONFIRMATION")
            lockfd = os.open(DEST / ".rehearsal-toolkit-upgrade.lock",
                             os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            try:
                fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                require(classify()[0] == "OLD", "BLOCKED_DRIFT")
                idle_check()
                backup = Path(tempfile.mkdtemp(prefix="kmj-rehearsal-backup-", dir="/root")) / "original"
                apply(DEST, old, new, backup)
                print("REHEARSAL_TOOLKIT_UPGRADE=PASS BACKUP=" + str(backup))
            finally:
                os.close(lockfd)
        elif args.apply:
            print("REHEARSAL_TOOLKIT_UPGRADE=ALREADY_CURRENT")
        else:
            print("REHEARSAL_TOOLKIT_UPGRADE=INSPECT_ONLY")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print("REHEARSAL_TOOLKIT_UPGRADE=BLOCKED " + type(exc).__name__ + ":" + str(exc)[:100])
        return 1
    print("PRODUCTION_RELEASE=UNCHANGED APPROVAL_UPDATED=NO RECEIPT_WRITTEN=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
