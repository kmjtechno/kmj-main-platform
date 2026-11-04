#!/usr/bin/env python3
"""Fixed read-only staging pre-migration gate; no secrets in output.

Reads only newly created candidate .env/password, exact metadata,
candidate-only PostgreSQL system catalogs, FPM pool key existence and a
non-mutating Laravel Application storagePath() probe under kmjstage.
No Artisan execution, app routes, database records, DDL, service changes,
network, activation, production env access or raw config/log/secret output.
"""
from __future__ import annotations
import grp
import hashlib
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import subprocess
import sys

SHA = "a9796a25a2801cd303a69f5ad468aa9a704e5fff"
OLD_STAGE = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
OLD_PROD = "platform-574e443a2c75"
CODE = Path("/var/lib/kmj-main-platform-stage-serving") / SHA / "code"
ENVFILE = CODE / ".env"
STORAGE = Path("/var/lib/kmj-main-platform-stage-runtime") / SHA / "storage"
SECRET = STORAGE.parent / "credentials/postgres-password"
DB = "kmj_stage_a9796a25"
ROLE = "kmjstage_a9796a25"
POOL = Path("/etc/php/8.4/fpm/pool.d/kmjstage.conf")
PROD = Path("/home/kmjprod/current")
STAGE = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
ROOTFILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
PROCESS_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/var/lib/postgresql",
               "LANG": "C", "LC_ALL": "C", "PGHOST": "/var/run/postgresql",
               "PGPORT": "5432", "PGPASSFILE": "/dev/null", "PGUSER": "postgres"}
PHP_PROBE = r'''$base="/var/lib/kmj-main-platform-stage-serving/a9796a25a2801cd303a69f5ad468aa9a704e5fff/code";
require $base."/vendor/autoload.php";
$app=new \Illuminate\Foundation\Application($base);
$actual=$app->storagePath();
$want="/var/lib/kmj-main-platform-stage-runtime/a9796a25a2801cd303a69f5ad468aa9a704e5fff/storage";
echo ($actual===$want && is_dir($actual)) ? "MATCH\n" : "MISMATCH\n";
'''


def emit(key: str, value: str) -> None:
    print(key + "=" + value, flush=True)


def expected_links() -> bool:
    try:
        return (stat.S_ISLNK(os.lstat(PROD).st_mode) and
                os.readlink(PROD) in {"/home/kmjprod/releases/" + OLD_PROD,
                                     "releases/" + OLD_PROD} and
                stat.S_ISLNK(os.lstat(STAGE).st_mode) and
                os.readlink(STAGE) in {
                    "/home/kmjstage/releases/" + OLD_STAGE + "/apps/platform",
                    "../releases/" + OLD_STAGE + "/apps/platform"})
    except OSError:
        return False


def trusted_file(path: Path, uid: int, gid: int | None, mode: int, max_bytes: int) -> bytes | None:
    # Fixed paths; no user paths or filename arguments permitted.
    try:
        fd = os.open(path, ROOTFILE_FLAGS)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != uid
                or (gid is not None and st.st_gid != gid)
                or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) != mode
                or not 0 < st.st_size <= max_bytes):
            return None
        result = os.read(fd, max_bytes + 1)
        later = os.fstat(fd)
        if (len(result) != st.st_size
                or (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns)
                != (later.st_dev, later.st_ino, later.st_mtime_ns, later.st_ctime_ns)):
            return None
        return result
    finally:
        os.close(fd)


def parse_env(raw: bytes | None, password: bytes | None) -> str:
    if raw is None or password is None:
        return "UNVERIFIED"
    try:
        text = raw.decode("ascii")
        lines = text.splitlines()
        if len(lines) > 60 or any(not line or "=" not in line for line in lines):
            return "INVALID"
        rows: dict[str, str] = {}
        for line in lines:
            k, v = line.split("=", 1)
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", k) or k in rows:
                return "INVALID"
            rows[k] = v
        fixed = {
            "APP_ENV": "staging", "APP_DEBUG": "false",
            "APP_URL": "https://staging.kmjtechno.com",
            "DB_CONNECTION": "pgsql", "DB_HOST": "127.0.0.1",
            "DB_PORT": "5432", "DB_DATABASE": DB, "DB_USERNAME": ROLE,
            "LARAVEL_STORAGE_PATH": str(STORAGE),
            "MAIL_MAILER": "log", "CODEBRIDGE_OAUTH_ENABLED": "false",
            "PUBLIC_INDEXING_ENABLED": "false",
        }
        if any(rows.get(k) != v for k, v in fixed.items()):
            return "CANDIDATE_SCOPE_MISMATCH"
        db_secret = rows.get("DB_PASSWORD", "")
        if (not re.fullmatch(r"[a-f0-9]{64}", db_secret)
                or not re.fullmatch(rb"[a-f0-9]{64}\n", password)
                or not hashlib.compare_digest(db_secret.encode(), password.strip())):
            return "SECRET_MISMATCH"
        if not re.fullmatch(r"base64:[A-Za-z0-9+/]{43}=", rows.get("APP_KEY", "")):
            return "APPKEY_UNVERIFIED"
        return "CANDIDATE_SCOPE_MATCH"
    except (ValueError, UnicodeError):
        return "INVALID"


def fixed_run(args: list[str], timeout: int = 12) -> bytes | None:
    try:
        p = subprocess.run(args, capture_output=True, check=False, timeout=timeout,
                           env=PROCESS_ENV)
        if p.returncode != 0 or len(p.stdout) > 128:
            return None
        return p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None


def db_catalog() -> str:
    sql = (f"SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_database d "
           f"JOIN pg_roles r ON r.oid=d.datdba "
           f"WHERE d.datname='{DB}' AND r.rolname='{ROLE}' "
           f"AND NOT r.rolsuper AND NOT r.rolcreatedb AND NOT r.rolcreaterole "
           f"AND NOT r.rolreplication AND NOT r.rolinherit AND r.rolcanlogin "
           f"AND r.rolconnlimit=8) THEN 'MATCH' ELSE 'MISMATCH' END;")
    out = fixed_run(["/usr/sbin/runuser", "-u", "postgres", "--",
                     "/usr/bin/psql", "-X", "-Atq", "-v", "ON_ERROR_STOP=1",
                     "-d", "postgres", "-c", sql])
    return "RESTRICTED_OWNER_MATCH" if out == b"MATCH" else "UNVERIFIED_OR_DRIFT"


def database_empty() -> str:
    sql = ("SELECT COUNT(*) FROM pg_catalog.pg_tables WHERE "
           "schemaname='public';")
    out = fixed_run(["/usr/sbin/runuser", "-u", "postgres", "--", "/usr/bin/psql",
                     "-X", "-Atq", "-v", "ON_ERROR_STOP=1",
                     "-d", DB, "-c", sql])
    return "EMPTY_PUBLIC_SCHEMA" if out == b"0" else ("NOT_EMPTY" if out is not None else "UNVERIFIED")


def test_as(user: str, opt: str, path: Path) -> bool | None:
    if user not in {"kmjstage", "www-data"} or opt not in {"-r", "-w"}:
        return None
    args = ["/usr/sbin/runuser", "-u", user, "--",
            "/usr/bin/test", opt, str(path)]
    try:
        p = subprocess.run(args, capture_output=True, env=PROCESS_ENV, check=False, timeout=8)
        return p.returncode == 0 if p.returncode in (0, 1) else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def storage_identity() -> str:
    try:
        st = os.lstat(STORAGE)
        uid = pwd.getpwnam("kmjstage").pw_uid
        gid = grp.getgrnam("kmjstage").gr_gid
        return ("STAGE_USER_0700" if stat.S_ISDIR(st.st_mode) and st.st_uid == uid
                and st.st_gid == gid and stat.S_IMODE(st.st_mode) == 0o700
                else "UNTRUSTED")
    except (OSError, KeyError):
        return "UNVERIFIED"


def fpm_pool_binding() -> str:
    raw = trusted_file(POOL, 0, None, 0o644, 50000)
    if raw is None:
        return "POOL_NOT_ATTESTED"
    lines = []
    for line in raw.decode("utf-8", "replace").splitlines():
        item = line.strip()
        if item and not item.startswith((";", "#")):
            m = re.fullmatch(r"env\[LARAVEL_STORAGE_PATH\]\s*=\s*(.*)", item)
            if m:
                lines.append(m.group(1).strip())
    if not lines:
        return "MISSING"
    return ("EXACT_MATCH" if len(lines) == 1 and lines[0] == str(STORAGE)
            else "DRIFT_OR_DUPLICATE")


def early_php_probe() -> str:
    # Test vendor autoload + Foundation Application only, never app routes,
    # Laravel artisan, database queries, migrations or HTTP serving.
    args = ["/usr/sbin/runuser", "-u", "kmjstage", "--", "/usr/bin/env", "-i",
            "LARAVEL_STORAGE_PATH=" + str(STORAGE),
            "HOME=/home/kmjstage", "PATH=/usr/bin:/bin", "APP_ENV=staging",
            "/usr/bin/php8.4", "-d", "display_errors=0",
            "-r", PHP_PROBE]
    # Do not print PHP stdout/stderr; only classify a bounded exact sentinel.
    try:
        p = subprocess.run(args, capture_output=True, check=False, timeout=20,
                           env=PROCESS_ENV)
        if p.returncode != 0 or len(p.stdout) > 40:
            return "UNVERIFIED"
        return "EXPLICIT_EARLY_BIND_MATCH" if p.stdout.strip() == b"MATCH" else "MISMATCH"
    except (OSError, subprocess.TimeoutExpired):
        return "UNVERIFIED"


def main() -> int:
    if (len(sys.argv) != 1 or os.geteuid() != 0
            or socket.gethostname().split(".")[0].lower() != "kmj-elite"):
        emit("KMJ_STAGE_PREMIGRATION_GATE", "BLOCKED_HOST_ROOT_ARGS")
        return 2
    emit("KMJ_STAGE_PREMIGRATION_GATE", "READ_ONLY_V1")
    emit("STAGING_POINTER", "EXPECTED" if expected_links() else "DRIFT")
    emit("PRODUCTION_POINTER", "EXPECTED" if expected_links() else "DRIFT")
    gid = grp.getgrnam("kmjstage").gr_gid
    raw = trusted_file(ENVFILE, 0, gid, 0o640, 20000)
    pw = trusted_file(SECRET, 0, None, 0o600, 80)
    emit("STAGING_CANDIDATE_ENV", parse_env(raw, pw))
    emit("STAGING_STORAGE_OWNER", storage_identity())
    emit("STAGING_ENV_STAGE_READ", "YES" if test_as("kmjstage", "-r", ENVFILE) is True else "NO_OR_UNVERIFIED")
    emit("STAGING_ENV_STAGE_WRITE", "DENIED" if test_as("kmjstage", "-w", ENVFILE) is False else "WRITABLE_OR_UNVERIFIED")
    emit("STAGING_ENV_NGINX_READ", "DENIED" if test_as("www-data", "-r", ENVFILE) is False else "ACCESS_OR_UNVERIFIED")
    emit("STAGING_NEW_DB_ROLE", db_catalog())
    emit("STAGING_NEW_DB_SCHEMA", database_empty())
    emit("STAGING_FPM_EARLY_STORAGE_SETTING", fpm_pool_binding())
    emit("STAGING_UNPRIVILEGED_LARAVEL_STORAGE_PROBE", early_php_probe())
    emit("STAGING_FPM_CONFIG", "NOT_MODIFIED")
    emit("STAGING_DB_MIGRATIONS", "NOT_RUN")
    emit("STAGING_VIEWS", "NOT_COMPILED")
    emit("STAGING_PROTECTED_SEAL", "NOT_MODIFIED")
    emit("STAGING_OWNER_APPROVAL", "NOT_MODIFIED")
    emit("STAGING_NGINX_ROUTE", "NOT_MODIFIED")
    emit("PRODUCTION_MUTATIONS", "NONE")
    emit("KMJ_STAGE_PREMIGRATION_GATE", "READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError):
        emit("KMJ_STAGE_PREMIGRATION_GATE", "BLOCKED_METADATA_UNVERIFIED")
        raise SystemExit(2)
