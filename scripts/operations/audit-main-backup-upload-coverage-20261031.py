#!/usr/bin/env python3
"""Read-only P0 coverage check for the witnessed local storage/app backup.

This is an advisory check, NOT a production approval, filesystem snapshot,
remote-retention proof, or authenticated upload QA. Never prints file names,
contents, credentials, .env, or product/customer identifiers.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys
import tarfile


class CoverageError(Exception):
    pass


def reject(reason: str) -> None:
    raise CoverageError(reason)


def digest(stream) -> str:
    h = hashlib.sha256()
    for part in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(part)
    return h.hexdigest()


def open_directory_chain(root: Path) -> int:
    """Open every ancestor without following symlinks; return the pinned root FD."""
    if not root.is_absolute():
        reject("STORAGE_APP_PATH_NOT_ABSOLUTE")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        fd = os.open("/", flags)
        for component in root.parts[1:]:
            try:
                child = os.open(component, flags, dir_fd=fd)
            finally:
                os.close(fd)
            fd = child
        return fd
    except OSError:
        reject("STORAGE_APP_PATH_UNSAFE")


def snapshot_storage(root: Path) -> dict[str, tuple[int, str]]:
    # Pin every ancestor and the storage root by descriptor. A symlink
    # inserted between the advisory layout check and the scan cannot redirect
    # a root-owned auditor to an unrelated tree.
    root_fd = open_directory_chain(root)
    result: dict[str, tuple[int, str]] = {}

    def fail_walk(error: OSError) -> None:
        reject("LIVE_STORAGE_SCAN_ERROR")

    try:
        for parent, dirs, files, dirfd in os.fwalk(
            ".", dir_fd=root_fd, follow_symlinks=False, onerror=fail_walk
        ):
            for name in dirs:
                info = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
                if not stat.S_ISDIR(info.st_mode):
                    reject("LIVE_STORAGE_SYMLINK_OR_SPECIAL_DIR")
            for name in files:
                before_path = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
                if not stat.S_ISREG(before_path.st_mode):
                    reject("LIVE_STORAGE_NOT_REGULAR")
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                fd = os.open(name, flags, dir_fd=dirfd)
                try:
                    before = os.fstat(fd)
                    if (not stat.S_ISREG(before.st_mode) or
                        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                         before.st_ctime_ns) !=
                        (before_path.st_dev, before_path.st_ino, before_path.st_size,
                         before_path.st_mtime_ns, before_path.st_ctime_ns)):
                        reject("LIVE_STORAGE_REPLACED")
                    with os.fdopen(os.dup(fd), "rb") as stream:
                        checksum = digest(stream)
                    after = os.fstat(fd)
                    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                        before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size,
                        after.st_mtime_ns, after.st_ctime_ns):
                        reject("LIVE_STORAGE_CHANGED")
                    rel = (Path(parent) / name).as_posix()
                    result[rel] = (before.st_size, checksum)
                finally:
                    os.close(fd)
    finally:
        os.close(root_fd)
    return result


def archive_storage(bundle: Path) -> dict[str, tuple[int, str]]:
    with tarfile.open(bundle, "r:gz") as outer:
        members = outer.getmembers()
        required = {"database.dump", "storage.tar.gz", "metadata.txt", "SHA256SUMS"}
        if len(members) != 4 or {m.name for m in members} != required:
            reject("LOCAL_BUNDLE_LAYOUT")
        if any(not m.isfile() for m in members):
            reject("LOCAL_BUNDLE_NONREGULAR")
        entry = outer.extractfile("storage.tar.gz")
        if entry is None:
            reject("STORAGE_ARCHIVE_MISSING")
        found: dict[str, tuple[int, str]] = {}
        seen: set[str] = set()
        with entry, tarfile.open(fileobj=entry, mode="r|gz") as inner:
            for member in inner:
                name = member.name.rstrip("/")
                if (not name or name.startswith("/") or "\\" in name
                    or any(p in (".", "..", "") for p in name.split("/"))
                    or name in seen):
                    reject("STORAGE_MEMBER_UNSAFE")
                seen.add(name)
                if name == ".env":
                    if not member.isfile():
                        reject("ENV_MEMBER_INVALID")
                    continue
                if name != "storage/app" and not name.startswith("storage/app/"):
                    reject("STORAGE_MEMBER_OUTSIDE_APP")
                if not (member.isdir() or member.isfile()):
                    reject("STORAGE_MEMBER_NOT_REGULAR")
                if member.isfile():
                    if name == "storage/app":
                        reject("STORAGE_APP_NOT_DIRECTORY")
                    stream = inner.extractfile(member)
                    if stream is None:
                        reject("STORAGE_MEMBER_UNREADABLE")
                    with stream:
                        checksum = digest(stream)
                    found[name[len("storage/app/"):]] = (member.size, checksum)
        return found


def verify_real_directories(paths: tuple[Path, ...]) -> None:
    """Reject symlinked ancestors before any root-owned live storage scan."""
    for path in paths:
        try:
            mode = path.lstat().st_mode
        except OSError:
            reject("LIVE_LAYOUT_UNVERIFIED")
        if not stat.S_ISDIR(mode):
            reject("LIVE_LAYOUT_SYMLINK_OR_SPECIAL")


# The protected live storage-switch migration uses ONE explicit shared root.
# Do not generalize this exception to arbitrary symlinks or other upload trees.
SHARED_ROOT = Path("/home/kmjprod/shared/storage")


def select_live_storage(release: Path, app: Path, public: Path) -> tuple[Path, str, tuple[int, ...] | None]:
    """Choose only a physical in-release tree or the exact preapproved shared link.

    The original auditor rejected ANY storage ancestor symlink; that made its
    backup-coverage check unusable after the owner-approved shared-storage
    migration. Every OTHER symlink still blocks. This remains advisory: a
    moving live tree is not an atomic filesystem snapshot.
    """
    verify_real_directories((release.parent, release, release / "apps", app, public))
    storage = app / "storage"
    try:
        info = storage.lstat()
    except OSError:
        reject("LIVE_STORAGE_LAYOUT_UNVERIFIED")
    if stat.S_ISDIR(info.st_mode):
        verify_real_directories((storage, storage / "app"))
        return storage / "app", "RELEASE_LOCAL", None
    if not stat.S_ISLNK(info.st_mode):
        reject("LIVE_STORAGE_LAYOUT_UNSAFE")
    release_uid = release.lstat().st_uid
    if info.st_uid not in (0, release_uid) or os.readlink(storage) != str(SHARED_ROOT):
        reject("LIVE_STORAGE_LINK_NOT_APPROVED")
    # The selected physical target must not depend on another symlink. It
    # must also be under an owner-controlled, non-group/world-writable chain.
    for folder in (SHARED_ROOT.parent, SHARED_ROOT, SHARED_ROOT / "app"):
        try:
            st = folder.lstat()
        except OSError:
            reject("SHARED_STORAGE_NOT_READY")
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid not in (0, release_uid)
                or st.st_mode & 0o022):
            reject("SHARED_STORAGE_CHAIN_UNSAFE")
    if storage.resolve(strict=True) != SHARED_ROOT:
        reject("SHARED_STORAGE_LINK_CHANGED")
    return SHARED_ROOT / "app", "EXACT_SHARED_LINK", (
        info.st_dev, info.st_ino, info.st_uid, info.st_mtime_ns, info.st_ctime_ns
    )


def recheck_storage_link(app: Path, stamp: tuple[int, ...] | None) -> None:
    if stamp is None:
        return
    path = app / "storage"
    try:
        now = path.lstat()
        current = (now.st_dev, now.st_ino, now.st_uid, now.st_mtime_ns, now.st_ctime_ns)
        if (not stat.S_ISLNK(now.st_mode) or current != stamp
                or os.readlink(path) != str(SHARED_ROOT)
                or path.resolve(strict=True) != SHARED_ROOT):
            reject("SHARED_STORAGE_LINK_CHANGED")
    except OSError:
        reject("SHARED_STORAGE_LINK_CHANGED")


# Only an EXACT tracked Laravel placeholder, with NO public-upload payload
# anywhere under storage/app/public, can justify an absent public/storage link.
# That is a narrow advisory classification; it does not prove all other
# customer upload locations or authorize production activation.
PUBLIC_PLACEHOLDER = b"*\\n!.gitignore\\n".replace(b"\\n", b"\n")
PUBLIC_PLACEHOLDER_STAT = (
    len(PUBLIC_PLACEHOLDER), hashlib.sha256(PUBLIC_PLACEHOLDER).hexdigest()
)


def public_storage_link_status(link: Path, expected: Path,
                               live: dict[str, tuple[int, str]],
                               parity: bool) -> str:
    try:
        info = link.lstat()
    except FileNotFoundError:
        info = None
    except OSError:
        return "UNVERIFIABLE"
    if info is not None:
        if not stat.S_ISLNK(info.st_mode):
            return "MISSING_OR_DIFFERENT"
        try:
            if expected.is_dir() and link.resolve(strict=True) == expected:
                return "EXPECTED"
        except (OSError, RuntimeError):
            pass
        return "MISSING_OR_DIFFERENT"
    if (parity and expected.is_dir()
            and {name: value for name, value in live.items()
                 if name.startswith("public/")} == {
                     "public/.gitignore": PUBLIC_PLACEHOLDER_STAT
                 }):
        # Recheck the absence: an actor might have created a public/storage
        # path during the live-source scan. No symlink of any other kind is
        # accepted by this exception.
        try:
            link.lstat()
        except FileNotFoundError:
            return "NOT_REQUIRED_PLACEHOLDER_ONLY"
        except OSError:
            return "UNVERIFIABLE"
    return "MISSING_OR_DIFFERENT"


def audit(release: Path, bundle: Path, witness: Path, candidate: str,
          current: str) -> dict[str, str]:
    if not re.fullmatch(r"[0-9a-f]{40}", candidate):
        reject("CANDIDATE_INVALID")
    if not re.fullmatch(r"platform-[0-9a-f]{12}", current):
        reject("RELEASE_INVALID")
    with witness.open("r", encoding="utf-8") as stream:
        record = json.load(stream)
    if (record.get("approvedSha") != candidate or
        record.get("currentRelease") != current):
        reject("WITNESS_IDENTITY_MISMATCH")
    with bundle.open("rb") as stream:
        if digest(stream) != record.get("backupSha256"):
            reject("LOCAL_BUNDLE_SHA_MISMATCH")
    archived = archive_storage(bundle)
    app = release / "apps/platform"
    public = app / "public"
    live_root, layout, link_stamp = select_live_storage(release, app, public)
    expected = live_root / "public"
    if expected.exists() or expected.is_symlink():
        verify_real_directories((expected,))
    live = snapshot_storage(live_root)
    # A service actor could replace the symbolic link while our protected FD
    # scanner is active; never call the source-to-archive parity a PASS then.
    recheck_storage_link(app, link_stamp)
    link = public / "storage"
    alternate = any((public / name).exists() or (public / name).is_symlink()
                    for name in ("uploads", "media", "product-images"))
    parity = archived == live
    link_status = public_storage_link_status(link, expected, live, parity)
    return {
        "LIVE_STORAGE_LAYOUT": layout,
        "ARCHIVED_STORAGE_FILES": str(len(archived)),
        "ARCHIVED_STORAGE_BYTES": str(sum(size for size, _ in archived.values())),
        "LIVE_STORAGE_FILES": str(len(live)),
        "LIVE_STORAGE_BYTES": str(sum(size for size, _ in live.values())),
        "STORAGE_APP_CONTENT_PARITY": "PASS" if parity else "MISMATCH",
        "PUBLIC_STORAGE_LINK": link_status,
        "ALTERNATE_PUBLIC_UPLOAD_DIRS": "PRESENT_REVIEW" if alternate else "NONE_OBSERVED",
        "ALL_CUSTOMER_UPLOAD_LOCATIONS_VERIFIED": "NO",
        "OWNER_AUTHENTICATED_UPLOAD_QA": "NOT_VERIFIED",
        "PRODUCTION_RELEASE_MODIFIED": "NO",
    }


def protected(path: Path) -> bool:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1:
            return False
        if stat.S_IMODE(info.st_mode) != 0o600:
            return False
        parent = path.parent
        while True:
            p = parent.lstat()
            if (not stat.S_ISDIR(p.st_mode) or p.st_uid != 0
                or stat.S_IMODE(p.st_mode) & 0o022):
                return False
            if parent == parent.parent:
                return True
            parent = parent.parent
    except OSError:
        return False


def main(argv: list[str]) -> int:
    if (len(argv) != 4 or argv[0] != "--candidate-sha" or
        argv[2] != "--expected-release" or
        not re.fullmatch(r"[0-9a-f]{40}", argv[1]) or
        not re.fullmatch(r"platform-[0-9a-f]{12}", argv[3])):
        print("BACKUP_UPLOAD_AUDIT=BLOCKED_ARGUMENTS")
        return 2
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        print("BACKUP_UPLOAD_AUDIT=BLOCKED_OPERATOR")
        return 2
    candidate, current = argv[1], argv[3]
    pointer = Path("/home/kmjprod/current")
    release = Path("/home/kmjprod/releases") / current
    backup = Path("/var/backups/kmj-platform")
    bundle = backup / f"pre-deploy-{candidate[:12]}.tar.gz"
    witness = backup / f"pre-deploy-{candidate[:12]}.json"
    try:
        if not pointer.is_symlink() or pointer.resolve(strict=True) != release:
            reject("CURRENT_POINTER_MISMATCH")
        if not protected(bundle) or not protected(witness):
            reject("BACKUP_WITNESS_NOT_ROOT_PROTECTED")
        result = audit(release, bundle, witness, candidate, current)
        for key, value in result.items():
            print(f"{key}={value}")
        if (result["STORAGE_APP_CONTENT_PARITY"] != "PASS" or
            result["PUBLIC_STORAGE_LINK"] not in ("EXPECTED", "NOT_REQUIRED_PLACEHOLDER_ONLY") or
            result["ALTERNATE_PUBLIC_UPLOAD_DIRS"] != "NONE_OBSERVED"):
            print("BACKUP_UPLOAD_AUDIT=REVIEW_REQUIRED")
            return 2
        print("BACKUP_UPLOAD_AUDIT=STORAGE_APP_ONLY_PASS")
        return 0
    except (CoverageError, OSError, ValueError, KeyError, tarfile.TarError,
            json.JSONDecodeError) as exc:
        reason = str(exc)
        if not re.fullmatch(r"[A-Z0-9_]+", reason):
            reason = "READ_FAILED"
        print("BACKUP_UPLOAD_AUDIT=BLOCKED_" + reason)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
