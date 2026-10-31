#!/usr/bin/env python3
"""READ-ONLY root preflight for prepare-main-platform-local-recovery-exact.sh (witnessed pre-deploy backup).

Answers one question without changing anything: would the exact-release local backup start, and if not, why.
No service control, no database access, no network, no files written next to production. The only
write is one sanitized JSON receipt (root forks, drops to the project owner) and contains only sanitized check results, candidate identity and timestamp.

    preflight-local-backup-witness-20261031.py --candidate-sha <40 lowercase hex> --expected-release platform-<12 hex>

READY does NOT mean a backup exists, restore works or release is approved; it only means the next step is not blocked.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pwd
import re
import shutil
import socket
import stat
import subprocess
import sys
from pathlib import Path

SHA_RE = re.compile(r"[0-9a-f]{40}")
REL_RE = re.compile(r"platform-[0-9a-f]{12}")
MIN_FREE_KIB = 12582912
TOOLS = ("git", "php8.4", "pg_dump", "pg_restore", "tar", "sha256sum", "python3", "runuser")
PG_BINS = ("initdb", "pg_ctl", "psql", "pg_restore", "createdb")
DEFAULT_RECEIPT_DIR = Path("/srv/kmj-codebridge-projects/kmj-main-platform/work/qa")


class Env:
    """All host access in one place so tests can drive it without touching a real host."""

    root = Path("/home/kmjprod")
    backup_dir = Path("/var/backups/kmj-platform")
    lock = Path("/run/lock/kmj-main-platform-production-release.lock")
    pg_glob_dir = Path("/usr/lib/postgresql")

    def is_root(self) -> bool:
        return os.geteuid() == 0

    def hostname(self) -> str:
        return socket.gethostname().split(".")[0]

    def which(self, name: str):
        return shutil.which(name)

    def service_active(self, unit: str) -> bool:
        return subprocess.run(["systemctl", "is-active", "--quiet", unit], timeout=15).returncode == 0

    def free_kib(self, path: str) -> int:
        st = os.statvfs(path)
        return st.f_bavail * st.f_frsize // 1024

    def candidate_head(self, directory: Path):
        r = subprocess.run(["runuser", "-u", "kmjprod", "--", "git", "-C", str(directory), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else None


def lstat_mode(path: Path):
    try:
        return os.lstat(path)
    except OSError:
        return None


def run_checks(env: Env, sha: str, expected: str) -> dict:
    short = sha[:12]
    checks: dict[str, bool] = {}

    def check(name: str, ok: bool) -> bool:
        checks[name] = bool(ok)
        return bool(ok)

    check("root_user", env.is_root())
    check("host_is_KMJ_elite", env.hostname() == "KMJ-elite")
    check("target_differs_from_current", f"platform-{short}" != expected)

    cur = env.root / "current"
    st = lstat_mode(cur)
    resolved = None
    if check("current_is_symlink", st is not None and stat.S_ISLNK(st.st_mode)):
        resolved = Path(os.path.realpath(cur))
    inside = resolved is not None and resolved.parent == env.root / "releases" and resolved.is_dir()
    check("current_inside_releases", inside)
    check("current_matches_expected_release", inside and resolved.name == expected)
    if inside:
        app = resolved / "apps/platform"
        check("source_app_files_present", (app / ".env").is_file() and (app / "vendor/autoload.php").is_file()
              and (app / "storage/app").is_dir())
    else:
        check("source_app_files_present", False)

    cand = env.root / "releases" / f"platform-{short}"
    has_git = (cand / ".git").is_dir()
    check("candidate_checkout_present", has_git)
    check("candidate_head_equals_sha", has_git and env.candidate_head(cand) == sha)

    bst = lstat_mode(env.backup_dir)
    check("backup_dir_real_root_owned", bst is not None and stat.S_ISDIR(bst.st_mode) and bst.st_uid == 0 and not (bst.st_mode & 0o022))
    check("archive_absent", lstat_mode(env.backup_dir / f"pre-deploy-{short}.tar.gz") is None)
    check("witness_absent", lstat_mode(env.backup_dir / f"pre-deploy-{short}.json") is None)

    for tool in TOOLS:
        check(f"tool_{tool}", env.which(tool) is not None)
    pgdir_ok = False
    if env.pg_glob_dir.is_dir():
        for d in sorted(env.pg_glob_dir.glob("*/bin")):
            if all(os.access(d / b, os.X_OK) for b in PG_BINS):
                pgdir_ok = True
    check("postgres_restore_binaries", pgdir_ok)
    check("nginx_active", env.service_active("nginx"))
    check("php_fpm_active", env.service_active("php8.4-fpm"))
    check("free_space_over_12GiB", env.free_kib(str(env.backup_dir)) > MIN_FREE_KIB)

    lst = lstat_mode(env.lock)
    lock_ok = lst is None or (stat.S_ISREG(lst.st_mode) and lst.st_uid == 0 and lst.st_nlink == 1)
    check("release_lock_absent_or_root_regular", lock_ok)
    return checks


def build_record(env: Env, sha: str, expected: str) -> dict:
    checks = run_checks(env, sha, expected)
    failed = sorted(k for k, v in checks.items() if not v)
    return {
        "schema": "kmj-local-backup-witness-preflight-v1",
        "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "candidateSha": sha,
        "expectedCurrentRelease": expected,
        "checks": checks,
        "failed": failed,
        "result": "READY_FOR_WITNESSED_BACKUP_RUN" if not failed else "BLOCKED",
        "backupCreated": False,
        "restoreVerified": False,
        "productionChanged": False,
        "approvalImplied": False,
    }


def write_receipt_no_clobber(record: dict, directory: Path, owner_uid: int) -> None:
    """Create one canonical receipt via no-follow directory FDs; never replace an existing file.

    Called ONLY after dropping root privileges. directory is fixed by save(); tests may inject
    an isolated directory. Every path component is opened with O_NOFOLLOW, closing symlink races.
    """
    sha = record.get("candidateSha", "")
    if not isinstance(sha, str) or SHA_RE.fullmatch(sha) is None:
        raise ValueError("RECEIPT_CANDIDATE_INVALID")
    if not directory.is_absolute() or any(p in (".", "..") for p in directory.parts):
        raise ValueError("RECEIPT_DIRECTORY_INVALID")
    name = f"KMJ_BACKUP_WITNESS_PREFLIGHT_{sha[:12]}.json"
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open("/", flags)
    try:
        parts = directory.parts[1:]
        if not parts:
            raise ValueError("RECEIPT_DIRECTORY_INVALID")
        for part in parts:
            if part in ("", ".", ".."):
                raise ValueError("RECEIPT_DIRECTORY_INVALID")
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
            st = os.fstat(fd)
            if st.st_uid not in (0, owner_uid):
                raise PermissionError("RECEIPT_ANCESTOR_OWNER_INVALID")
            # A root-owned sticky directory (e.g. /tmp in tests) cannot replace
            # another user's private child; ordinary writable ancestors are refused.
            if st.st_mode & 0o022 and not (st.st_uid == 0 and st.st_mode & stat.S_ISVTX):
                raise PermissionError("RECEIPT_ANCESTOR_WRITABLE")
        st = os.fstat(fd)
        if st.st_uid != owner_uid or st.st_mode & 0o022:
            raise PermissionError("RECEIPT_PARENT_NOT_PRIVATE_OWNER")
        out = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                      0o600, dir_fd=fd)
        with os.fdopen(out, "w", encoding="utf-8") as stream:
            json.dump(record, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(fd)
    finally:
        os.close(fd)


def save(record: dict) -> None:
    owner = pwd.getpwnam("kmjcode")
    pid = os.fork()
    if pid == 0:
        try:
            os.setgroups([])
            os.setgid(owner.pw_gid)
            os.setuid(owner.pw_uid)
            write_receipt_no_clobber(record, DEFAULT_RECEIPT_DIR, owner.pw_uid)
            os._exit(0)
        except Exception:
            os._exit(3)
    _, status = os.waitpid(pid, 0)
    if status:
        raise RuntimeError("RECEIPT_WRITE_FAILED")


def main(argv=None, env: Env | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate-sha", required=True)
    ap.add_argument("--expected-release", required=True)
    args = ap.parse_args(argv)
    if not SHA_RE.fullmatch(args.candidate_sha):
        print("PREFLIGHT=BLOCKED CANDIDATE_SHA_INVALID")
        return 2
    if not REL_RE.fullmatch(args.expected_release):
        print("PREFLIGHT=BLOCKED EXPECTED_RELEASE_INVALID")
        return 2
    env = env or Env()
    record = build_record(env, args.candidate_sha, args.expected_release)
    if record["checks"]["root_user"] and record["checks"]["host_is_KMJ_elite"]:
        try:
            save(record)
        except Exception:
            print("PREFLIGHT=RECEIPT_WRITE_FAILED")
            return 2
    print("PREFLIGHT=" + record["result"])
    for name in record["failed"]:
        print("FAILED=" + name)
    return 0 if record["result"].startswith("READY") else 2


if __name__ == "__main__":
    sys.exit(main())
