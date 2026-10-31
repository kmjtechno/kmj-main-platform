#!/usr/bin/env python3
"""Read-only KMJ-elite production release approval diagnostics.

No deployment, approval creation, protected manifest writes, DB access,
service restart, secret printing, or backup trust elevation.
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
CURRENT = ROOT / "current"
RELEASES = ROOT / "releases"
APPROVAL = Path("/etc/kmj-codebridge/main-platform-production-release.json")
BACKUP_ROOT = Path("/var/backups/kmj-platform")
GITHUB_REMOTE = "https://github.com/kmjtechno/kmj-main-platform.git"
SHA_RE = re.compile(r"[a-f0-9]{40}")
NAME_RE = re.compile(r"platform-[a-z0-9_-]{8,100}")
MAX_BACKUP_HASH_SIZE = 512 * 1024 * 1024


def out(name: str, value: str) -> None:
    print(f"PROD_GATE_{name}={value}", flush=True)


def run_read(*args: str, timeout: int = 15) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            list(args), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, check=False, timeout=timeout,
            env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                 "HOME": "/root", "GIT_TERMINAL_PROMPT": "0",
                 "GIT_OPTIONAL_LOCKS": "0"},
        )
        return proc.returncode, proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return -1, ""


def protected(path: Path, max_size: int) -> bool:
    try:
        info = path.lstat()
        return (stat.S_ISREG(info.st_mode) and info.st_uid == 0
                and info.st_nlink == 1 and info.st_size <= max_size
                and (info.st_mode & 0o022) == 0)
    except OSError:
        return False


def read_json(path: Path) -> dict | None:
    if not protected(path, 4096):
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (ValueError, OSError, UnicodeError):
        return None


def git_sha(release: Path) -> str | None:
    # The release builder validates Git as kmjprod. Use the same identity and
    # include system sbin paths for runuser; never fall back to a guessed SHA.
    if not (release / ".git").is_dir() or (release / ".git").is_symlink():
        return None
    rc, value = run_read(
        "/usr/sbin/runuser", "-u", "kmjprod", "--", "git", "-C",
        str(release), "rev-parse", "--verify", "HEAD",
    )
    return value if rc == 0 and SHA_RE.fullmatch(value) else None


def storage_snapshot(app: Path) -> dict[str, str]:
    """Summarize bounded local storage shape; never list paths or read records."""
    result: dict[str, str] = {}
    root = app / "storage"
    if not root.exists():
        return {"ROOT": "MISSING", "PUBLIC_FILES": "UNKNOWN", "PRIVATE_FILES": "UNKNOWN"}
    try:
        resolved = root.resolve(strict=True)
        result["ROOT"] = "WITHIN_PRODUCTION" if resolved.is_relative_to(ROOT) else "OUTSIDE_PRODUCTION"
        result["ROOT_LINK"] = "YES" if root.is_symlink() else "NO"
    except (OSError, RuntimeError):
        return {"ROOT": "UNVERIFIED", "PUBLIC_FILES": "UNKNOWN", "PRIVATE_FILES": "UNKNOWN"}
    for label, name in (("PUBLIC", "app/public"), ("PRIVATE", "app/private")):
        directory = root / name
        if not directory.is_dir():
            result[label + "_FILES"] = "DIRECTORY_ABSENT"
            continue
        count = 0
        links = 0
        for parent, folders, files in os.walk(directory, followlinks=False):
            for entry in list(folders):
                if (Path(parent) / entry).is_symlink():
                    folders.remove(entry)
                    links += 1
            for entry in files:
                item = Path(parent) / entry
                if item.is_symlink():
                    links += 1
                elif item.is_file():
                    count += 1
            if count > 10000:
                break
        result[label + "_FILES"] = str(count) if count <= 10000 else "MORE_THAN_10000"
        result[label + "_LINKS"] = str(links)
    public = app / "public/storage"
    if public.is_symlink():
        try:
            target = public.resolve(strict=True)
            result["WEB_STORAGE_LINK"] = (
                "TARGETS_APP_PUBLIC" if target == (root / "app/public").resolve(strict=True)
                else "OTHER_TARGET")
        except (OSError, RuntimeError):
            result["WEB_STORAGE_LINK"] = "BROKEN_OR_UNVERIFIED"
    else:
        result["WEB_STORAGE_LINK"] = "MISSING" if not public.exists() else "NOT_SYMLINK"
    return result


def assess():
    if len(sys.argv) != 1:
        out("RESULT", "BLOCKED_ARGUMENTS")
        return 2
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        out("RESULT", "BLOCKED_WRONG_HOST")
        return 2

    if not CURRENT.is_symlink():
        out("RESULT", "BLOCKED_CURRENT_NOT_LINK")
        return 2
    try:
        raw = os.readlink(CURRENT)
        match = re.fullmatch(r"(?:/home/kmjprod/)?releases/(platform-[a-z0-9_-]{8,100})", raw)
        if match is None:
            out("RESULT", "BLOCKED_CURRENT_LINK_SCOPE")
            return 2
        current_name = match.group(1)
        current = (RELEASES / current_name).resolve(strict=True)
        if current != RELEASES / current_name or not current.is_dir():
            out("RESULT", "BLOCKED_CURRENT_LINK_TARGET")
            return 2
    except (OSError, RuntimeError):
        out("RESULT", "BLOCKED_CURRENT_LINK_RESOLVE")
        return 2

    out("CURRENT_RELEASE", current_name)
    old_sha = git_sha(current)
    out("CURRENT_SOURCE_GIT", "VALID" if old_sha else
        "NO_GIT_METADATA" if not (current / ".git").is_dir() else "UNVERIFIED")
    if old_sha:
        out("CURRENT_SOURCE_SHA", old_sha)
    old_storage = storage_snapshot(current / "apps/platform")
    for key, value in old_storage.items():
        out("LIVE_STORAGE_" + key, value)

    approval = read_json(APPROVAL)
    allowed_keys = {"approvedSha", "expectedCurrentRelease", "backupVerified", "rollbackVerified"}
    accepted = bool(approval and set(approval) == allowed_keys
                    and isinstance(approval.get("approvedSha"), str)
                    and SHA_RE.fullmatch(approval["approvedSha"])
                    and isinstance(approval.get("expectedCurrentRelease"), str)
                    and NAME_RE.fullmatch(approval["expectedCurrentRelease"])
                    and approval.get("backupVerified") is True
                    and approval.get("rollbackVerified") is True)
    out("PROTECTED_APPROVAL", "STRUCTURALLY_VALID" if accepted else "INVALID_OR_ABSENT")
    approved = approval["approvedSha"] if accepted else None
    if approved:
        out("MANIFEST_TARGET_SHA", approved)
        out("MANIFEST_EXPECTED_RELEASE", approval["expectedCurrentRelease"])
        out("MANIFEST_EXPECTED_CURRENT", "MATCH" if current_name == approval["expectedCurrentRelease"] else "MISMATCH")
        out("MANIFEST_TARGET_ALREADY_CURRENT", "YES" if old_sha == approved else "NO")

    rc, remote_main = run_read("git", "ls-remote", "--exit-code",
                               GITHUB_REMOTE, "refs/heads/main", timeout=25)
    if rc != 0 or not SHA_RE.fullmatch(remote_main.split("\t")[0] if remote_main else ""):
        out("REMOTE_MAIN_SHA", "UNVERIFIED")
        target = None
    else:
        target = remote_main.split("\t")[0]
        out("REMOTE_MAIN_SHA", target)

    rc, stage_head = run_read("git", "ls-remote", "--exit-code",
                              GITHUB_REMOTE, "refs/heads/staging-approved", timeout=25)
    stage = stage_head.split("\t")[0] if rc == 0 and stage_head else ""
    out("PROMOTION_REF", "MATCH_MAIN" if target and stage == target else "NOT_MATCHED_OR_UNVERIFIED")

    # Candidate presence does not assert migrations or authentication readiness.
    if target:
        candidate = RELEASES / ("platform-" + target[:12])
        if candidate.is_symlink():
            out("CURRENT_MAIN_CANDIDATE", "BLOCKED_SYMLINK")
        elif not candidate.is_dir():
            out("CURRENT_MAIN_CANDIDATE", "MISSING")
        else:
            mode = candidate.stat()
            safe_mode = (mode.st_mode & 0o022) == 0
            sha = git_sha(candidate) if safe_mode else None
            app = candidate / "apps/platform"
            artifacts = all((app / path).is_file() and (app / path).stat().st_size > 0
                for path in ("artisan", "vendor/autoload.php",
                             "public/build/manifest.json", "public/assets/kmj-codebridge-icon.png"))
            if sha != target:
                out("CURRENT_MAIN_CANDIDATE", "BLOCKED_GIT_SHA_UNVERIFIED")
            elif not artifacts:
                out("CURRENT_MAIN_CANDIDATE", "BLOCKED_ARTIFACT_MISSING")
            else:
                out("CURRENT_MAIN_CANDIDATE", "ARTIFACTS_AND_SHA_PASS")
            candidate_storage = storage_snapshot(app)
            for key, value in candidate_storage.items():
                out("CANDIDATE_STORAGE_" + key, value)
            try:
                same_root = (current / "apps/platform/storage").resolve(strict=True) == (app / "storage").resolve(strict=True)
            except (OSError, RuntimeError):
                same_root = False
            out("STORAGE_CONTINUITY", "SHARED" if same_root else "SEPARATE_NEEDS_RELEASE_REVIEW")
            env = app / ".env"
            out("CANDIDATE_RUNTIME_ENV", "PRESENT_NEEDS_OPERATOR_REVIEW" if env.is_file() and not env.is_symlink() else "MISSING")
            # Candidate backup witness is exact target + actual current pointer.
            witness = BACKUP_ROOT / ("pre-deploy-" + target[:12] + ".json")
            backup = BACKUP_ROOT / ("pre-deploy-" + target[:12] + ".tar.gz")
            record = read_json(witness)
            record_ok = bool(record and set(record) == {"approvedSha", "currentRelease", "backupSha256"}
                             and record.get("approvedSha") == target
                             and record.get("currentRelease") == current_name
                             and isinstance(record.get("backupSha256"), str)
                             and re.fullmatch(r"[a-f0-9]{64}", record["backupSha256"]))
            out("TARGET_BACKUP_WITNESS", "MATCHES_CURRENT" if record_ok else "MISSING_OR_UNVERIFIED")
            if record_ok and protected(backup, MAX_BACKUP_HASH_SIZE):
                digest = hashlib.sha256()
                with backup.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                out("TARGET_BACKUP_ARCHIVE", "HASH_MATCH" if digest.hexdigest() == record["backupSha256"] else "HASH_MISMATCH")
            else:
                out("TARGET_BACKUP_ARCHIVE", "NOT_VERIFIED")
            out("DISPOSABLE_RESTORE_EVIDENCE", "NOT_ATTESTED_BY_FILE_CHECKS")
            out("CANDIDATE_OWNER_AUTH_QA", "NOT_ATTESTED_BY_FILE_CHECKS")
    else:
        out("CURRENT_MAIN_CANDIDATE", "UNVERIFIED")

    for key, service in (("NGINX", "nginx"), ("PHP_FPM", "php8.4-fpm"),
                         ("RELEASE_UNIT", "kmj-main-platform-production-release")):
        rc, state = run_read("systemctl", "is-active", service)
        if key == "RELEASE_UNIT":
            out(key, "IDLE" if state == "inactive" else
                "ACTIVE" if state == "active" else "UNVERIFIED")
        else:
            out(key, "ACTIVE" if rc == 0 and state == "active" else "NOT_ACTIVE")

    if os.readlink(CURRENT) != raw:
        out("RESULT", "BLOCKED_CONCURRENT_POINTER_CHANGE")
        return 2
    out("APPROVAL_RENEWAL", "NOT_PERFORMED")
    out("RELEASE_CUTOVER", "NOT_PERFORMED")
    out("DATABASE_CHANGES", "NOT_PERFORMED")
    out("RESULT", "READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(assess())
    except Exception:
        out("RESULT", "BLOCKED_UNEXPECTED_RUNTIME")
        sys.exit(2)
