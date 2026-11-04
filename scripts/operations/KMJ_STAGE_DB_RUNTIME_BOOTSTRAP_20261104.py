#!/usr/bin/env python3
"""Owner-root CREATE-ONLY isolated staging DB, role and private runtime storage.

Exactly one new candidate-specific PostgreSQL role and database. Never reads
or edits existing stage/prod DB records, never runs Laravel/Composer/NGINX,
never changes production/stage pointers/services/SSH/approvals. Generates a
new random password in one root:root 0600 file, never prints secrets.
Refuses preexisting runtime path or database/role, and if ANY post-create
step fails, preserves evidence for explicit owner review (no destructive
auto-rollback, no silent retry).
"""
from __future__ import annotations
import os
from pathlib import Path
import grp
import pwd
import secrets
import socket
import stat
import subprocess
import sys

SHA = "a9796a25a2801cd303a69f5ad468aa9a704e5fff"
OLD_STAGE = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
OLD_PROD = "platform-574e443a2c75"
DB = "kmj_stage_a9796a25"
ROLE = "kmjstage_a9796a25"
SOURCE_PARENT = Path("/var/lib/kmj-main-platform-stage-releases")
MIRROR = Path("/var/lib/kmj-main-platform-stage-serving") / SHA
RUNTIME_PARENT = Path("/var/lib/kmj-main-platform-stage-runtime")
RUNTIME = RUNTIME_PARENT / SHA
SECRET_DIR = RUNTIME / "credentials"
SECRET_FILE = SECRET_DIR / "postgres-password"
STORAGE = RUNTIME / "storage"
STAGE_SITE = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
PROD_SITE = Path("/home/kmjprod/current")
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
SECRET_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/var/lib/postgresql",
       "LANG": "C", "LC_ALL": "C", "PGPASSFILE": "/dev/null",
       "PGDATABASE": "postgres", "PGHOST": "/var/run/postgresql",
       "PGPORT": "5432", "PGUSER": "postgres"}


def emit(key: str, value: str) -> None:
    print(key + "=" + value, flush=True)


def deny(reason: str) -> None:
    emit("KMJ_STAGE_RUNTIME_BOOTSTRAP", "BLOCKED_" + reason)
    raise SystemExit(2)


def pointer(path: Path, expected: set[str]) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(path).st_mode) and os.readlink(path) in expected
    except OSError:
        return False


def exact_pointers() -> bool:
    return (pointer(PROD_SITE, {"/home/kmjprod/releases/" + OLD_PROD,
                                "releases/" + OLD_PROD}) and
            pointer(STAGE_SITE, {"/home/kmjstage/releases/" + OLD_STAGE + "/apps/platform",
                                 "../releases/" + OLD_STAGE + "/apps/platform"}))


def root_dir(path: Path, mode: int | None = None) -> os.stat_result:
    if not path.is_absolute() or ".." in path.parts:
        deny("PATH")
    cur = Path("/")
    for item in path.parts[1:]:
        cur = cur / item
        st = os.lstat(cur)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            deny("ROOT_DIRECTORY_TRUST")
    st = os.lstat(path)
    if mode is not None and stat.S_IMODE(st.st_mode) != mode:
        deny("ROOT_DIRECTORY_MODE")
    if any(x in ("system.posix_acl_access", "system.posix_acl_default") for x in os.listxattr(path, follow_symlinks=False)):
        deny("ROOT_DIRECTORY_ACL")
    return st


def mirror_ready() -> None:
    root_dir(SOURCE_PARENT, 0o700)
    root_dir(MIRROR.parent, 0o711)
    root_dir(MIRROR, 0o711)
    for name, group, directory, mode in (
        ("code", "kmjstage", True, 0o550),
        ("public", "www-data", True, 0o550),
        ("code/vendor/autoload.php", "kmjstage", False, 0o440),
        ("public/build/manifest.json", "www-data", False, 0o440),
    ):
        path = MIRROR / name
        st = os.lstat(path)
        expected_gid = grp.getgrnam(group).gr_gid
        if (st.st_uid != 0 or st.st_gid != expected_gid
            or stat.S_IMODE(st.st_mode) != mode or st.st_mode & 0o022
            or not (stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode))):
            deny("MIRROR_METADATA_UNTRUSTED")


def pg(argv: list[str], statement: bytes | None = None) -> bytes:
    # Constant executable, role and flags. Secret is supplied to psql via
    # private stdin, NEVER as process argv/environment or printed output.
    allowed = ["-X", "-Atq", "-v", "ON_ERROR_STOP=1", "-d", "postgres"]
    if argv[:len(allowed)] != allowed:
        deny("POSTGRES_ARGS")
    full = ["/usr/sbin/runuser", "-u", "postgres", "--", "/usr/bin/psql"] + argv
    try:
        p = subprocess.run(full, input=statement, capture_output=True, check=False,
                           timeout=30, env=ENV)
    except (OSError, subprocess.TimeoutExpired):
        deny("POSTGRES_UNAVAILABLE")
    if p.returncode != 0 or len(p.stdout) > 200:
        deny("POSTGRES_COMMAND_FAILED")
    return p.stdout.strip()


def catalog(name: str) -> int:
    if name == "role":
        sql = f"SELECT count(*) FROM pg_catalog.pg_roles WHERE rolname='{ROLE}'"
    elif name == "db":
        sql = f"SELECT count(*) FROM pg_catalog.pg_database WHERE datname='{DB}'"
    else:
        deny("CATALOG_SCOPE")
    out = pg(["-X", "-Atq", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-c", sql])
    if out not in (b"0", b"1"):
        deny("CATALOG_UNEXPECTED")
    return int(out)


def database_owned_by_role() -> bool:
    q = (f"SELECT count(*) FROM pg_catalog.pg_database d JOIN pg_catalog.pg_roles r "
         f"ON d.datdba=r.oid WHERE d.datname='{DB}' AND r.rolname='{ROLE}'")
    return pg(["-X", "-Atq", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-c", q]) == b"1"


def sql_stdin(sql: str) -> None:
    # No SQL/secret rendered on any error; psql output is captured and dropped.
    pg(["-X", "-Atq", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-f", "-"],
       sql.encode("ascii"))


def new_dir(parent: Path, name: str, mode: int) -> Path:
    if "/" in name or not name or name in (".", ".."):
        deny("DIRECTORY_NAME")
    parentfd = os.open(parent, DIR_FLAGS)
    try:
        os.mkdir(name, mode=mode, dir_fd=parentfd)
        fd = os.open(name, DIR_FLAGS, dir_fd=parentfd)
        try:
            st = os.fstat(fd)
            if st.st_uid != 0 or stat.S_IMODE(st.st_mode) != mode:
                deny("CREATED_DIR_METADATA")
        finally:
            os.close(fd)
    finally:
        os.close(parentfd)
    return parent / name


def private_password() -> str:
    password = secrets.token_hex(32)
    fd = os.open(SECRET_FILE, SECRET_FLAGS, 0o600)
    try:
        info = os.fstat(fd)
        if info.st_uid != 0 or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
            deny("PRIVATE_SECRET_METADATA")
        os.write(fd, (password + "\n").encode("ascii"))
        os.fsync(fd)
    finally:
        os.close(fd)
    return password


def storage_tree(stage_uid: int, stage_gid: int) -> None:
    # Construct under root control then assign each subtree to stage user.
    new_dir(RUNTIME, "storage", 0o700)
    dirs = (
        "app", "app/private", "app/public",
        "framework", "framework/cache", "framework/cache/data",
        "framework/sessions", "logs",
    )
    for d in dirs:
        parent, child = d.rsplit("/", 1) if "/" in d else ("", d)
        new_dir(STORAGE / parent, child, 0o700)
    # All paths are newly created under a root-private, unshared parent.
    # These are mutable storage directories, not signed executable code.
    for d in reversed(dirs):
        os.chown(STORAGE / d, stage_uid, stage_gid, follow_symlinks=False)
    os.chown(STORAGE, stage_uid, stage_gid, follow_symlinks=False)


def main() -> int:
    if (len(sys.argv) != 1 or os.geteuid() != 0
        or socket.gethostname().split(".")[0].lower() != "kmj-elite"):
        deny("HOST_ROOT_ARGS")
    os.umask(0o077)
    if not exact_pointers():
        deny("POINTER_DRIFT")
    mirror_ready()
    root_dir(RUNTIME_PARENT.parent)
    if os.path.lexists(RUNTIME_PARENT):
        deny("RUNTIME_PARENT_ALREADY_EXISTS")
    if catalog("role") != 0 or catalog("db") != 0:
        deny("DB_ROLE_ALREADY_PRESENT")
    stage_uid = pwd.getpwnam("kmjstage").pw_uid
    stage_gid = grp.getgrnam("kmjstage").gr_gid
    if stage_uid == 0 or stage_gid == 0 or pwd.getpwnam("postgres").pw_uid == 0:
        deny("SYSTEM_USER_UNSAFE")
    # Created paths are exclusively NEW. Any failed later step leaves a
    # root-only password witness for manual recovery, never silently retry.
    new_dir(RUNTIME_PARENT.parent, RUNTIME_PARENT.name, 0o700)
    new_dir(RUNTIME_PARENT, SHA, 0o700)
    new_dir(RUNTIME, "credentials", 0o700)
    password = private_password()
    storage_tree(stage_uid, stage_gid)
    if not exact_pointers():
        deny("POINTER_DRIFT_BEFORE_SQL")
    sql_stdin(f"CREATE ROLE {ROLE} WITH LOGIN NOSUPERUSER NOCREATEDB "
              f"NOCREATEROLE NOREPLICATION NOINHERIT CONNECTION LIMIT 8 "
              f"PASSWORD '{password}';")
    sql_stdin(f"CREATE DATABASE {DB} OWNER {ROLE};")
    sql_stdin(f"REVOKE ALL ON DATABASE {DB} FROM PUBLIC;")
    if not (catalog("role") == 1 and catalog("db") == 1 and database_owned_by_role()):
        deny("POSTGRES_READBACK_FAILED")
    if not exact_pointers():
        deny("POINTER_DRIFT_AFTER_SQL")
    # Finalize newly owned root-only credential directory and root candidate
    # to traverse-only; user can access ONLY stage-owned storage subtree.
    os.chmod(RUNTIME, 0o711, follow_symlinks=False)
    os.chmod(RUNTIME_PARENT, 0o711, follow_symlinks=False)
    emit("KMJ_STAGE_RUNTIME_BOOTSTRAP", "PASS_ISOLATED_DB_STORAGE_ONLY")
    emit("STAGING_CANDIDATE_SHA", SHA)
    emit("STAGING_DB_ROLE", "NEW_RESTRICTED_ROLE")
    emit("STAGING_DATABASE", "NEW_ISOLATED_DATABASE")
    emit("STAGING_PUBLIC_DATABASE_GRANTS", "REVOKED")
    emit("STAGING_DB_SECRET", "ROOT_ONLY_PRIVATE_NOT_PRINTED")
    emit("STAGING_STORAGE", "NEW_STAGE_USER_ONLY")
    emit("STAGING_STORAGE_VIEWS", "NOT_COMPILED")
    emit("STAGING_RUNTIME_ENV", "NOT_CREATED")
    emit("STAGING_DB_MIGRATIONS", "NOT_RUN")
    emit("STAGING_FPM_CONFIG", "UNCHANGED")
    emit("STAGING_NGINX_ROUTE", "UNCHANGED")
    emit("STAGING_SEAL", "NOT_CREATED")
    emit("STAGING_APPROVAL", "NOT_CREATED")
    emit("STAGING_ACTIVATION", "NOT_ATTEMPTED")
    emit("PRODUCTION_POINTER", "UNCHANGED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError):
        emit("KMJ_STAGE_RUNTIME_BOOTSTRAP", "BLOCKED_IO_OR_ACCOUNT_REVIEW_REQUIRED")
        raise SystemExit(2)
