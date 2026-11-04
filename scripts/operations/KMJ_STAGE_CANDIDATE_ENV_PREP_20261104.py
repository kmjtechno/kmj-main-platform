#!/usr/bin/env python3
"""Fixed-path create-only isolated staging ENV. NO activation or migrations.

Creates a single protected CODE .env root:kmjstage 0640, for candidate a979
and its NEW previously provisioned database. Never reads legacy production or
staging env. Runtime storage early FPM binding remains UNATTESTED. Fail-closed.
"""
from __future__ import annotations
import base64
import grp
import os
from pathlib import Path
import pwd
import re
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
BASE = Path("/var/lib/kmj-main-platform-stage-serving") / SHA
CODE = BASE / "code"
PUBLIC = BASE / "public"
RT = Path("/var/lib/kmj-main-platform-stage-runtime") / SHA
STORAGE = RT / "storage"
SECRET = RT / "credentials/postgres-password"
STAGE = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
PROD = Path("/home/kmjprod/current")
D_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
R_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
W_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
DB_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/var/lib/postgresql",
          "LANG": "C", "LC_ALL": "C", "PGHOST": "/var/run/postgresql",
          "PGPORT": "5432", "PGUSER": "postgres", "PGPASSFILE": "/dev/null"}


def emit(k: str, v: str) -> None:
    print(k + "=" + v, flush=True)


def stop(v: str) -> None:
    emit("KMJ_STAGE_ENV_PREP", "BLOCKED_" + v)
    raise SystemExit(2)


def expected_links() -> bool:
    try:
        return (
            stat.S_ISLNK(os.lstat(PROD).st_mode) and
            os.readlink(PROD) in {"/home/kmjprod/releases/" + OLD_PROD, "releases/" + OLD_PROD}
            and stat.S_ISLNK(os.lstat(STAGE).st_mode) and
            os.readlink(STAGE) in {
                "/home/kmjstage/releases/" + OLD_STAGE + "/apps/platform",
                "../releases/" + OLD_STAGE + "/apps/platform"})
    except OSError:
        return False


def open_root_chain(path: Path) -> int:
    fd = os.open("/", D_FLAGS)
    try:
        for component in path.parts[1:]:
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                stop("PARENT_TRUST")
            new = os.open(component, D_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = new
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            stop("DIRECTORY_TRUST")
        return fd
    except BaseException:
        os.close(fd)
        raise


def protected_dir(path: Path, mode: int, gid: int | None = None) -> None:
    fd = open_root_chain(path)
    try:
        st = os.fstat(fd)
        if (stat.S_IMODE(st.st_mode) != mode or
            (gid is not None and st.st_gid != gid)):
            stop("MODE_OR_GROUP")
        if any(v in ("system.posix_acl_access", "system.posix_acl_default") for v in os.listxattr(fd)):
            stop("UNEXPECTED_ACL")
    finally:
        os.close(fd)


def fresh_db_owned() -> bool:
    sql = (f"SELECT count(*) FROM pg_catalog.pg_database d JOIN pg_catalog.pg_roles r "
           f"ON d.datdba=r.oid WHERE d.datname='{DB}' AND r.rolname='{ROLE}';")
    try:
        r = subprocess.run(
            ["/usr/sbin/runuser", "-u", "postgres", "--", "/usr/bin/psql",
             "-X", "-Atq", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-c", sql],
            capture_output=True, timeout=12, env=DB_ENV, check=False)
        return r.returncode == 0 and r.stdout.strip() == b"1"
    except (OSError, subprocess.TimeoutExpired):
        return False


def private_password() -> str:
    protected_dir(SECRET.parent, 0o700)
    fd = os.open(SECRET, R_FLAGS)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or
            st.st_nlink != 1 or stat.S_IMODE(st.st_mode) != 0o600 or
            st.st_size != 65):
            stop("CREDENTIAL_INODE")
        buf = os.read(fd, 66)
        after = os.fstat(fd)
        if (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns) != (
                st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns):
            stop("CREDENTIAL_CHANGED")
        if not re.fullmatch(rb"[a-f0-9]{64}\n", buf):
            stop("CREDENTIAL_FORMAT")
        return buf.decode("ascii").strip()
    finally:
        os.close(fd)


def env_bytes(password: str, key: str) -> bytes:
    if not re.fullmatch(r"[a-f0-9]{64}", password):
        stop("PASSWORD_FORMAT")
    if not re.fullmatch(r"base64:[A-Za-z0-9+/]{43}=", key):
        stop("KEY_FORMAT")
    fields = [
        'APP_NAME="KMJ TECHNO STAGING"',
        "APP_ENV=staging",
        "APP_DEBUG=false",
        "APP_URL=https://staging.kmjtechno.com",
        "APP_KEY=" + key,
        "PUBLIC_INDEXING_ENABLED=false",
        "SESSION_DRIVER=database",
        "SESSION_DOMAIN=null",
        "SESSION_COOKIE=kmj_a979_staging_session",
        "SESSION_SECURE_COOKIE=true",
        "CACHE_STORE=database",
        "QUEUE_CONNECTION=database",
        "DB_CONNECTION=pgsql",
        "DB_HOST=127.0.0.1",
        "DB_PORT=5432",
        "DB_DATABASE=" + DB,
        "DB_USERNAME=" + ROLE,
        "DB_PASSWORD=" + password,
        "FILESYSTEM_DISK=local",
        "LARAVEL_STORAGE_PATH=" + str(STORAGE),
        "LOG_CHANNEL=single",
        "LOG_LEVEL=warning",
        "MAIL_MAILER=log",
        "CODEBRIDGE_OAUTH_ENABLED=false",
        "CODEBRIDGE_GATEWAY_URL=",
        "CODEBRIDGE_AGENT_PUBLIC_URL=",
        "CODEBRIDGE_OAUTH_SIGNING_KEY=",
    ]
    return ("\n".join(fields) + "\n").encode("ascii")


def create_new_env(basefd: int, payload: bytes, stage_gid: int) -> None:
    # Controlled directory-FD write, EXCL and no-follow, never truncate.
    try:
        os.stat(".env", dir_fd=basefd, follow_symlinks=False)
        stop("ENV_ALREADY_EXISTS")
    except FileNotFoundError:
        pass
    fd = os.open(".env", W_FLAGS, 0o600, dir_fd=basefd)
    try:
        os.fchown(fd, 0, stage_gid)
        written = 0
        while written < len(payload):
            n = os.write(fd, payload[written:])
            if n <= 0:
                stop("WRITE_SHORT")
            written += n
        os.fchmod(fd, 0o640)
        os.fsync(fd)
        s = os.fstat(fd)
        if (not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or
                s.st_gid != stage_gid or s.st_nlink != 1 or
                stat.S_IMODE(s.st_mode) != 0o640 or s.st_size != len(payload)):
            stop("FILE_ATTESTATION")
    finally:
        os.close(fd)


def main() -> int:
    if (len(sys.argv) != 1 or os.geteuid() != 0 or
            socket.gethostname().split(".")[0].lower() != "kmj-elite"):
        stop("HOST_ROOT_ARGS")
    os.umask(0o077)
    if not expected_links():
        stop("POINTER_DRIFT")
    stage = pwd.getpwnam("kmjstage")
    stage_gid = grp.getgrnam("kmjstage").gr_gid
    web_gid = grp.getgrnam("www-data").gr_gid
    if stage.pw_uid == 0 or stage_gid == 0 or web_gid == 0:
        stop("SYSTEM_GROUP")
    if not fresh_db_owned():
        stop("FRESH_DB_NOT_OWNED_BY_ROLE")
    protected_dir(BASE.parent, 0o711)
    protected_dir(BASE, 0o711)
    protected_dir(PUBLIC, 0o550, web_gid)
    protected_dir(RT.parent, 0o711)
    protected_dir(RT, 0o711)
    protected_dir(SECRET.parent, 0o700)
    s = os.lstat(STORAGE)
    if (not stat.S_ISDIR(s.st_mode) or s.st_uid != stage.pw_uid or
            s.st_gid != stage_gid or stat.S_IMODE(s.st_mode) != 0o700):
        stop("STORAGE_UNTRUSTED")
    codefd = open_root_chain(CODE)
    try:
        c = os.fstat(codefd)
        if stat.S_IMODE(c.st_mode) != 0o550 or c.st_gid != stage_gid:
            stop("CODE_UNTRUSTED")
        for filename in ("vendor/autoload.php", "public/build/manifest.json"):
            st = os.stat(filename, dir_fd=codefd, follow_symlinks=False)
            if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
                stop("SOURCE_ASSETS")
        password = private_password()
        key = "base64:" + base64.b64encode(secrets.token_bytes(32)).decode("ascii")
        contents = env_bytes(password, key)
        if not expected_links():
            stop("PRE_WRITE_POINTER_DRIFT")
        create_new_env(codefd, contents, stage_gid)
    finally:
        os.close(codefd)
    if not expected_links():
        stop("POST_WRITE_POINTER_DRIFT_REVIEW")
    emit("KMJ_STAGE_ENV_PREP", "PASS_CANDIDATE_ENV_ONLY")
    emit("STAGING_CANDIDATE_SHA", SHA)
    emit("STAGING_ENV_OWNER", "ROOT_GROUP_KMJSTAGE_0640")
    emit("STAGING_APP_KEY", "NEW_PRIVATE_NOT_PRINTED")
    emit("STAGING_DB_PASSWORD", "NEW_CANDIDATE_ONLY_NOT_PRINTED")
    emit("STAGING_DATABASE", "CANDIDATE_ONLY_NOT_MODIFIED")
    emit("STAGING_STORAGE_PATH", "ISOLATED_CANDIDATE_CONFIGURED")
    emit("STAGING_FPM_EARLY_STORAGE_BINDING", "NOT_ATTESTED")
    emit("STAGING_DATABASE_MIGRATIONS", "NOT_RUN")
    emit("STAGING_STORAGE_VIEWS", "NOT_COMPILED")
    emit("STAGING_SEAL", "NOT_CREATED")
    emit("STAGING_APPROVAL", "NOT_CREATED")
    emit("STAGING_NGINX_ROUTE", "UNCHANGED")
    emit("STAGING_FPM_SERVICE", "UNCHANGED")
    emit("STAGING_ACTIVATION", "NOT_ATTEMPTED")
    emit("PRODUCTION_POINTER", "UNCHANGED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError):
        emit("KMJ_STAGE_ENV_PREP", "BLOCKED_FS_OR_ACCOUNT_REVIEW")
        raise SystemExit(2)
