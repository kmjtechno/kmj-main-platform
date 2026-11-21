#!/usr/bin/env python3
"""Fixed-capability Elite production activation broker, INSTALL-OPT-IN ONLY.

An owner-authenticated web request is *intent*, NEVER release approval.
Root independently rechecks the existing protected approval, immutable exact
SHA/predecessor, staged branch SHA, candidate source and admission evidence
before asking the existing production unit to start. Neither accepted
systemd start nor broker exit 0 is proof of an activated LIVE release.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import subprocess
import sys
import time
import uuid

HOST = "KMJ-elite"
OWNER_USER = "kmjprod"
INTENT = Path("/home/kmjprod/shared/storage/app/private/ops/production-activation-request.json")
GATE = Path("/opt/kmj-main-platform-autopublish/main_platform_autopublish_gate.py")
STATE_DIR = Path("/var/lib/kmj-main-platform/activation-broker")
UNIT = "kmj-main-platform-production-release.service"
SHA_RE = re.compile(r"[a-f0-9]{40}\Z")
RELEASE_RE = re.compile(r"platform-[a-f0-9]{12}\Z")
INTENT_KEYS = frozenset({
    "schema", "intent_id", "actor_user_id", "action", "approved_sha",
    "expected_current_release", "created_at_unix", "expires_at_unix",
})
MAX_BYTES = 2048


def strict_json(data: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("BLOCKED_DUPLICATE_INTENT_FIELD")
            result[key] = value
        return result
    try:
        obj = json.loads(
            data.decode("utf-8"), object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("BLOCKED_NONFINITE")),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("BLOCKED_INTENT_FORMAT") from exc
    if not isinstance(obj, dict) or set(obj) != INTENT_KEYS:
        raise ValueError("BLOCKED_INTENT_SCHEMA")
    return obj


def validate_intent(obj: dict, now: int) -> dict:
    if (obj.get("schema") != "kmj.elite.production-activation-intent.v1"
            or obj.get("action") != "activate_existing_approved_release"):
        raise ValueError("BLOCKED_INTENT_ACTION")
    requested_id = obj.get("intent_id")
    try:
        parsed_id = uuid.UUID(requested_id, version=4)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("BLOCKED_INTENT_ID") from exc
    if str(parsed_id) != requested_id or parsed_id.version != 4:
        raise ValueError("BLOCKED_INTENT_ID")
    actor = obj.get("actor_user_id")
    if type(actor) is not int or not (1 <= actor <= 2147483647):
        raise ValueError("BLOCKED_ACTOR_ID")
    sha, previous = obj.get("approved_sha"), obj.get("expected_current_release")
    if (not isinstance(sha, str) or not SHA_RE.fullmatch(sha)
            or not isinstance(previous, str) or not RELEASE_RE.fullmatch(previous)
            or previous == "platform-" + sha[:12]):
        raise ValueError("BLOCKED_RELEASE_IDENTITY")
    created, expires = obj.get("created_at_unix"), obj.get("expires_at_unix")
    if (type(created) is not int or type(expires) is not int or
            created > now + 5 or created < now - 120 or expires <= now or
            expires > created + 120 or expires < created):
        raise ValueError("BLOCKED_INTENT_EXPIRED_OR_FUTURE")
    return obj


def read_owner_intent(path: Path, uid: int, now: int) -> dict:
    # Exactly one fixed, preconfigured input file; never read a supplied path.
    parent = path.parent.lstat()
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != uid or
            stat.S_IMODE(parent.st_mode) & 0o022):
        raise ValueError("BLOCKED_INTENT_PARENT")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o027
                or not 128 <= info.st_size <= MAX_BYTES):
            raise ValueError("BLOCKED_INTENT_IDENTITY")
        data = os.read(fd, MAX_BYTES + 1)
        after = os.fstat(fd)
        if (len(data) != info.st_size or after.st_size != info.st_size
                or after.st_mtime_ns != info.st_mtime_ns):
            raise ValueError("BLOCKED_INTENT_RACE")
        return validate_intent(strict_json(data), now)
    finally:
        os.close(fd)


def trusted_gate():
    parent, info = GATE.parent.lstat(), GATE.lstat()
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0
            or stat.S_IMODE(parent.st_mode) & 0o022
            or not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o022
            or not 1000 <= info.st_size <= 30000):
        raise ValueError("BLOCKED_FIXED_GATE_IDENTITY")
    # Avoid writing bytecode into the trusted root-owned install directory.
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("kmj_fixed_release_gate", GATE)
    if spec is None or spec.loader is None:
        raise ValueError("BLOCKED_FIXED_GATE_IMPORT")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    return gate


def protected_activation_match(obj: dict, gate) -> str:
    approval = gate.protected_json(gate.APPROVAL)
    if not isinstance(approval, dict):
        raise ValueError("BLOCKED_APPROVAL_UNAVAILABLE")
    sha = obj["approved_sha"]
    admission = gate.protected_json(
        gate.ADMISSION_DIR / ("main-platform-autopublish-" + sha[:12] + ".json")
    )
    current = gate.live_release()
    remote = gate.remote_sha()
    candidate = gate.candidate_sha(sha)
    outcome = gate.decision(approval, admission, current, remote, candidate)
    if (outcome != "READY_APPROVED_RELEASE"
            or approval.get("approvedSha") != sha
            or approval.get("expectedCurrentRelease") != obj["expected_current_release"]
            or current != obj["expected_current_release"]
            or remote != sha or candidate != sha):
        raise ValueError("BLOCKED_PROTECTED_GATE_" + outcome[:45])
    return outcome


def check_root_state_dir() -> None:
    info = STATE_DIR.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise ValueError("BLOCKED_ROOT_STATE_DIR")


def claim_once(obj: dict, now: int) -> Path:
    check_root_state_dir()
    path = STATE_DIR / (obj["intent_id"] + ".claimed")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            data = (json.dumps({
                "intent_id": obj["intent_id"], "approved_sha": obj["approved_sha"],
                "expected_current_release": obj["expected_current_release"],
                "claimed_at_unix": now, "status": "START_REQUESTED_NOT_PROVEN",
            }, separators=(",", ":")) + "\n").encode()
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        dirfd = os.open(STATE_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except BaseException:
        # Preserve the no-replay marker on uncertain write failures.
        raise
    return path


def previously_claimed(obj: dict) -> bool:
    """An identical root-owned claimed marker means no replay, not LIVE PASS."""
    check_root_state_dir()
    path = STATE_DIR / (obj["intent_id"] + ".claimed")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return False
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o077
                or not 64 <= info.st_size <= 512):
            raise ValueError("BLOCKED_CLAIM_IDENTITY")
        data = os.read(fd, 513)
        if len(data) != info.st_size:
            raise ValueError("BLOCKED_CLAIM_PARTIAL")
        claimed = strict_claim(data)
        if (claimed.get("intent_id") != obj["intent_id"]
                or claimed.get("approved_sha") != obj["approved_sha"]
                or claimed.get("expected_current_release") != obj["expected_current_release"]
                or claimed.get("status") != "START_REQUESTED_NOT_PROVEN"):
            raise ValueError("BLOCKED_CLAIM_MISMATCH")
        return True
    finally:
        os.close(fd)


def strict_claim(data: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("BLOCKED_CLAIM_DUPLICATE")
            result[key] = value
        return result
    try:
        parsed = json.loads(data.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("BLOCKED_CLAIM_JSON") from exc
    if (not isinstance(parsed, dict) or set(parsed) != {
        "intent_id", "approved_sha", "expected_current_release",
        "claimed_at_unix", "status"
    } or type(parsed["claimed_at_unix"]) is not int):
        raise ValueError("BLOCKED_CLAIM_SCHEMA")
    return parsed


def fixed_unit_status() -> bool:
    # The unit name is constant and not taken from browser-controlled JSON.
    try:
        p = subprocess.run(
            ["/usr/bin/systemctl", "show", UNIT,
             "-p", "LoadState", "-p", "ActiveState", "--value"],
            check=False, capture_output=True, text=True, timeout=12,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return p.returncode == 0 and p.stdout.splitlines() == ["loaded", "inactive"]


def trigger_fixed_unit() -> bool:
    try:
        p = subprocess.run(
            ["/usr/bin/systemctl", "start", UNIT],
            check=False, timeout=180, capture_output=True, text=True,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"},
            cwd="/",
        )
        return p.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run(execute: bool, *, now: int | None = None) -> int:
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != HOST:
        print("KMJ_ACTIVATION_BROKER=BLOCKED_HOST_ROOT")
        return 2
    now = int(time.time()) if now is None else now
    try:
        uid = pwd.getpwnam(OWNER_USER).pw_uid
        try:
            obj = read_owner_intent(INTENT, uid, now)
        except FileNotFoundError:
            print("KMJ_ACTIVATION_BROKER=NO_PENDING_INTENT")
            return 0
        if previously_claimed(obj):
            print("KMJ_ACTIVATION_BROKER=ALREADY_REQUESTED_NOT_LIVE_PROOF")
            return 0
        protected_activation_match(obj, trusted_gate())
        if not fixed_unit_status():
            raise ValueError("BLOCKED_FIXED_UNIT_NOT_READY")
        if not execute:
            print("KMJ_ACTIVATION_BROKER=EXACT_PROTECTED_PREFLIGHT_PASS")
            print("PRODUCTION_MUTATION=NONE")
            return 0
        claim_once(obj, now)
        accepted = trigger_fixed_unit()
        print("KMJ_ACTIVATION_BROKER=" + (
            "UNIT_START_ACCEPTED_NOT_LIVE_PROOF" if accepted else
            "BLOCKED_UNIT_START_FAILED_REVIEW_REQUIRED"
        ))
        print("LIVE_RELEASE_VERIFIED=NO")
        return 0 if accepted else 3
    except (ValueError, OSError, KeyError, AttributeError, ImportError, TimeoutError) as exc:
        error = str(exc)
        code = error if error.startswith("BLOCKED_") else "BLOCKED_TRUSTED_PREFLIGHT_ERROR"
        print("KMJ_ACTIVATION_BROKER=" + code[:95])
        return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    return run(execute=args.execute)


if __name__ == "__main__":
    raise SystemExit(main())
