#!/usr/bin/env python3
"""KMJ-elite: create one NEW candidate-only FPM pool config, not active.

The old staging pool/socket is never edited or reloaded. A new pool has a
separate UNIX socket and an EARLY LARAVEL_STORAGE_PATH environment variable
for exact candidate a979. Validates the entire on-disk PHP-FPM config with
php-fpm8.4 -t (captured, no raw output), but never reloads the service.

Only permitted filesystem mutation is one new root-owned pool config. On a
validation failure, the script removes only its own newly created inode if
it still matches; other configurations and live services remain untouched.
"""
from __future__ import annotations
import hashlib
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
OLD_STAGE = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
OLD_PROD = "platform-574e443a2c75"
FPM_DIR = Path("/etc/php/8.4/fpm/pool.d")
OLD_POOL = FPM_DIR / "kmjstage.conf"
NEW_NAME = "kmjstage-a979.conf"
NEW_POOL = FPM_DIR / NEW_NAME
NEW_SOCKET = Path("/run/php/kmjstage-a979-php84-fpm.sock")
OLD_SOCKET = Path("/run/php/kmjstage-php84-fpm.sock")
BASE = Path("/var/lib/kmj-main-platform-stage-serving") / SHA
CODE = BASE / "code"
ENV_FILE = CODE / ".env"
RUNTIME = Path("/var/lib/kmj-main-platform-stage-runtime") / SHA
STORAGE = RUNTIME / "storage"
STAGE_SITE = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
PROD_SITE = Path("/home/kmjprod/current")
DIRFLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILEFLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
CREATEFLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "LANG": "C"}


def emit(k: str, v: str) -> None:
    print(k + "=" + v, flush=True)


def fail(reason: str) -> None:
    emit("KMJ_STAGE_FPM_POOL_PREP", "BLOCKED_" + reason)
    raise SystemExit(2)


def check_pointer(path: Path, targets: set[str]) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(path).st_mode) and os.readlink(path) in targets
    except OSError:
        return False


def original_pointers() -> bool:
    return (check_pointer(PROD_SITE, {
        "/home/kmjprod/releases/" + OLD_PROD, "releases/" + OLD_PROD}) and
        check_pointer(STAGE_SITE, {
            "/home/kmjstage/releases/" + OLD_STAGE + "/apps/platform",
            "../releases/" + OLD_STAGE + "/apps/platform"}))


def root_chain_fd(path: Path) -> int:
    if not path.is_absolute() or ".." in path.parts:
        fail("UNTRUSTED_PATH")
    fd = os.open("/", DIRFLAGS)
    try:
        for part in path.parts[1:]:
            old = os.fstat(fd)
            if not stat.S_ISDIR(old.st_mode) or old.st_uid != 0 or old.st_mode & 0o022:
                fail("ROOT_PARENT")
            nxt = os.open(part, DIRFLAGS, dir_fd=fd)
            os.close(fd)
            fd = nxt
        st = os.fstat(fd)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            fail("ROOT_PARENT")
        if any(name in ("system.posix_acl_access", "system.posix_acl_default")
               for name in os.listxattr(fd)):
            fail("ROOT_PARENT_ACL")
        return fd
    except BaseException:
        os.close(fd)
        raise


def file_bytes(parentfd: int, name: str, mode: int, owner: int = 0,
               gid: int | None = None, limit: int = 64000) -> tuple[bytes, os.stat_result]:
    fd = os.open(name, FILEFLAGS, dir_fd=parentfd)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != owner
                or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) != mode
                or (gid is not None and st.st_gid != gid)
                or st.st_size <= 0 or st.st_size > limit):
            fail("FILE_METADATA")
        raw = os.read(fd, limit + 1)
        after = os.fstat(fd)
        if (len(raw) != st.st_size or
            (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns) !=
            (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns)):
            fail("FILE_CHANGED")
        return raw, st
    finally:
        os.close(fd)


def no_legacy_pool_change(raw: bytes) -> bool:
    try:
        lines = raw.decode("utf-8", "strict").splitlines()
    except UnicodeError:
        return False
    settings: dict[str, str] = {}
    for line in lines:
        item = line.strip()
        if not item or item[0] in "#;":
            continue
        if "=" not in item:
            continue
        key, value = map(str.strip, item.split("=", 1))
        if key in ("user", "group", "listen"):
            if key in settings:
                return False
            settings[key] = value
    return settings == {
        "user": "kmjstage", "group": "kmjstage",
        "listen": str(OLD_SOCKET),
    }


def validate_service() -> bool:
    try:
        result = subprocess.run(
            ["/usr/bin/systemctl", "is-active", "--quiet", "php8.4-fpm.service"],
            timeout=8, capture_output=True, check=False, env=ENV)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def candidate_scope(stage_uid: int, stage_gid: int) -> None:
    basefd = root_chain_fd(BASE)
    try:
        st = os.fstat(basefd)
        if st.st_uid != 0 or stat.S_IMODE(st.st_mode) != 0o711:
            fail("BASE_NOT_PRIVATE")
    finally:
        os.close(basefd)
    codefd = root_chain_fd(CODE)
    try:
        st = os.fstat(codefd)
        if (st.st_uid != 0 or st.st_gid != stage_gid or
                stat.S_IMODE(st.st_mode) != 0o550):
            fail("CODE_NOT_STAGE_GROUP")
        env_raw, _ = file_bytes(codefd, ".env", 0o640, gid=stage_gid, limit=10000)
        if (b"APP_ENV=staging\n" not in env_raw or
            b"DB_DATABASE=kmj_stage_a9796a25\n" not in env_raw or
            b"DB_USERNAME=kmjstage_a9796a25\n" not in env_raw or
            b"LARAVEL_STORAGE_PATH=" + os.fsencode(STORAGE) + b"\n" not in env_raw):
            fail("CANDIDATE_ENV_SCOPE")
        file_bytes(codefd, "vendor/autoload.php", 0o440,
                   gid=stage_gid, limit=200000)
    finally:
        os.close(codefd)
    rtfd = root_chain_fd(RUNTIME)
    try:
        st = os.fstat(rtfd)
        if st.st_uid != 0 or stat.S_IMODE(st.st_mode) != 0o711:
            fail("STAGE_RUNTIME_SCOPE")
    finally:
        os.close(rtfd)
    st = os.lstat(STORAGE)
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != stage_uid or
            st.st_gid != stage_gid or stat.S_IMODE(st.st_mode) != 0o700):
        fail("STORAGE_NOT_STAGE_USER")


def config_bytes() -> bytes:
    return (
        "[kmjstage-a979]\n"
        "user = kmjstage\n"
        "group = kmjstage\n"
        "listen = /run/php/kmjstage-a979-php84-fpm.sock\n"
        "listen.owner = www-data\n"
        "listen.group = www-data\n"
        "listen.mode = 0660\n"
        "clear_env = yes\n"
        "env[APP_ENV] = staging\n"
        "env[LARAVEL_STORAGE_PATH] = " + str(STORAGE) + "\n"
        "pm = ondemand\n"
        "pm.max_children = 2\n"
        "pm.process_idle_timeout = 10s\n"
        "pm.max_requests = 200\n"
        "security.limit_extensions = .php\n"
        "php_admin_flag[display_errors] = off\n"
        "php_admin_flag[log_errors] = on\n"
        "php_admin_flag[expose_php] = off\n"
    ).encode("ascii")


def validate_php_config() -> bool:
    # php-fpm -t checks configuration only. Never starts or reloads daemon.
    try:
        p = subprocess.run(["/usr/sbin/php-fpm8.4", "-t"],
                           capture_output=True, check=False, timeout=18, env=ENV)
        return p.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def remove_own_failed_file(dirfd: int, dev: int, ino: int,
                           expected_hash: str) -> str:
    # Only for rollback of a NEW failed config, NEVER remove any older pool.
    try:
        fd = os.open(NEW_NAME, FILEFLAGS, dir_fd=dirfd)
        try:
            st = os.fstat(fd)
            if (st.st_dev, st.st_ino) != (dev, ino) or st.st_uid != 0 or st.st_nlink != 1:
                return "BLOCKED_OWN_INODE_CHANGED"
            raw = os.read(fd, 32000)
            if hashlib.sha256(raw).hexdigest() != expected_hash:
                return "BLOCKED_OWN_CONTENT_CHANGED"
            named = os.stat(NEW_NAME, dir_fd=dirfd, follow_symlinks=False)
            if (named.st_dev, named.st_ino) != (dev, ino):
                return "BLOCKED_OWN_NAME_CHANGED"
            os.unlink(NEW_NAME, dir_fd=dirfd)
            return "PASS_OWN_NEW_FILE_ONLY"
        finally:
            os.close(fd)
    except OSError:
        return "BLOCKED_CLEANUP_UNVERIFIED"


def main() -> int:
    if (len(sys.argv) != 1 or os.geteuid() != 0 or
            socket.gethostname().split(".")[0].lower() != "kmj-elite"):
        fail("ROOT_HOST_ARGS")
    os.umask(0o077)
    if not original_pointers():
        fail("BASELINE_POINTER_DRIFT")
    stage_uid = pwd.getpwnam("kmjstage").pw_uid
    stage_gid = grp.getgrnam("kmjstage").gr_gid
    web_gid = grp.getgrnam("www-data").gr_gid
    if stage_uid == 0 or stage_gid == 0 or web_gid == 0:
        fail("ACCOUNT_UNTRUSTED")
    candidate_scope(stage_uid, stage_gid)
    if not validate_service():
        fail("FPM_SERVICE_NOT_ACTIVE")
    if os.path.lexists(NEW_SOCKET):
        fail("NEW_SOCKET_ALREADY_EXISTS")
    dirfd = root_chain_fd(FPM_DIR)
    try:
        previous, old_stat = file_bytes(dirfd, OLD_POOL.name, 0o644, limit=50000)
        if not no_legacy_pool_change(previous):
            fail("LEGACY_STAGE_POOL_UNEXPECTED")
        try:
            os.stat(NEW_NAME, dir_fd=dirfd, follow_symlinks=False)
            fail("NEW_POOL_ALREADY_EXISTS")
        except FileNotFoundError:
            pass
        payload = config_bytes()
        if not original_pointers():
            fail("POINTER_CHANGED_PREP")
        fd = os.open(NEW_NAME, CREATEFLAGS, 0o600, dir_fd=dirfd)
        own_dev = own_ino = 0
        try:
            st = os.fstat(fd)
            own_dev, own_ino = st.st_dev, st.st_ino
            total = 0
            while total < len(payload):
                n = os.write(fd, payload[total:])
                if n <= 0:
                    fail("WRITE_SHORT")
                total += n
            os.fchmod(fd, 0o644)
            os.fsync(fd)
        finally:
            os.close(fd)
        verdict = ("CONFIG_TEST_PASS" if validate_php_config()
                   else "CONFIG_TEST_FAILED")
        try:
            current, old_after = file_bytes(dirfd, OLD_POOL.name, 0o644, limit=50000)
            old_same = (current == previous and
                        (old_stat.st_dev, old_stat.st_ino, old_stat.st_mtime_ns,
                         old_stat.st_ctime_ns) ==
                        (old_after.st_dev, old_after.st_ino, old_after.st_mtime_ns,
                         old_after.st_ctime_ns))
        except (OSError, SystemExit):
            old_same = False
        if verdict != "CONFIG_TEST_PASS" or not old_same or not original_pointers():
            outcome = remove_own_failed_file(dirfd, own_dev, own_ino,
                                             hashlib.sha256(payload).hexdigest())
            emit("KMJ_STAGE_FPM_CANDIDATE_ROLLBACK", outcome)
            fail("POST_WRITE_VALIDATION_" + verdict)
        emit("KMJ_STAGE_FPM_POOL_PREP", "PASS_NEW_CONFIG_VALIDATED_NOT_RELOADED")
        emit("STAGING_CANDIDATE_SHA", SHA)
        emit("STAGING_CANDIDATE_FPM_POOL", "NEW_SEPARATE_POOL_VALID_CONFIG")
        emit("STAGING_CANDIDATE_FPM_SOCKET", "NOT_ACTIVE")
        emit("STAGING_FPM_EARLY_STORAGE_BINDING", "CONFIGURED_NEW_POOL_ON_DISK")
        emit("LEGACY_STAGING_POOL", "UNTOUCHED")
        emit("LEGACY_STAGING_SOCKET", "UNTOUCHED")
        emit("PHP_FPM_SERVICE", "NOT_RELOADED")
        emit("STAGING_DATABASE_MIGRATIONS", "NOT_RUN")
        emit("STAGING_NGINX_ROUTE", "UNCHANGED")
        emit("STAGING_OWNER_APPROVAL", "NOT_CREATED")
        emit("STAGING_ACTIVATION", "NOT_ATTEMPTED")
        emit("PRODUCTION_POINTER", "UNCHANGED")
        return 0
    finally:
        os.close(dirfd)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError):
        emit("KMJ_STAGE_FPM_POOL_PREP", "BLOCKED_FILE_SYSTEM_OR_ACCOUNT")
        raise SystemExit(2)
