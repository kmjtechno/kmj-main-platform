#!/usr/bin/env python3
"""Fixed-path, read-only KMJ-elite production release evidence inventory.

NEVER deploys, signs approvals, runs migrations, changes symlinks, or operates
the separately owned staging website. It is not an activation authorization.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

ROOT = Path("/home/kmjprod")
RELEASES = ROOT / "releases"
CURRENT = ROOT / "current"
APPROVAL = Path("/etc/kmj-codebridge/main-platform-production-release.json")
BACKUPS = Path("/var/backups/kmj-platform")
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
RELEASE_RE = re.compile(r"platform-[0-9a-f]{12}\Z")


def report(name: str, value: str) -> None:
    print(f"KMJ_RELEASE_AUDIT_{name}={value}", flush=True)


def protected_regular(path: Path, *, max_bytes: int | None = None) -> bool:
    try:
        info = path.lstat()
        return (
            stat.S_ISREG(info.st_mode)
            and info.st_uid == 0
            and info.st_nlink == 1
            and info.st_mode & 0o077 == 0
            and (max_bytes is None or info.st_size <= max_bytes)
            and info.st_size > 0
        )
    except OSError:
        return False


def check_approval(data: object, sha: str, current: str) -> str:
    if not isinstance(data, dict) or set(data) != {
        "approvedSha", "expectedCurrentRelease", "backupVerified", "rollbackVerified"
    }:
        return "INVALID"
    if data["expectedCurrentRelease"] != current:
        return "PROTECTED_EXPECTED_CURRENT_RELEASE_MISMATCH"
    if data["approvedSha"] != sha:
        return "APPROVED_CANDIDATE_SHA_MISMATCH"
    if data["backupVerified"] is not True or data["rollbackVerified"] is not True:
        return "UNATTESTED_FLAGS"
    return "FIELDS_MATCH_FLAGS_NOT_INDEPENDENT_PROOF"


def witness_matches(data: object, sha: str, current: str, backup: Path) -> bool:
    if not isinstance(data, dict) or set(data) != {
        "approvedSha", "currentRelease", "backupSha256"
    }:
        return False
    if data["approvedSha"] != sha or data["currentRelease"] != current:
        return False
    expected = data["backupSha256"]
    if not isinstance(expected, str) or re.fullmatch(r"[a-f0-9]{64}", expected) is None:
        return False
    digest = hashlib.sha256()
    try:
        with backup.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return False
    return digest.hexdigest() == expected


def fixed_read(argv: list[str], *, timeout: int = 20) -> str | None:
    try:
        done = subprocess.run(
            argv, check=False, capture_output=True, text=True, timeout=timeout,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root",
                 "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "--inspect" or SHA_RE.fullmatch(sys.argv[2]) is None:
        report("RESULT", "BLOCKED_EXACT_SHA_ARGUMENT")
        return 2
    sha = sys.argv[2]
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        report("RESULT", "BLOCKED_KMJ_ELITE_ROOT_REQUIRED")
        return 2

    blockers: list[str] = []
    if not CURRENT.is_symlink() or RELEASES.is_symlink():
        report("CURRENT", "INVALID_RELEASE_PATH")
        return 2
    try:
        live = CURRENT.resolve(strict=True)
    except OSError:
        report("CURRENT", "UNRESOLVED")
        return 2
    if live.parent != RELEASES or RELEASE_RE.fullmatch(live.name) is None:
        report("CURRENT", "INVALID_RELEASE_PATH")
        return 2
    current_name = live.name
    report("CURRENT", current_name)

    short = sha[:12]
    candidate = RELEASES / ("platform-" + short)
    if candidate.is_symlink() or not candidate.is_dir():
        report("CANDIDATE", "MISSING_OR_UNSAFE")
        blockers.append("CANDIDATE")
    else:
        head = fixed_read(["/usr/sbin/runuser", "-u", "kmjprod", "--",
                           "/usr/bin/git", "-C", str(candidate), "rev-parse", "HEAD"])
        dirty = fixed_read(["/usr/sbin/runuser", "-u", "kmjprod", "--",
                            "/usr/bin/git", "-C", str(candidate), "status",
                            "--porcelain", "--untracked-files=normal"])
        artifacts = (
            "apps/platform/artisan", "apps/platform/vendor/autoload.php",
            "apps/platform/public/build/manifest.json",
            "apps/platform/public/assets/kmj-codebridge-icon.png"
        )
        safe_assets = all(
            (candidate / rel).is_file()
            and not (candidate / rel).is_symlink()
            and (candidate / rel).stat().st_size > 0
            for rel in artifacts
        )
        env_file = candidate / "apps/platform/.env"
        if head != sha or dirty is None or dirty or not safe_assets or env_file.is_symlink():
            report("CANDIDATE", "EXACT_SHA_CLEAN_ASSETS_NOT_VERIFIED")
            blockers.append("CANDIDATE")
        else:
            report("CANDIDATE", "EXACT_SHA_CLEAN_ASSETS_PASS")
            report("CANDIDATE_ENV", "PRESENT_REVIEW_ONLY" if env_file.exists() else "ABSENT")

    if not protected_regular(APPROVAL, max_bytes=4096):
        approval_state = "MISSING_OR_UNPROTECTED"
    else:
        try:
            approval_state = check_approval(json.loads(APPROVAL.read_text()), sha, current_name)
        except (OSError, ValueError, UnicodeError):
            approval_state = "INVALID_JSON"
    report("APPROVAL", approval_state)
    if approval_state != "FIELDS_MATCH_FLAGS_NOT_INDEPENDENT_PROOF":
        blockers.append("APPROVAL")

    backup = BACKUPS / f"pre-deploy-{short}.tar.gz"
    witness = BACKUPS / f"pre-deploy-{short}.json"
    if not protected_regular(backup) or not protected_regular(witness, max_bytes=4096):
        backup_state = "MISSING_OR_UNPROTECTED"
    else:
        try:
            backup_state = (
                "LOCAL_SHA256_WITNESS_PASS"
                if witness_matches(json.loads(witness.read_text()), sha, current_name, backup)
                else "WITNESS_OR_DIGEST_MISMATCH"
            )
        except (OSError, ValueError, UnicodeError):
            backup_state = "INVALID_WITNESS"
    report("BACKUP", backup_state)
    if backup_state != "LOCAL_SHA256_WITNESS_PASS":
        blockers.append("BACKUP")

    nginx = fixed_read(["/usr/bin/systemctl", "is-active", "nginx.service"])
    php = fixed_read(["/usr/bin/systemctl", "is-active", "php8.4-fpm.service"])
    syntax = fixed_read(["/usr/sbin/nginx", "-t", "-q"])
    service_state = "PASS" if nginx == "active" and php == "active" and syntax is not None else "BLOCKED"
    report("WEB_SERVICES", service_state)
    if service_state != "PASS":
        blockers.append("SERVICES")

    try:
        still = CURRENT.resolve(strict=True)
    except OSError:
        still = None
    if still != live:
        blockers.append("LIVE_POINTER_CHANGED")
        report("POINTER_READBACK", "CHANGED")
    else:
        report("POINTER_READBACK", "UNCHANGED")

    # These require independent human/equipment evidence; never infer from flags.
    report("INDEPENDENT_OFFSITE_RESTORE", "NOT_ATTESTED_BY_THIS_READ_ONLY_AUDIT")
    report("AUTHENTICATED_OWNER_QA", "NOT_ATTESTED_BY_THIS_READ_ONLY_AUDIT")
    report("P520_P720", "INTENTIONALLY_OFFLINE_NO_ACTION")
    report("STAGING", "OWNED_BY_SEPARATE_CHAT_NO_ACTION")
    report("MUTATIONS", "NONE")
    report("PRODUCTION_ACTIVATION", "NOT_ATTEMPTED")
    report("RESULT", "BLOCKED_" + "_".join(blockers) if blockers else "SOURCE_PREFLIGHT_PASS_MANUAL_RELEASE_GATES_PENDING")
    return 2 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
