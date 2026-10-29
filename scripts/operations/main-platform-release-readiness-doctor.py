#!/usr/bin/env python3
"""Read-only Main Platform production release readiness doctor (KMJ-elite).

Mirrors the checks of the fixed activation controller
(/usr/local/libexec/kmj-codebridge/activate-main-platform-approved.py) so the
owner sees, BEFORE triggering activation, exactly which gate is missing.

It never writes, restarts, switches symlinks, creates approvals or backups.
Usage (root, KMJ-elite):
    main-platform-release-readiness-doctor.py <target-40-hex-sha>
Prints one KEY=VALUE line per gate and a final RELEASE_READINESS verdict.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SHA = re.compile(r"^[a-f0-9]{40}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
RELEASE = re.compile(r"^[a-z0-9][a-z0-9_-]{3,100}$")
ARTIFACTS = (
    "apps/platform/artisan",
    "apps/platform/vendor/autoload.php",
    "apps/platform/public/build/manifest.json",
    "apps/platform/public/assets/kmj-codebridge-icon.png",
)


@dataclass(frozen=True)
class Paths:
    root: Path = Path("/home/kmjprod")
    approval: Path = Path("/etc/kmj-codebridge/main-platform-production-release.json")
    backups: Path = Path("/var/backups/kmj-platform")
    controller: Path = Path("/usr/local/libexec/kmj-codebridge/activate-main-platform-approved.py")
    unit: Path = Path("/etc/systemd/system/kmj-main-platform-production-release.service")


def _protected(path: Path, require_root: bool) -> str | None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return "MISSING"
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        return "NOT_REGULAR"
    if require_root and info.st_uid != 0:
        return "NOT_ROOT_OWNED"
    if info.st_mode & 0o022:
        return "GROUP_OR_WORLD_WRITABLE"
    if info.st_size > 4096 and path.suffix == ".json":
        return "TOO_LARGE"
    return None



def _load_protected_json(path: Path, require_root: bool) -> object | None:
    """Read the same protected inode, rejecting symlink swaps and ambiguous JSON.

    This is advisory readiness evidence only; the installed activation
    controller must independently recheck its own protected release gates.
    """
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("DUPLICATE_PROTECTED_JSON_KEY")
            result[key] = value
        return result

    def reject_nonfinite(value):
        raise ValueError("NONFINITE_PROTECTED_JSON")

    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            before = os.fstat(fd)
            at_path = os.lstat(path)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or (require_root and before.st_uid != 0)
                    or before.st_mode & 0o022
                    or before.st_size > 4096
                    or (before.st_dev, before.st_ino) != (at_path.st_dev, at_path.st_ino)):
                return None
            data = os.read(fd, 4097)
            after = os.fstat(fd)
            now = os.lstat(path)
            # Include the final path metadata: a same-inode write or mode change
            # between fstat(fd) and lstat(path) must not be trusted.
            def fingerprint(info):
                return (info.st_dev, info.st_ino, info.st_mode,
                        info.st_uid, info.st_gid, info.st_nlink,
                        info.st_size, info.st_mtime_ns, info.st_ctime_ns)

            if (len(data) != before.st_size
                    or fingerprint(before) != fingerprint(after)
                    or fingerprint(after) != fingerprint(now)):
                return None
            return json.loads(data, object_pairs_hook=unique_pairs,
                              parse_constant=reject_nonfinite)
        finally:
            os.close(fd)
    except (OSError, ValueError, UnicodeError):
        return None


def _git(tree: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-c", f"safe.directory={tree}", "-c", "core.fsmonitor=false",
             "-c", "core.untrackedCache=false", "-C", str(tree), *args],
            check=False, capture_output=True, text=True, timeout=60,
            env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
                 "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
                 "GIT_OPTIONAL_LOCKS": "0"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _web_user_can_read(path: Path) -> bool | None:
    """Read-only check that nginx's www-data can read a candidate file."""
    try:
        result = subprocess.run(["runuser", "-u", "www-data", "--", "test", "-r", str(path)],
                                check=False, capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.returncode == 0


def evaluate(target: str, paths: Paths = Paths(), require_root: bool = True,
             web_read=None) -> tuple[list[str], list[str]]:
    """Return (report lines, blocking reasons)."""
    if not SHA.fullmatch(target):
        return ["TARGET_SHA=INVALID"], ["TARGET_SHA_INVALID"]
    short = target[:12]
    lines: list[str] = [f"TARGET_SHA={target}"]
    blockers: list[str] = []

    # Live pointer.
    current = paths.root / "current"
    current_release = None
    if current.is_symlink():
        match = re.fullmatch(
            r"(?:" + re.escape(str(paths.root)) + r"/)?releases/([a-z0-9][a-z0-9_-]{3,100})",
            os.readlink(current),
        )
        if match and (paths.root / "releases" / match.group(1)).is_dir():
            current_release = match.group(1)
    lines.append(f"CURRENT_RELEASE={current_release or 'UNSAFE_OR_MISSING'}")
    if current_release is None:
        blockers.append("PRODUCTION_POINTER_UNSAFE")
    elif current_release == f"platform-{short}":
        lines.append("RELEASE_READINESS=ALREADY_LIVE")
        return lines, []

    # Candidate.
    candidate = paths.root / "releases" / f"platform-{short}"
    try:
        info = os.lstat(candidate)
        ok_dir = stat.S_ISDIR(info.st_mode) and not info.st_mode & 0o022
    except FileNotFoundError:
        ok_dir = False
    if not ok_dir or not (candidate / ".git").is_dir():
        lines.append("CANDIDATE=MISSING_OR_UNSAFE")
        blockers.append("CANDIDATE_NOT_STAGED")
    else:
        head = _git(candidate, "rev-parse", "HEAD")
        dirty = _git(candidate, "status", "--porcelain")
        missing = [item for item in ARTIFACTS
                   if not (candidate / item).is_file() or (candidate / item).stat().st_size <= 0]
        state = ("SHA_MISMATCH" if head != target else "DIRTY" if dirty
                 else "ARTIFACT_MISSING" if missing else "PASS")
        lines.append(f"CANDIDATE={state}")
        if state != "PASS":
            blockers.append("CANDIDATE_" + state)
        # The activation controller does not provide runtime state; the
        # candidate must already carry the live .env (materialize step).
        env = candidate / "apps/platform/.env"
        env_ok = env.is_file() and not env.is_symlink() and not env.stat().st_mode & 0o077
        lines.append("CANDIDATE_RUNTIME_ENV=" + ("PRESENT" if env_ok else "MISSING_RUN_MATERIALIZE"))
        if not env_ok:
            blockers.append("CANDIDATE_RUNTIME_ENV_MISSING")
        # The activation health check fetches a static asset through nginx.
        if web_read is not None:
            icon = candidate / "apps/platform/public/assets/kmj-codebridge-icon.png"
            readable, env_private = web_read(icon), web_read(env) is False
            state = ("PASS" if readable and env_private else
                     "ENV_EXPOSED" if readable else "UNREADABLE_RUN_MATERIALIZE")
            lines.append("CANDIDATE_NGINX_ACCESS=" + state)
            if state != "PASS":
                blockers.append("CANDIDATE_NGINX_" + ("ENV_EXPOSED" if state == "ENV_EXPOSED" else "UNREADABLE"))

    # Backup witness + archive digest.
    witness = paths.backups / f"pre-deploy-{short}.json"
    archive = paths.backups / f"pre-deploy-{short}.tar.gz"
    problem = _protected(witness, require_root) or _protected(archive, require_root)
    if problem:
        lines.append(f"BACKUP_WITNESS={problem}")
        blockers.append("BACKUP_WITNESS_" + problem)
    else:
        try:
            record = _load_protected_json(witness, require_root)
        except (OSError, ValueError):
            record = None
        if (not isinstance(record, dict)
                or set(record) != {"approvedSha", "currentRelease", "backupSha256"}
                or record.get("approvedSha") != target
                or record.get("currentRelease") != current_release
                or not SHA256.fullmatch(str(record.get("backupSha256", "")))):
            lines.append("BACKUP_WITNESS=MISMATCH")
            blockers.append("BACKUP_WITNESS_MISMATCH")
        else:
            digest = hashlib.sha256()
            with archive.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            good = digest.hexdigest() == record["backupSha256"]
            lines.append("BACKUP_WITNESS=" + ("PASS" if good else "CHECKSUM_MISMATCH"))
            if not good:
                blockers.append("BACKUP_CHECKSUM_MISMATCH")

    # Root approval (owner action; this doctor never writes it).
    problem = _protected(paths.approval, require_root)
    if problem:
        lines.append(f"APPROVAL={problem}")
        blockers.append("APPROVAL_" + problem)
    else:
        try:
            data = _load_protected_json(paths.approval, require_root)
        except (OSError, ValueError):
            data = None
        keys = {"approvedSha", "expectedCurrentRelease", "backupVerified", "rollbackVerified"}
        if not isinstance(data, dict) or set(data) != keys:
            lines.append("APPROVAL=SCHEMA_INVALID")
            blockers.append("APPROVAL_SCHEMA_INVALID")
        else:
            if data["approvedSha"] != target:
                lines.append("APPROVAL=APPROVES_OTHER_SHA")
                blockers.append("APPROVAL_SHA_MISMATCH")
            elif data["expectedCurrentRelease"] != current_release:
                lines.append("APPROVAL=EXPECTS_OTHER_CURRENT_RELEASE")
                blockers.append("APPROVAL_STALE_EXPECTED_CURRENT")
            elif data["backupVerified"] is not True or data["rollbackVerified"] is not True:
                lines.append("APPROVAL=OWNER_VERIFICATION_FLAGS_FALSE")
                blockers.append("APPROVAL_FLAGS_NOT_TRUE")
            else:
                lines.append("APPROVAL=PASS")

    # Fixed controller installation.
    unit_ok = paths.unit.is_file() and paths.controller.is_file()
    lines.append("RELEASE_UNIT=" + ("INSTALLED" if unit_ok else "MISSING"))
    if not unit_ok:
        blockers.append("RELEASE_UNIT_MISSING")

    lines.append("RELEASE_READINESS=" + ("READY_TO_ACTIVATE" if not blockers else "BLOCKED"))
    lines.extend(f"BLOCKER={item}" for item in blockers)
    lines.append("PRODUCTION_CHANGED=NO")
    return lines, blockers


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("RELEASE_READINESS=BLOCKED\nBLOCKER=USAGE_TARGET_SHA_REQUIRED")
        return 2
    if os.geteuid() != 0:
        print("RELEASE_READINESS=BLOCKED\nBLOCKER=ROOT_REQUIRED")
        return 2
    lines, blockers = evaluate(argv[1], web_read=_web_user_can_read)
    print("\n".join(lines))
    return 0 if not blockers else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
