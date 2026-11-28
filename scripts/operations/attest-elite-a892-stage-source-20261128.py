#!/usr/bin/env python3
"""Root-only exact staging source attestation; never changes a serving route.
Uses the already reviewed, pinned repair guard and installed runner digest.
"""
import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import re
import runpy
import signal
import stat
import subprocess
import tempfile

REPAIR_PIN = "9cc17c0c5db18a7b371461820ea4fb06a44dc15e"
BUILDER_PIN = "654525519ee4b21c03f41a86da26fcf9f357d6dd"
SHA = "a892b0d5d851129a9d8ed00c1af1390da6ee584f"
RELEASE = Path("/home/kmjstage/releases") / SHA
APP = RELEASE / "apps/platform"
MARKER = APP / "public/build/.kmj-deploy-sha"
SEAL = Path("/etc/kmj-codebridge") / ("main-platform-staging-seal-" + SHA + ".sha256")
LOCK = Path("/run/kmj-main-platform-staging/deploy.lock")


def need(ok, label):
    if not ok:
        raise ValueError(label)


def pin(raw, expected):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == expected


def protected_input(path, expected):
    for p in path.parents:
        s = p.lstat()
        need(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022, "INPUT_PARENT")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as f:
        s = os.fstat(f.fileno())
        need(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1
             and not s.st_mode & 0o022 and 0 < s.st_size <= 65536, "INPUT_METADATA")
        raw = f.read(65537)
        def fp(x):
            return x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns
        need(len(raw) == s.st_size and fp(s) == fp(os.fstat(f.fileno()))
             and fp(s) == fp(path.lstat()) and pin(raw, expected), "INPUT_PIN")
    return raw


def install_marker(path, sha):
    need(re.fullmatch(r"[a-f0-9]{40}", sha) is not None, "MARKER_SHA")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o400)
    with os.fdopen(fd, "wb") as f:
        s = os.fstat(f.fileno())
        try:
            f.write((sha + "\n").encode("ascii"))
            f.flush()
            os.fchmod(f.fileno(), 0o444)
            os.fsync(f.fileno())
        except BaseException:
            current = path.lstat()
            if (current.st_dev, current.st_ino) == (s.st_dev, s.st_ino):
                path.unlink()
            raise
    return s.st_dev, s.st_ino


def remove_own(path, inode):
    s = path.lstat()
    need((s.st_dev, s.st_ino) == inode and stat.S_ISREG(s.st_mode), "MARKER_ROLLBACK_DRIFT")
    path.unlink()


def tracked_clean(r):
    # No untracked build-output assumptions: existing protected seal binds them.
    out = r["command"](["/usr/bin/git", "-c", "safe.directory=" + str(RELEASE),
                        "-c", "core.fsmonitor=false", "-C", str(RELEASE),
                        "status", "--porcelain", "--untracked-files=no"])
    need(not out.strip(), "TRACKED_SOURCE_DIRTY")


def main():
    import socket
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repair", type=Path, required=True)
    p.add_argument("--builder", type=Path, required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm", default="")
    a = p.parse_args()
    need(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite", "HOST_ROOT")
    need((a.apply and a.confirm == "OWNER_ATTEST_EXACT_STAGE_SOURCE") or
         (not a.apply and not a.confirm), "CONFIRMATION")
    os.umask(0o077)
    # Execute the exact verified bytes, not a second pathname lookup.
    r, b = {}, {}
    for path, expected, namespace in ((a.repair, REPAIR_PIN, r), (a.builder, BUILDER_PIN, b)):
        raw = protected_input(path, expected)
        namespace.update(__name__="pinned_attestation_dependency", __file__=str(path))
        exec(compile(raw, str(path), "exec"), namespace)
    r["protected_dir"](MARKER.parent)
    r["protected_dir"](LOCK.parent)
    fd = os.open(LOCK, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as lock:
        s = os.fstat(lock.fileno())
        need(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1 and
             stat.S_IMODE(s.st_mode) == 0o600, "LOCK_SCOPE")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        need(r["command"](["/usr/bin/systemctl", "show", "kmj-main-platform-staging-deploy.service",
                           "-p", "ActiveState", "--value"]).strip() == b"inactive", "STAGE_UNIT_BUSY")
        r["guard"](b)
        tracked_clean(r)
        old = r["read_file"](SEAL, 0, 65)[0]
        need(re.fullmatch(rb"[a-f0-9]{64}\n?", old) is not None and
             b["seal_sha"](APP) == old.decode().strip(), "ORIGINAL_SEAL")
        need(b"HEALTH_OK\n" in r["php"](r["PHP_HEALTH"]), "IMMUTABLE_HEALTH")
        need(not os.path.lexists(MARKER), "MARKER_ALREADY_EXISTS")
        print("SOURCE_SHA="+SHA, flush=True)
        print("TRACKED_SOURCE=PASS ORIGINAL_SEAL=PASS IMMUTABLE_HEALTH=PASS", flush=True)
        if not a.apply:
            print("STAGE_ATTESTATION=DRY_RUN_NO_CHANGES")
            return
        backup = Path(tempfile.mkdtemp(prefix="kmj-stage-source-seal-", dir="/root"))
        (backup/"original.sha256").write_bytes(old)
        r["sync_dir"](backup)
        print("ORIGINAL_SEAL_BACKUP="+str(backup), flush=True)
        inode = None
        new = None
        try:
            inode = install_marker(MARKER, SHA)
            r["sync_dir"](MARKER.parent)
            need(r["read_file"](MARKER, 0, 41)[0] == (SHA+"\n").encode(), "MARKER_READBACK")
            tracked_clean(r)
            r["guard"](b)
            new = (b["seal_sha"](APP)+"\n").encode()
            r["replace_seal"](old, new)
            need(r["read_file"](SEAL, 0, 65)[0] == new and
                 b["seal_sha"](APP) == new.decode().strip(), "FINAL_SEAL")
            r["guard"](b)
            tracked_clean(r)
        except BaseException:
            if inode is not None:
                current = r["read_file"](SEAL, 0, 65)[0]
                need(current in (old, new), "ROLLBACK_SEAL_DRIFT")
                remove_own(MARKER, inode)
                r["sync_dir"](MARKER.parent)
                if current != old:
                    r["replace_seal"](current, old)
                need(b["seal_sha"](APP) == old.decode().strip(), "ROLLBACK_SEAL")
                print("ATTESTATION_ROLLBACK=PASS", flush=True)
            raise
        print("DEPLOY_ATTESTATION=PASS")
        print("CANDIDATE_SECURITY_SEAL=REGENERATED_VERIFIED")
        print("STAGING_POINTER=UNCHANGED PRODUCTION_POINTER=UNCHANGED APPROVAL_UPDATED=NO")
        print("STAGE_ATTESTATION=PASS")


if __name__ == "__main__":
    def interrupted(_signum, _frame):
        raise InterruptedError("SIGNAL")
    signal.signal(signal.SIGHUP, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        main()
    except Exception as e:
        print("STAGE_ATTESTATION=BLOCKED_"+(str(e) if isinstance(e, ValueError)
              and re.fullmatch(r"[A-Z_]+", str(e)) else type(e).__name__))
        raise SystemExit(2)
