#!/usr/bin/env python3
"""Exact a892 staging-only Blade repair; compile as kmjstage, never as root.
Preserve original immutable views and seal, validate actual health before and
after publication. No live route, database migration, service or approval write.
"""
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import signal
import socket
import stat
import subprocess
import tempfile

SHA = "a892b0d5d851129a9d8ed00c1af1390da6ee584f"
OLD = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
LIVE = "platform-457481eb652f"
BASE = Path("/home/kmjstage")
RELEASE = BASE / "releases" / SHA
APP = RELEASE / "apps/platform"
FRAMEWORK = APP / "storage/framework"
VIEWS = FRAMEWORK / "views"
SEAL = Path("/etc/kmj-codebridge") / ("main-platform-staging-seal-" + SHA + ".sha256")
APPROVAL = SEAL.parent / "main-platform-staging-approval.json"
LOCK = Path("/run/kmj-main-platform-staging/deploy.lock")
BUILDER_BLOB = "654525519ee4b21c03f41a86da26fcf9f357d6dd"
RUNNER_SHA = "27f4c1734b15f886f761f60e37b6db9ddc5922737159a1c6089ad081b3b96477"
REMOTE = "https://github.com/kmjtechno/kmj-main-platform.git"
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "GIT_TERMINAL_PROMPT": "0"}
PHP_COMPILE = r"""<?php
$phase = 'AUTOLOAD';
try {
    require 'vendor/autoload.php';
    $app = require 'bootstrap/app.php';
    $kernel = $app->make(Illuminate\Contracts\Http\Kernel::class);
    $phase = 'BOOTSTRAP';
    $kernel->bootstrap();
    $phase = 'COMPILE_SCOPE';
    $target = getenv('VIEW_COMPILED_PATH');
    if (config('view.compiled') !== $target || !is_dir($target)) {
        throw new RuntimeException('compile scope');
    }
    $phase = 'RESOLVE_COMPILER';
    $compiler = $app->make('blade.compiler');
    $source = dirname((new ReflectionClass(Illuminate\Foundation\Http\HealthCheck::class))->getFileName()).'/../resources/health-up.blade.php';
    if (dirname($compiler->getCompiledPath($source)) !== $target || !is_file($source)) {
        throw new RuntimeException('compiler scope');
    }
    $phase = 'ARTISAN_VIEW_CACHE';
    if (Illuminate\Support\Facades\Artisan::call('view:cache') !== 0) {
        throw new RuntimeException('view cache');
    }
    // Register framework error views separately: a missing app errors path
    // must not break the ordinary view:cache Finder.
    $phase = 'FRAMEWORK_ERROR_VIEWS';
    $errors = dirname((new ReflectionClass(Illuminate\Foundation\Exceptions\RegisterErrorViewPaths::class))->getFileName()).'/views';
    foreach (glob($errors.'/*.blade.php') ?: [] as $errorView) {
        $compiler->compile($errorView);
        if ($compiler->isExpired($errorView)) {
            $compiler->compile($errorView);
        }
        if ($compiler->isExpired($errorView)) {
            throw new RuntimeException('error cache expired');
        }
    }
    $phase = 'FRAMEWORK_HEALTH_VIEW';
    // HealthCheck uses View::file with this lexical path, including /../.
    $compiler->compile($source);
    if ($compiler->isExpired($source)) {
        $compiler->compile($source);
    }
    if ($compiler->isExpired($source)) {
        throw new RuntimeException('health cache expired');
    }
    echo "COMPILE_OK\n";
} catch (Throwable $e) {
    echo "COMPILE_FAILED ".get_class($e)."\n";
    echo "COMPILE_PHASE=".$phase."\n";
    echo "COMPILE_LOCATION=".basename($e->getFile()).":".$e->getLine()."\n";
    foreach (array_slice($e->getTrace(), 0, 8) as $t) {
        echo "COMPILE_TRACE=".($t['class']??'')."::".($t['function']??'')."\n";
    }
    exit(1);
}
"""
PHP_HEALTH = r"""<?php
try {
    require 'vendor/autoload.php';
    $app = require 'bootstrap/app.php';
    $kernel = $app->make(Illuminate\Contracts\Http\Kernel::class);
    $kernel->bootstrap();
    $expected = getenv('VIEW_COMPILED_PATH') ?: getcwd().'/storage/framework/views';
    if (config('view.compiled') !== $expected) {
        throw new RuntimeException('view scope');
    }
    $source = dirname((new ReflectionClass(Illuminate\Foundation\Http\HealthCheck::class))->getFileName()).'/../resources/health-up.blade.php';
    if ($app->make('blade.compiler')->isExpired($source)) {
        throw new RuntimeException('health view expired');
    }
    $response = $kernel->handle(Illuminate\Http\Request::create('https://staging.kmjtechno.com/up', 'GET'));
    if ($response->getStatusCode() !== 200) {
        throw new RuntimeException('health status');
    }
    echo "HEALTH_OK\n";
} catch (Throwable $e) {
    echo "HEALTH_FAILED ".get_class($e)."\n";
    exit(1);
}
"""


def need(ok, label):
    if not ok:
        raise ValueError(label)


def protected_dir(path):
    for p in (path, *path.parents):
        s = p.lstat()
        need(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
             "UNTRUSTED_ROOT_DIRECTORY")


def stamp(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink,
            s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def read_file(path, owner, limit, protected=True):
    if protected:
        protected_dir(path.parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as f:
        s = os.fstat(f.fileno())
        need(stat.S_ISREG(s.st_mode) and s.st_uid == owner and s.st_nlink == 1
             and not s.st_mode & 0o022 and 0 < s.st_size <= limit, "FILE_METADATA")
        data = f.read(limit + 1)
        need(len(data) == s.st_size and stamp(s) == stamp(os.fstat(f.fileno()))
             and stamp(s) == stamp(path.lstat()), "FILE_DRIFT")
    return data, s


def command(args, *, input=None, timeout=120, cwd="/"):
    p = subprocess.run(args, input=input, cwd=cwd, env=ENV, capture_output=True,
                       timeout=timeout, check=False)
    if p.returncode != 0:
        marker = re.search(rb"(?m)^(?:COMPILE|HEALTH)_FAILED [A-Za-z0-9_\\]+$", p.stdout)
        if marker:
            print(marker.group().decode("ascii"), flush=True)
        for line in p.stdout.splitlines():
            if re.fullmatch(rb"COMPILE_(?:PHASE=[A-Z_]+|LOCATION=[A-Za-z0-9_.-]+:[0-9]+|TRACE=[A-Za-z0-9_\\:{}().-]+)", line):
                print(line.decode("ascii"), flush=True)
        raise ValueError("COMMAND_FAILED")
    return p.stdout


def php(script, target=None):
    args = ["/usr/sbin/runuser", "-u", "kmjstage", "--", "/usr/bin/env", "-i",
            "PATH=/usr/bin:/bin", "HOME=/home/kmjstage"]
    if target:
        args.append("VIEW_COMPILED_PATH=" + str(target))
    args += ["/usr/bin/php8.4", "-d", "display_errors=0", "-d", "log_errors=0"]
    return command(args, input=script.encode(), cwd=APP, timeout=240)


def exchange(a, b):
    f = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    need(f is not None, "ATOMIC_EXCHANGE_UNAVAILABLE")
    f.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    f.restype = ctypes.c_int
    need(f(-100, os.fsencode(a), -100, os.fsencode(b), 2) == 0, "ATOMIC_EXCHANGE_FAILED")


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def replace_seal(old, new):
    need(read_file(SEAL, 0, 65)[0] == old, "SEAL_DRIFT")
    fd, path = tempfile.mkstemp(prefix=".kmj-view-seal-", dir=SEAL.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            os.fchmod(f.fileno(), 0o644)
            f.write(new)
            f.flush()
            os.fsync(f.fileno())
        need(read_file(SEAL, 0, 65)[0] == old, "SEAL_DRIFT")
        os.replace(path, SEAL)
        sync_dir(SEAL.parent)
    finally:
        if os.path.lexists(path):
            os.unlink(path)


def guard(b):
    need(b["exact_link"](BASE / "htdocs/staging.kmjtechno.com",
                         BASE / "releases" / OLD / "apps/platform"), "STAGE_DRIFT")
    need(b["exact_link"](Path("/home/kmjprod/current"),
                         Path("/home/kmjprod/releases") / LIVE), "LIVE_DRIFT")
    need(b["exact_link"](APP / "storage/app", BASE / "shared/storage-app-b2e69decab3a"),
         "SHARED_STORAGE_DRIFT")
    refs = command(["/usr/bin/git", "ls-remote", "--exit-code", REMOTE,
                    "refs/heads/main", "refs/heads/staging-approved"], timeout=30)
    need(set(refs.decode().splitlines()) ==
         {SHA + "\trefs/heads/main", SHA + "\trefs/heads/staging-approved"}, "SOURCE_DRIFT")
    head = command(["/usr/bin/git", "-c", "safe.directory=" + str(RELEASE),
                    "-C", str(RELEASE), "rev-parse", "HEAD"]).decode().strip()
    need(head == SHA, "CANDIDATE_HEAD")
    approval, _ = read_file(APPROVAL, 0, 65536)
    need(json.loads(approval).get("approvedSha") != SHA, "CANDIDATE_ALREADY_APPROVED")
    runner = b["protected_root_file"](b["RUNNER"])
    need(hashlib.sha256(runner).hexdigest() == RUNNER_SHA, "RUNNER_DRIFT")
    raw, _ = read_file(APP / ".env", 0, 1048576)
    need(b["staging_env_isolated"](raw), "ENV_SCOPE")
    old = BASE / "releases" / OLD / "apps/platform/.env"
    need(b["normalize_candidate_mailer"](old.read_bytes()) == raw, "ENV_DRIFT")
    need(not (APP / "bootstrap/cache/config.php").exists(), "CONFIG_CACHE_PRESENT")


def copy_views(src, dest, uid):
    # The parent is root-owned and not writable by kmjstage. Refuse links,
    # hardlinks, unexpected names, metadata drift and unbounded output.
    items = sorted(src.iterdir())
    need(1 <= len(items) <= 1000, "VIEW_COUNT")
    total = 0
    for p in items:
        need(re.fullmatch(r"[a-f0-9]{32}\.php", p.name) is not None, "VIEW_NAME")
        data, s = read_file(p, uid, 4 * 1024 * 1024, protected=False)
        total += len(data)
        need(total <= 64 * 1024 * 1024, "VIEW_BYTES")
        fd = os.open(dest / p.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fchmod(out.fileno(), 0o444)
            os.utime(out.fileno(), ns=(s.st_atime_ns, s.st_mtime_ns))
            os.fsync(out.fileno())
        command(["/usr/sbin/runuser", "-u", "kmjstage", "--",
                 "/usr/bin/php8.4", "-l", str(dest / p.name)], timeout=15)
    need(sorted(p.name for p in src.iterdir()) == [p.name for p in items], "VIEW_LIST_DRIFT")
    sync_dir(dest)
    return len(items)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--builder", type=Path, required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm", default="")
    args = p.parse_args()
    need(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite", "HOST_ROOT")
    need((args.apply and args.confirm == "OWNER_RESEAL_EXACT_STAGING_VIEWS") or
         (not args.apply and not args.confirm), "CONFIRMATION")
    os.umask(0o077)
    raw, _ = read_file(args.builder, 0, 65536)
    need(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == BUILDER_BLOB,
         "BUILDER_PIN")
    b = runpy.run_path(str(args.builder))
    protected_dir(FRAMEWORK)
    protected_dir(VIEWS)
    need(command(["/usr/bin/systemctl", "show", "kmj-main-platform-staging-deploy.service",
                  "-p", "ActiveState", "--value"]).strip() == b"inactive", "STAGE_UNIT_BUSY")
    if not os.path.lexists(LOCK.parent):
        LOCK.parent.mkdir(mode=0o700)
    protected_dir(LOCK.parent)
    fd = os.open(LOCK, os.O_RDONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, "rb") as lock:
        st = os.fstat(lock.fileno())
        need(stat.S_ISREG(st.st_mode) and st.st_uid == 0 and st.st_nlink == 1
             and stat.S_IMODE(st.st_mode) == 0o600, "LOCK_SCOPE")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        guard(b)
        old_seal, _ = read_file(SEAL, 0, 65)
        need(re.fullmatch(rb"[a-f0-9]{64}\n?", old_seal) is not None, "SEAL_FORMAT")
        need(b["seal_sha"](APP) == old_seal.decode().strip(), "ORIGINAL_SEAL")
        print("ORIGINAL_SEAL=PASS", flush=True)
        import pwd
        user = pwd.getpwnam("kmjstage")
        scratch = Path(tempfile.mkdtemp(prefix="kmj-view-repair-", dir="/run"))
        scratch.chmod(0o711)
        output = scratch / "compiled"
        output.mkdir(mode=0o700)
        os.chown(output, user.pw_uid, user.pw_gid)
        need(b"COMPILE_OK\n" in php(PHP_COMPILE, output), "COMPILE")
        need(b"HEALTH_OK\n" in php(PHP_HEALTH, output), "SCRATCH_HEALTH")
        print("FINAL_PATH_COMPILE=PASS SCRATCH_HEALTH=PASS", flush=True)
        if not args.apply:
            print("VIEW_REPAIR=DRY_RUN_NO_SEAL_CHANGE")
            print("SCRATCH="+str(scratch))
            return
        next_views = Path(tempfile.mkdtemp(prefix="views.before-repair-", dir=FRAMEWORK))
        next_views.chmod(0o755)
        count = copy_views(output, next_views, user.pw_uid)
        guard(b)
        need(b["seal_sha"](APP) == old_seal.decode().strip(), "ORIGINAL_SEAL_DRIFT")
        witness = Path(tempfile.mkdtemp(prefix="kmj-view-seal-backup-", dir="/root"))
        (witness / "original.sha256").write_bytes(old_seal)
        print("ORIGINAL_SEAL_BACKUP="+str(witness), flush=True)
        print("ORIGINAL_VIEWS_BACKUP="+str(next_views), flush=True)
        swapped = False
        new_seal = None
        try:
            exchange(VIEWS, next_views)
            swapped = True
            sync_dir(FRAMEWORK)
            need(b"HEALTH_OK\n" in php(PHP_HEALTH), "FINAL_IMMUTABLE_HEALTH")
            new_seal = (b["seal_sha"](APP) + "\n").encode()
            guard(b)
            replace_seal(old_seal, new_seal)
            need(read_file(SEAL, 0, 65)[0] == new_seal, "SEAL_READBACK")
            need(b["seal_sha"](APP) == new_seal.decode().strip(), "FINAL_SEAL")
            guard(b)
        except BaseException:
            if swapped:
                current = read_file(SEAL, 0, 65)[0]
                need(current in (old_seal, new_seal), "ROLLBACK_SEAL_DRIFT")
                exchange(VIEWS, next_views)
                sync_dir(FRAMEWORK)
                if current != old_seal:
                    replace_seal(current, old_seal)
                need(b["seal_sha"](APP) == old_seal.decode().strip(), "ROLLBACK_SEAL")
                print("VIEW_REPAIR_ROLLBACK=PASS", flush=True)
            raise
        print("COMPILED_VIEWS="+str(count))
        print("IMMUTABLE_HEALTH=PASS")
        print("CANDIDATE_SECURITY_SEAL=REGENERATED_VERIFIED")
        print("STAGING_POINTER=UNCHANGED PRODUCTION_POINTER=UNCHANGED APPROVAL_UPDATED=NO")
        print("VIEW_REPAIR=PASS")


if __name__ == "__main__":
    def interrupted(_signum, _frame):
        raise InterruptedError("SIGNAL")
    signal.signal(signal.SIGHUP, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as e:
        # No raw subprocess output, environment or credentials.
        print("VIEW_REPAIR=BLOCKED_" + (str(e) if isinstance(e, ValueError)
              and re.fullmatch(r"[A-Z_]+", str(e)) else type(e).__name__))
        raise SystemExit(2)
