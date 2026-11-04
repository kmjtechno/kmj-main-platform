#!/usr/bin/env python3
"""KMJ-elite: exact-scope candidate-only Laravel migration execution.

Default --inspect is READ-ONLY; --apply explicitly runs ONLY committed a979
code, as kmjstage (never root), against the NEW a979 isolated PostgreSQL DB.
No production/staging release, Nginx, FPM, secrets, backup, or pointer changes.
No migration rollback or destructive DB operations. On a failed migration,
retain only-candidate DB state for explicit review; no blind retry.
"""
from __future__ import annotations
import grp
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import subprocess
import sys

SHA = "a9796a25a2801cd303a69f5ad468aa9a704e5fff"
STAGE_OLD = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
PROD_OLD = "platform-574e443a2c75"
DB = "kmj_stage_a9796a25"
ROLE = "kmjstage_a9796a25"
MIRROR = Path("/var/lib/kmj-main-platform-stage-serving") / SHA
CODE = MIRROR / "code"
STATIC = MIRROR / "public"
ENV_FILE = CODE / ".env"
RUNTIME = Path("/var/lib/kmj-main-platform-stage-runtime") / SHA
STORAGE = RUNTIME / "storage"
POOL = Path("/etc/php/8.4/fpm/pool.d/kmjstage-a979.conf")
OLD_POOL = Path("/etc/php/8.4/fpm/pool.d/kmjstage.conf")
STAGE_LINK = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
PROD_LINK = Path("/home/kmjprod/current")
D_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
F_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
PG_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/var/lib/postgresql",
          "LANG": "C", "LC_ALL": "C", "PGHOST": "/var/run/postgresql",
          "PGPORT": "5432", "PGUSER": "postgres", "PGPASSFILE": "/dev/null"}


def emit(key: str, value: str) -> None:
    print(key + "=" + value, flush=True)


def stop(reason: str) -> None:
    emit("KMJ_STAGE_A979_MIGRATIONS", "BLOCKED_" + reason)
    raise SystemExit(2)


def pinned_pointers() -> bool:
    try:
        return (stat.S_ISLNK(os.lstat(STAGE_LINK).st_mode) and
                os.readlink(STAGE_LINK) in {
                    "/home/kmjstage/releases/" + STAGE_OLD + "/apps/platform",
                    "../releases/" + STAGE_OLD + "/apps/platform"}
                and stat.S_ISLNK(os.lstat(PROD_LINK).st_mode) and
                os.readlink(PROD_LINK) in {
                    "/home/kmjprod/releases/" + PROD_OLD, "releases/" + PROD_OLD})
    except OSError:
        return False


def open_trusted(path: Path) -> int:
    if not path.is_absolute() or ".." in path.parts:
        stop("PATH")
    fd = os.open("/", D_FLAGS)
    try:
        for item in path.parts[1:]:
            old = os.fstat(fd)
            if not stat.S_ISDIR(old.st_mode) or old.st_uid != 0 or old.st_mode & 0o022:
                stop("ROOT_ANCESTOR")
            new = os.open(item, D_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = new
        st = os.fstat(fd)
        if st.st_uid != 0 or not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o022:
            stop("ROOT_DIRECTORY")
        return fd
    except BaseException:
        os.close(fd)
        raise


def file_check(fd: int, name: str, mode: int, gid: int,
               limit: int = 150_000) -> bytes:
    child = os.open(name, F_FLAGS, dir_fd=fd)
    try:
        st = os.fstat(child)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or
                st.st_gid != gid or st.st_nlink != 1 or
                stat.S_IMODE(st.st_mode) != mode or
                not 0 < st.st_size <= limit):
            stop("SOURCE_FILE_METADATA")
        raw = os.read(child, limit + 1)
        after = os.fstat(child)
        if (len(raw) != st.st_size or
                (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns)
                != (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns)):
            stop("SOURCE_FILE_CHANGED")
        return raw
    finally:
        os.close(child)


def file_safe(path: Path, owner: int, mode: int) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return (stat.S_ISREG(st.st_mode) and st.st_uid == owner and
            st.st_nlink == 1 and stat.S_IMODE(st.st_mode) == mode)


def inspect_env(raw: bytes) -> bool:
    try:
        lines = raw.decode("ascii").splitlines()
        fields: dict[str, str] = {}
        for line in lines:
            if not line or "=" not in line:
                return False
            key, value = line.split("=", 1)
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,64}", key) or key in fields:
                return False
            fields[key] = value
        expected = {
            "APP_ENV": "staging", "APP_DEBUG": "false",
            "APP_URL": "https://staging.kmjtechno.com",
            "DB_CONNECTION": "pgsql", "DB_HOST": "127.0.0.1",
            "DB_DATABASE": DB, "DB_USERNAME": ROLE,
            "DB_PORT": "5432",
            "LARAVEL_STORAGE_PATH": str(STORAGE),
            "MAIL_MAILER": "log", "CODEBRIDGE_OAUTH_ENABLED": "false",
        }
        return (all(fields.get(k) == v for k, v in expected.items())
                and bool(re.fullmatch(r"[a-f0-9]{64}", fields.get("DB_PASSWORD", "")))
                and bool(re.fullmatch(r"base64:[A-Za-z0-9+/]{43}=", fields.get("APP_KEY", ""))))
    except UnicodeError:
        return False


def pg_query(statement: str, *, database: str = "postgres") -> bytes | None:
    if database not in ("postgres", DB):
        stop("UNEXPECTED_DATABASE")
    if statement not in (
        "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public';",
        "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public' AND tablename='migrations';",
        "SELECT count(*) FROM public.migrations;",
        f"SELECT count(*) FROM pg_catalog.pg_database d JOIN pg_catalog.pg_roles r ON r.oid=d.datdba "
        f"WHERE d.datname='{DB}' AND r.rolname='{ROLE}' AND NOT r.rolsuper "
        f"AND NOT r.rolcreatedb AND NOT r.rolcreaterole AND NOT r.rolreplication AND NOT r.rolinherit;",
    ):
        stop("SQL_NOT_ALLOWLISTED")
    try:
        p = subprocess.run(
            ["/usr/sbin/runuser", "-u", "postgres", "--", "/usr/bin/psql",
             "-X", "-Atq", "-v", "ON_ERROR_STOP=1", "-d", database,
             "-c", statement], capture_output=True, timeout=18,
            check=False, env=PG_ENV)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout.strip() if p.returncode == 0 and len(p.stdout) <= 16 else None


def catalog(stage_gid: int) -> None:
    scoped = (f"SELECT count(*) FROM pg_catalog.pg_database d JOIN pg_catalog.pg_roles r "
              f"ON r.oid=d.datdba WHERE d.datname='{DB}' AND r.rolname='{ROLE}' "
              f"AND NOT r.rolsuper AND NOT r.rolcreatedb AND NOT r.rolcreaterole "
              f"AND NOT r.rolreplication AND NOT r.rolinherit;")
    if pg_query(scoped) != b"1":
        stop("CANDIDATE_ROLE_DB_SCOPE")
    fd = open_trusted(MIRROR)
    try:
        if stat.S_IMODE(os.fstat(fd).st_mode) != 0o711:
            stop("CANDIDATE_RELEASE_TRUST")
    finally:
        os.close(fd)
    codefd = open_trusted(CODE)
    try:
        st = os.fstat(codefd)
        if st.st_gid != stage_gid or stat.S_IMODE(st.st_mode) != 0o550:
            stop("CODE_OWNER_GROUP")
        raw = file_check(codefd, ".env", 0o640, stage_gid, 20000)
        if not inspect_env(raw):
            stop("ENV_CANDIDATE_ONLY")
        for item in ("artisan", "vendor/autoload.php", "public/index.php"):
            # artisan is read-only, code executable bits may vary.
            child = os.stat(item, dir_fd=codefd, follow_symlinks=False)
            if not stat.S_ISREG(child.st_mode) or child.st_uid != 0 or child.st_mode & 0o022:
                stop("CODE_MISSING_OR_MUTABLE")
    finally:
        os.close(codefd)
    pfd = open_trusted(POOL.parent)
    try:
        fd = os.open(POOL.name, F_FLAGS, dir_fd=pfd)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or stat.S_IMODE(st.st_mode) != 0o644:
                stop("FPM_POOL_UNTRUSTED")
            raw = os.read(fd, 10000)
            if (b"[kmjstage-a979]\n" not in raw or
                b"env[LARAVEL_STORAGE_PATH] = " + os.fsencode(STORAGE) + b"\n" not in raw):
                stop("FPM_POOL_STORAGE_DRIFT")
        finally:
            os.close(fd)
    finally:
        os.close(pfd)
    st = os.lstat(STORAGE)
    uid = pwd.getpwnam("kmjstage").pw_uid
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != uid or st.st_gid != stage_gid or
            stat.S_IMODE(st.st_mode) != 0o700):
        stop("STORAGE_OWNER_DRIFT")


def ensure_private_views(stage_uid: int, stage_gid: int) -> None:
    # The stage bootstrap intentionally left Blade's compile directory absent.
    # Create it under the NEW stage-only storage as stage user (never root).
    framework = STORAGE / "framework"
    st = os.lstat(framework)
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != stage_uid or
            st.st_gid != stage_gid or stat.S_IMODE(st.st_mode) != 0o700):
        stop("FRAMEWORK_STORAGE_UNTRUSTED")
    views = framework / "views"
    try:
        st = os.lstat(views)
    except FileNotFoundError:
        try:
            p = subprocess.run(
                ["/usr/sbin/runuser", "-u", "kmjstage", "--",
                 "/usr/bin/mkdir", "-m", "0700", "--", str(views)],
                capture_output=True, timeout=10, check=False, env=PG_ENV)
        except (OSError, subprocess.TimeoutExpired):
            stop("VIEWS_CREATE_UNAVAILABLE")
        if p.returncode != 0:
            stop("VIEWS_CREATE_FAILED")
        st = os.lstat(views)
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != stage_uid or
            st.st_gid != stage_gid or stat.S_IMODE(st.st_mode) != 0o700):
        stop("VIEWS_OWNER_DRIFT")


def run_migrate() -> str:
    args = ["/usr/sbin/runuser", "-u", "kmjstage", "--",
            "/usr/bin/env", "-i", "HOME=/home/kmjstage", "LANG=C",
            "PATH=/usr/bin:/bin", "APP_ENV=staging",
            "LARAVEL_STORAGE_PATH=" + str(STORAGE),
            "/usr/bin/php8.4", "artisan", "migrate",
            "--force", "--no-interaction", "--no-ansi"]
    try:
        r = subprocess.run(args, cwd=CODE, capture_output=True, timeout=720,
                           check=False, env=PG_ENV)
    except (OSError, subprocess.TimeoutExpired):
        return "COMMAND_UNAVAILABLE_OR_TIMEOUT"
    if r.returncode != 0 or len(r.stdout) > 1_000_000 or len(r.stderr) > 1_000_000:
        return "MIGRATION_FAILED_REVIEW_REQUIRED"
    return "COMMAND_SUCCESS"


def main() -> int:
    if sys.argv[1:] not in (["--inspect"], ["--apply"]):
        stop("ARGUMENTS")
    if os.geteuid() != 0 or socket.gethostname().split(".")[0].lower() != "kmj-elite":
        stop("OWNER_ROOT_HOST")
    os.umask(0o077)
    if not pinned_pointers():
        stop("LIVE_POINTER_DRIFT")
    stage_gid = grp.getgrnam("kmjstage").gr_gid
    catalog(stage_gid)
    tables_before = pg_query("SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public';", database=DB)
    if tables_before != b"0":
        stop("DATABASE_ALREADY_MIGRATED_OR_PARTIAL")
    emit("STAGING_MIGRATION_TARGET", "EXACT_NEW_CANDIDATE_DB_ONLY")
    emit("STAGING_CANDIDATE_SHA", SHA)
    emit("STAGING_DB_BEFORE", "EMPTY_PUBLIC_SCHEMA")
    if sys.argv[1:] == ["--inspect"]:
        emit("KMJ_STAGE_A979_MIGRATIONS", "READ_ONLY_READY")
        emit("STAGING_DATABASE_MUTATIONS", "NONE")
        emit("PRODUCTION_POINTER", "UNCHANGED")
        return 0
    if not pinned_pointers():
        stop("LIVE_POINTER_RECHECK")
    ensure_private_views(pwd.getpwnam("kmjstage").pw_uid, stage_gid)
    emit("STAGING_MIGRATION_EXECUTION", "STARTED_UNPRIVILEGED")
    outcome = run_migrate()
    if outcome != "COMMAND_SUCCESS":
        emit("STAGING_MIGRATION_EXECUTION", outcome)
        stop("PARTIAL_DB_OWNER_REVIEW_REQUIRED")
    migrations_table = pg_query(
        "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public' AND tablename='migrations';",
        database=DB)
    count = pg_query("SELECT count(*) FROM public.migrations;", database=DB) if migrations_table == b"1" else None
    if count is None or not count.isdigit() or int(count) < 1:
        stop("MIGRATION_TABLE_ATTESTATION")
    if not pinned_pointers():
        stop("POINTER_DRIFT_AFTER_MIGRATION")
    emit("KMJ_STAGE_A979_MIGRATIONS", "PASS_CANDIDATE_DB_SCHEMA_ONLY")
    emit("STAGING_MIGRATION_TABLE", "PRESENT_NONEMPTY")
    emit("STAGING_MIGRATION_COUNT", str(int(count)))
    emit("STAGING_LEGACY_DB", "UNTOUCHED_BY_SCRIPT")
    emit("STAGING_PRODUCTION_DB", "UNTOUCHED_BY_SCRIPT")
    emit("STAGING_PHP_FPM", "NOT_RELOADED")
    emit("STAGING_NGINX", "NOT_CHANGED")
    emit("STAGING_UI_ACTIVATION", "NOT_ATTEMPTED")
    emit("STAGING_OWNER_SEAL", "NOT_CREATED")
    emit("PRODUCTION_POINTER", "UNCHANGED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError):
        emit("KMJ_STAGE_A979_MIGRATIONS", "BLOCKED_SYSTEM_OR_METADATA")
        raise SystemExit(2)
