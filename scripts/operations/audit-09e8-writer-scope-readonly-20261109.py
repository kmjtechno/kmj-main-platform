#!/usr/bin/env python3
"""Exact KMJ-elite 09e8 candidate writer-admission audit: READ ONLY, NEVER apply.

No arbitrary argv, paths, shell, SSH, deployment, systemd changes, or secrets.
This reports service/scheduler policy and an immutable-source v6 storage plan.
It cannot attest process generation, PHP-FPM pool isolation, queue drain,
network admission or writer quiescence and MUST NEVER authorize a storage switch.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

TARGET = "09e8a224cd37445c42588a073a6b52d207475a09"
CURRENT = "platform-bce4100d005e"
ROOT = Path("/home/kmjprod")
APP = ROOT / "releases" / ("platform-" + TARGET[:12]) / "apps/platform"
SHARED = ROOT / "shared/storage"
SCANNER = Path("/usr/local/libexec/kmj-codebridge/main-platform-storage-switch-v6.py")
SCANNER_SHA = "f4d01f6e3b40c9ad774c8ada5129b241cee93dac782ce75bb0e229b26bbc95ba"
HELPER = Path("/usr/local/libexec/kmj-codebridge/main-platform-storage-snapshot-attest.py")
HELPER_SHA = "72fe5702c59599bd1b28b88dad808dda5d6be97b61f0db06dc3a7295258a51b6"
QUEUE = "kmj-main-platform-queue.service"
SCHEDULER = "kmj-main-platform-scheduler.service"
TIMER = "kmj-main-platform-scheduler.timer"
FPM = "php8.4-fpm.service"
NGINX = "nginx.service"
UNITS = (QUEUE, SCHEDULER, TIMER, FPM, NGINX)
PROPS = ("LoadState", "ActiveState", "SubState", "MainPID", "Restart", "KillMode",
         "TimeoutStopUSec", "User", "Triggers")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "HOME": "/nonexistent"}


class Blocked(Exception):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise Blocked(reason)


def protected_sha(path: Path, digest: str) -> None:
    require(str(path) == os.path.realpath(path), "DEPENDENCY_PATH")
    for parent in path.parents:
        st = parent.lstat()
        require(stat.S_ISDIR(st.st_mode) and st.st_uid == 0 and not st.st_mode & 0o022,
                "DEPENDENCY_PARENT")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == 0
                and before.st_nlink == 1 and not before.st_mode & 0o022
                and 0 < before.st_size <= 1024 * 1024, "DEPENDENCY_MODE")
        h = hashlib.sha256()
        remaining = before.st_size
        while remaining:
            buf = os.read(fd, min(65536, remaining))
            require(bool(buf), "DEPENDENCY_SHORT_READ")
            h.update(buf)
            remaining -= len(buf)
        after = os.fstat(fd)
        current = path.lstat()
        stamp = lambda st: (st.st_dev, st.st_ino, st.st_mode, st.st_uid,
                            st.st_nlink, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        require(stamp(before) == stamp(after) == stamp(current), "DEPENDENCY_CHANGED")
        require(h.hexdigest() == digest, "DEPENDENCY_SHA_MISMATCH")
    finally:
        os.close(fd)


def unit_properties(unit: str) -> dict[str, str]:
    require(unit in UNITS, "UNIT_NOT_FIXED")
    p = subprocess.run(
        ["/usr/bin/systemctl", "show", unit, "--all",
         "--property=" + ",".join(PROPS), "--no-pager"],
        stdin=subprocess.DEVNULL, capture_output=True, check=False, timeout=12, env=ENV)
    require(p.returncode == 0 and len(p.stdout) <= 16384, "UNIT_READ_FAILED")
    rows: dict[str, str] = {}
    for line in p.stdout.decode("utf-8", "strict").splitlines():
        key, sep, value = line.partition("=")
        require(bool(sep) and key in PROPS and key not in rows, "UNIT_PROPERTIES_INVALID")
        rows[key] = value
    require(set(rows) == set(PROPS), "UNIT_PROPERTIES_MISSING")
    return rows


def unit_assessment(rows: dict[str, str], unit: str) -> dict[str, str]:
    require(unit in UNITS, "UNIT_NOT_FIXED")
    active = rows.get("ActiveState")
    loaded = rows.get("LoadState")
    label = {QUEUE: "QUEUE", SCHEDULER: "SCHEDULER", TIMER: "SCHEDULER_TIMER",
             FPM: "PHP_FPM", NGINX: "NGINX"}[unit]
    if loaded != "loaded" or active not in {"active", "inactive", "failed"}:
        return {label + "_STATE": "UNVERIFIED"}
    output = {label + "_STATE": active.upper()}
    if unit == QUEUE:
        output["QUEUE_RESTART_ALWAYS"] = "YES" if rows.get("Restart") == "always" else "NO_OR_UNVERIFIED"
        output["QUEUE_SERVICE_IDENTITY"] = "EXPECTED" if rows.get("User") == "kmjprod" else "UNVERIFIED"
        output["QUEUE_KILL_CONTROL_GROUP"] = "YES" if rows.get("KillMode") == "control-group" else "NO_OR_UNVERIFIED"
        stop = rows.get("TimeoutStopUSec", "")
        output["QUEUE_STOP_TIMEOUT_REPORTED"] = "YES" if stop and stop != "infinity" else "NO_OR_UNVERIFIED"
        output["QUEUE_PROCESS_RUNNING"] = "YES" if rows.get("MainPID", "").isdigit() and int(rows["MainPID"]) > 0 else "NO"
    if unit == TIMER:
        output["TIMER_TRIGGERS_EXPECTED_SCHEDULER"] = (
            "YES" if rows.get("Triggers", "").strip() == SCHEDULER else "NO_OR_UNVERIFIED"
        )
    if unit == FPM:
        output["PHP_FPM_RUNNING"] = "YES" if active == "active" else "NO"
        output["PRODUCTION_FPM_POOL_DRAINED"] = "NOT_ATTESTED"
    return output


def storage_plan(raw: str, rc: int) -> dict[str, str]:
    try:
        info = json.loads(raw)
    except (ValueError, TypeError):
        raise Blocked("PLAN_JSON")
    require(type(info) is dict and rc == 0 and info.get("command") == "plan"
            and info.get("mutated") is False
            and info.get("inventory_only_not_release_readiness") is True, "PLAN_SCOPE")
    conflicts = info.get("persistent_conflicts")
    require(type(conflicts) is list and all(isinstance(v, str) for v in conflicts), "PLAN_CONFLICTS")
    require(type(info.get("ready")) is bool and
            all(type(info.get(k)) is int and 0 <= info[k] <= 200000
                for k in ("live_files", "shared_files", "to_copy")), "PLAN_FIELDS")
    planid = info.get("plan_id")
    require(isinstance(planid, str) and re.fullmatch(r"[0-9a-f]{16}", planid) is not None,
            "PLAN_ID_INVALID")
    return {"STORAGE_PLAN_READY": "YES" if info["ready"] else "NO",
            "STORAGE_PLAN_ID": planid,
            "STORAGE_TO_COPY": str(info["to_copy"]),
            "STORAGE_PERSISTENT_CONFLICT_COUNT": str(len(conflicts)),
            "STORAGE_SHARED_FILE_COUNT": str(info["shared_files"]),
            "STORAGE_CANDIDATE_FILE_COUNT": str(info["live_files"])}


def verify_layout() -> None:
    require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite",
            "HOST_OR_USER")
    current = ROOT / "current"
    require(current.is_symlink()
            and current.resolve(strict=True) == ROOT / "releases" / CURRENT, "LIVE_POINTER")
    live_storage = current / "apps/platform/storage"
    require(live_storage.is_symlink() and os.readlink(live_storage) == str(SHARED)
            and SHARED.is_dir() and not SHARED.is_symlink(), "LIVE_SHARED_LAYOUT")
    storage = APP / "storage"
    require(stat.S_ISDIR(storage.lstat().st_mode) and not storage.is_symlink(),
            "CANDIDATE_LAYOUT")
    require(APP.is_dir() and not APP.is_symlink(), "CANDIDATE_APP")
    require(not (APP / ".env").exists() and not (APP / ".env").is_symlink(),
            "CANDIDATE_ALREADY_MATERIALIZED")


def execute() -> dict[str, str]:
    verify_layout()
    protected_sha(SCANNER, SCANNER_SHA)
    protected_sha(HELPER, HELPER_SHA)
    reports: dict[str, str] = {
        "SOURCE_CANDIDATE_SHA": TARGET,
        "LIVE_RELEASE": CURRENT,
        "PINNED_STORAGE_DEPENDENCIES": "PASS",
    }
    for unit in UNITS:
        reports.update(unit_assessment(unit_properties(unit), unit))
    p = subprocess.run(
        [sys.executable, "-I", "-B", str(SCANNER), "plan",
         "--app-dir", str(APP), "--shared", str(SHARED),
         "--allowed-root", str(ROOT)],
        stdin=subprocess.DEVNULL, capture_output=True, check=False, timeout=75, env=ENV)
    require(len(p.stdout) <= 65536, "PLAN_OUTPUT_LIMIT")
    reports.update(storage_plan(p.stdout.decode("utf-8", "strict"), p.returncode))
    require(current_pointer_ok(), "LIVE_POINTER_CHANGED")
    return reports


def current_pointer_ok() -> bool:
    link = ROOT / "current"
    try:
        return link.is_symlink() and link.resolve(strict=True) == ROOT / "releases" / CURRENT
    except OSError:
        return False


def main() -> int:
    print("SCHEMA=kmj.09e8.writer-scope.readonly.v1")
    try:
        report = execute()
    except (Blocked, OSError, subprocess.TimeoutExpired, UnicodeError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, Blocked) else "UNVERIFIABLE_RUNTIME"
        print("WRITER_SCOPE_AUDIT=BLOCKED_" + reason)
        print("WRITER_EXCLUSION=NOT_ATTESTED")
        print("STORAGE_APPLY_ALLOWED=NO")
        print("PRODUCTION_MUTATION=NONE")
        return 2
    for key, value in report.items():
        print(key + "=" + value)
    print("WRITER_EXCLUSION=NOT_ATTESTED")
    print("STORAGE_APPLY_ALLOWED=NO")
    print("PRODUCTION_MUTATION=NONE")
    print("WRITER_SCOPE_AUDIT=READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
