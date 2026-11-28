#!/usr/bin/env python3
"""Opt-in, immutable-source installation of the Elite SHA-map preparation lane.

Stage installs only the two new helpers and fixed unit. Enable separately,
after a real already-live service witness, with no pending owner intent.
Never starts production, changes approval/admission, or enables a timer.
"""
import argparse
import hashlib
import fcntl
import os
from pathlib import Path
import socket
import stat
import subprocess
import tempfile
import urllib.request

SOURCE = "0ea9f019fcfeeeb64bad9ad6714e650a8947264b"
BASE = "https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/" + SOURCE + "/"
DEST = Path("/opt/kmj-main-platform-release-evidence")
UNIT_DIR = Path("/etc/systemd/system")
UNIT = "kmj-elite-production-sha-map.service"
QUALIFICATION = Path("/run/kmj-production-sha-map-qualification")
BROKER = "elite_admission_broker.py"
DROP = "kmj-elite-release-admission-broker.service.d/20-production-sha-map.conf"
OLD_BROKER = "71f4eae8588441f08dd6f17a84d3c512226d7df5"
APPROVAL = Path("/etc/kmj-codebridge/main-platform-production-release.json")
INTENTS = (
    Path("/home/kmjprod/shared/storage/app/private/ops/release-admission-request.json"),
    Path("/home/kmjprod/shared/storage/app/private/ops/production-activation-request.json"),
)
STAGE = (
    ("scripts/operations/production_release_sha_map.py", DEST / "production_release_sha_map.py", "7e04e9eb8a4aeeed5067518d3e5dc4b2e29df4c2", 0o500),
    ("scripts/operations/refresh_production_release_sha_map.py", DEST / "refresh_production_release_sha_map.py", "989c55dc74dc4b1e8f0535561ac358e62d22adb3", 0o500),
    ("infra/server/systemd/" + UNIT, UNIT_DIR / UNIT, "fdc0d295f353bae8864b5d617d571f1a7d3e7d29", 0o644),
)
ENABLE = (
    ("scripts/operations/" + BROKER, DEST / BROKER, "d421469831ccb051796e932742107066e02a47ab", 0o500),
    ("infra/server/systemd/" + DROP, UNIT_DIR / DROP, "2fdb6acd0bd9fe0f2c3431efe8a9f443ff0c23dc", 0o644),
)

def require(ok, code):
    if not ok:
        raise ValueError(code)

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def protected_dir(path):
    for p in (path, *path.parents):
        s = p.lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022, "BLOCKED_DIRECTORY")

def read_existing(path, mode):
    protected_dir(path.parent)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as handle:
        s = os.fstat(handle.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1
                and stat.S_IMODE(s.st_mode) == mode and s.st_size <= 60000, "BLOCKED_INSTALLED_IDENTITY")
        data = handle.read(60001)
        require(len(data) == s.st_size and os.fstat(handle.fileno()).st_mtime_ns == s.st_mtime_ns,
                "BLOCKED_INSTALLED_RACE")
        return data

def fetch(entry):
    source, _, pin, _ = entry
    with urllib.request.urlopen(BASE + source, timeout=25) as response:
        data = response.read(60001)
    require(len(data) <= 60000 and blob(data) == pin, "BLOCKED_SOURCE_PIN")
    if source.endswith(".py"):
        compile(data, source, "exec")
    return data

def replace(path, data, mode):
    protected_dir(path.parent)
    fd, tmp = tempfile.mkstemp(prefix=".kmj-map-install-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), mode)
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

def fixed(*args):
    subprocess.run(args, cwd="/", env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C"},
                   check=True, timeout=260)

def guard_live():
    import importlib.util
    gate_path = Path("/opt/kmj-main-platform-autopublish/main_platform_autopublish_gate.py")
    require(read_existing(gate_path, 0o500) is not None, "BLOCKED_GATE")
    spec = importlib.util.spec_from_file_location("trusted_gate", gate_path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    approval = gate.protected_json(APPROVAL)
    require(isinstance(approval, dict) and set(approval) == gate.APPROVAL_KEYS, "BLOCKED_APPROVAL")
    target = approval.get("approvedSha")
    require(isinstance(target, str) and gate.SHA_RE.fullmatch(target) is not None
            and approval.get("backupVerified") is True and approval.get("rollbackVerified") is True
            and gate.live_release() == "platform-" + target[:12], "BLOCKED_NOT_ALREADY_LIVE")
    require(not any(os.path.lexists(p) for p in INTENTS), "BLOCKED_PENDING_INTENT")
    require(gate.candidate_sha(target) == target and gate.exact_https_sha_ok(gate.public_https_response(), target),
            "BLOCKED_LIVE_WITNESS")
    return target, approval

def apply(entries, live_snapshot):
    prepared = []
    for entry in entries:
        _, path, pin, mode = entry
        data = fetch(entry)
        old = read_existing(path, mode)
        if old is not None:
            allowed = {pin, OLD_BROKER} if path == DEST / BROKER else {pin}
            require(blob(old) in allowed, "BLOCKED_UNKNOWN_INSTALLED_VERSION")
        elif path == DEST / BROKER:
            raise ValueError("BLOCKED_EXISTING_BROKER_MISSING")
        prepared.append((path, data, old, mode))
    require(guard_live() == live_snapshot, "BLOCKED_LIVE_DRIFT")
    backup = Path(tempfile.mkdtemp(prefix="kmj-map-install-backup-", dir="/root"))
    changed = []
    try:
        for i, (path, data, old, mode) in enumerate(prepared):
            require(read_existing(path, mode) == old, "BLOCKED_INSTALL_RACE")
            if old == data:
                continue
            if old is not None:
                copy = backup / (str(i) + "-" + path.name)
                copy.write_bytes(old)
                copy.chmod(0o400)
            changed.append((path, old, mode))
            replace(path, data, mode)
            require(read_existing(path, mode) == data, "BLOCKED_INSTALL_READBACK")
        fixed("/usr/bin/systemd-analyze", "verify", str(UNIT_DIR / UNIT))
        fixed("/usr/bin/systemctl", "daemon-reload")
        require(guard_live() == live_snapshot, "BLOCKED_LIVE_DRIFT")
    except BaseException:
        for path, old, mode in reversed(changed):
            if old is None:
                path.unlink(missing_ok=True)
            else:
                replace(path, old, mode)
        fixed("/usr/bin/systemctl", "daemon-reload")
        raise
    print("INSTALL_BACKUP=" + str(backup))

def unit_property(name):
    return subprocess.run(
        ["/usr/bin/systemctl", "show", UNIT, "-p", name, "--value"],
        cwd="/", env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C"},
        check=True, capture_output=True, text=True, timeout=15
    ).stdout.strip()

def qualify_service(snapshot):
    protected_dir(QUALIFICATION.parent)
    require(guard_live() == snapshot, "BLOCKED_LIVE_DRIFT")
    before = int(unit_property("ExecMainStartTimestampMonotonic") or "0")
    fd = os.open(QUALIFICATION, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        os.close(fd)
        fixed("/usr/bin/systemctl", "start", UNIT)
        after = int(unit_property("ExecMainStartTimestampMonotonic") or "0")
        require(after > before and unit_property("Result") == "success"
                and unit_property("ExecMainStatus") == "0", "BLOCKED_SERVICE_NOT_EXECUTED")
        require(guard_live() == snapshot, "BLOCKED_LIVE_DRIFT")
    finally:
        QUALIFICATION.unlink()
    print("SHA_MAP_SERVICE_WITNESS=PASS")

def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--inspect", action="store_true")
    modes.add_argument("--stage", action="store_true")
    modes.add_argument("--enable-admission-dependency", action="store_true")
    args = parser.parse_args()
    require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite", "BLOCKED_HOST")
    protected_dir(DEST)
    protected_dir(UNIT_DIR)
    protected_dir(Path("/root"))
    snapshot = guard_live()
    if args.inspect:
        for _, path, pin, mode in STAGE + ENABLE:
            if not path.parent.exists():
                data = None
            else:
                data = read_existing(path, mode)
            print(path.name + "=" + ("MISSING" if data is None else "PIN_MATCH" if blob(data) == pin else "OTHER"))
        print("INSTALL_INSPECT=PASS")
    elif args.stage:
        apply(STAGE, snapshot)
        print("SHA_MAP_STAGE=PASS ADMISSION_DEPENDENCY=UNCHANGED")
    else:
        for _, path, pin, mode in STAGE:
            data = read_existing(path, mode)
            require(data is not None and blob(data) == pin, "BLOCKED_STAGE_NOT_PINNED")
        qualify_service(snapshot)
        parent = (UNIT_DIR / DROP).parent
        if not parent.exists():
            parent.mkdir(mode=0o755)
        protected_dir(parent)
        apply(ENABLE, snapshot)
        print("SHA_MAP_DEPENDENCY=INSTALLED")
    print("PRODUCTION_ACTIVATION=NOT_ATTEMPTED APPROVAL_UPDATED=NO ADMISSION_WRITTEN=NO")

def locked_main():
    require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite", "BLOCKED_HOST")
    fd = os.open("/run/lock/kmj-production-sha-map-install.lock",
                 os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o600, "BLOCKED_INSTALL_LOCK")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        main()
    finally:
        os.close(fd)

if __name__ == "__main__":
    try:
        locked_main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        code = str(exc) if isinstance(exc, ValueError) and str(exc).startswith("BLOCKED_") else type(exc).__name__
        print("SHA_MAP_INSTALL=BLOCKED:" + code)
        raise SystemExit(2)
