#!/usr/bin/env python3
"""Sanitized exact-bce410 queue/scheduler argv SHA witness for 09e8 review.

READ ONLY, ROOT KMJ-elite, no caller-selected paths, services, args, shell,
process signals, firewall writes or release/approval control.
Hashes are emitted ONLY for schema-validated fixed PHP Artisan commands with
bounded non-secret option values. They match the digest scheme used by the
reviewed native_plan.argv_evidence (sha256(json.dumps(argv).encode())).
A digest here is still NOT proof of live writer quiescence.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import sys

CURRENT = "/home/kmjprod/releases/platform-bce4100d005e"
APP = CURRENT + "/apps/platform"
QUEUE = "kmj-main-platform-queue.service"
SCHEDULER = "kmj-main-platform-scheduler.service"
TIMER = "kmj-main-platform-scheduler.timer"
UNITS = {
    QUEUE: ("queue:work", "active", "always", "simple"),
    SCHEDULER: ("schedule:run", "inactive", "no", "oneshot"),
}
FIELDS = ("ExecStart", "WorkingDirectory", "User", "ActiveState",
          "Restart", "KillMode", "Type", "MainPID")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
       "HOME": "/nonexistent", "LC_ALL": "C"}


class Refused(Exception):
    pass


def insist(ok: bool, reason: str) -> None:
    if not ok:
        raise Refused(reason)


def live_pointer() -> None:
    current = Path("/home/kmjprod/current")
    insist(current.is_symlink()
           and str(current.resolve(strict=True)) == CURRENT,
           "LIVE_RELEASE_CHANGED")


def show(unit: str, properties: tuple[str, ...]) -> dict[str, str]:
    insist(unit in (QUEUE, SCHEDULER, TIMER), "UNIT_NOT_FIXED")
    insist(properties in (FIELDS, ("ActiveState", "Triggers")),
           "UNAPPROVED_FIELDS")
    p = subprocess.run(
        ["/usr/bin/systemctl", "show", unit, "--all",
         "--property=" + ",".join(properties), "--no-pager"],
        env=ENV, stdin=subprocess.DEVNULL,
        capture_output=True, check=False, timeout=12,
    )
    insist(p.returncode == 0 and len(p.stdout) <= 16384,
           "SYSTEMD_READ_UNVERIFIABLE")
    values: dict[str, str] = {}
    for line in p.stdout.decode("utf-8", "strict").splitlines():
        key, sep, value = line.partition("=")
        insist(bool(sep) and key in properties and key not in values,
               "SYSTEMD_FIELDS_UNVERIFIED")
        values[key] = value
    insist(set(values) == set(properties), "SYSTEMD_FIELDS_MISSING")
    return values


def safe_args(args: list[str], command: str) -> None:
    insist(type(args) is list and len(args) >= 3
           and args[0] == "/usr/bin/php8.4"
           and args[1] == "artisan"
           and args[2] == command, "NOT_FIXED_PHP_ARTISAN")
    seen = set()
    for arg in args[3:]:
        insist(type(arg) is str and len(arg) <= 100
               and arg not in seen, "DUPLICATE_OR_LONG_OPTION")
        seen.add(arg)
        if arg in ("--no-interaction", "--quiet", "-q"):
            continue
        if command == "queue:work":
            if arg in ("--once", "--stop-when-empty"):
                continue
            match = re.fullmatch(r"--(sleep|tries|timeout|memory|backoff|max-time|max-jobs)=([0-9]{1,10})", arg)
            if match:
                insist(int(match.group(2)) <= 100000000, "NUMERIC_OPTION_BOUNDS")
                continue
            match = re.fullmatch(r"--queue=([A-Za-z0-9_.-]{1,40}(?:,[A-Za-z0-9_.-]{1,40}){0,5})", arg)
            if match:
                continue
        raise Refused("UNREVIEWED_OPTION")


def fingerprint(unit: str, values: dict[str, str]) -> str:
    insist(unit in UNITS, "UNIT_NOT_FIXED")
    command, active, restart, service_type = UNITS[unit]
    insist(values.get("User") == "kmjprod"
           and values.get("ActiveState") == active
           and values.get("Restart") == restart
           and values.get("Type") == service_type,
           "UNIT_POLICY_UNVERIFIED")
    if unit == QUEUE:
        insist(values.get("KillMode") == "control-group"
               and values.get("MainPID", "").isdigit()
               and int(values["MainPID"]) > 0, "QUEUE_LIFETIME_UNVERIFIED")
    else:
        insist(values.get("MainPID") == "0", "SCHEDULER_RUNNING_OR_UNVERIFIED")
    cwd = values.get("WorkingDirectory", "")
    insist(cwd.startswith("/") and os.path.realpath(cwd) == APP,
           "LIVE_APP_WORKDIR_MISMATCH")
    effective = values.get("ExecStart", "")
    insist(type(effective) is str and effective.count("path=") == 1
           and effective.count("argv[]=") == 1
           and effective.strip().endswith("}")
           and not any(char in effective for char in ("$", "\\")),
           "SERVICE_EXEC_FORMAT_UNVERIFIED")
    parsed = re.match(r"\s*\{\s*path=([^;]+?)\s*;\s*argv\[\]=(.*?) ;", effective)
    insist(parsed is not None and parsed.group(1).strip() == "/usr/bin/php8.4",
           "SERVICE_EXECUTABLE_UNVERIFIED")
    args = shlex.split(parsed.group(2), posix=True)
    safe_args(args, command)
    insist(os.path.realpath(Path(cwd) / args[1]) == APP + "/artisan",
           "ARTISAN_PATH_UNVERIFIED")
    return hashlib.sha256(json.dumps(args).encode()).hexdigest()


def attest_once() -> tuple[str, str]:
    live_pointer()
    a = show(QUEUE, FIELDS)
    b = show(SCHEDULER, FIELDS)
    timer = show(TIMER, ("ActiveState", "Triggers"))
    insist(timer == {"ActiveState": "active", "Triggers": SCHEDULER},
           "SCHEDULER_TIMER_SCOPE_UNVERIFIED")
    queue_hash = fingerprint(QUEUE, a)
    scheduler_hash = fingerprint(SCHEDULER, b)
    live_pointer()
    return queue_hash, scheduler_hash


def main(args: list[str]) -> int:
    print("SCHEMA=kmj.09e8.live-unit-argv-fingerprint.readonly.v1")
    try:
        insist(not args, "ARGUMENTS_NOT_ALLOWED")
        insist(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite",
               "ROOT_ELITE_ONLY")
        first = attest_once()
        second = attest_once()
        insist(first == second, "UNIT_GENERATION_CHANGED")
        print("QUEUE_ARGV_SHA256=" + first[0])
        print("SCHEDULER_ARGV_SHA256=" + first[1])
        print("ARGV_SAFE_SCHEMA=YES")
        print("EXPECTED_LIVE_RELEASE=platform-bce4100d005e")
        print("ARGV_FINGERPRINT=READ_ONLY_VERIFIED")
        rc = 0
    except (Refused, OSError, ValueError, UnicodeError, KeyError,
            subprocess.SubprocessError) as exc:
        print("ARGV_FINGERPRINT=BLOCKED_UNVERIFIABLE")
        rc = 2
    print("WRITER_ADMISSION=NOT_ATTESTED")
    print("STORAGE_APPLY_ALLOWED=NO")
    print("PRODUCTION_MUTATION=NONE")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
