#!/usr/bin/env python3
"""One-time KMJ-elite installer for the read-only release readiness publisher.

Owner invocation only. The only remotely retrieved source is the exact immutable
main-platform merge commit below; no checkout hooks, shell, arbitrary URL,
approvals, candidate release, database, symlink or production mutation.

--inspect: no mutations.
--install: guarded fixed root-owned publisher file and unit templates; the timer is NOT enabled.
--install --enable-timer: additionally enables ONLY the publisher timer. This flag is the owner's explicit
    approval to enable it. The publisher only writes a read-only receipt for the Ops page; this installer
    never starts the production release unit, writes an approval or switches LIVE.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile

SOURCE_COMMIT = "003f49aabac0bb067707e5137a74104646547e74"
SOURCE_URL = "https://github.com/kmjtechno/kmj-main-platform.git"
EXPECTED_HOST = "KMJ-elite"
GATE = Path("/opt/kmj-main-platform-autopublish/main_platform_autopublish_gate.py")
TARGETS = (
    (
        "scripts/operations/elite_release_readiness_receipt.py",
        Path("/opt/kmj-main-platform-release-readiness/elite_release_readiness_receipt.py"),
        0o500,
        20000,
    ),
    (
        "infra/server/systemd/kmj-elite-release-readiness-publisher.service",
        Path("/etc/systemd/system/kmj-elite-release-readiness-publisher.service"),
        0o644,
        10000,
    ),
    (
        "infra/server/systemd/kmj-elite-release-readiness-publisher.timer",
        Path("/etc/systemd/system/kmj-elite-release-readiness-publisher.timer"),
        0o644,
        10000,
    ),
)
SYSTEMD_TIMER = "kmj-elite-release-readiness-publisher.timer"
ENV = {
    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
    "HOME": "/root",
    "LANG": "C",
    "LC_ALL": "C",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_LFS_SKIP_SMUDGE": "1",
}


class Blocked(Exception):
    pass


def check(condition: bool, code: str) -> None:
    if not condition:
        raise Blocked(code)


def protected_dir(path: Path) -> bool:
    """Every ancestor is a real, root-owned, non-world-writable directory."""
    if not path.is_absolute() or ".." in path.parts:
        return False
    current = Path("/")
    for part in path.parts[1:]:
        current /= part
        try:
            info = os.lstat(current)
        except OSError:
            return False
        if (not stat.S_ISDIR(info.st_mode)
                or info.st_uid != 0 or (info.st_mode & 0o022)):
            return False
    return True


def classify_file(path: Path, mode: int, desired_digest: str | None = None) -> str:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return "MISSING"
    except OSError:
        return "UNTRUSTED"
    if (not protected_dir(path.parent) or not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0 or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != mode
            or info.st_size < 20 or info.st_size > 200000):
        return "UNTRUSTED"
    if desired_digest is None:
        return "PRESENT_UNATTESTED"
    h = hashlib.sha256()
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            while chunk := stream.read(65536):
                h.update(chunk)
            after = os.fstat(stream.fileno())
        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            return "UNTRUSTED"
    except OSError:
        return "UNTRUSTED"
    return "PIN_MATCH" if h.hexdigest() == desired_digest else "DIFFERENT"


def fixed_run(argv: list[str], timeout: int = 45) -> bytes:
    try:
        proc = subprocess.run(
            argv, cwd="/", env=ENV, capture_output=True,
            check=False, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("FIXED_TOOL_UNAVAILABLE") from None
    if proc.returncode != 0 or len(proc.stdout) > 250000:
        raise Blocked("FIXED_TOOL_FAILED")
    return proc.stdout


def reviewed_bytes() -> dict[Path, tuple[bytes, int]]:
    """Fetch exact Git object into disposable root-only bare repo, no checkout."""
    check(protected_dir(Path("/root")), "ROOT_PARENT_UNTRUSTED")
    with tempfile.TemporaryDirectory(prefix="kmj-rr-reviewed-", dir="/root") as dirname:
        root = Path(dirname)
        repo = root / "source.git"
        fixed_run(["/usr/bin/git", "init", "--bare", "--quiet", str(repo)])
        fixed_run([
            "/usr/bin/git", "-c", "credential.helper=", "-c",
            "core.hooksPath=/dev/null", "-C", str(repo),
            "fetch", "--no-tags", "--depth=1", SOURCE_URL, SOURCE_COMMIT,
        ], timeout=100)
        actual = fixed_run([
            "/usr/bin/git", "-C", str(repo), "rev-parse", "--verify",
            "FETCH_HEAD^{commit}",
        ]).decode("ascii", "strict").strip()
        check(actual == SOURCE_COMMIT, "REVIEWED_SOURCE_SHA_MISMATCH")
        results: dict[Path, tuple[bytes, int]] = {}
        for source, target, mode, limit in TARGETS:
            data = fixed_run([
                "/usr/bin/git", "--no-pager", "-C", str(repo),
                "show", SOURCE_COMMIT + ":" + source,
            ])
            check(20 < len(data) <= limit and b"\x00" not in data,
                  "REVIEWED_ARTIFACT_INVALID")
            results[target] = (data, mode)
        script = results[TARGETS[0][1]][0]
        service = results[TARGETS[1][1]][0]
        timer = results[TARGETS[2][1]][0]
        check(b"--publish" in script and b"release-readiness.json" in script,
              "PUBLISHER_ARTIFACT_DRIFT")
        check(b"--publish" in service and b"elite_release_readiness_receipt.py" in service
              and b"production-release.service" not in service
              and b"systemctl" not in service,
              "SERVICE_PUBLISHER_DRIFT")
        check(b"Unit=kmj-elite-release-readiness-publisher.service" in timer,
              "TIMER_SERVICE_DRIFT")
        return results


def install_new(path: Path, contents: bytes, mode: int) -> str:
    """No overwrite, no symlink following, atomic link of a root-created inode."""
    check(protected_dir(path.parent), "INSTALL_PARENT_UNTRUSTED")
    sha = hashlib.sha256(contents).hexdigest()
    existing = classify_file(path, mode, sha)
    if existing == "PIN_MATCH":
        return "ALREADY_INSTALLED_PIN_MATCH"
    check(existing == "MISSING", "EXISTING_ARTIFACT_MISMATCH")
    token = os.urandom(12).hex()
    tmp = path.parent / ("." + path.name + "." + token + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, mode, follow_symlinks=False)
        check(classify_file(tmp, mode, sha) == "PIN_MATCH",
              "STAGED_ARTIFACT_SHA_MISMATCH")
        try:
            os.link(tmp, path, follow_symlinks=False)
        except FileExistsError:
            raise Blocked("INSTALL_TARGET_RACE") from None
        # Remove the transient second hard link BEFORE checking the required
        # single-link root-owned installed inode. No overwrite or replace.
        os.unlink(tmp)
        check(classify_file(path, mode, sha) == "PIN_MATCH",
              "INSTALLED_ARTIFACT_SHA_MISMATCH")
        return "INSTALLED_PIN_MATCH"
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def require_operator() -> None:
    check(os.geteuid() == 0 and socket.gethostname().split(".")[0] == EXPECTED_HOST,
          "ROOT_ELITE_ONLY")
    for parent in (Path("/"), Path("/root"), Path("/opt"), Path("/etc"),
                   Path("/etc/systemd"), Path("/etc/systemd/system")):
        check(protected_dir(parent), "PROTECTED_PARENT_UNTRUSTED")


def run(mode: str, enable_timer: bool = False) -> int:
    require_operator()
    dest = TARGETS[0][1].parent
    if mode == "inspect":
        for i, (_, file, permissions, _) in enumerate(TARGETS, 1):
            print(f"KMJ_ELITE_RELEASE_READINESS_PUBLISHER_ARTIFACT_{i}="
                  + classify_file(file, permissions))
        print("KMJ_ELITE_RELEASE_READINESS_PUBLISHER_GATE="
              + classify_file(GATE, 0o500))
        print("KMJ_ELITE_RELEASE_READINESS_PUBLISHER_INSPECT=PASS_READ_ONLY")
        print("PRODUCTION_MUTATION=NONE")
        return 0

    check(mode == "install", "UNSUPPORTED_MODE")
    # The publisher imports only the already installed protected gate.
    check(classify_file(GATE, 0o500) in ("PRESENT_UNATTESTED", "PIN_MATCH"),
          "AUTOPUBLISH_GATE_MISSING_RUN_INSTALL_ELITE_AUTOPUBLISH_V2_FIRST")
    reviewed = reviewed_bytes()
    if not dest.exists():
        check(protected_dir(dest.parent), "INSTALL_OPT_PARENT_UNTRUSTED")
        os.mkdir(dest, 0o700)
    check(protected_dir(dest), "INSTALL_ROOT_UNTRUSTED")
    for file, (blob, permissions) in reviewed.items():
        result = install_new(file, blob, permissions)
        print(f"KMJ_ELITE_RELEASE_READINESS_PUBLISHER_FILE_{file.suffix.lstrip('.')}={result}")

    fixed_run([
        "/usr/bin/systemd-analyze", "verify",
        str(TARGETS[1][1]), str(TARGETS[2][1]),
    ])
    fixed_run(["/usr/bin/systemctl", "daemon-reload"])
    if enable_timer:
        # Publisher timer only. NEVER start the production release service or set approval flags.
        fixed_run(["/usr/bin/systemctl", "enable", "--now", SYSTEMD_TIMER])
        fixed_run(["/usr/bin/systemctl", "is-enabled", "--quiet", SYSTEMD_TIMER])
        fixed_run(["/usr/bin/systemctl", "is-active", "--quiet", SYSTEMD_TIMER])
        print("KMJ_ELITE_RELEASE_READINESS_PUBLISHER_TIMER=ACTIVE")
    else:
        print("KMJ_ELITE_RELEASE_READINESS_PUBLISHER_TIMER=NOT_ENABLED_RERUN_WITH_ENABLE_TIMER_TO_APPROVE")
    print("KMJ_ELITE_RELEASE_READINESS_PUBLISHER_INSTALL=PASS")
    print("PRODUCTION_RELEASE_SWITCH=NOT_ATTEMPTED")
    print("APPROVAL_UPDATED=NO")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect", action="store_true")
    group.add_argument("--install", action="store_true")
    parser.add_argument("--enable-timer", action="store_true")
    args = parser.parse_args()
    if args.enable_timer and not args.install:
        print("KMJ_ELITE_RELEASE_READINESS_PUBLISHER_INSTALL=BLOCKED_ENABLE_TIMER_NEEDS_INSTALL")
        return 2
    try:
        return run("install" if args.install else "inspect", args.enable_timer)
    except Blocked as error:
        print("KMJ_ELITE_RELEASE_READINESS_PUBLISHER_INSTALL=BLOCKED_" + str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
