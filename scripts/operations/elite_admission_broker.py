#!/usr/bin/env python3
"""Fixed root admission broker (source only, INSTALL-OPT-IN, never auto-started).

An owner-authenticated web request is INTENT, never approval. After the owner's
passkey step-up the web app drops one short-lived intent file. Root then, and only
then, independently re-verifies everything and writes the per-release admission
file that the existing fixed gate requires:

  * the protected approval names this exact SHA and predecessor,
  * the live pointer is that predecessor,
  * every non-owner receipt (staging-origin, public-qa, backup-witness,
    disposable-restore, rollback-rehearsal, migration-storage) is fresh, exact-SHA
    and passing, read from the root-protected receipt directory,
  * the intent carries the owner's explicit authenticated-QA attestation; root mints
    the `authenticated-qa` receipt from it (an owner attestation, labelled as such).

It writes ONLY the admission file (0600 root, no clobber).
The fixed systemd dependency prepares the Nginx SHA map separately;
this broker checks the exact pair again before admitting a release. It starts no unit,
changes no approval or pointer, and touches no production data.

  --inspect   verify everything, write nothing
  --execute   verify and write the admission file
"""
import hashlib
import json
import os
import pwd
import socket
import stat
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import release_admission_receipts as ra  # noqa: E402
import release_receipt_store as store  # noqa: E402
import elite_collect_staging_origin_receipt as common  # noqa: E402
import main_platform_autopublish_gate as gate  # noqa: E402
import production_release_sha_map as sha_map  # noqa: E402
import refresh_production_release_sha_map as map_refresh  # noqa: E402

HOST = "KMJ-elite"
OWNER_USER = "kmjprod"
INTENT = Path("/home/kmjprod/shared/storage/app/private/ops/release-admission-request.json")
STATE_DIR = Path("/var/lib/kmj-main-platform/admission-broker")
INTENT_SCHEMA = "kmj.elite.release-admission-intent.v1"
INTENT_ACTION = "write_release_admission"
INTENT_KEYS = frozenset({
    "schema", "intent_id", "actor_user_id", "action", "approved_sha",
    "expected_current_release", "created_at_unix", "expires_at_unix",
    "owner_authenticated_qa_attested",
})
MAX_BYTES = 2048


def parse_intent(data, now):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError("BLOCKED_DUPLICATE_INTENT_FIELD")
            out[k] = v
        return out
    try:
        obj = json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("BLOCKED_NONFINITE")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("BLOCKED_INTENT_FORMAT") from exc
    if not isinstance(obj, dict) or set(obj) != INTENT_KEYS:
        raise ValueError("BLOCKED_INTENT_SCHEMA")
    if obj["schema"] != INTENT_SCHEMA or obj["action"] != INTENT_ACTION:
        raise ValueError("BLOCKED_INTENT_ACTION")
    try:
        parsed = uuid.UUID(obj["intent_id"], version=4)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("BLOCKED_INTENT_ID") from exc
    if str(parsed) != obj["intent_id"]:
        raise ValueError("BLOCKED_INTENT_ID")
    actor = obj["actor_user_id"]
    if type(actor) is not int or not 1 <= actor <= 2147483647:
        raise ValueError("BLOCKED_ACTOR_ID")
    sha, prev = obj["approved_sha"], obj["expected_current_release"]
    if (not isinstance(sha, str) or not ra.SHA_RE.fullmatch(sha)
            or not isinstance(prev, str) or not ra.RELEASE_RE.fullmatch(prev)
            or prev == "platform-" + sha[:12]):
        raise ValueError("BLOCKED_RELEASE_IDENTITY")
    c, e = obj["created_at_unix"], obj["expires_at_unix"]
    if (type(c) is not int or type(e) is not int or c > now + 5 or c < now - 120
            or e <= now or e < c or e > c + 120):
        raise ValueError("BLOCKED_INTENT_EXPIRED_OR_FUTURE")
    if obj["owner_authenticated_qa_attested"] is not True:
        raise ValueError("BLOCKED_OWNER_QA_NOT_ATTESTED")
    return obj


def read_intent(path, uid, now):
    parent = path.parent.lstat()
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != uid
            or stat.S_IMODE(parent.st_mode) & 0o022):
        raise ValueError("BLOCKED_INTENT_PARENT")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) & 0o027 or not 128 <= info.st_size <= MAX_BYTES):
            raise ValueError("BLOCKED_INTENT_IDENTITY")
        data = os.read(fd, MAX_BYTES + 1)
        after = os.fstat(fd)
        if len(data) != info.st_size or after.st_mtime_ns != info.st_mtime_ns:
            raise ValueError("BLOCKED_INTENT_RACE")
        return parse_intent(data, now), data
    finally:
        os.close(fd)


def owner_qa_receipt(intent, raw, now):
    return {"schema": ra.RECEIPT_SCHEMA, "kind": "authenticated-qa", "host": ra.HOST,
            "approvedSha": intent["approved_sha"],
            "expectedCurrentRelease": intent["expected_current_release"],
            "capturedAt": int(now), "result": "pass",
            "artifactSha256": hashlib.sha256(raw).hexdigest()}


def decide(intent, raw, approval, live_release, receipts_dir, now, receipts_uid=0):
    """Pure-ish decision. Returns (admission_dict, []) or (None, blockers)."""
    sha, prev = intent["approved_sha"], intent["expected_current_release"]
    if not isinstance(approval, dict) or set(approval) != gate.APPROVAL_KEYS:
        return None, ["BLOCKED_APPROVAL_SCHEMA"]
    if (approval.get("approvedSha") != sha or approval.get("expectedCurrentRelease") != prev
            or approval.get("backupVerified") is not True
            or approval.get("rollbackVerified") is not True):
        return None, ["BLOCKED_APPROVAL_MISMATCH"]
    if live_release != prev:
        return None, ["BLOCKED_LIVE_RELEASE_DRIFT"]
    # authenticated-qa is minted only from this intent; a file by that name is never read.
    receipts = []
    for kind in ra.KIND_TO_FLAG:
        if kind == "authenticated-qa":
            continue
        data = store.read_protected(Path(receipts_dir) / "{}-{}.json".format(kind, sha[:12]),
                                    receipts_uid)
        if data is not None:
            receipts.append(data)
    receipts.append(owner_qa_receipt(intent, raw, now))
    return ra.build_admission(receipts, sha, prev, True, now)


def write_admission(admission, directory=gate.ADMISSION_DIR, uid=0):
    directory = Path(directory)
    info = directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) & 0o022):
        raise ValueError("BLOCKED_ADMISSION_DIR")
    final = directory / ("main-platform-autopublish-" + admission["approvedSha"][:12] + ".json")
    data = (json.dumps(admission, sort_keys=True, separators=(",", ":")) + "\n").encode()
    tmp = directory / ("." + final.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(tmp, final)  # no clobber: fails if an admission already exists
    except FileExistsError as exc:
        raise ValueError("BLOCKED_ADMISSION_ALREADY_EXISTS") from exc
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return final


def claim_once(intent, now, state_dir=STATE_DIR, uid=0):
    info = Path(state_dir).lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("BLOCKED_ROOT_STATE_DIR")
    path = Path(state_dir) / (intent["intent_id"] + ".claimed")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    except FileExistsError as exc:
        raise ValueError("BLOCKED_INTENT_ALREADY_CLAIMED") from exc
    with os.fdopen(fd, "wb") as handle:
        handle.write((json.dumps({"intent_id": intent["intent_id"], "claimed_at_unix": now})
                      + "\n").encode())
        handle.flush()
        os.fsync(handle.fileno())


def consume_intent(path, uid):
    """Remove a processed or rejected intent so the owner can retry; never follows links."""
    try:
        parent = path.parent.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != uid
                or stat.S_IMODE(parent.st_mode) & 0o022):
            return False
        os.unlink(path)
        return True
    except OSError:
        return False


def run(execute, now=None):
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != HOST:
        print("KMJ_ADMISSION_BROKER=BLOCKED_HOST_ROOT")
        return 2
    now = int(time.time()) if now is None else now
    try:
        uid = pwd.getpwnam(OWNER_USER).pw_uid
        if not INTENT.exists() and not INTENT.is_symlink():
            print("KMJ_ADMISSION_BROKER=NO_PENDING_INTENT")
            return 0
        try:
            return decide_and_write(execute, uid, now)
        finally:
            # One attempt per intent, success or not: a stale file must never block a retry.
            if execute:
                consume_intent(INTENT, uid)
    except (ValueError, OSError, KeyError) as exc:
        code = str(exc) if str(exc).startswith("BLOCKED_") else "BLOCKED_TRUSTED_PREFLIGHT_ERROR"
        print("KMJ_ADMISSION_BROKER=" + code[:95])
        return 2


def verify_admission_map(intent):
    data, _ = map_refresh.read_map(map_refresh.MAP)
    target = intent["approved_sha"]
    previous = intent["expected_current_release"]
    values = sha_map.parse_existing(data)
    if (len(values) != 2 or target not in values
            or not any("platform-" + value[:12] == previous for value in values)):
        raise ValueError("BLOCKED_PRODUCTION_SHA_MAP_NOT_READY")


def decide_and_write(execute, uid, now):
    try:
        intent, raw = read_intent(INTENT, uid, now)
        approval = gate.protected_json(gate.APPROVAL)
        admission, blockers = decide(
            intent, raw, approval, gate.live_release(),
            common.RECEIPT_DIR, now)
        if admission is None:
            print("KMJ_ADMISSION_BROKER=BLOCKED " + ",".join(blockers)[:200])
            return 2
        verify_admission_map(intent)
        if (gate.live_release() != intent["expected_current_release"]
                or gate.protected_json(gate.APPROVAL) != approval):
            raise ValueError("BLOCKED_APPROVAL_DRIFT_AFTER_MAP")
        if not execute:
            print("KMJ_ADMISSION_BROKER=EXACT_PREFLIGHT_PASS WRITTEN=NO")
        else:
            claim_once(intent, now)
            write_admission(admission)
            print("KMJ_ADMISSION_BROKER=ADMISSION_WRITTEN")
        print("PRODUCTION_RELEASE=NOT_ATTEMPTED APPROVAL_UPDATED=NO UNIT_STARTED=NO")
        return 0
    except (ValueError, OSError, KeyError) as exc:
        code = str(exc) if str(exc).startswith("BLOCKED_") else "BLOCKED_TRUSTED_PREFLIGHT_ERROR"
        print("KMJ_ADMISSION_BROKER=" + code[:95])
        return 2


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("--inspect", "--execute"):
        print("usage: --inspect|--execute")
        raise SystemExit(2)
    raise SystemExit(run(sys.argv[1] == "--execute"))
