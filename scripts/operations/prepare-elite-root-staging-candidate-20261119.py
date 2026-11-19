#!/usr/bin/env python3
"""Prepare the exact owner-approved staging SHA without touching LIVE pointers.

Reviewed root-only KMJ-elite operation:
  --inspect <sha> <stage-current-sha> <live-release>
  --prepare <sha> <stage-current-sha> <live-release> OWNER_STAGE_PREPARE

PREPARE locks the existing stage parent directory identities (with scoped,
reversible ACL metadata), builds the approved source as unprivileged kmjstage
in a private scratch directory, precompiles Blade views, freezes the entire
executable tree as root-owned, publishes no-clobber, and writes an immutable
tree digest using the INSTALLED guarded runner's exact digest algorithm.

It does NOT write protected staging/production approval, move either active
pointer, contact production DB, start units, or certify rollback/storage.
"""
from __future__ import annotations

import argparse
import ctypes
import fcntl
import hashlib
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile

SHA_RE = re.compile(r"[a-f0-9]{40}\Z")
LIVE_RE = re.compile(r"platform-[a-f0-9]{12}\Z")
REMOTE = "https://github.com/kmjtechno/kmj-main-platform.git"
STAGE = Path("/home/kmjstage")
RELEASES = STAGE / "releases"
SITE = STAGE / "htdocs/staging.kmjtechno.com"
LIVE = Path("/home/kmjprod/current")
RUNNER = Path("/usr/local/libexec/kmj-codebridge/kmj-main-platform-staging-deploy.sh")
SEAL_DIR = Path("/etc/kmj-codebridge")
PARENTS = (STAGE, STAGE / "htdocs", RELEASES)
STAGE_USER = "kmjstage"
WEB_USER = "www-data"
MIN_SPACE = 2 * 1024**3
ENV = {"PATH": "/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C",
       "GIT_TERMINAL_PROMPT": "0"}


class Block(Exception):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise Block(reason)


def fixed(argv: list[str], *, timeout: int = 60, env=None) -> str:
    try:
        r = subprocess.run(argv, capture_output=True, text=True,
                           env=env or ENV, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Block("FIXED_COMMAND_FAILED") from None
    require(r.returncode == 0 and len(r.stdout) < 65536,
            "FIXED_COMMAND_FAILED")
    return r.stdout.strip()


def stage_run(*args: str, timeout=3600, home: Path | None = None) -> str:
    allowed_env = dict(ENV)
    if home:
        allowed_env.update(HOME=str(home), COMPOSER_HOME=str(home / "composer"),
                           npm_config_cache=str(home / "npm"))
    injected = ["/usr/bin/env", "PATH=" + ENV["PATH"], "LANG=C"]
    if home:
        injected += ["HOME=" + str(home),
                     "COMPOSER_HOME=" + str(home / "composer"),
                     "npm_config_cache=" + str(home / "npm")]
    return fixed(["/usr/sbin/runuser", "-u", STAGE_USER, "--",
                  *injected, *args], timeout=timeout, env=allowed_env)


def exact_link(link: Path, target: Path) -> bool:
    try:
        return (stat.S_ISLNK(os.lstat(link).st_mode)
                and link.resolve(strict=True) == target
                and target.is_dir())
    except OSError:
        return False


def lstat_real_dir(path: Path) -> os.stat_result:
    try:
        st = os.lstat(path)
        require(stat.S_ISDIR(st.st_mode) and st.st_nlink >= 2,
                "PARENT_NOT_REAL_DIRECTORY")
        return st
    except OSError:
        raise Block("PARENT_DIRECTORY_MISSING") from None


def parent_plan(uid: int) -> list[tuple[Path, int, int, int]]:
    require(lstat_real_dir(Path("/home")).st_uid == 0,
            "HOME_PARENT_NOT_ROOT")
    seen = []
    for path in PARENTS:
        st = lstat_real_dir(path)
        require(st.st_uid in (0, uid) and not st.st_mode & 0o022,
                "STAGING_PARENT_UNSAFE")
        seen.append((path, st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)))
    require(STAGE != RELEASES and SITE.parent in PARENTS,
            "FIXED_PATH_LAYOUT")
    return seen


def protected_root_file(path: Path) -> bytes:
    require(path.is_absolute() and path.parent == RUNNER.parent,
            "RUNNER_PATH_UNEXPECTED")
    parent = path.parent
    while parent != Path("/"):
        st = lstat_real_dir(parent)
        require(st.st_uid == 0 and not st.st_mode & 0o022,
                "RUNNER_PARENT_UNTRUSTED")
        parent = parent.parent
    try:
        st = os.lstat(path)
        require(stat.S_ISREG(st.st_mode) and st.st_uid == 0 and st.st_nlink == 1
                and 0 < st.st_size < 65536 and not st.st_mode & 0o022,
                "RUNNER_UNTRUSTED")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            opened = os.fstat(fd)
            data = os.read(fd, 65536)
            after = os.fstat(fd)
            now = os.lstat(path)
            stamp = lambda x: (x.st_dev, x.st_ino, x.st_uid, x.st_nlink,
                               x.st_size, x.st_mode, x.st_mtime_ns, x.st_ctime_ns)
            require(stamp(st) == stamp(opened) == stamp(after) == stamp(now)
                    and len(data) == st.st_size, "RUNNER_CHANGED")
            return data
        finally:
            os.close(fd)
    except OSError:
        raise Block("RUNNER_UNREADABLE") from None


def digest_program(script: bytes) -> str:
    match = re.search(rb"<<'DIGEST_PY'\n(.*?)\nDIGEST_PY\n", script, re.S)
    require(match is not None, "INSTALLED_RUNNER_DIGEST_ABSENT")
    return match.group(1).decode("ascii", "strict")


def approved_ref_sha() -> str:
    out = fixed(["/usr/bin/git", "ls-remote", "--exit-code",
                 REMOTE, "refs/heads/staging-approved"], timeout=20)
    parts = out.split()
    require(len(parts) == 2 and parts[1] == "refs/heads/staging-approved"
            and SHA_RE.fullmatch(parts[0]) is not None,
            "APPROVED_REF_UNVERIFIED")
    return parts[0]



def staging_env_isolated(raw: bytes) -> bool:
    """Require one local, staging-namespaced DB identity; never print secrets."""
    try:
        values = {}
        for line in raw.decode("utf-8", "strict").splitlines():
            if not line or line.lstrip().startswith("#"):
                continue
            if "=" not in line:
                return False
            key, value = line.split("=", 1)
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,80}", key) or key in values:
                return False
            values[key] = value.strip()
        return (
            values.get("APP_ENV") == "staging"
            and values.get("APP_URL") == "https://staging.kmjtechno.com"
            and values.get("DB_CONNECTION") == "pgsql"
            and re.fullmatch(r"kmj_stage_[a-z0-9_]{2,64}",
                             values.get("DB_DATABASE", "")) is not None
            and re.fullmatch(r"kmjstage(?:_[a-z0-9_]{1,64})?",
                             values.get("DB_USERNAME", "")) is not None
            and values.get("DB_HOST") in {
                "127.0.0.1", "localhost", "/var/run/postgresql"
            }
            and values.get("DB_PORT", "5432") == "5432"
            and values.get("MAIL_MAILER") in {"log", "array"}
            and values.get("APP_DEBUG") in {"false", "0"}
        )
    except UnicodeError:
        return False


def inspect(sha: str, old: str, live: str) -> tuple[Path, Path, list]:
    require(os.geteuid() == 0 and socket.gethostname().split(".")[0] ==
            "KMJ-elite", "ROOT_ELITE_ONLY")
    require(SHA_RE.fullmatch(sha) is not None and
            SHA_RE.fullmatch(old) is not None and
            LIVE_RE.fullmatch(live) is not None and sha != old,
            "RELEASE_IDENTITY_INVALID")
    require(exact_link(LIVE, Path("/home/kmjprod/releases") / live),
            "LIVE_RELEASE_DRIFT")
    old_app = RELEASES / old / "apps/platform"
    require(exact_link(SITE, old_app), "STAGE_POINTER_DRIFT")
    require(approved_ref_sha() == sha, "APPROVED_SOURCE_MOVED")
    st_uid = int(fixed(["/usr/bin/id", "-u", STAGE_USER]))
    plan = parent_plan(st_uid)
    require(fixed(["/usr/bin/systemctl", "is-active", "nginx"]) == "active"
            and fixed(["/usr/bin/systemctl", "is-active", "php8.4-fpm"]) == "active",
            "STAGE_SERVICES_INACTIVE")
    require(Path("/run/php/kmjstage-php84-fpm.sock").is_socket(),
            "STAGE_PHP_SOCKET_MISSING")
    old_env = old_app / ".env"
    require(old_env.is_file() and not old_env.is_symlink() and
            old_env.stat().st_uid == st_uid and
            stat.S_IMODE(old_env.stat().st_mode) in (0o400, 0o600),
            "PREDECESSOR_ENV_UNTRUSTED")
    data = old_env.read_bytes()
    require(staging_env_isolated(data),
            "PREDECESSOR_STAGING_DATABASE_NOT_ISOLATED")
    require(not (RELEASES / sha).exists() and
            not (RELEASES / sha).is_symlink(),
            "CANDIDATE_ALREADY_PRESENT")
    require(shutil.disk_usage(RELEASES).free > MIN_SPACE,
            "STAGING_DISK_UNAVAILABLE")
    require(lstat_real_dir(SEAL_DIR).st_uid == 0 and
            not lstat_real_dir(SEAL_DIR).st_mode & 0o022,
            "SEAL_DIR_UNTRUSTED")
    require(not (SEAL_DIR / ("main-platform-staging-seal-" + sha + ".sha256")).exists(),
            "SEAL_ALREADY_PRESENT")
    digest_program(protected_root_file(RUNNER))
    return old_app, RELEASES / sha, plan


def restore_metadata(backups: list[bytes]) -> bool:
    # Restore ONLY the three fixed original paths saved by getfacl -p.
    ok = True
    for content in reversed(backups):
        try:
            result = subprocess.run(
                ["/usr/bin/setfacl", "--restore=-"], input=content,
                capture_output=True, timeout=15, check=False)
            ok &= result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            ok = False
    return ok


def lock_stage_parents(plan: list, old_app: Path) -> None:
    backups: list[bytes] = []
    for path, *_ in plan:
        backups.append(subprocess.run(
            ["/usr/bin/getfacl", "-p", str(path)], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=10).stdout)
    try:
        for path, *_ in plan:
            os.chown(path, 0, 0, follow_symlinks=False)
            os.chmod(path, 0o750, follow_symlinks=False)
            fixed(["/usr/bin/setfacl", "-m",
                   "u:kmjstage:r-x,u:www-data:--x", str(path)])
        require(all(lstat_real_dir(path).st_uid == 0 and
                    not lstat_real_dir(path).st_mode & 0o022 for path in PARENTS),
                "PARENT_LOCK_INCOMPLETE")
        stage_run("/usr/bin/test", "-r", str(old_app / ".env"))
        fixed(["/usr/sbin/runuser", "-u", WEB_USER, "--",
               "/usr/bin/test", "-r", str(old_app / "public/index.php")])
    except (Block, OSError, subprocess.SubprocessError):
        restored = restore_metadata(backups)
        raise Block("STAGE_PARENT_LOCK_FAILED" if restored else
                    "STAGE_PARENT_ROLLBACK_UNVERIFIED") from None


def build_stage(sha: str, old_app: Path, scratch: Path) -> Path:
    tree = scratch / "repo"
    home = scratch / "home"
    home.mkdir(mode=0o700)
    os.chown(home, int(fixed(["/usr/bin/id", "-u", STAGE_USER])),
             int(fixed(["/usr/bin/id", "-g", STAGE_USER])),
             follow_symlinks=False)
    stage_run("/usr/bin/git", "clone", "--quiet", "--depth", "1",
              "--single-branch", "--branch", "staging-approved", "--",
              REMOTE, str(tree), timeout=240, home=home)
    require(stage_run("/usr/bin/git", "-C", str(tree), "rev-parse", "HEAD") ==
            sha, "CLONE_HEAD_MISMATCH")
    app = tree / "apps/platform"
    require((app / "composer.lock").is_file() and
            (app / "package-lock.json").is_file() and
            not (app / ".env").exists(), "APP_TREE_INCOMPLETE")
    # Only staging env copied; no production env/DB access.
    env = app / ".env"
    fd = os.open(env, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write((old_app / ".env").read_bytes())
        stream.flush()
        os.fsync(stream.fileno())
    uid = int(fixed(["/usr/bin/id", "-u", STAGE_USER]))
    gid = int(fixed(["/usr/bin/id", "-g", STAGE_USER]))
    os.chown(env, uid, gid, follow_symlinks=False)
    stage_run("/bin/bash", "-c",
              'set -Eeuo pipefail; cd "$1"; COMPOSER_MEMORY_LIMIT=-1 '
              'composer install --no-dev --no-plugins --no-scripts --no-interaction '
              '--prefer-dist --optimize-autoloader --no-progress --no-ansi; '
              'npm ci --ignore-scripts --no-audit --no-fund; '
              'npm run build; '
              '/usr/bin/php8.4 artisan view:cache --no-ansi',
              "stage-build", str(app), timeout=1800, home=home)
    require((app / "vendor/autoload.php").is_file() and
            (app / "public/build/manifest.json").is_file() and
            any((app / "storage/framework/views").glob("*.php")),
            "STAGE_BUILD_INCOMPLETE")
    require(stage_run("/usr/bin/git", "-C", str(tree),
                      "status", "--porcelain", "--untracked-files=normal") == "",
            "STAGE_SOURCE_DIRTY")
    # Remove generated Node dependencies from this never-live isolated
    # candidate after frontend output is sealed. They are not runtime code.
    deps = app / "node_modules"
    if deps.exists() and deps.is_dir() and not deps.is_symlink():
        shutil.rmtree(deps)
    return tree


def mutable(relative: str) -> bool:
    """Only these Laravel runtime directories may remain stage-user writable."""
    paths = ("apps/platform/storage/app",
             "apps/platform/storage/logs",
             "apps/platform/storage/framework/cache",
             "apps/platform/storage/framework/sessions")
    return any(relative == p or relative.startswith(p + "/") for p in paths)


def freeze_plan(tree: Path, stage_uid: int, stage_gid: int) -> list:
    """Pure metadata plan: strict no-follow type and link validation."""
    paths = []
    for root, subdirs, files in os.walk(tree, followlinks=False):
        rootp = Path(root)
        for name in subdirs + files:
            path = rootp / name
            st = os.lstat(path)
            rel = path.relative_to(tree).as_posix()
            allow_symlink = (rel.startswith("apps/platform/node_modules/")
                             or rel.startswith(".git/"))
            require(stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)
                    or (stat.S_ISLNK(st.st_mode) and allow_symlink),
                    "EXECUTABLE_TREE_SYMLINK_OR_SPECIAL")
            if stat.S_ISLNK(st.st_mode):
                subdirs[:] = [d for d in subdirs if d != name]
                continue
            require(st.st_nlink == 1 if stat.S_ISREG(st.st_mode) else True,
                    "EXECUTABLE_TREE_HARDLINK")
            paths.append((path, rel, st))
    operations = []
    for path, rel, st in reversed(paths):
        isdir = stat.S_ISDIR(st.st_mode)
        if rel == "apps/platform/.env":
            owner, group, mode = 0, stage_gid, 0o640
        elif mutable(rel):
            owner, group = stage_uid, stage_gid
            mode = (0o750 if isdir else 0o640)
        elif (rel in {"apps/platform/storage",
                      "apps/platform/storage/framework",
                      "apps/platform/storage/framework/views"} or
              rel.startswith("apps/platform/storage/framework/views/")):
            # Existing guarded tree digest requires 0755 immutable Blade
            # parent chain and world-readable compiled PHP views.
            owner, group = 0, 0
            mode = (0o755 if isdir else 0o444)
        else:
            # Private source is accessible to PHP's staging group, NOT to
            # the untrusted www-data worker or other VPS users.
            owner, group = 0, stage_gid
            mode = (0o750 if isdir else
                    (0o550 if st.st_mode & 0o111 else 0o440))
        operations.append((path, rel, owner, group, mode))
    return operations


def freeze(tree: Path, stage_uid: int, stage_gid: int) -> None:
    """Stage-user cannot traverse tree; apply no-follow root metadata freeze."""
    for path, _rel, owner, group, mode in freeze_plan(tree, stage_uid, stage_gid):
        os.chown(path, owner, group, follow_symlinks=False)
        os.chmod(path, mode, follow_symlinks=False)
    os.chown(tree, 0, stage_gid, follow_symlinks=False)
    os.chmod(tree, 0o750, follow_symlinks=False)
    # www-data needs only public assets, never the private source or .env.
    for ancestor in (tree, tree / "apps", tree / "apps/platform"):
        fixed(["/usr/bin/setfacl", "-m", "u:www-data:--x", str(ancestor)])
    fixed(["/usr/bin/setfacl", "-R", "-m", "u:www-data:rX",
           str(tree / "apps/platform/public")], timeout=120)
    # The entire writable storage subtrees must be children of root-owned
    # storage parents, not a way to replace sealed compiled views.
    views = tree / "apps/platform/storage/framework/views"
    require(views.is_dir() and views.stat().st_uid == 0 and
            not views.stat().st_mode & 0o022, "VIEWS_NOT_FROZEN")


def seal_sha(app: Path) -> str:
    script = digest_program(protected_root_file(RUNNER))
    output = fixed(["/usr/bin/python3", "-I", "-c", script, str(app)],
                   timeout=240)
    require(re.fullmatch(r"OK [a-f0-9]{64}", output) is not None,
            "ROOT_STAGING_TREE_SEAL_FAILED")
    return output[3:]


def publish_noclobber(source: Path, destination: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    f = getattr(libc, "renameat2", None)
    require(f is not None, "ATOMIC_NOCLOBBER_UNAVAILABLE")
    f.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                  ctypes.c_char_p, ctypes.c_uint]
    f.restype = ctypes.c_int
    require(f(-100, os.fsencode(source), -100,
              os.fsencode(destination), 1) == 0, "CANDIDATE_PUBLISH_CONFLICT")


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    parser.add_argument("sha")
    parser.add_argument("stage_current_sha")
    parser.add_argument("live_release")
    parser.add_argument("confirmation", nargs="?", default="")
    a = parser.parse_args(argv)
    a.mode = "--inspect" if a.inspect else "--prepare"
    require((a.mode == "--inspect" and a.confirmation == "") or
            (a.mode == "--prepare" and a.confirmation == "OWNER_STAGE_PREPARE"),
            "EXPLICIT_OWNER_CONFIRMATION_REQUIRED")
    old, candidate, parent_status = inspect(
        a.sha, a.stage_current_sha, a.live_release)
    print("STAGE_SOURCE_APPROVED_SHA=PASS")
    print("STAGE_PARENT_ROOT_LOCK=" +
          ("READY" if all(uid == 0 for _p, uid, _g, _m in parent_status)
           else "REQUIRED_EXPLICIT_OWNER_PREPARE"))
    print("STAGE_CANDIDATE=ABSENT_READY_FOR_ISOLATED_BUILD")
    if a.mode == "--inspect":
        print("STAGE_PREPARE=INSPECT_PASS_NO_CHANGES")
        print("PRODUCTION_SWITCH=NOT_ATTEMPTED")
        return 0

    # Untrusted sticky lock directory: never open through a symlink, never
    # truncate or chmod a pre-existing inode.
    lock_path = "/run/lock/kmj-stage-root-prepare.lock"
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT |
                      os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(lock_fd, "r+b", buffering=0) as lock:
        st = os.fstat(lock.fileno())
        require(stat.S_ISREG(st.st_mode) and st.st_uid == 0 and
                st.st_nlink == 1 and stat.S_IMODE(st.st_mode) == 0o600,
                "STAGE_PREPARE_LOCK_INVALID")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Recheck after acquiring lock to avoid changing staging after drift.
        old, candidate, parent_status = inspect(
            a.sha, a.stage_current_sha, a.live_release)
        lock_stage_parents(parent_status, old)
        scratch = Path(tempfile.mkdtemp(prefix=".kmj-stage-root-" + a.sha[:12] + "-",
                                        dir=RELEASES))
        stage_uid = int(fixed(["/usr/bin/id", "-u", STAGE_USER]))
        stage_gid = int(fixed(["/usr/bin/id", "-g", STAGE_USER]))
        try:
            os.chown(scratch, stage_uid, stage_gid, follow_symlinks=False)
            os.chmod(scratch, 0o700, follow_symlinks=False)
            tree = build_stage(a.sha, old, scratch)
            # Stage UID must lose scratch-parent write access BEFORE the
            # root-owned freeze; otherwise it could swap the final tree by
            # renaming a root-owned child from its stage-owned parent.
            os.chown(scratch, 0, 0, follow_symlinks=False)
            os.chmod(scratch, 0o700, follow_symlinks=False)
            os.chown(tree, 0, 0, follow_symlinks=False)
            os.chmod(tree, 0o700, follow_symlinks=False)
            freeze(tree, stage_uid, stage_gid)
            app = tree / "apps/platform"
            digest = seal_sha(app)
            require(exact_link(SITE, old) and exact_link(
                    LIVE, Path("/home/kmjprod/releases") / a.live_release),
                    "POINTER_DRIFT_DURING_PREPARE")
            require(approved_ref_sha() == a.sha, "APPROVED_REF_DRIFT")
            # Rename only after root has frozen the entire candidate tree.
            publish_noclobber(tree, candidate)
            final_digest = seal_sha(candidate / "apps/platform")
            require(final_digest == digest, "PUBLISHED_CANDIDATE_DRIFT")
            stage_run("/usr/bin/test", "-r", str(candidate / "apps/platform/.env"))
            fixed(["/usr/sbin/runuser", "-u", WEB_USER, "--", "/usr/bin/test",
                   "-r", str(candidate / "apps/platform/public/index.php")])
            # Enforce web-user denial of the root-sealed application .env.
            readable = subprocess.run(
                ["/usr/sbin/runuser", "-u", WEB_USER, "--", "/usr/bin/test",
                 "-r", str(candidate / "apps/platform/.env")],
                env=ENV, timeout=10, capture_output=True, check=False)
            require(readable.returncode == 1, "WEB_ENV_EXPOSED")
            seal_path = SEAL_DIR / (
                "main-platform-staging-seal-" + a.sha + ".sha256")
            fd = os.open(seal_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         os.O_NOFOLLOW | os.O_CLOEXEC, 0o644)
            with os.fdopen(fd, "w", encoding="ascii") as output:
                output.write(digest + "\n")
                output.flush()
                os.fsync(output.fileno())
            print("STAGING_CANDIDATE=ROOT_OWNED_SEALED_PASS")
            print("STAGING_SOURCE_SHA=" + a.sha)
            print("STAGING_STORAGE_CONTINUITY=NOT_ATTESTED")
            print("STAGING_ROLLBACK=NOT_ATTESTED")
            print("STAGING_PROTECTED_APPROVAL=NOT_CREATED")
            print("STAGING_POINTER=UNCHANGED")
            print("PRODUCTION_POINTER=UNCHANGED")
            print("STAGE_ROOT_PREPARE=PASS")
            return 0
        finally:
            if scratch.is_dir() and not scratch.is_symlink():
                shutil.rmtree(scratch)


if __name__ == "__main__":
    try:
        raise SystemExit(run(sys.argv[1:]))
    except (Block, OSError, ValueError, subprocess.SubprocessError) as exc:
        code = str(exc) if isinstance(exc, Block) else "OPERATOR_FAILURE"
        print("STAGE_ROOT_PREPARE=BLOCKED_" + code)
        print("PRODUCTION_SWITCH=NOT_ATTEMPTED")
        print("STAGING_APPROVAL_MUTATION=NONE")
        raise SystemExit(2)
