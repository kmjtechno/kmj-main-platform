#!/usr/bin/env python3
"""One-time KMJ-elite installer for the release evidence collectors and admission broker.

Owner invocation only. The only remotely retrieved source is the exact immutable
main-platform merge commit below; no checkout hooks, shell, arbitrary URL,
approvals, candidate release, database, symlink or production mutation.

--inspect: no mutations.
--install: guarded fixed root-owned collector/broker files and unit templates, plus the
    receipt and broker state directories (0700 root). The broker timer is NOT enabled.
--install --enable-timer: additionally enables ONLY the admission broker timer.
    This flag is the owner's explicit approval to enable it. The broker writes only the
    per-release admission file after verifying receipts; this installer never starts the
    production release unit, writes an approval, writes an admission or switches LIVE.
    The rollback rehearsal needs an owner-provisioned disposable database config; this
    installer does not create one.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile

SOURCE_COMMIT = "ee7bef15c82d16933ab0e7fe187d8aa1649790c6"
SOURCE_URL = "https://github.com/kmjtechno/kmj-main-platform.git"
EXPECTED_HOST = "KMJ-elite"
GATE = Path("/opt/kmj-main-platform-autopublish/main_platform_autopublish_gate.py")
DEST = Path("/opt/kmj-main-platform-release-evidence")
PY_FILES = (
    "release_admission_receipts.py", "release_receipt_store.py",
    "elite_collect_staging_origin_receipt.py", "check-staging-readback.py",
    "elite_collect_public_qa_receipt.py", "elite_collect_backup_receipts.py",
    "verify-elite-local-upload-restore-20261119.py",
    "elite_collect_rollback_rehearsal_receipt.py",
    "rehearse-app-http-db-rollback-20261029.py",
    "elite_derive_migration_storage_receipt.py", "elite_collect_all_receipts.py",
    "elite_admission_broker.py", "main_platform_autopublish_gate.py",
)
UNITS = (
    "kmj-elite-release-admission-broker.service",
    "kmj-elite-release-admission-broker.timer",
)
TARGETS = tuple(
    ("scripts/operations/" + name, DEST / name, 0o500, 60000) for name in PY_FILES
) + tuple(
    ("infra/server/systemd/" + name, Path("/etc/systemd/system/" + name), 0o644, 10000)
    for name in UNITS
)
DIRS = (
    (Path("/var/lib/kmj-release-receipts"), 0o700),
    (Path("/var/lib/kmj-main-platform/admission-broker"), 0o700),
)
SYSTEMD_TIMER = "kmj-elite-release-admission-broker.timer"
ENV = {
    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
    "HOME": "/root",
    "LANG": "C",
    "LC_ALL": "C",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_LFS_SKIP_SMUDGE": "1",
}


class Blocked(Exception):
    pass


def check(condition: bool, code: str) -> None:
    if not condition:
        raise Blocked(code)


def protected_dir(path: Path) -> bool:
    """Every ancestor is a real, root-owned, non-world-writable directory."""
    if not path.is_absolute() or ".." in path.parts:
        return False
    current = Path("/")
    for part in path.parts[1:]:
        current /= part
        try:
            info = os.lstat(current)
        except OSError:
            return False
        if (not stat.S_ISDIR(info.st_mode)
                or info.st_uid != 0 or (info.st_mode & 0o022)):
            return False
    return True


def classify_file(path: Path, mode: int, desired_digest: str | None = None) -> str:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return "MISSING"
    except OSError:
        return "UNTRUSTED"
    if (not protected_dir(path.parent) or not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0 or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != mode
            or info.st_size < 20 or info.st_size > 200000):
        return "UNTRUSTED"
    if desired_digest is None:
        return "PRESENT_UNATTESTED"
    h = hashlib.sha256()
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            while chunk := stream.read(65536):
                h.update(chunk)
            after = os.fstat(stream.fileno())
        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            return "UNTRUSTED"
    except OSError:
        return "UNTRUSTED"
    return "PIN_MATCH" if h.hexdigest() == desired_digest else "DIFFERENT"


def fixed_run(argv: list[str], timeout: int = 45) -> bytes:
    try:
        proc = subprocess.run(
            argv, cwd="/", env=ENV, capture_output=True,
            check=False, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("FIXED_TOOL_UNAVAILABLE") from None
    if proc.returncode != 0 or len(proc.stdout) > 250000:
        raise Blocked("FIXED_TOOL_FAILED")
    return proc.stdout


def reviewed_bytes() -> dict[Path, tuple[bytes, int]]:
    """Fetch exact Git object into disposable root-only bare repo, no checkout."""
    check(protected_dir(Path("/root")), "ROOT_PARENT_UNTRUSTED")
    with tempfile.TemporaryDirectory(prefix="kmj-rr-reviewed-", dir="/root") as dirname:
        root = Path(dirname)
        repo = root / "source.git"
        fixed_run(["/usr/bin/git", "init", "--bare", "--quiet", str(repo)])
        fixed_run([
            "/usr/bin/git", "-c", "credential.helper=", "-c",
            "core.hooksPath=/dev/null", "-C", str(repo),
            "fetch", "--no-tags", "--depth=1", SOURCE_URL, SOURCE_COMMIT,
        ], timeout=100)
        actual = fixed_run([
            "/usr/bin/git", "-C", str(repo), "rev-parse", "--verify",
            "FETCH_HEAD^{commit}",
        ]).decode("ascii", "strict").strip()
        check(actual == SOURCE_COMMIT, "REVIEWED_SOURCE_SHA_MISMATCH")
        results: dict[Path, tuple[bytes, int]] = {}
        for source, target, mode, limit in TARGETS:
            data = fixed_run([
                "/usr/bin/git", "--no-pager", "-C", str(repo),
                "show", SOURCE_COMMIT + ":" + source,
            ])
            check(20 < len(data) <= limit and b"\x00" not in data,
                  "REVIEWED_ARTIFACT_INVALID")
            results[target] = (data, mode)
        names = {t[1].name: results[t[1]][0] for t in TARGETS}
        check(b"--execute" in names["elite_admission_broker.py"]
              and b"release-admission-request.json" in names["elite_admission_broker.py"],
              "BROKER_ARTIFACT_DRIFT")
        service = names["kmj-elite-release-admission-broker.service"]
        check(b"elite_admission_broker.py --execute" in service
              and b"production-release" not in service and b"systemctl" not in service,
              "SERVICE_BROKER_DRIFT")
        check(b"Unit=kmj-elite-release-admission-broker.service"
              in names["kmj-elite-release-admission-broker.timer"], "TIMER_SERVICE_DRIFT")
        for name, data in names.items():
            if name.endswith(".py"):
                check(b"shell" + b"=True" not in data and b"os." + b"system" not in data,
                      "SHELL_IN_REVIEWED_SOURCE")
        # The private gate copy must be byte-identical to the installed, trusted gate.
        installed = classify_file(GATE, 0o500,
                                  hashlib.sha256(names["main_platform_autopublish_gate.py"]).hexdigest())
        check(installed == "PIN_MATCH", "INSTALLED_GATE_DIFFERS_FROM_REVIEWED_COPY")
        return results


def install_new(path: Path, contents: bytes, mode: int) -> str:
    """No overwrite, no symlink following, atomic link of a root-created inode."""
    check(protected_dir(path.parent), "INSTALL_PARENT_UNTRUSTED")
    sha = hashlib.sha256(contents).hexdigest()
    existing = classify_file(path, mode, sha)
    if existing == "PIN_MATCH":
        return "ALREADY_INSTALLED_PIN_MATCH"
    check(existing == "MISSING", "EXISTING_ARTIFACT_MISMATCH")
    token = os.urandom(12).hex()
    tmp = path.parent / ("." + path.name + "." + token + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, mode, follow_symlinks=False)
        check(classify_file(tmp, mode, sha) == "PIN_MATCH",
              "STAGED_ARTIFACT_SHA_MISMATCH")
        try:
            os.link(tmp, path, follow_symlinks=False)
        except FileExistsError:
            raise Blocked("INSTALL_TARGET_RACE") from None
        # Remove the transient second hard link BEFORE checking the required
        # single-link root-owned installed inode. No overwrite or replace.
        os.unlink(tmp)
        check(classify_file(path, mode, sha) == "PIN_MATCH",
              "INSTALLED_ARTIFACT_SHA_MISMATCH")
        return "INSTALLED_PIN_MATCH"
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def require_operator() -> None:
    check(os.geteuid() == 0 and socket.gethostname().split(".")[0] == EXPECTED_HOST,
          "ROOT_ELITE_ONLY")
    for parent in (Path("/"), Path("/root"), Path("/opt"), Path("/etc"),
                   Path("/etc/systemd"), Path("/etc/systemd/system")):
        check(protected_dir(parent), "PROTECTED_PARENT_UNTRUSTED")


def ensure_dir(path: Path, mode: int) -> None:
    check(protected_dir(path.parent), "STATE_PARENT_UNTRUSTED")
    if not path.exists():
        os.mkdir(path, mode)
    info = os.lstat(path)
    check(stat.S_ISDIR(info.st_mode) and info.st_uid == 0
          and stat.S_IMODE(info.st_mode) & 0o077 == 0, "STATE_DIR_UNTRUSTED")


def run(mode: str, enable_timer: bool = False) -> int:
    require_operator()
    if mode == "inspect":
        for i, (_, file, permissions, _) in enumerate(TARGETS, 1):
            print(f"KMJ_ELITE_RELEASE_EVIDENCE_ARTIFACT_{i}=" + classify_file(file, permissions))
        print("KMJ_ELITE_RELEASE_EVIDENCE_GATE=" + classify_file(GATE, 0o500))
        print("KMJ_ELITE_RELEASE_EVIDENCE_INSPECT=PASS_READ_ONLY")
        print("PRODUCTION_MUTATION=NONE")
        return 0

    check(mode == "install", "UNSUPPORTED_MODE")
    check(classify_file(GATE, 0o500) in ("PRESENT_UNATTESTED", "PIN_MATCH"),
          "AUTOPUBLISH_GATE_MISSING_RUN_INSTALL_ELITE_AUTOPUBLISH_V2_FIRST")
    reviewed = reviewed_bytes()
    if not DEST.exists():
        check(protected_dir(DEST.parent), "INSTALL_OPT_PARENT_UNTRUSTED")
        os.mkdir(DEST, 0o700)
    check(protected_dir(DEST), "INSTALL_ROOT_UNTRUSTED")
    for directory, permissions in DIRS:
        ensure_dir(directory, permissions)
    results = []
    for file, (blob, permissions) in reviewed.items():
        results.append(install_new(file, blob, permissions))
    print("KMJ_ELITE_RELEASE_EVIDENCE_FILES=" + ",".join(sorted(set(results))))

    fixed_run([
        "/usr/bin/systemd-analyze", "verify",
        str(Path("/etc/systemd/system/" + UNITS[0])), str(Path("/etc/systemd/system/" + UNITS[1])),
    ])
    fixed_run(["/usr/bin/systemctl", "daemon-reload"])
    if enable_timer:
        # Admission broker timer only. NEVER start the production release service.
        fixed_run(["/usr/bin/systemctl", "enable", "--now", SYSTEMD_TIMER])
        fixed_run(["/usr/bin/systemctl", "is-enabled", "--quiet", SYSTEMD_TIMER])
        fixed_run(["/usr/bin/systemctl", "is-active", "--quiet", SYSTEMD_TIMER])
        print("KMJ_ELITE_RELEASE_EVIDENCE_TIMER=ACTIVE")
    else:
        print("KMJ_ELITE_RELEASE_EVIDENCE_TIMER=NOT_ENABLED_RERUN_WITH_ENABLE_TIMER_TO_APPROVE")
    print("KMJ_ELITE_RELEASE_EVIDENCE_INSTALL=PASS")
    print("REHEARSAL_CONFIG=OWNER_PROVISIONED_SEPARATELY")
    print("PRODUCTION_RELEASE_SWITCH=NOT_ATTEMPTED")
    print("APPROVAL_UPDATED=NO ADMISSION_WRITTEN=NO")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect", action="store_true")
    group.add_argument("--install", action="store_true")
    parser.add_argument("--enable-timer", action="store_true")
    args = parser.parse_args()
    if args.enable_timer and not args.install:
        print("KMJ_ELITE_RELEASE_EVIDENCE_INSTALL=BLOCKED_ENABLE_TIMER_NEEDS_INSTALL")
        return 2
    try:
        return run("install" if args.install else "inspect", args.enable_timer)
    except Blocked as error:
        print("KMJ_ELITE_RELEASE_EVIDENCE_INSTALL=BLOCKED_" + str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
