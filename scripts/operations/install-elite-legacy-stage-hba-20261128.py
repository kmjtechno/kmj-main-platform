#!/usr/bin/env python3
"""Owner-only legacy staging HBA installation, exact plan pins, live proofs, rollback.

Never changes SQL grants, roles, databases, pointers or protected approvals.
Requires the reviewed plan module beside this file in a private root directory.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path
import pwd
import re
import signal
import socket
import stat
import subprocess
import tempfile
import time

PLAN_BLOB = "0d80534470728745a98c2f532c847c18859f49b5"
CONFIRM = "OWNER_APPROVES_EXACT_LEGACY_STAGE_HBA_ONLY"


def require(ok, label):
    if not ok:
        raise ValueError(label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_plan():
    folder = Path(__file__).resolve().parent
    for p in (folder, *folder.parents):
        s = p.lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
                "PLAN_PARENT")
    p = folder / "plan-elite-legacy-stage-hba-20261128.py"
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as f:
        s = os.fstat(f.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1
                and not s.st_mode & 0o022 and 0 < s.st_size <= 65536, "PLAN_METADATA")
        raw = f.read(65537)
    require(len(raw) == s.st_size and hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == PLAN_BLOB, "PLAN_PIN")
    # Execute the same verified bytes, never reopen the source file for import.
    import types
    module = types.ModuleType("reviewed_legacy_hba_plan")
    module.__file__ = str(p)
    exec(compile(raw, str(p), "exec"), module.__dict__)
    return module


def snapshot(plan):
    plan.pointer_guard()
    path = plan.STAGE_TARGET / ".env"
    uid = pwd.getpwnam("kmjstage").pw_uid
    s = path.lstat()
    require(s.st_uid == uid and stat.S_IMODE(s.st_mode) in (0o400, 0o600), "ENV_METADATA")
    raw = plan.read_regular(path, (uid,), 1048576)
    db, role, host, password = plan.identity(raw)
    names = plan.catalog(db, role)
    hba_path, old = plan.hba()
    return raw, db, role, host, password, names, hba_path, old


def own_login(plan, db, role, host, password):
    r = plan.probe(db, role, host, password)
    require(r.returncode == 0 and r.stdout.strip() == (db + ":" + role).encode(),
            "OWN_STAGE_LOGIN")


def listener_evidence(plan):
    # An absent IPv6 listener is not an HBA rejection. Prove its absence
    # separately using the kernel socket inventory and a specific refusal.
    require(plan.pg("SHOW port") == "5432", "PG_PORT")
    config = plan.pg("SHOW listen_addresses")
    require(bool(config) and len(config) <= 1024, "LISTENER_CONFIG")
    def listeners(family):
        r = subprocess.run(["/usr/bin/ss", "-H", "-ltn" + family,
                            "sport", "=", ":5432"],
                           env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
                           capture_output=True, text=True, timeout=10, check=True)
        require(len(r.stdout) <= 16384, "LISTENER_INVENTORY")
        return tuple(sorted(line.strip() for line in r.stdout.splitlines() if line.strip()))
    v4, v6 = listeners("4"), listeners("6")
    require(bool(v4), "IPV4_LISTENER_MISSING")
    def connect_result(family, addr):
        with socket.socket(family, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            return s.connect_ex((addr, 5432))
    require(connect_result(socket.AF_INET, "127.0.0.1") == 0, "IPV4_UNREACHABLE")
    result = connect_result(socket.AF_INET6, "::1")
    if result == 0:
        require(bool(v6), "IPV6_INVENTORY_MISMATCH")
        transports = ("127.0.0.1", "::1", "/var/run/postgresql")
    else:
        import errno
        require(result == errno.ECONNREFUSED and not v6, "IPV6_STATE_UNVERIFIED")
        transports = ("127.0.0.1", "/var/run/postgresql")
    return config, v4, v6, transports


def live_proof(plan, db, role, host, password, names, transports=("127.0.0.1", "::1", "/var/run/postgresql")):
    own_login(plan, db, role, host, password)
    total = 0
    for name in names:
        if name == db:
            continue
        for transport in transports:
            # Never send the real password to a different database.
            require(plan.explicitly_rejected(plan.probe(name, role, transport)),
                    "OTHER_DB_NOT_EXPLICITLY_REJECTED")
            total += 1
    allowed = {host}
    if host == "localhost":
        allowed = {"127.0.0.1", "::1"}
    for transport in transports:
        if transport not in allowed:
            require(plan.explicitly_rejected(plan.probe(db, role, transport)),
                    "OWN_DB_OTHER_TRANSPORT_NOT_REJECTED")
            total += 1
    require(plan.catalog(db, role) == names, "CATALOG_DRIFT")
    return total


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def replace(plan, path, expected, new):
    require(plan.hba() == (path, expected), "HBA_CONTENT_DRIFT")
    metadata = path.lstat()
    require(not os.listxattr(path, follow_symlinks=False), "HBA_EXTENDED_ATTRIBUTES")
    fd, name = tempfile.mkstemp(prefix=".kmj-legacy-stage-hba-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchown(handle.fileno(), metadata.st_uid, metadata.st_gid)
            os.fchmod(handle.fileno(), stat.S_IMODE(metadata.st_mode))
            handle.write(new)
            handle.flush()
            os.fsync(handle.fileno())
        check = path.lstat()
        require((check.st_dev, check.st_ino, check.st_uid, check.st_gid, check.st_mode,
                 check.st_mtime_ns, check.st_ctime_ns) ==
                (metadata.st_dev, metadata.st_ino, metadata.st_uid, metadata.st_gid, metadata.st_mode,
                 metadata.st_mtime_ns, metadata.st_ctime_ns)
                and plan.hba() == (path, expected), "HBA_INODE_DRIFT")
        os.replace(name, path)
        sync_dir(path.parent)
    finally:
        if os.path.lexists(name):
            os.unlink(name)


def reload_config(plan):
    require(plan.pg("SELECT pg_reload_conf()") == "t", "RELOAD_SIGNAL")


def validate_loaded(plan, db, role, host, password, names, transports):
    # pg_reload_conf only acknowledges a signal. Require actual connections.
    for i in range(5):
        try:
            require(plan.pg("SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL") == "0",
                    "HBA_PARSE_ERRORS")
            return live_proof(plan, db, role, host, password, names, transports)
        except ValueError:
            if i == 4:
                raise
            time.sleep(0.5)


def install(plan, original, new, baseline_pin, proposal_pin, root=Path("/root")):
    raw, db, role, host, password, names, path, old = original
    require(sha(old) == baseline_pin and sha(new) == proposal_pin, "REVIEWED_PINS_MISMATCH")
    listeners = listener_evidence(plan)
    own_login(plan, db, role, host, password)
    require(snapshot(plan) == original, "PRE_APPLY_DRIFT")
    backup = Path(tempfile.mkdtemp(prefix="kmj-legacy-stage-hba-backup-", dir=root))
    fd = os.open(backup / "pg_hba.conf.original",
                 os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(old)
        handle.flush()
        os.fsync(handle.fileno())
    sync_dir(backup)
    sync_dir(root)
    print("HBA_BACKUP=" + str(backup), flush=True)
    try:
        require(snapshot(plan) == original, "PRE_REPLACE_DRIFT")
        require(listener_evidence(plan) == listeners, "LISTENER_DRIFT")
        replace(plan, path, old, new)
        require(plan.hba() == (path, new), "HBA_WRITE_READBACK")
        require(plan.pg("SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL") == "0",
                "HBA_PARSE_ERRORS")
        reload_config(plan)
        total = validate_loaded(plan, db, role, host, password, names, listeners[-1])
        require(listener_evidence(plan) == listeners, "LISTENER_DRIFT")
        print("IPV6_TRANSPORT=" + ("LIVE_HBA_TESTED" if "::1" in listeners[-1] else "NO_LISTENER_VERIFIED"))
        require(snapshot(plan) == (*original[:-1], new), "POST_APPLY_DRIFT")
        return total
    except BaseException:
        # Never overwrite bytes written by an unrelated concurrent operator.
        current = plan.hba()
        if current == (path, new):
            replace(plan, path, new, old)
            reload_config(plan)
            require(plan.hba() == (path, old), "ROLLBACK_READBACK")
            # Confirm the original stage login works after reload, without
            # asserting that original cross-database isolation was secure.
            for i in range(5):
                try:
                    own_login(plan, db, role, host, password)
                    break
                except ValueError:
                    if i == 4:
                        raise
                    time.sleep(0.5)
            print("HBA_ROLLBACK=ORIGINAL_BYTES_RESTORED_STAGE_LOGIN_PASS", flush=True)
        elif current != (path, old):
            print("HBA_ROLLBACK=BLOCKED_EXTERNAL_DRIFT", flush=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--proposal-sha256", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite",
                "HOST_ROOT")
        require(args.confirm == CONFIRM, "OWNER_CONFIRMATION")
        require(all(re.fullmatch(r"[0-9a-f]{64}", s) for s in
                    (args.baseline_sha256, args.proposal_sha256)), "PIN_FORMAT")
        plan = load_plan()
        root = Path("/root")
        s = root.lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o077, "ROOT_DIR")
        fd = os.open(root / ".kmj-stage-hba-install.lock",
                     os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600)
        with os.fdopen(fd, "r+b") as lock:
            s = os.fstat(lock.fileno())
            require(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1
                    and stat.S_IMODE(s.st_mode) == 0o600, "LOCK_METADATA")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for sig in (signal.SIGTERM, signal.SIGHUP):
                signal.signal(sig, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
            original = snapshot(plan)
            new = plan.proposal(original[-1], *original[1:4])
            total = install(plan, original, new, args.baseline_sha256, args.proposal_sha256)
            print("HBA_LIVE_EXPLICIT_DENIALS=PASS COUNT=" + str(total))
            print("HBA_INSTALL=PASS_SCOPED_LIVE_PROOF")
            return 0
    except (OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt) as exc:
        reason = str(exc)
        print("HBA_INSTALL=BLOCKED_" + (reason if re.fullmatch(r"[A-Z_]+", reason)
                                        else "SYSTEM_OR_FORMAT"))
        return 2
    finally:
        print("DATABASE_GRANTS_CHANGED=NO RELEASE_POINTER_CHANGED=NO APPROVAL_UPDATED=NO SECRET_OUTPUT=NONE")


if __name__ == "__main__":
    raise SystemExit(main())
