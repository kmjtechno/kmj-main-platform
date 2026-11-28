"""Root-only map refresh for an already protected candidate; never deploys.

Run from the reviewed Elite prepare lane, not the read-only autopublish
sandbox. Existing backend header configuration is a prerequisite.
"""
import fcntl
import importlib.util
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile

from production_release_sha_map import parse_existing, plan

MAP = Path("/etc/nginx/conf.d/kmj-production-release-sha.conf")
GATE = Path("/opt/kmj-main-platform-autopublish/main_platform_autopublish_gate.py")
NGINX = "/usr/sbin/nginx"

def protected(path):
    for p in path.parents:
        s = p.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022:
            raise ValueError("BLOCKED_PARENT")
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or s.st_nlink != 1 or s.st_mode & 0o022:
        raise ValueError("BLOCKED_FILE")
    return s

def read_map(path):
    before = protected(path)
    if before.st_size > 1024:
        raise ValueError("BLOCKED_MAP_SIZE")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as handle:
        current = os.fstat(handle.fileno())
        data = handle.read(1025)
        if (current.st_dev, current.st_ino, current.st_mtime_ns, current.st_size) != (
                before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size):
            raise ValueError("BLOCKED_MAP_RACE")
        if len(data) != before.st_size:
            raise ValueError("BLOCKED_MAP_SIZE")
    return data.decode("ascii"), stat.S_IMODE(before.st_mode)

def replace(path, content, mode):
    fd, name = tempfile.mkstemp(prefix=".kmj-map-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(content.encode("ascii"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        parent = os.open(path.parent, os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.lexists(name):
            os.unlink(name)

def command(*args):
    subprocess.run(args, cwd="/", env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C"},
                   check=True, timeout=45)

def transaction(old, new, unchanged, write, validate, reload, witness):
    """Testable bounded transaction; never reports PASS on failed rollback."""
    if not unchanged() or not witness():
        raise ValueError("BLOCKED_PREVIOUS_LIVE_WITNESS")
    validate()
    if old == new:
        return "MAP_ALREADY_READY"
    try:
        write(new)
        validate()
        reload()
        if not unchanged() or not witness():
            raise ValueError("BLOCKED_POST_MAP_WITNESS")
    except BaseException:
        write(old)
        validate()
        reload()
        if not unchanged() or not witness():
            raise RuntimeError("BLOCKED_MAP_ROLLBACK_WITNESS")
        raise
    return "MAP_REFRESHED"

def main():
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        raise ValueError("BLOCKED_HOST")
    protected(GATE)
    spec = importlib.util.spec_from_file_location("installed_gate", GATE)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    fd = os.open(gate.LOCK, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or s.st_nlink != 1 or stat.S_IMODE(s.st_mode) != 0o600:
            raise ValueError("BLOCKED_LOCK")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        approval = gate.protected_json(gate.APPROVAL)
        if not isinstance(approval, dict) or set(approval) != gate.APPROVAL_KEYS:
            raise ValueError("BLOCKED_APPROVAL")
        target = approval.get("approvedSha")
        if not isinstance(target, str) or not gate.SHA_RE.fullmatch(target):
            raise ValueError("BLOCKED_SHA")
        live = gate.live_release()
        if (approval.get("expectedCurrentRelease") != live
                or approval.get("backupVerified") is not True
                or approval.get("rollbackVerified") is not True
                or gate.remote_sha() != target):
            raise ValueError("BLOCKED_APPROVAL_IDENTITY")
        old, mode = read_map(MAP)
        current = [s for s in parse_existing(old) if live == "platform-" + s[:12]]
        if len(current) != 1:
            raise ValueError("BLOCKED_CURRENT_MAP")
        new = plan(old, current[0], target, gate.candidate_sha)
        def witness():
            return gate.exact_https_sha_ok(gate.public_https_response(), current[0])
        if sys.argv == [sys.argv[0], "--inspect"]:
            if not witness():
                raise ValueError("BLOCKED_PREVIOUS_LIVE_WITNESS")
            print("MAP_PREFLIGHT=PASS")
            return
        if sys.argv != [sys.argv[0], "--apply"]:
            raise ValueError("BLOCKED_MODE")
        backup = Path(tempfile.mkdtemp(prefix="kmj-release-map-", dir="/root"))
        (backup / "previous.conf").write_text(old, encoding="ascii")
        print("MAP_BACKUP=" + str(backup))
        result = transaction(old, new, lambda: gate.live_release() == live,
                             lambda data: replace(MAP, data, mode),
                             lambda: command(NGINX, "-t"),
                             lambda: command("/usr/bin/systemctl", "reload", "nginx"),
                             witness)
        print("PRODUCTION_SHA_MAP=" + result)
        print("PRODUCTION_ACTIVATION=NOT_ATTEMPTED")
    finally:
        os.close(fd)

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("PRODUCTION_SHA_MAP=BLOCKED:" + type(exc).__name__)
        raise SystemExit(2)
