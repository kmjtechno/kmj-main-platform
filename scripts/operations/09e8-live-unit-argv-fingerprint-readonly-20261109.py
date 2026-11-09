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


# Emitted diagnostic identifiers are fixed source constants only. Never
# interpolate systemctl output, exceptions, argv, environment or paths.
STAGES = frozenset({
    "ROOT_SCOPE", "LIVE_POINTER_BEFORE", "QUEUE_UNIT_READ",
    "SCHEDULER_UNIT_READ", "TIMER_UNIT_READ", "TIMER_TRIGGER",
    "QUEUE_COMMAND", "SCHEDULER_COMMAND", "LIVE_POINTER_AFTER",
    "SECOND_READ_STABILITY",
})
REASONS = frozenset({
    "ARGUMENTS_NOT_ALLOWED", "ROOT_ELITE_ONLY", "LIVE_RELEASE_CHANGED",
    "UNIT_NOT_FIXED", "UNAPPROVED_FIELDS", "SYSTEMD_READ_UNVERIFIABLE",
    "SYSTEMD_FIELDS_UNVERIFIED", "SYSTEMD_FIELDS_MISSING",
    "NOT_FIXED_PHP_ARTISAN", "DUPLICATE_OR_LONG_OPTION",
    "NUMERIC_OPTION_BOUNDS", "UNREVIEWED_OPTION",
    "UNIT_POLICY_UNVERIFIED", "QUEUE_LIFETIME_UNVERIFIED",
    "SCHEDULER_RUNNING_OR_UNVERIFIED", "LIVE_APP_WORKDIR_MISMATCH",
    "SERVICE_EXEC_FORMAT_UNVERIFIED", "SERVICE_EXECUTABLE_UNVERIFIED",
    "ARTISAN_PATH_UNVERIFIED", "SCHEDULER_TIMER_SCOPE_UNVERIFIED",
    "UNIT_GENERATION_CHANGED", "RUNTIME_UNVERIFIABLE",
})

# Only these fixed category names can be returned. Never include raw
# ExecStart flags, values, tokens, filesystem paths, or process arguments.
# Exact Laravel queue connection names previously classified as KNOWN_QUEUE_CONNECTION.
# This is only a read-only command-identity validator; a matching fingerprint
# never admits, stops or restarts live writers.
KNOWN_QUEUE_CONNECTIONS = frozenset({"database", "redis", "sqs", "sync", "beanstalkd"})

OPTION_SHAPES = frozenset({
    "KNOWN_QUEUE_CONNECTION", "SPLIT_NUMERIC_OPTION",
    "SPLIT_NUMERIC_VALUE", "SPLIT_QUEUE_OPTION",
    "VERBOSITY_OPTION", "QUEUE_NAME_REJECTED",
    "SENSITIVE_OPTION", "UNKNOWN_LONG_VALUE_OPTION",
    "UNKNOWN_LONG_FLAG", "UNKNOWN_SHORT_FLAG",
    "UNKNOWN_POSITIONAL", "UNKNOWN_SYNTAX",
})


class UnreviewedOption(Refused):
    def __init__(self, shape: str):
        self.shape = shape if shape in OPTION_SHAPES else "UNKNOWN_SYNTAX"
        super().__init__("UNREVIEWED_OPTION")


def classify_option_shape(value: str) -> str:
    """Privacy-preserving syntax class only; never makes an option safe."""
    if not isinstance(value, str) or len(value) > 100:
        return "UNKNOWN_SYNTAX"
    low = value.lower()
    if any(secret in low for secret in (
            "password", "passwd", "secret", "token", "credential",
            "private", "authorization", "api-key", "api_key")):
        return "SENSITIVE_OPTION"
    if value in KNOWN_QUEUE_CONNECTIONS:
        return "KNOWN_QUEUE_CONNECTION"
    if value in {"--sleep", "--tries", "--timeout", "--memory",
                 "--backoff", "--max-time", "--max-jobs"}:
        return "SPLIT_NUMERIC_OPTION"
    if re.fullmatch(r"[0-9]{1,10}", value):
        return "SPLIT_NUMERIC_VALUE"
    if value == "--queue":
        return "SPLIT_QUEUE_OPTION"
    if value in {"--verbose", "-v", "-vv", "-vvv"}:
        return "VERBOSITY_OPTION"
    if value.startswith("--queue="):
        return "QUEUE_NAME_REJECTED"
    if value.startswith("--") and "=" in value:
        return "UNKNOWN_LONG_VALUE_OPTION"
    if value.startswith("--"):
        return "UNKNOWN_LONG_FLAG"
    if value.startswith("-"):
        return "UNKNOWN_SHORT_FLAG"
    if re.fullmatch(r"[A-Za-z0-9_.:/-]{1,100}", value):
        return "UNKNOWN_POSITIONAL"
    return "UNKNOWN_SYNTAX"


class AuditBlocked(Refused):
    def __init__(self, stage: str, reason: str, option_shape: str | None = None):
        self.stage = stage if stage in STAGES else "ROOT_SCOPE"
        self.reason = reason if reason in REASONS else "RUNTIME_UNVERIFIABLE"
        self.option_shape = option_shape if option_shape in OPTION_SHAPES else None
        super().__init__("BLOCKED_REDACTED")


def at(stage: str, action):
    """Classify a failed fixed step without exposing any untrusted input."""
    if stage not in STAGES:
        raise AuditBlocked("ROOT_SCOPE", "RUNTIME_UNVERIFIABLE")
    try:
        return action()
    except AuditBlocked:
        raise
    except UnreviewedOption as exc:
        raise AuditBlocked(stage, "UNREVIEWED_OPTION", exc.shape) from None
    except Refused as exc:
        reason = str(exc)
        raise AuditBlocked(stage, reason) from None
    except (OSError, ValueError, UnicodeError, KeyError,
            subprocess.SubprocessError):
        raise AuditBlocked(stage, "RUNTIME_UNVERIFIABLE") from None


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
    connection_seen = False
    for arg in args[3:]:
        insist(type(arg) is str and len(arg) <= 100
               and arg not in seen, "DUPLICATE_OR_LONG_OPTION")
        seen.add(arg)
        if command == "queue:work":
            # One finite, recognized Laravel positional connection, independent
            # of options ordering. Reject a second distinct positional name
            # rather than accidentally trusting an arbitrary trailing arg.
            if arg in KNOWN_QUEUE_CONNECTIONS:
                insist(not connection_seen, "DUPLICATE_OR_LONG_OPTION")
                connection_seen = True
                continue
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
        raise UnreviewedOption(classify_option_shape(arg))


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
    at("LIVE_POINTER_BEFORE", live_pointer)
    a = at("QUEUE_UNIT_READ", lambda: show(QUEUE, FIELDS))
    b = at("SCHEDULER_UNIT_READ", lambda: show(SCHEDULER, FIELDS))
    timer = at("TIMER_UNIT_READ", lambda: show(TIMER, ("ActiveState", "Triggers")))
    at("TIMER_TRIGGER", lambda: insist(
        timer == {"ActiveState": "active", "Triggers": SCHEDULER},
        "SCHEDULER_TIMER_SCOPE_UNVERIFIED"))
    queue_hash = at("QUEUE_COMMAND", lambda: fingerprint(QUEUE, a))
    scheduler_hash = at("SCHEDULER_COMMAND", lambda: fingerprint(SCHEDULER, b))
    at("LIVE_POINTER_AFTER", live_pointer)
    return queue_hash, scheduler_hash


def main(args: list[str]) -> int:
    print("SCHEMA=kmj.09e8.live-unit-argv-fingerprint.readonly.v1")
    try:
        at("ROOT_SCOPE", lambda: insist(not args, "ARGUMENTS_NOT_ALLOWED"))
        at("ROOT_SCOPE", lambda: insist(
            os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite",
            "ROOT_ELITE_ONLY"))
        first = attest_once()
        second = attest_once()
        at("SECOND_READ_STABILITY", lambda: insist(
            first == second, "UNIT_GENERATION_CHANGED"))
        print("QUEUE_ARGV_SHA256=" + first[0])
        print("SCHEDULER_ARGV_SHA256=" + first[1])
        print("ARGV_SAFE_SCHEMA=YES")
        print("EXPECTED_LIVE_RELEASE=platform-bce4100d005e")
        print("ARGV_FINGERPRINT=READ_ONLY_VERIFIED")
        rc = 0
    except AuditBlocked as exc:
        print("ARGV_BLOCKER_STAGE=" + exc.stage)
        print("ARGV_BLOCKER_REASON=" + exc.reason)
        if exc.reason == "UNREVIEWED_OPTION" and exc.option_shape is not None:
            print("ARGV_UNREVIEWED_SHAPE=" + exc.option_shape)
        print("ARGV_FINGERPRINT=BLOCKED_UNVERIFIABLE")
        rc = 2
    except (Refused, OSError, ValueError, UnicodeError, KeyError,
            subprocess.SubprocessError):
        print("ARGV_BLOCKER_STAGE=ROOT_SCOPE")
        print("ARGV_BLOCKER_REASON=RUNTIME_UNVERIFIABLE")
        print("ARGV_FINGERPRINT=BLOCKED_UNVERIFIABLE")
        rc = 2
    print("WRITER_ADMISSION=NOT_ATTESTED")
    print("STORAGE_APPLY_ALLOWED=NO")
    print("PRODUCTION_MUTATION=NONE")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
