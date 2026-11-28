#!/usr/bin/env python3
"""Owner-only upgrade of both root-installed gate copies; never deploys."""
import argparse
import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path
import socket
import stat
import tempfile
import urllib.request

SOURCE = "47a23e5cedbc38def7499a7e2c1fee14c00008bb"
OLD = "b43621f9ccfd8a210659bfe9441026951aa7f485"
NEW = "2da9259a7823117400ce477dc9c2361298bad31b"
URL = "https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/" + SOURCE + "/scripts/operations/main_platform_autopublish_gate.py"
GATES = (
    Path("/opt/kmj-main-platform-autopublish/main_platform_autopublish_gate.py"),
    Path("/opt/kmj-main-platform-release-evidence/main_platform_autopublish_gate.py"),
)
LOCK = Path("/run/lock/kmj-main-platform-autopublish.lock")
CONFIRM = "OWNER_APPROVES_LIVE_HEALTH_GATE_UPGRADE"

def require(ok, code):
    if not ok:
        raise ValueError(code)

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def protected_dir(path):
    for parent in (path, *path.parents):
        s = parent.lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022, "BLOCKED_PARENT")

def read_gate(path):
    protected_dir(path.parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and before.st_nlink == 1
                and stat.S_IMODE(before.st_mode) == 0o500 and 0 < before.st_size <= 30000, "BLOCKED_GATE_IDENTITY")
        data = handle.read(30001)
        after = os.fstat(handle.fileno())
        require(len(data) == before.st_size and (before.st_size, before.st_mtime_ns) ==
                (after.st_size, after.st_mtime_ns), "BLOCKED_GATE_RACE")
    require(blob(data) in (OLD, NEW), "BLOCKED_GATE_UNKNOWN")
    return data

def fetch():
    with urllib.request.urlopen(URL, timeout=30) as response:
        data = response.read(30001)
    require(len(data) <= 30000 and blob(data) == NEW, "BLOCKED_SOURCE_PIN")
    compile(data, URL, "exec")
    return data

def load_gate():
    spec = importlib.util.spec_from_file_location("fixed_gate", GATES[0])
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    return gate

def verify_live(gate):
    approval = gate.protected_json(gate.APPROVAL)
    require(isinstance(approval, dict) and set(approval) == gate.APPROVAL_KEYS, "BLOCKED_APPROVAL")
    target = approval.get("approvedSha")
    require(isinstance(target, str) and gate.SHA_RE.fullmatch(target) is not None, "BLOCKED_SHA")
    current = gate.live_release()
    require(current == "platform-" + target[:12], "BLOCKED_NOT_ALREADY_LIVE")
    admission = gate.protected_json(gate.ADMISSION_DIR / ("main-platform-autopublish-" + target[:12] + ".json"))
    # Validate historical admission with its own exact staging SHA; this is a
    # read-only health proof, not a prospective release authorization.
    require(gate.decision(approval, admission, current, target, gate.candidate_sha(target)) == "ALREADY_LIVE",
            "BLOCKED_HISTORICAL_ADMISSION")
    require(gate.exact_https_sha_ok(gate.public_https_response(), target), "BLOCKED_PUBLIC_SHA")
    return approval, admission, current

def replace(path, data):
    protected_dir(path.parent)
    fd, tmp = tempfile.mkstemp(prefix=".live-health-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), 0o500)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)

def run(apply):
    require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite", "BLOCKED_HOST")
    new = fetch()
    fd = os.open(LOCK, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "r+b") as lock:
        info = os.fstat(lock.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o600, "BLOCKED_LOCK")
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        old = tuple(read_gate(path) for path in GATES)
        require(old[0] == old[1], "BLOCKED_INSTALLED_COPY_DRIFT")
        witness = verify_live(load_gate())
        if not apply or old[0] == new:
            print("LIVE_HEALTH_UPGRADE=" + ("ALREADY_PINNED" if old[0] == new else "INSPECT_PASS"))
            return
        protected_dir(Path("/root"))
        backup = Path(tempfile.mkdtemp(prefix="kmj-live-health-gate-backup-", dir="/root"))
        for i, data in enumerate(old):
            p = backup / ("gate-" + str(i) + ".py")
            p.write_bytes(data)
            p.chmod(0o400)
        changed = []
        try:
            require(verify_live(load_gate()) == witness, "BLOCKED_LIVE_DRIFT")
            for i, path in enumerate(GATES):
                require(read_gate(path) == old[i], "BLOCKED_GATE_CHANGED")
                changed.append(i)
                replace(path, new)
                require(read_gate(path) == new, "BLOCKED_READBACK")
            require(verify_live(load_gate()) == witness, "BLOCKED_LIVE_DRIFT")
        except BaseException:
            for i in reversed(changed):
                replace(GATES[i], old[i])
                require(read_gate(GATES[i]) == old[i], "BLOCKED_ROLLBACK_READBACK")
            raise
        print("LIVE_HEALTH_UPGRADE=PASS_BOTH_COPIES")
        print("INSTALL_BACKUP=" + str(backup))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    try:
        require(not args.apply or args.confirm == CONFIRM, "BLOCKED_OWNER_CONFIRMATION")
        run(args.apply)
        return 0
    except (ValueError, OSError, ImportError, AttributeError) as exc:
        print("LIVE_HEALTH_UPGRADE=BLOCKED:" + (str(exc) if str(exc).startswith("BLOCKED_") else type(exc).__name__))
        return 2
    finally:
        print("PRODUCTION_ACTIVATION=NOT_ATTEMPTED APPROVAL_UPDATED=NO ADMISSION_WRITTEN=NO")

if __name__ == "__main__":
    raise SystemExit(main())
