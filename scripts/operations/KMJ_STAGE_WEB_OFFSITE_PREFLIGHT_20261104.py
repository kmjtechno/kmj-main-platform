#!/usr/bin/env python3
"""KMJ owner-root READ-ONLY staging Nginx and legacy offsite unit preflight.

All inspect targets are fixed. No config contents, paths from systemd,
secrets, keys, journal output, executable arguments or environment are
printed. No network, writes, service starts, release switches or approvals.
"""
from __future__ import annotations
import os
import re
import socket
import stat
import subprocess
import sys
from pathlib import Path

EXPECTED_PROD = "platform-574e443a2c75"
EXPECTED_STAGE = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
ANCHOR = Path("/var/lib/kmj-main-platform-stage-releases")
STAGE_HOME = Path("/home/kmjstage")
PROD_LINK = Path("/home/kmjprod/current")
STAGE_LINK = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
BACKUP_UNIT = "kmj-elite-offsite-backup.service"
CONFIG_REFERENCE = b"/etc/kmj-codebridge/offsite-sftp.conf"
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "LANG": "C"}
EXEC = re.compile(r"(?:^|\s)path=(/[A-Za-z0-9._/@+-]{1,240})(?=[\s;]|$)")
SERVER = re.compile(rb"(?m)^[ \t]*server_name[ \t]+([^;\n]{1,500})[ \t]*;")
MAX_NGINX_BYTES = 4 * 1024 * 1024


def emit(k: str, v: str) -> None:
    print(k + "=" + v, flush=True)


def link_expected(path: Path, options: set[str]) -> str:
    try:
        info = os.lstat(path)
        if not stat.S_ISLNK(info.st_mode):
            return "UNTRUSTED_NOT_SYMLINK"
        return "EXPECTED" if os.readlink(path) in options else "DRIFT"
    except OSError:
        return "UNVERIFIED"


def anchor_status() -> str:
    try:
        st = os.lstat(ANCHOR)
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != 0
            or stat.S_IMODE(st.st_mode) != 0o700):
            return "UNTRUSTED"
        names = os.listxattr(ANCHOR, follow_symlinks=False)
        if any(n in ("system.posix_acl_access", "system.posix_acl_default")
               for n in names):
            return "UNTRUSTED_ACL"
        return "ROOT_0700_PRESENT"
    except OSError:
        return "MISSING_OR_UNVERIFIED"


def run_fixed(argv: list[str], *, timeout: int, max_bytes: int) -> bytes | None:
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout,
                           env=ENV, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0 or len(p.stdout) > max_bytes:
        return None
    return p.stdout


def nginx_classify(raw: bytes | None) -> dict[str, str]:
    if raw is None:
        return {
            "STAGING_NGINX_CONFIG": "UNVERIFIED",
            "STAGING_NGINX_HOST": "UNVERIFIED",
            "STAGING_NGINX_STAGE_HOME_HINT": "UNVERIFIED",
            "STAGING_NGINX_ROOT_ANCHOR_HINT": "UNVERIFIED",
        }
    stage = 0
    for match in SERVER.finditer(raw):
        labels = match.group(1).split()
        if b"staging.kmjtechno.com" in labels:
            stage += 1
    return {
        "STAGING_NGINX_CONFIG": "PARSED_ADVISORY_ONLY",
        "STAGING_NGINX_HOST": ("ONE_OR_MORE_MATCHES" if stage else "NOT_SEEN"),
        "STAGING_NGINX_STAGE_HOME_HINT":
            ("REFERENCED" if b"/home/kmjstage/" in raw else "NOT_SEEN"),
        "STAGING_NGINX_ROOT_ANCHOR_HINT":
            ("REFERENCED" if os.fsencode(ANCHOR) in raw else "NOT_SEEN"),
    }


def protected_exec_reference(raw: str | None) -> str:
    if not raw or len(raw) > 4096 or raw.count("path=") != 1:
        return "NOT_ATTESTED"
    paths = EXEC.findall(raw)
    if len(paths) != 1:
        return "NOT_ATTESTED"
    path = Path(paths[0])
    if ".." in path.parts:
        return "NOT_ATTESTED"
    parent = path.parent
    while True:
        try:
            p = os.lstat(parent)
        except OSError:
            return "NOT_ATTESTED"
        if not stat.S_ISDIR(p.st_mode) or p.st_uid != 0 or p.st_mode & 0o022:
            return "NOT_ATTESTED"
        if parent == Path("/"):
            break
        parent = parent.parent
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return "NOT_ATTESTED"
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1 or st.st_mode & 0o022 or st.st_size > 1024 * 1024:
            return "NOT_ATTESTED"
        data = os.read(fd, 1024 * 1024 + 1)
        if len(data) != st.st_size:
            return "NOT_ATTESTED"
        return ("SFTP_CONFIG_PATH_REFERENCED_ONLY" if CONFIG_REFERENCE in data
                else "SFTP_CONFIG_NOT_REFERENCED")
    finally:
        os.close(fd)


def unit_prop(name: str) -> str | None:
    if name not in {"ExecMainStatus", "ActiveState", "Result", "ExecStart", "DropInPaths", "User"}:
        return None
    out = run_fixed(["/usr/bin/systemctl", "show", BACKUP_UNIT,
                     "--property=" + name, "--value", "--no-pager"], timeout=8,
                    max_bytes=8192)
    if out is None:
        return None
    try:
        return out.decode("utf-8", "strict").strip()
    except UnicodeError:
        return None


def main() -> int:
    if len(sys.argv) != 1 or os.geteuid() != 0 or socket.gethostname().split(".")[0].lower() != "kmj-elite":
        emit("KMJ_STAGE_WEB_OFFSITE_PREFLIGHT", "BLOCKED_HOST_ROOT_ARGS")
        return 2
    emit("KMJ_STAGE_WEB_OFFSITE_PREFLIGHT", "READ_ONLY_V1")
    emit("ROOT_STAGE_ANCHOR", anchor_status())
    emit("PRODUCTION_POINTER", link_expected(PROD_LINK, {
        "/home/kmjprod/releases/" + EXPECTED_PROD,
        "releases/" + EXPECTED_PROD,
    }))
    emit("STAGING_POINTER", link_expected(STAGE_LINK, {
        f"/home/kmjstage/releases/{EXPECTED_STAGE}/apps/platform",
        f"../releases/{EXPECTED_STAGE}/apps/platform",
    }))
    n = nginx_classify(run_fixed(["/usr/sbin/nginx", "-T", "-q"],
                                 timeout=15, max_bytes=MAX_NGINX_BYTES))
    for k, v in n.items():
        emit(k, v)
    try:
        st = os.lstat(STAGE_HOME / "htdocs")
        owner = "KMJSTAGE" if st.st_uid == __import__("pwd").getpwnam("kmjstage").pw_uid else ("ROOT" if st.st_uid == 0 else "OTHER")
        emit("STAGING_HTDOCS_OWNER", owner if stat.S_ISDIR(st.st_mode) else "UNTRUSTED")
    except (OSError, KeyError):
        emit("STAGING_HTDOCS_OWNER", "UNVERIFIED")
    status = unit_prop("ExecMainStatus")
    result = unit_prop("Result")
    emit("LEGACY_OFFSITE_EXIT255", "YES" if status == "255" and result == "exit-code" else "NO_OR_UNVERIFIED")
    drop = unit_prop("DropInPaths")
    emit("LEGACY_OFFSITE_DROPINS", "UNVERIFIED" if drop is None else ("PRESENT" if drop else "ABSENT"))
    emit("LEGACY_OFFSITE_EXEC_REFERENCE", protected_exec_reference(unit_prop("ExecStart")))
    user = unit_prop("User")
    emit("LEGACY_OFFSITE_USER", ("ROOT_OR_DEFAULT" if user in ("", "root")
                                else "NONROOT_OR_UNVERIFIED"))
    emit("STAGING_NGINX_ROUTING_AUTHORITY", "NOT_VERIFIED")
    emit("STAGING_CANDIDATE", "NOT_ATTESTED")
    emit("STAGING_PROTECTED_APPROVAL", "NOT_MODIFIED")
    emit("STAGING_WEB_CHANGES", "NONE")
    emit("PRODUCTION_CHANGES", "NONE")
    emit("OFFSITE_SERVICE_CHANGES", "NONE")
    emit("KMJ_STAGE_WEB_OFFSITE_PREFLIGHT", "READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
