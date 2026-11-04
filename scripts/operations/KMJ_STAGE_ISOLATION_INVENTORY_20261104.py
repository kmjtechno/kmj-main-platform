#!/usr/bin/env python3
"""READ-ONLY owner-root bounded stage mirror, group and PostgreSQL isolation inventory.

NO env/config contents printed, NO Nginx config body or DB records exposed,
NO production data reads, no services, writes, DDL, network or activation.
Fixed absolute paths/identifiers only; every subprocess uses a fixed argv
and outputs only redacted enum classes.
"""
from __future__ import annotations
import os
from pathlib import Path
import pwd
import grp
import re
import socket
import stat
import subprocess
import sys

SHA = "a9796a25a2801cd303a69f5ad468aa9a704e5fff"
STAGE_OLD = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
PROD_OLD = "platform-574e443a2c75"
BASE = Path("/var/lib/kmj-main-platform-stage-serving")
RELEASE = BASE / SHA
CODE = RELEASE / "code"
PUBLIC = RELEASE / "public"
RUNTIME = Path("/var/lib/kmj-main-platform-stage-runtime")
STAGE_SITE = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
PROD_SITE = Path("/home/kmjprod/current")
STAGE_OLD_ENV = Path("/home/kmjstage/releases") / STAGE_OLD / "apps/platform/.env"
STAGE_DATABASE = "kmj_stage_a9796a25"
STAGE_ROLE = "kmjstage_a9796a25"
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C",
       "PGHOST": "/var/run/postgresql", "PGPORT": "5432",
       "PGDATABASE": "postgres", "PGUSER": "postgres", "PGPASSFILE": "/dev/null"}


def emit(key: str, value: str) -> None:
    print(key + "=" + value, flush=True)


def metadata(path: Path) -> os.stat_result | None:
    try:
        return os.lstat(path)
    except OSError:
        return None


def path_group(path: Path, group: str, mode: int, expect_dir: bool = False) -> str:
    st = metadata(path)
    if st is None:
        return "MISSING"
    try:
        gid = grp.getgrnam(group).gr_gid
    except KeyError:
        return "GROUP_MISSING"
    istype = stat.S_ISDIR(st.st_mode) if expect_dir else stat.S_ISREG(st.st_mode)
    return ("MATCH" if istype and st.st_uid == 0 and st.st_gid == gid
            and stat.S_IMODE(st.st_mode) == mode and st.st_nlink >= 1
            and not st.st_mode & 0o022 else "UNTRUSTED")


def pointer(path: Path, choices: set[str]) -> str:
    try:
        st = os.lstat(path)
        if not stat.S_ISLNK(st.st_mode):
            return "UNTRUSTED"
        return "EXPECTED" if os.readlink(path) in choices else "DRIFT"
    except OSError:
        return "MISSING"


def test_as(user: str, option: str, path: Path) -> bool | None:
    if user not in {"kmjstage", "www-data"} or option not in {"-r", "-w", "-x"}:
        return None
    try:
        p = subprocess.run(["/usr/sbin/runuser", "-u", user, "--", "/usr/bin/test",
                            option, str(path)], capture_output=True, check=False,
                           env=ENV, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.returncode == 0 if p.returncode in (0, 1) else None


def access_class(user: str, path: Path, need_read: bool = True) -> str:
    read = test_as(user, "-r", path)
    write = test_as(user, "-w", path)
    if read is None or write is None:
        return "UNVERIFIED"
    if write:
        return "BLOCKED_WRITABLE"
    return "PASS_READ_NO_WRITE" if read else ("PASS_DENIED_NO_WRITE" if not need_read else "BLOCKED_NO_READ")


def pg_exists(table: str, column: str, identifier: str) -> str:
    allowed = {("pg_database", "datname", STAGE_DATABASE),
               ("pg_roles", "rolname", STAGE_ROLE)}
    if (table, column, identifier) not in allowed:
        return "UNVERIFIED"
    sql = f"SELECT COUNT(*) FROM pg_catalog.{table} WHERE {column} = '{identifier}';"
    try:
        p = subprocess.run(
            ["/usr/sbin/runuser", "-u", "postgres", "--", "/usr/bin/psql",
             "-X", "-Atq", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-c", sql],
            capture_output=True, check=False, env=ENV, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return "UNVERIFIED"
    if p.returncode != 0 or len(p.stdout) > 20:
        return "UNVERIFIED"
    return {"0": "ABSENT", "1": "ALREADY_EXISTS"}.get(p.stdout.decode("ascii", "replace").strip(), "UNVERIFIED")


def main() -> int:
    if (len(sys.argv) != 1 or os.geteuid() != 0 or
            socket.gethostname().split(".")[0].lower() != "kmj-elite"):
        emit("KMJ_STAGE_ISOLATION_INVENTORY", "BLOCKED_HOST_ROOT_ARGS")
        return 2
    emit("KMJ_STAGE_ISOLATION_INVENTORY", "READ_ONLY_V1")
    emit("PRODUCTION_POINTER", pointer(PROD_SITE, {
        "/home/kmjprod/releases/" + PROD_OLD, "releases/" + PROD_OLD}))
    emit("STAGING_POINTER", pointer(STAGE_SITE, {
        "/home/kmjstage/releases/" + STAGE_OLD + "/apps/platform",
        "../releases/" + STAGE_OLD + "/apps/platform"}))
    st = metadata(BASE)
    emit("STAGING_SERVING_PARENT", "ROOT_0711" if st is not None and
         stat.S_ISDIR(st.st_mode) and st.st_uid == 0 and
         stat.S_IMODE(st.st_mode) == 0o711 else "UNVERIFIED")
    st = metadata(RELEASE)
    emit("STAGING_SERVING_CANDIDATE", "ROOT_0711" if st is not None and
         stat.S_ISDIR(st.st_mode) and st.st_uid == 0 and
         stat.S_IMODE(st.st_mode) == 0o711 else "UNVERIFIED")
    emit("STAGING_CODE_DIRECTORY", path_group(CODE, "kmjstage", 0o550, True))
    emit("STAGING_STATIC_DIRECTORY", path_group(PUBLIC, "www-data", 0o550, True))
    code_file = CODE / "vendor/autoload.php"
    static_file = PUBLIC / "build/manifest.json"
    emit("STAGING_CODE_FILE", path_group(code_file, "kmjstage", 0o440))
    emit("STAGING_STATIC_FILE", path_group(static_file, "www-data", 0o440))
    emit("STAGING_FPM_CODE_READ", access_class("kmjstage", code_file))
    emit("STAGING_NGINX_STATIC_READ", access_class("www-data", static_file))
    emit("STAGING_FPM_STATIC_DENIAL", access_class("kmjstage", static_file, False))
    emit("STAGING_NGINX_CODE_DENIAL", access_class("www-data", code_file, False))
    st = metadata(RUNTIME)
    emit("STAGING_ISOLATED_RUNTIME_ROOT",
         "ABSENT" if st is None else "PRESENT_NEEDS_REVIEW")
    st = metadata(STAGE_OLD_ENV)
    emit("LEGACY_STAGE_ENV", "PRESENT_METADATA_ONLY" if st is not None and
         stat.S_ISREG(st.st_mode) else "UNVERIFIED")
    emit("STAGING_FRESH_DATABASE", pg_exists("pg_database", "datname", STAGE_DATABASE))
    emit("STAGING_FRESH_DB_ROLE", pg_exists("pg_roles", "rolname", STAGE_ROLE))
    emit("STAGING_CANDIDATE_ENV", "NOT_CREATED_BY_AUDIT")
    emit("STAGING_CANDIDATE_STORAGE", "NOT_CREATED_BY_AUDIT")
    emit("STAGING_OWNER_SEAL", "NOT_CREATED_BY_AUDIT")
    emit("STAGING_PROTECTED_APPROVAL", "NOT_MODIFIED")
    emit("STAGING_NGINX_ROUTE", "NOT_CHANGED")
    emit("STAGING_FPM_SERVICE", "NOT_CHANGED")
    emit("PRODUCTION_POINTER_CHANGED", "NO")
    emit("KMJ_STAGE_ISOLATION_INVENTORY", "READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
