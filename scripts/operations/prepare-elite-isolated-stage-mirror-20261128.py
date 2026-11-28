#!/usr/bin/env python3
"""Prepare a NON-LIVE, immutable dual-access staging CODE/static mirror.

Source is the existing root-sealed exact staging candidate, NOT a user-owned checkout.
The original candidate stays unchanged. New code is readable only by stage FPM
group kmjstage; separate public static mirror is readable by www-data.
Neither group can write. No credentials, storage, executable cache, approval,
Nginx changes, database, service, shell or application execution.
"""
from __future__ import annotations
import argparse
import ctypes
import errno
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import socket
import stat
import sys
import tempfile

SHA = "710c6f3ca10310457bc7243caabc0e48476ec110"
OLD_STAGE = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
OLD_PROD = "platform-72e7c9ada190"
ROOT_SOURCE = Path("/home/kmjstage/releases")
SOURCE = ROOT_SOURCE / SHA / "apps/platform"
BASE = Path("/var/lib/kmj-main-platform-stage-serving")
PROD = Path("/home/kmjprod/current")
STAGE = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
MAX_FILES = 130000
MAX_BYTES = 2_000_000_000
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
EXCLUDED = {"storage", "node_modules"}
EXCLUDED_SUBPATHS = {"bootstrap/cache", "vendor/bin"}
DANGEROUS_NAMES = {".git", ".ssh", ".aws", ".gnupg", ".env"}
PRIVATE_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


def emit(k: str, v: str) -> None:
    print(k + "=" + v, flush=True)


def fail(label: str) -> None:
    emit("KMJ_STAGE_SERVING_MIRROR", "BLOCKED_" + label)
    raise SystemExit(2)


def exact_pointers() -> bool:
    try:
        return (stat.S_ISLNK(os.lstat(PROD).st_mode) and
                os.readlink(PROD) in {"/home/kmjprod/releases/" + OLD_PROD, "releases/" + OLD_PROD}
                and stat.S_ISLNK(os.lstat(STAGE).st_mode)
                and os.readlink(STAGE) in {
                    "/home/kmjstage/releases/" + OLD_STAGE + "/apps/platform",
                    "../releases/" + OLD_STAGE + "/apps/platform",
                })
    except OSError:
        return False


def trusted_dir(path: Path, exact_mode: int | None = None) -> os.stat_result:
    parent = Path("/")
    # Detect links in every ancestor. Never descend through a user-writable
    # path, even if its final inode appears root-owned.
    for component in path.parts[1:]:
        parent = parent / component
        st = os.lstat(parent)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            fail("TRUSTED_DIRECTORY_CHAIN")
    st = os.lstat(path)
    if exact_mode is not None and stat.S_IMODE(st.st_mode) != exact_mode:
        fail("PROTECTED_DIRECTORY_MODE")
    return st


def open_root_fd(path: Path) -> int:
    fd = os.open("/", DIR_FLAGS)
    try:
        for c in path.parts[1:]:
            nxt = os.open(c, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def approved_name(name: str, relative: str) -> bool:
    if not name or name in (".", "..") or "/" in name:
        fail("UNSAFE_NAME")
    if name in DANGEROUS_NAMES or name.startswith(".env."):
        return False
    if name in EXCLUDED and relative in ("storage", "node_modules"):
        return False
    if relative in EXCLUDED_SUBPATHS:
        return False
    if name.lower().endswith(PRIVATE_SUFFIXES) or name in {"id_ed25519", "id_rsa"}:
        return False
    return True


def copied_file(fromfd: int, name: str, dest: Path, gid: int, stats: dict) -> None:
    fd = os.open(name, FILE_FLAGS, dir_fd=fromfd)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0
                or st.st_nlink != 1 or st.st_mode & 0o022
                or st.st_size > MAX_BYTES):
            fail("SOURCE_FILE_TRUST")
        stats["files"] += 1
        stats["bytes"] += st.st_size
        if stats["files"] > MAX_FILES or stats["bytes"] > MAX_BYTES:
            fail("RESOURCE_LIMIT")
        out = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            os.fchown(out, 0, gid)
            count = 0
            while True:
                data = os.read(fd, 1024 * 1024)
                if not data:
                    break
                view = memoryview(data)
                while view:
                    n = os.write(out, view)
                    if n <= 0:
                        fail("SHORT_WRITE")
                    view = view[n:]
                count += len(data)
            os.fchmod(out, 0o550 if st.st_mode & 0o111 else 0o440)
            os.fsync(out)
        finally:
            os.close(out)
        after = os.fstat(fd)
        if (count != st.st_size or (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            fail("SOURCE_CHANGED_DURING_COPY")
    finally:
        os.close(fd)


def copy_dir(fromfd: int, to: Path, gid: int, rel: str, depth: int,
             expected_dev: int, stats: dict) -> None:
    if depth > 42:
        fail("DEPTH_LIMIT")
    start = os.fstat(fromfd)
    if (start.st_dev != expected_dev or not stat.S_ISDIR(start.st_mode) or
            start.st_uid != 0 or start.st_mode & 0o022):
        fail("SOURCE_DIR_TRUST")
    for name in sorted(os.listdir(fromfd)):
        relative = (rel + "/" + name).lstrip("/")
        if not approved_name(name, relative):
            continue
        entry = os.stat(name, dir_fd=fromfd, follow_symlinks=False)
        if entry.st_dev != expected_dev or entry.st_uid != 0 or entry.st_mode & 0o022:
            fail("SOURCE_ENTRY_TRUST")
        target = to / name
        if stat.S_ISDIR(entry.st_mode):
            os.mkdir(target, 0o700)
            child = os.open(name, DIR_FLAGS, dir_fd=fromfd)
            try:
                opened = os.fstat(child)
                if (opened.st_ino, opened.st_dev) != (entry.st_ino, entry.st_dev):
                    fail("SOURCE_INODE_RACE")
                copy_dir(child, target, gid, relative, depth + 1, expected_dev, stats)
            finally:
                os.close(child)
            os.chown(target, 0, gid, follow_symlinks=False)
            os.chmod(target, 0o550, follow_symlinks=False)
        elif stat.S_ISREG(entry.st_mode):
            copied_file(fromfd, name, target, gid, stats)
        else:
            fail("SOURCE_LINK_OR_SPECIAL")
    now = os.fstat(fromfd)
    if (start.st_dev, start.st_ino, start.st_mtime_ns) != (
        now.st_dev, now.st_ino, now.st_mtime_ns):
        fail("SOURCE_DIRECTORY_CHANGED")


def public_manifest_check(codedir: Path, staticdir: Path) -> None:
    for root in (codedir, staticdir):
        m = root / "public/build/manifest.json" if root == codedir else root / "build/manifest.json"
        if not m.is_file() or m.is_symlink() or m.stat().st_size > 2_000_000:
            fail("PUBLIC_MANIFEST_MISSING")
        data = json.loads(m.read_text())
        row = data.get("resources/js/pages/services/codebridge-workspace.tsx")
        chunk = row.get("file") if isinstance(row, dict) else None
        if not isinstance(chunk, str) or not chunk.startswith("assets/") or ".." in Path(chunk).parts:
            fail("PUBLIC_CHUNK_INVALID")
        asset = m.parent / chunk
        if not asset.is_file() or asset.is_symlink():
            fail("PUBLIC_CHUNK_ABSENT")
    # Code + static are byte-for-byte equal for critical public entrypoints.
    for rel in ("index.php", "build/manifest.json"):
        code = (codedir / "public" / rel).read_bytes()
        static = (staticdir / rel).read_bytes()
        if hashlib.sha256(code).digest() != hashlib.sha256(static).digest():
            fail("DUAL_PUBLIC_CONTENT_MISMATCH")


def rename_noreplace(source: Path, dirfd: int, name: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    f = getattr(libc, "renameat2", None)
    if f is None:
        fail("NO_ATOMIC_NOREPLACE")
    f.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    f.restype = ctypes.c_int
    if f(-100, os.fsencode(source), dirfd, name.encode(), 1) != 0:
        fail("NO_CLOBBER_" + errno.errorcode.get(ctypes.get_errno(), "IO"))


# Identical digest program from reviewed staging deploy runner blob 39fd993d4bc2cd4427fc6d460073204a7e1f82e3.
# It hashes executable/static files and compiled views without revealing secrets.
DIGEST_PROGRAM = "import hashlib, os, stat, sys\nroot = sys.argv[1]\nSKIP = {\"storage\", \"node_modules\", \".git\"}\nlines, count = [], 0\ndef die(code):\n    print(\"ERR \" + code); sys.exit(0)\nfor cur, dirs, files in os.walk(root, followlinks=False):\n    rel = os.path.relpath(cur, root).replace(os.sep, \"/\")\n    rel = \"\" if rel == \".\" else rel\n    dirs[:] = sorted(d for d in dirs if (rel + \"/\" + d).lstrip(\"/\") not in SKIP)\n    for name in sorted(files) + dirs:\n        r = (rel + \"/\" + name).lstrip(\"/\")\n        if r in SKIP:\n            continue\n        st = os.lstat(os.path.join(cur, name))\n        count += 1\n        if count > 400000: die(\"TOO_MANY\")\n        if stat.S_ISLNK(st.st_mode): die(\"LINK\")\n        if st.st_uid != os.getuid(): die(\"OWNER\")\n        if st.st_mode & 0o022: die(\"WRITABLE\")\n        elif stat.S_ISDIR(st.st_mode):\n            lines.append(\"d:%s:%o\" % (r, st.st_mode & 0o7777))\n        elif stat.S_ISREG(st.st_mode):\n            if st.st_nlink != 1: die(\"HARDLINK\")\n            h = hashlib.sha256()\n            with open(os.path.join(cur, name), \"rb\") as f:\n                for chunk in iter(lambda: f.read(1 << 20), b\"\"): h.update(chunk)\n            lines.append(\"f:%s:%o:%s\" % (r, st.st_mode & 0o7777, h.hexdigest()))\n        else:\n            die(\"SPECIAL\")\n# Blade's compiled views are executable PHP. The mutable upload/session/cache\n# storage subtrees are intentionally outside the release seal, but that exclusion\n# MUST NOT apply to storage/framework/views. Staging should precompile views\n# before root seals the candidate; the live PHP user may READ, never WRITE them.\nviews_root = os.path.join(root, \"storage\", \"framework\", \"views\")\nfor r in (\"storage\", \"storage/framework\", \"storage/framework/views\"):\n    p = os.path.join(root, r)\n    try: st = os.lstat(p)\n    except OSError: die(\"VIEWS_MISSING\")\n    if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode): die(\"VIEWS_LINK\")\n    if st.st_uid != os.getuid() or st.st_mode & 0o022: die(\"VIEWS_WRITABLE\")\n    # PHP service must traverse these immutable parent directories.\n    if not st.st_mode & 0o005 == 0o005: die(\"VIEWS_UNREADABLE\")\n    lines.append(\"d:%s:%o\" % (r, st.st_mode & 0o7777))\n    count += 1\ncompiled = 0\nfor cur, dirs, files in os.walk(views_root, followlinks=False):\n    dirs.sort()\n    for name in sorted(dirs + files):\n        p = os.path.join(cur, name)\n        rel = os.path.relpath(p, root).replace(os.sep, \"/\")\n        try: st = os.lstat(p)\n        except OSError: die(\"VIEWS_DRIFT\")\n        count += 1\n        if count > 400000: die(\"TOO_MANY\")\n        if st.st_uid != os.getuid() or st.st_mode & 0o022: die(\"VIEWS_WRITABLE\")\n        if stat.S_ISLNK(st.st_mode): die(\"VIEWS_LINK\")\n        if stat.S_ISDIR(st.st_mode):\n            if not st.st_mode & 0o005 == 0o005: die(\"VIEWS_UNREADABLE\")\n            lines.append(\"d:%s:%o\" % (rel, st.st_mode & 0o7777))\n        elif stat.S_ISREG(st.st_mode):\n            if st.st_nlink != 1: die(\"VIEWS_HARDLINK\")\n            if not st.st_mode & 0o004: die(\"VIEWS_UNREADABLE\")\n            h = hashlib.sha256()\n            with open(p, \"rb\") as f:\n                for chunk in iter(lambda: f.read(1 << 20), b\"\"): h.update(chunk)\n            lines.append(\"f:%s:%o:%s\" % (rel, st.st_mode & 0o7777, h.hexdigest()))\n            if name.endswith(\".php\"): compiled += 1\n        else: die(\"VIEWS_SPECIAL\")\nif compiled == 0: die(\"VIEWS_UNCOMPILED\")\nprint(\"OK \" + hashlib.sha256(\"\\n\".join(sorted(lines)).encode()).hexdigest())"

def verify_source_seal():
    seal = Path("/etc/kmj-codebridge/main-platform-staging-seal-" + SHA + ".sha256")
    trusted_dir(seal.parent)
    fd = os.open(seal, FILE_FLAGS)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1
                or st.st_mode & 0o077 or st.st_size not in (64, 65)):
            fail("SOURCE_SEAL_UNTRUSTED")
        expected = os.read(fd, 66).decode("ascii").strip()
    finally:
        os.close(fd)
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        fail("SOURCE_SEAL_FORMAT")
    proc = subprocess.run(["/usr/bin/python3", "-I", "-B", "-c", DIGEST_PROGRAM, str(SOURCE)],
                          cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C"},
                          capture_output=True, text=True, timeout=300, check=False)
    if proc.returncode or proc.stdout.strip() != "OK " + expected:
        fail("SOURCE_SEAL_MISMATCH")
    # The SHA-specific seal binds the built artifact, while Git independently
    # confirms the exact source revision. No remote ref is mutated.
    release = SOURCE.parent.parent
    result = subprocess.run(["/usr/bin/git", "-c", "safe.directory=" + str(release),
                             "-C", str(release), "rev-parse", "HEAD"],
                            cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C",
                                          "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"},
                            capture_output=True, text=True, timeout=20, check=False)
    if result.returncode or result.stdout.strip() != SHA:
        fail("SOURCE_HEAD_MISMATCH")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if os.geteuid() != 0 or socket.gethostname().split(".")[0].lower() != "kmj-elite":
        fail("ROOT_HOST_ARGS")
    if args.prepare and args.confirm != "OWNER_APPROVES_REVIEWED_ISOLATED_STAGE_MIRROR":
        fail("OWNER_CONFIRMATION")
    if not exact_pointers():
        fail("LIVE_POINTER_CHANGED")
    trusted_dir(ROOT_SOURCE)
    trusted_dir(ROOT_SOURCE / SHA)
    trusted_dir(SOURCE)
    verify_source_seal()
    if not (SOURCE / "public/build/manifest.json").is_file():
        fail("BUILT_CODE_MISSING")
    try:
        stage_gid = grp.getgrnam("kmjstage").gr_gid
        web_gid = grp.getgrnam("www-data").gr_gid
        if pwd.getpwnam("kmjstage").pw_uid == 0 or stage_gid == 0 or web_gid == 0:
            fail("GROUP_ID_UNSAFE")
    except KeyError:
        fail("GROUP_MISSING")
    trusted_dir(BASE.parent)
    if args.inspect:
        emit("KMJ_STAGE_SERVING_MIRROR", "SOURCE_SEAL_PASS_INSPECT_ONLY")
        emit("STAGING_TARGET_PRESENT", "YES" if os.path.lexists(BASE / SHA) else "NO")
        emit("PRODUCTION_POINTER", "UNCHANGED")
        return 0
    if not BASE.exists():
        os.mkdir(BASE, 0o700)
        os.chmod(BASE, 0o711)
    trusted_dir(BASE, 0o711)
    parent_fd = open_root_fd(BASE)
    scratch = None
    published = False
    try:
        try:
            os.stat(SHA, dir_fd=parent_fd, follow_symlinks=False)
            fail("TARGET_ALREADY_EXISTS")
        except FileNotFoundError:
            pass
        if shutil.disk_usage(BASE).free < 4 * 1024**3:
            fail("LOW_DISK")
        scratch = Path(tempfile.mkdtemp(prefix=".kmj-stage-access-" + SHA[:12] + ".", dir=BASE))
        code = scratch / "code"
        static = scratch / "public"
        code.mkdir(mode=0o700)
        static.mkdir(mode=0o700)
        stats = {"files": 0, "bytes": 0}
        sourcefd = open_root_fd(SOURCE)
        try:
            st = os.fstat(sourcefd)
            copy_dir(sourcefd, code, stage_gid, "", 0, st.st_dev, stats)
            pubfd = os.open("public", DIR_FLAGS, dir_fd=sourcefd)
            try:
                copy_dir(pubfd, static, web_gid, "", 0, st.st_dev, stats)
            finally:
                os.close(pubfd)
        finally:
            os.close(sourcefd)
        os.chown(code, 0, stage_gid, follow_symlinks=False)
        os.chmod(code, 0o550, follow_symlinks=False)
        os.chown(static, 0, web_gid, follow_symlinks=False)
        os.chmod(static, 0o550, follow_symlinks=False)
        public_manifest_check(code, static)
        verify_source_seal()
        if not exact_pointers():
            fail("LIVE_POINTER_CHANGED_AFTER_COPY")
        if (code / ".env").exists() or (code / "storage/app").exists():
            fail("RUNTIME_SECRET_OR_STORAGE_PRESENT")
        os.chmod(scratch, 0o711, follow_symlinks=False)
        rename_noreplace(scratch, parent_fd, SHA)
        published = True
        emit("KMJ_STAGE_SERVING_MIRROR", "PASS_PREPARED_NOT_LIVE")
        emit("STAGING_CANDIDATE_SHA", SHA)
        emit("STAGING_CODE_ACCESS", "ROOT_OWNED_GROUP_KMJSTAGE_READ_EXEC_ONLY")
        emit("STAGING_STATIC_ACCESS", "ROOT_OWNED_GROUP_WWW_DATA_READ_EXEC_ONLY")
        emit("STAGING_FILES_COPIED", str(stats["files"]))
        emit("STAGING_BYTES_COPIED", str(stats["bytes"]))
        emit("STAGING_RUNTIME_ENV", "NOT_PRESENT")
        emit("STAGING_STORAGE", "NOT_PREPARED")
        emit("STAGING_DATABASE", "NOT_MODIFIED")
        emit("STAGING_SEAL", "NOT_CREATED")
        emit("STAGING_APPROVAL", "NOT_CREATED")
        emit("STAGING_NGINX_ROUTE", "NOT_CHANGED")
        emit("STAGING_FPM_SERVICE", "NOT_CHANGED")
        emit("STAGING_ACTIVATION", "NOT_ATTEMPTED")
        emit("PRODUCTION_POINTER", "UNCHANGED")
        return 0
    finally:
        os.close(parent_fd)
        if scratch is not None and not published:
            shutil.rmtree(scratch)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError):
        emit("KMJ_STAGE_SERVING_MIRROR", "BLOCKED_FS_OR_CONTENT")
        raise SystemExit(2)
