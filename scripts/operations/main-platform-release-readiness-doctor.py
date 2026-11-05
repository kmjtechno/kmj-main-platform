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
import ctypes
import fcntl
import json
import math
import os
import pwd
import re
import stat
import subprocess
import sys
import types
from dataclasses import dataclass
from pathlib import Path

SHA = re.compile(r"^[a-f0-9]{40}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
RELEASE = re.compile(r"^[a-z0-9][a-z0-9_-]{3,100}$")
SNAPSHOT = re.compile(r"storage\.pre-shared-\d{8}T\d{6}Z\Z")
SNAPSHOT_HELPER_SHA256 = "72fe5702c59599bd1b28b88dad808dda5d6be97b61f0db06dc3a7295258a51b6"
SNAPSHOT_SCANNER_SHA256 = "f4d01f6e3b40c9ad774c8ada5129b241cee93dac782ce75bb0e229b26bbc95ba"
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
    snapshot_helper: Path = Path("/usr/local/libexec/kmj-codebridge/main-platform-storage-snapshot-attest.py")
    snapshot_scanner: Path = Path("/usr/local/libexec/kmj-codebridge/main-platform-storage-switch-v6.py")
    snapshot_state: Path = Path("/var/lib/kmj-main-platform-storage-switch")


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

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("NONFINITE_PROTECTED_JSON_NUMBER")
        return number

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
                              parse_constant=reject_nonfinite, parse_float=finite_float)
        finally:
            os.close(fd)
    except (OSError, ValueError, UnicodeError):
        return None


def _git(tree: Path, *args: str) -> str | None:
    try:
        credentials = {}
        if os.geteuid() == 0:
            account = pwd.getpwnam("kmjprod")
            if account.pw_uid == 0 or tree.stat().st_uid != account.pw_uid:
                return None
            credentials = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[], preexec_fn=_no_new_privileges)
        result = subprocess.run(
            ["/usr/bin/git", "--no-optional-locks", "-c", f"safe.directory={tree}", "-c", "core.fsmonitor=false",
             "-c", "core.untrackedCache=false", "-C", str(tree), *args],
            check=False, capture_output=True, text=True, timeout=60,
            env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
                 "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
                 "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_OPTIONAL_LOCKS": "0"}, **credentials,
        )
    except (KeyError, OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _no_new_privileges():
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS failed")


def _protected_snapshot_code(path: Path, digest: str) -> bytes:
    if str(path) != os.path.realpath(path) or not path.is_absolute():
        raise ValueError("noncanonical dependency")
    for parent in path.parents:
        s = os.lstat(parent)
        if s.st_uid != 0 or s.st_mode & 0o022 and not s.st_mode & stat.S_ISVTX:
            raise ValueError("unprotected dependency ancestor")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != 0 or s.st_mode & 0o022 or s.st_size > 1048576:
            raise ValueError("unprotected dependency")
        with os.fdopen(os.dup(fd), "rb") as source:
            raw = source.read(1048577)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("dependency hash mismatch")
        return raw
    finally:
        os.close(fd)


def _snapshot_source_state(candidate: Path, paths: Paths, target: str) -> str:
    """Call the same pinned root attestor used by the materializer/controller."""
    try:
        if os.geteuid() != 0 or not SHA.fullmatch(target):
            return "SNAPSHOT_ATTESTATION_BLOCKED"
        app = candidate / "apps/platform"
        names = [p.name for p in app.iterdir() if p.name.startswith("storage.pre-shared-")]
        raw = _protected_snapshot_code(paths.snapshot_helper, SNAPSHOT_HELPER_SHA256)
        _protected_snapshot_code(paths.snapshot_scanner, SNAPSHOT_SCANNER_SHA256)
        module = types.ModuleType("protected_snapshot_attestor")
        module.__file__ = str(paths.snapshot_helper)
        exec(compile(raw, str(paths.snapshot_helper), "exec"), module.__dict__)
        if names:
            if len(names) != 1 or not SNAPSHOT.fullmatch(names[0]):
                return "SNAPSHOT_ATTESTATION_BLOCKED"
            permitted = module.check_source(release_root=str(candidate), app_dir=str(app), expected_sha=target,
                                            shared_dir=str(paths.root / "shared/storage"), snapshot_name=names[0],
                                            state_dir=str(paths.snapshot_state), scanner_path=str(paths.snapshot_scanner))
            if permitted != "apps/platform/" + names[0] + "/":
                return "SNAPSHOT_ATTESTATION_BLOCKED"
        else:
            module.canonical(str(candidate)); module.canonical(str(app))
            fd = module.open_dir(app)
            try:
                fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                if any(n.startswith("storage.pre-shared-") for n in os.listdir(fd)):
                    return "SNAPSHOT_ATTESTATION_BLOCKED"
                module.git_identity(candidate, target)
                args = ["status", "--porcelain=v1", "-z", "--untracked-files=all"]
                if (app / "storage").is_symlink():
                    args += ["--", ".", ":(literal,exclude)apps/platform/storage"]
                if module.git_read(candidate, *args, text=False):
                    return "DIRTY"
                module.git_identity(candidate, target)
            finally:
                os.close(fd)
        return "PASS"
    except Exception:
        return "SNAPSHOT_ATTESTATION_BLOCKED"


# Minimum *source + built chunk* UI evidence for the owner-requested release.
# This is advisory and cannot replace staging/production runtime attestations.
UI_BUNDLE_FILES = (
    "apps/platform/resources/js/pages/services/codebridge-workspace.tsx",
    "apps/platform/resources/js/pages/services/codebridge.tsx",
    "apps/platform/routes/codebridge-workspace.php",
    "apps/platform/database/migrations/2026_10_29_120000_create_codebridge_workspace_tables.php",
    "apps/platform/database/migrations/2026_10_30_120000_create_codebridge_workspace_jobs.php",
    "apps/platform/database/migrations/2026_10_31_120000_create_codebridge_workspace_tool_proposals.php",
)
UI_BUNDLE_PAGE = "resources/js/pages/services/codebridge-workspace.tsx"


def _ui_bundle_state(candidate: Path) -> str:
    """Fail closed if a purported new-UI release contains only old/static assets."""
    try:
        for name in UI_BUNDLE_FILES:
            parent = candidate
            for component in Path(name).parts[:-1]:
                parent = parent / component
                if not stat.S_ISDIR(os.lstat(parent).st_mode):
                    return "SOURCE_UNSAFE"
            info = os.lstat(candidate / name)
            if not stat.S_ISREG(info.st_mode) or info.st_size == 0:
                return "SOURCE_UNSAFE"
    except OSError:
        return "SOURCE_MISSING"

    build = candidate / "apps/platform/public/build"
    if build.is_symlink() or not build.is_dir():
        return "BUILD_PATH_UNSAFE"
    manifest = build / "manifest.json"
    try:
        info = os.lstat(manifest)
        if (not stat.S_ISREG(info.st_mode) or info.st_size < 2
                or info.st_size > 8 * 1024 * 1024):
            return "MANIFEST_UNSAFE"
        data = json.loads(manifest.read_text("utf-8"))
    except (OSError, ValueError, UnicodeError):
        return "MANIFEST_INVALID"
    if not isinstance(data, dict):
        return "MANIFEST_INVALID"
    item = data.get(UI_BUNDLE_PAGE)
    if not isinstance(item, dict):
        return "CHUNK_NOT_IN_MANIFEST"
    rel = item.get("file")
    if not isinstance(rel, str):
        return "CHUNK_PATH_UNSAFE"
    # A manifest entry alone does not prove that the emitted JavaScript exists.
    relative = Path(rel)
    if (relative.is_absolute() or len(relative.parts) < 2
            or relative.parts[0] != "assets"
            or any(part in ("..", ".") for part in relative.parts)
            or relative.suffix != ".js"):
        return "CHUNK_PATH_UNSAFE"
    output = build / relative
    try:
        parent = build
        for component in relative.parts[:-1]:
            parent = parent / component
            if not stat.S_ISDIR(os.lstat(parent).st_mode):
                return "CHUNK_PATH_UNSAFE"
        info = os.lstat(output)
        if not stat.S_ISREG(info.st_mode) or info.st_size == 0:
            return "CHUNK_MISSING"
        if not output.resolve(strict=True).is_relative_to(build.resolve(strict=True)):
            return "CHUNK_PATH_UNSAFE"
    except OSError:
        return "CHUNK_MISSING"
    return "PASS"


def _web_user_can_read(path: Path) -> bool | None:
    """Read-only check that nginx's www-data can read a candidate file."""
    try:
        result = subprocess.run(["runuser", "-u", "www-data", "--", "test", "-r", str(path)],
                                check=False, capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.returncode == 0


def _attested_shared_storage(candidate: Path, paths: Paths) -> bool:
    """Exclude only a fixed, owner-controlled runtime storage symlink.

    Git sees the tracked storage/.gitignore placeholders as deleted after the
    physical directory becomes a symlink. Neither a general dirty-worktree
    exemption nor an unverified arbitrary symlink is acceptable.
    """
    shared = paths.root / "shared" / "storage"
    candidate_link = candidate / "apps/platform/storage"
    live_link = paths.root / "current" / "apps/platform/storage"
    try:
        owner = os.lstat(candidate).st_uid
        for folder in (paths.root, paths.root / "shared", shared, shared / "app"):
            info = os.lstat(folder)
            if (not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o022
                    or info.st_uid not in (0, owner)):
                return False
        for link in (candidate_link, live_link):
            info = os.lstat(link)
            if (not stat.S_ISLNK(info.st_mode) or info.st_uid not in (0, owner)
                    or os.readlink(link) != str(shared)):
                return False
    except OSError:
        return False
    return True


def _candidate_git_state(candidate: Path, paths: Paths, target: str = "", require_protected: bool = False) -> str:
    storage = candidate / "apps/platform/storage"
    if storage.is_symlink():
        if not _attested_shared_storage(candidate, paths):
            return "STORAGE_LINK_UNVERIFIED"
        if require_protected or any(p.name.startswith("storage.pre-shared-") for p in storage.parent.iterdir()):
            return _snapshot_source_state(candidate, paths, target)
        # All non-storage source remains under ordinary exact-HEAD Git status.
        # The only exempt path has *independent* fixed shared-link attestation.
        dirty = _git(candidate, "status", "--porcelain", "--untracked-files=normal",
                     "--", ".", ":(exclude)apps/platform/storage")
    else:
        if require_protected:
            return _snapshot_source_state(candidate, paths, target)
        dirty = _git(candidate, "status", "--porcelain")
    if dirty is None:
        return "GIT_STATUS_UNVERIFIED"
    return "DIRTY" if dirty else "PASS"


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
        app = candidate / "apps/platform"
        has_snapshot = app.is_dir() and any(p.name.startswith("storage.pre-shared-") for p in app.iterdir())
        # The root helper independently checks HEAD under kmjprod credentials.
        # Do not precede it with root Git in a service-writable repository.
        protected_route = require_root or has_snapshot and (app / "storage").is_symlink()
        head = target if protected_route else _git(candidate, "rev-parse", "HEAD")
        git_state = _candidate_git_state(candidate, paths, target, require_protected=require_root)
        missing = [item for item in ARTIFACTS
                   if not (candidate / item).is_file() or (candidate / item).stat().st_size <= 0]
        state = ("SHA_MISMATCH" if head != target else git_state
                 if git_state != "PASS" else "ARTIFACT_MISSING" if missing else "PASS")
        lines.append(f"CANDIDATE={state}")
        if state != "PASS":
            blockers.append("CANDIDATE_" + state)
        if state == "PASS":
            ui_state = _ui_bundle_state(candidate)
            lines.append("CANDIDATE_UI_BUNDLE=" + ui_state)
            if ui_state != "PASS":
                blockers.append("CANDIDATE_UI_BUNDLE_" + ui_state)
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
