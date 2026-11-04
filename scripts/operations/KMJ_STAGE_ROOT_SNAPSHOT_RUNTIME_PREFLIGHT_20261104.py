#!/usr/bin/env python3
"""Fixed, owner-root read-only staging runtime feasibility assessment.

Checks the root-only staging CODE snapshot, FPM role/socket, approved
current pointers, and immutable serving boundary. No user-controlled
code execution, secrets, database connections, service changes, raw
config output, backup action, links, chmod, chown, or deployment.
Every observed PASS is narrow; no production/staging activation approval.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import subprocess
import sys

EXACT_SHA = "a9796a25a2801cd303a69f5ad468aa9a704e5fff"
STAGE_OLD = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
PROD_OLD = "platform-574e443a2c75"
ANCHOR = Path("/var/lib/kmj-main-platform-stage-releases")
RELEASE = ANCHOR / EXACT_SHA
APP = RELEASE / "apps/platform"
POOL = Path("/etc/php/8.4/fpm/pool.d/kmjstage.conf")
STAGE_SOCKET = Path("/run/php/kmjstage-php84-fpm.sock")
STAGE_LINK = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
PROD_LINK = Path("/home/kmjprod/current")
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"}
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


def emit(k: str, v: str) -> None:
    print(k + "=" + v, flush=True)


def root_dir(path: Path, mode: int | None = None) -> str:
    try:
        st = os.lstat(path)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            return "UNTRUSTED"
        if mode is not None and stat.S_IMODE(st.st_mode) != mode:
            return "MODE_MISMATCH"
        return "ROOT_OWNED_PRESENT"
    except OSError:
        return "ABSENT_OR_UNREADABLE"


def fixed_pointer(path: Path, allowed: set[str]) -> str:
    try:
        return ("EXPECTED" if stat.S_ISLNK(os.lstat(path).st_mode)
                and os.readlink(path) in allowed else "DRIFT")
    except OSError:
        return "UNVERIFIED"


def read_fixed_root_file(path: Path, maxbytes: int) -> bytes | None:
    # All root anchor and FPM configuration ancestors are root controlled.
    parent = path.parent
    while True:
        try:
            s = os.lstat(parent)
        except OSError:
            return None
        if not stat.S_ISDIR(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022:
            return None
        if parent == Path("/"):
            break
        parent = parent.parent
    try:
        fd = os.open(path, FILE_FLAGS)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0
                or st.st_mode & 0o022 or st.st_nlink != 1
                or not 0 < st.st_size <= maxbytes):
            return None
        raw = os.read(fd, maxbytes + 1)
        after = os.fstat(fd)
        if (len(raw) != st.st_size or
                (st.st_ino, st.st_dev, st.st_mtime_ns, st.st_ctime_ns) !=
                (after.st_ino, after.st_dev, after.st_mtime_ns, after.st_ctime_ns)):
            return None
        return raw
    finally:
        os.close(fd)


def app_snapshot_status() -> str:
    if root_dir(ANCHOR, 0o700) != "ROOT_OWNED_PRESENT":
        return "BLOCKED_ANCHOR"
    if root_dir(RELEASE) != "ROOT_OWNED_PRESENT":
        return "MISSING_OR_UNTRUSTED"
    if root_dir(APP) != "ROOT_OWNED_PRESENT":
        return "MISSING_OR_UNTRUSTED_APP"
    head = read_fixed_root_file(RELEASE / ".git/HEAD", 100)
    if head is None or head.strip() != EXACT_SHA.encode("ascii"):
        return "SOURCE_HEAD_UNVERIFIED"
    asset = read_fixed_root_file(APP / "public/build/manifest.json", 2_000_000)
    if asset is None:
        return "BUILD_MANIFEST_UNVERIFIED"
    try:
        manifest = json.loads(asset)
        row = manifest.get("resources/js/pages/services/codebridge-workspace.tsx")
        chunk = row.get("file") if isinstance(row, dict) else None
        if (not isinstance(chunk, str) or
                not re.fullmatch(r"assets/[A-Za-z0-9._/-]{1,220}", chunk)
                or ".." in Path(chunk).parts):
            return "AI_WORKSPACE_ASSET_NOT_ATTESTED"
    except (UnicodeError, ValueError, AttributeError):
        return "BUILD_MANIFEST_INVALID"
    if read_fixed_root_file(APP / "public/build" / chunk, 100_000_000) is None:
        return "AI_WORKSPACE_ASSET_UNVERIFIED"
    if read_fixed_root_file(APP / "vendor/autoload.php", 100_000) is None:
        return "VENDOR_AUTOLOAD_UNVERIFIED"
    if (APP / ".env").exists() or (APP / ".env").is_symlink():
        return "RUNTIME_ENV_PRESENT_NEEDS_REVIEW"
    return "SOURCE_ARTIFACTS_PRESENT_UNSEALED"


def fpm_pool_status() -> str:
    data = read_fixed_root_file(POOL, 50000)
    if data is None:
        return "POOL_NOT_ROOT_ATTESTED"
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        return "POOL_UNREADABLE"
    # Compare exact active key=value entries; never emit the values.
    parsed: dict[str, str] = {}
    for original in text.splitlines():
        line = original.strip()
        if not line or line.startswith((";", "#")) or "=" not in line:
            continue
        key, value = map(str.strip, line.split("=", 1))
        if key in {"user", "group", "listen"}:
            if key in parsed:
                return "POOL_DUPLICATE_SETTING"
            parsed[key] = value
    return ("STAGE_USER_GROUP_SOCKET_MATCH" if parsed ==
            {"user": "kmjstage", "group": "kmjstage", "listen": str(STAGE_SOCKET)}
            else "POOL_EFFECTIVE_ROLE_UNVERIFIED")


def service_state(unit: str) -> str:
    if unit not in ("nginx.service", "php8.4-fpm.service"):
        return "UNSUPPORTED"
    try:
        proc = subprocess.run(["/usr/bin/systemctl", "show", unit, "-P", "ActiveState"],
                              capture_output=True, timeout=8, check=False, env=FIXED_ENV)
        if proc.returncode != 0 or len(proc.stdout) > 120:
            return "UNVERIFIED"
        return "ACTIVE" if proc.stdout.strip() == b"active" else "NOT_ACTIVE"
    except (OSError, subprocess.TimeoutExpired):
        return "UNVERIFIED"


def main() -> int:
    if (len(sys.argv) != 1 or os.geteuid() != 0
            or socket.gethostname().split(".")[0].lower() != "kmj-elite"):
        emit("KMJ_ROOT_STAGE_RUNTIME_PREFLIGHT", "BLOCKED_HOST_ROOT_ARGS")
        return 2
    emit("KMJ_ROOT_STAGE_RUNTIME_PREFLIGHT", "READ_ONLY_V1")
    emit("PRODUCTION_POINTER", fixed_pointer(PROD_LINK, {
        "/home/kmjprod/releases/" + PROD_OLD, "releases/" + PROD_OLD}))
    emit("STAGING_POINTER", fixed_pointer(STAGE_LINK, {
        "/home/kmjstage/releases/" + STAGE_OLD + "/apps/platform",
        "../releases/" + STAGE_OLD + "/apps/platform"}))
    emit("ROOT_STAGE_ANCHOR", root_dir(ANCHOR, 0o700))
    emit("ROOT_STAGE_SOURCE", app_snapshot_status())
    emit("STAGE_FPM_POOL", fpm_pool_status())
    try:
        sk = os.lstat(STAGE_SOCKET)
        emit("STAGE_FPM_SOCKET", "PRESENT" if stat.S_ISSOCK(sk.st_mode) else "NOT_SOCKET")
    except OSError:
        emit("STAGE_FPM_SOCKET", "NOT_VERIFIED")
    emit("NGINX_SERVICE", service_state("nginx.service"))
    emit("PHP_FPM_SERVICE", service_state("php8.4-fpm.service"))
    # With anchor mode 0700 and UID0 owner, non-root stage user has no traversal.
    # This is intentional until a separately reviewed FPM-only access design.
    try:
        uid = pwd.getpwnam("kmjstage").pw_uid
        anchor = os.lstat(ANCHOR)
        status = ("BLOCKED_ROOT_ONLY_0700" if uid != 0 and anchor.st_uid == 0
                  and stat.S_IMODE(anchor.st_mode) == 0o700 else "UNVERIFIED")
    except (OSError, KeyError):
        status = "UNVERIFIED"
    emit("STAGE_FPM_SOURCE_ACCESS", status)
    emit("ROOT_STAGE_ENV", "NOT_PREPARED_BY_THIS_AUDIT")
    emit("STAGE_DATABASE_ISOLATION", "NOT_ATTESTED")
    emit("STAGE_OWNER_SEAL", "NOT_ATTESTED")
    emit("STAGE_APPROVAL", "NOT_ATTESTED")
    emit("ROOT_STAGE_NGINX_ROUTE", "NOT_INSTALLED_BY_THIS_AUDIT")
    emit("STAGING_MUTATIONS", "NONE")
    emit("PRODUCTION_MUTATIONS", "NONE")
    emit("KMJ_ROOT_STAGE_RUNTIME_PREFLIGHT", "READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
