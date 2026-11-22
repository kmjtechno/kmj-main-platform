#!/usr/bin/env python3
"""Collector 2+3: backup-witness and disposable-restore receipts (source only).

Builds on the EXISTING exact-release recovery run, which publishes the root-owned
witness /var/backups/kmj-platform/pre-deploy-<sha12>.json only after a real
disposable PostgreSQL restore succeeded. This collector adds nothing to that
claim; it re-verifies, read-only, what is on disk now:

  backup-witness      witness is protected, bound to the SHA and live predecessor,
                      and the bundle's SHA-256 recomputed now equals backupSha256.
  disposable-restore  the above, PLUS the existing uploads verifier passes against
                      the same bundle (real byte-for-byte extraction in scratch).

It never runs a backup, restores into any live path, touches production data,
approvals or pointers. The receipt write needs root on KMJ-elite.

  --check <sha> <expected-release> | --write <sha> <expected-release>
"""
import hashlib
import importlib.util
import os
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import release_admission_receipts as ra  # noqa: E402
import elite_collect_staging_origin_receipt as common  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "uploads_verifier", HERE / "verify-elite-local-upload-restore-20261119.py")
verifier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verifier)

BACKUP = Path("/var/backups/kmj-platform")
VERIFIER = HERE / "verify-elite-local-upload-restore-20261119.py"
MAX_BUNDLE = 4 * 1024**3


def bundle_sha256(path, uid):
    """Hash one protected regular bundle without following links."""
    before = os.lstat(path)
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != uid or before.st_nlink != 1
            or before.st_mode & 0o077 or not 0 < before.st_size <= MAX_BUNDLE):
        raise ValueError("BUNDLE_UNTRUSTED")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        opened = os.fstat(fd)
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError("BUNDLE_REPLACED")
        h, count = hashlib.sha256(), 0
        while block := os.read(fd, 1024 * 1024):
            count += len(block)
            if count > before.st_size:
                raise ValueError("BUNDLE_GROWING")
            h.update(block)
        after = os.fstat(fd)
        if count != before.st_size or after.st_mtime_ns != before.st_mtime_ns:
            raise ValueError("BUNDLE_CHANGED")
        return h.hexdigest()
    finally:
        os.close(fd)


def witnessed_backup(sha, expected, backup=BACKUP, uid=0):
    """Return the recomputed bundle digest only if witness and bundle agree."""
    info = os.lstat(backup)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or info.st_mode & 0o022:
        raise ValueError("BACKUP_DIR_UNTRUSTED")
    claimed = verifier.verify_witness(backup / ("pre-deploy-" + sha[:12] + ".json"),
                                      sha, expected, uid)
    actual = bundle_sha256(backup / ("pre-deploy-" + sha[:12] + ".tar.gz"), uid)
    if actual != claimed:
        raise ValueError("BUNDLE_DIGEST_MISMATCH")
    return actual


def run_uploads_verifier(sha, expected):
    out = subprocess.run(
        ["/usr/bin/python3", "-I", "-B", str(VERIFIER), "--candidate-sha", sha,
         "--expected-release", expected],
        cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C"}, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, check=False, timeout=3600)
    lines = out.stdout.splitlines()
    return (out.returncode == 0
            and "ELITE_UPLOADS_DISPOSABLE_RESTORE=PASS" in lines
            and "ELITE_UPLOADS_BYTE_SHA_READBACK=PASS" in lines)


def receipt(kind, sha, expected, digest, now):
    return {"schema": ra.RECEIPT_SCHEMA, "kind": kind, "host": ra.HOST,
            "approvedSha": sha, "expectedCurrentRelease": expected,
            "capturedAt": int(now), "result": "pass", "artifactSha256": digest}


def collect(sha, expected, now, backup=BACKUP, uid=0, verify=run_uploads_verifier):
    """Return [backup-witness, disposable-restore] receipts or raise ValueError."""
    digest = witnessed_backup(sha, expected, backup, uid)
    out = [receipt("backup-witness", sha, expected, digest, now)]
    if not verify(sha, expected):
        raise ValueError("UPLOADS_RESTORE_NOT_PASS")
    out.append(receipt("disposable-restore", sha, expected, digest, now))
    return out


def main(argv):
    if len(argv) != 4 or argv[1] not in ("--check", "--write"):
        print("usage: --check|--write <40-hex-sha> <platform-12hex>")
        return 2
    sha, expected = argv[2], argv[3]
    if not ra.SHA_RE.fullmatch(sha) or not ra.RELEASE_RE.fullmatch(expected):
        print("BACKUP_RECEIPTS=BLOCKED_INPUT")
        return 2
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        print("BACKUP_RECEIPTS=BLOCKED_OPERATOR_HOST")
        return 2
    live = Path("/home/kmjprod/current")
    try:
        if not live.is_symlink() or live.resolve(strict=True) != Path(
                "/home/kmjprod/releases") / expected:
            print("BACKUP_RECEIPTS=BLOCKED_LIVE_POINTER")
            return 1
        receipts = collect(sha, expected, time.time())
        if argv[1] == "--write":
            for r in receipts:
                common.write_receipt(r)
    except (OSError, ValueError, subprocess.SubprocessError, UnicodeError,
            getattr(verifier, "Blocked", ValueError)) as exc:
        print("BACKUP_RECEIPTS=FAIL REASON=" + type(exc).__name__)
        return 1
    print("BACKUP_RECEIPTS=PASS WRITTEN=" + ("YES" if argv[1] == "--write" else "NO"))
    print("PRODUCTION_RELEASE=NOT_ATTEMPTED APPROVAL_UPDATED=NO ADMISSION_WRITTEN=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
