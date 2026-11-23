#!/usr/bin/env python3
"""Fixed root release-prepare broker (source only, INSTALL-OPT-IN, never auto-started).

An owner-authenticated web click is INTENT. Root then re-verifies the candidate itself and
runs the owner's own pinned release helper in its bounded `--prepare-only` mode, and later,
once the approved candidate really is live, in its `--post-activation` migrate mode:

  * the SHA is exactly the current GitHub `main` head and every check run of that exact head
    is completed and successful,
  * the helper file fetched for that SHA is byte-identical to the sha256 pinned below,
  * the intent carries the owner's explicit backup/rollback and migrate-after-activation
    attestation (the same attestation the owner gives today by running the helper as root),
  * the intent is one-shot (claimed before anything runs, always consumed afterwards).

It never activates production: activation stays the separate guarded broker / Supervisor
step. Migration runs only for a candidate this broker prepared, and only once it is live.

  --inspect   verify everything, run nothing
  --execute   process one pending intent, then the post-activation migrate if due
"""
import hashlib
import json
import os
import pwd
import re
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

HOST = "KMJ-elite"
OWNER_USER = "kmjprod"
REPO = "kmjtechno/kmj-main-platform"
HELPER_SHA256 = "325b24d32ebcf01b42994276a7beb550ed72c69cb044f8ffab03db6f1e218cec"
HELPER_PATH = "scripts/operations/owner-release-main-platform.sh"
OPS_DIR = Path("/home/kmjprod/shared/storage/app/private/ops")
INTENT = OPS_DIR / "release-prepare-request.json"
STATUS = OPS_DIR / "release-prepare-status.json"
STATE_DIR = Path("/var/lib/kmj-main-platform/release-prepare")
PREPARED = STATE_DIR / "prepared.json"
LIVE_LINK = Path("/home/kmjprod/current")
INTENT_SCHEMA = "kmj.elite.release-prepare-intent.v1"
STATUS_SCHEMA = "kmj.elite.release-prepare-status.v1"
INTENT_ACTION = "prepare_release_candidate"
INTENT_KEYS = frozenset({
    "schema", "intent_id", "actor_user_id", "action", "approved_sha",
    "created_at_unix", "expires_at_unix",
    "owner_backup_rollback_attested", "migrate_after_activation_accepted",
})
SHA_RE = re.compile(r"[a-f0-9]{40}\Z")
LIVE_RE = re.compile(r"platform-[a-f0-9]{12}\Z")
PREPARE_OK = "APPROVAL_DONE_PREPARE_ONLY_ACTIVATE_THEN_RUN_POST_ACTIVATION"
MIGRATE_OK = "POST_ACTIVATION_MIGRATE_DONE"
MIN_CHECK_RUNS = 6
MAX_BYTES = 2048
PREPARE_TIMEOUT = 3600
MIGRATE_TIMEOUT = 900
SAFE_ENV = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "HOME": "/root"}


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
    if not isinstance(obj["approved_sha"], str) or not SHA_RE.fullmatch(obj["approved_sha"]):
        raise ValueError("BLOCKED_RELEASE_IDENTITY")
    c, e = obj["created_at_unix"], obj["expires_at_unix"]
    if (type(c) is not int or type(e) is not int or c > now + 5 or c < now - 120
            or e <= now or e < c or e > c + 120):
        raise ValueError("BLOCKED_INTENT_EXPIRED_OR_FUTURE")
    if obj["owner_backup_rollback_attested"] is not True:
        raise ValueError("BLOCKED_OWNER_ATTESTATION_MISSING")
    if obj["migrate_after_activation_accepted"] is not True:
        raise ValueError("BLOCKED_MIGRATE_ACCEPTANCE_MISSING")
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
        return parse_intent(data, now)
    finally:
        os.close(fd)


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
        handle.write((json.dumps({"intent_id": intent["intent_id"], "claimed_at_unix": now}) + "\n").encode())
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


def checks_all_green(payload):
    """Every check run of the exact head is completed and successful (none pending, none missing)."""
    runs = payload.get("check_runs") if isinstance(payload, dict) else None
    total = payload.get("total_count") if isinstance(payload, dict) else None
    if not isinstance(runs, list) or type(total) is not int or total != len(runs) or total < MIN_CHECK_RUNS:
        return False
    return all(isinstance(r, dict) and r.get("status") == "completed" and r.get("conclusion") == "success"
               for r in runs)


def verify_candidate(sha, main_head, checks_payload):
    if main_head != sha:
        raise ValueError("BLOCKED_SHA_NOT_MAIN_HEAD")
    if not checks_all_green(checks_payload):
        raise ValueError("BLOCKED_EXACT_HEAD_CHECKS_NOT_GREEN")


def helper_ok(data):
    return hashlib.sha256(data).hexdigest() == HELPER_SHA256


def live_release(link=LIVE_LINK):
    name = os.path.basename(os.path.realpath(link))
    if not LIVE_RE.fullmatch(name):
        raise ValueError("BLOCKED_LIVE_NAME_UNEXPECTED")
    return name


def write_status(state, sha, detail, uid, path=STATUS, now=None):
    """Owner-readable status for the Ops page. A status is a report, never a proof of release."""
    body = {"schema": STATUS_SCHEMA, "state": state, "approved_sha": sha, "detail": detail[:120],
            "updated_at_unix": int(time.time()) if now is None else now}
    data = (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode()
    tmp = Path(str(path) + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_CLOEXEC, 0o640)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.chown(tmp, uid, -1)
    os.replace(tmp, path)


def write_prepared(sha, now, state_dir=STATE_DIR, migrate_pending=True):
    data = (json.dumps({"approved_sha": sha, "prepared_at_unix": now, "migrate_pending": migrate_pending},
                       sort_keys=True) + "\n").encode()
    tmp = Path(state_dir) / ".prepared.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, Path(state_dir) / "prepared.json")


def read_prepared(state_dir=STATE_DIR):
    path = Path(state_dir) / "prepared.json"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (not isinstance(obj, dict) or set(obj) != {"approved_sha", "prepared_at_unix", "migrate_pending"}
            or not isinstance(obj["approved_sha"], str) or not SHA_RE.fullmatch(obj["approved_sha"])
            or type(obj["migrate_pending"]) is not bool):
        return None
    return obj


# ---- real I/O (replaced by fakes in the tests) ---------------------------------------------

def http_get(url, limit=1_000_000):
    request = urllib.request.Request(url, headers={"User-Agent": "kmj-elite-release-prepare-broker"})
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec - fixed https GitHub URLs only
        return response.read(limit + 1)[:limit]


def real_main_head():
    out = subprocess.run(["/usr/bin/git", "ls-remote", "--exit-code", "https://github.com/" + REPO + ".git",
                          "refs/heads/main"], capture_output=True, text=True, timeout=60, env=SAFE_ENV, check=False)
    parts = out.stdout.split()
    return parts[0] if out.returncode == 0 and parts else ""


def real_checks(sha):
    return json.loads(http_get("https://api.github.com/repos/{}/commits/{}/check-runs?per_page=100".format(REPO, sha)))


def real_helper(sha):
    return http_get("https://raw.githubusercontent.com/{}/{}/{}".format(REPO, sha, HELPER_PATH))


def real_run(helper_bytes, args, timeout):
    with tempfile.TemporaryDirectory(prefix="kmj-release-prepare-") as workdir:
        os.chmod(workdir, 0o700)
        script = Path(workdir) / "owner-release.sh"
        script.write_bytes(helper_bytes)
        os.chmod(script, 0o700)
        done = subprocess.run(["/bin/bash", str(script), *args], cwd=workdir, env=SAFE_ENV,
                              capture_output=True, text=True, timeout=timeout, check=False)
        return done.returncode, (done.stdout or "")[-4000:]


class Deps:
    main_head = staticmethod(real_main_head)
    checks = staticmethod(real_checks)
    helper = staticmethod(real_helper)
    run = staticmethod(real_run)
    live = staticmethod(live_release)


def prepare(intent, uid, now, deps=Deps, state_dir=STATE_DIR, status_path=STATUS, execute=True, state_uid=0):
    sha = intent["approved_sha"]
    verify_candidate(sha, deps.main_head(), deps.checks(sha))
    data = deps.helper(sha)
    if not helper_ok(data):
        raise ValueError("BLOCKED_HELPER_HASH_MISMATCH")
    if deps.live() == "platform-" + sha[:12]:
        raise ValueError("BLOCKED_ALREADY_LIVE")
    if not execute:
        return "PREPARE_PREFLIGHT_PASS"
    claim_once(intent, now, state_dir, state_uid)
    write_status("preparing", sha, "helper running", uid, status_path, now)
    code, output = deps.run(data, ["--prepare-only", sha], PREPARE_TIMEOUT)
    if code != 0 or PREPARE_OK not in output or "BLOCKED" in output:
        write_status("prepare_failed", sha, "helper did not finish; read the root log", uid, status_path, now)
        raise ValueError("BLOCKED_HELPER_FAILED")
    write_prepared(sha, now, state_dir)
    write_status("prepared_awaiting_activation", sha, "approval written; activate, then migrate runs", uid,
                 status_path, now)
    return "PREPARED_AWAITING_ACTIVATION"


def post_activation(uid, now, deps=Deps, state_dir=STATE_DIR, status_path=STATUS, execute=True):
    pending = read_prepared(state_dir)
    if pending is None or not pending["migrate_pending"]:
        return "NO_POST_ACTIVATION_DUE"
    sha = pending["approved_sha"]
    if deps.live() != "platform-" + sha[:12]:
        return "CANDIDATE_NOT_LIVE_YET"
    data = deps.helper(sha)
    if not helper_ok(data):
        raise ValueError("BLOCKED_HELPER_HASH_MISMATCH")
    if not execute:
        return "POST_ACTIVATION_PREFLIGHT_PASS"
    write_status("migrating", sha, "candidate is live; migrating", uid, status_path, now)
    code, output = deps.run(data, ["--post-activation", sha], MIGRATE_TIMEOUT)
    if code != 0 or MIGRATE_OK not in output or "BLOCKED" in output:
        write_status("migrate_failed", sha, "migrate did not finish; owner must investigate", uid, status_path, now)
        raise ValueError("BLOCKED_MIGRATE_FAILED")
    write_prepared(sha, now, state_dir, migrate_pending=False)
    write_status("live_and_migrated", sha, "candidate live; migrate finished; verify the site", uid, status_path, now)
    return "POST_ACTIVATION_MIGRATE_DONE"


def run(execute, now=None, deps=Deps):
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != HOST:
        print("KMJ_RELEASE_PREPARE_BROKER=BLOCKED_HOST_ROOT")
        return 2
    now = int(time.time()) if now is None else now
    results, failed = [], False
    try:
        uid = pwd.getpwnam(OWNER_USER).pw_uid
        if INTENT.exists() or INTENT.is_symlink():
            try:
                results.append(prepare(read_intent(INTENT, uid, now), uid, now, deps, execute=execute))
            except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
                failed = True
                results.append(str(exc) if str(exc).startswith("BLOCKED_") else "BLOCKED_TRUSTED_PREFLIGHT_ERROR")
            finally:
                if execute:
                    consume_intent(INTENT, uid)  # one attempt per intent so a stale file never blocks a retry
        try:
            results.append(post_activation(uid, now, deps, execute=execute))
        except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
            failed = True
            results.append(str(exc) if str(exc).startswith("BLOCKED_") else "BLOCKED_TRUSTED_PREFLIGHT_ERROR")
    except (ValueError, OSError, KeyError) as exc:
        print("KMJ_RELEASE_PREPARE_BROKER=" + (str(exc) if str(exc).startswith("BLOCKED_") else "BLOCKED_ERROR")[:95])
        return 2
    print("KMJ_RELEASE_PREPARE_BROKER=" + ",".join(results)[:200])
    print("PRODUCTION_ACTIVATION=NOT_ATTEMPTED")
    return 2 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("--inspect", "--execute"):
        print("usage: --inspect|--execute")
        raise SystemExit(2)
    raise SystemExit(run(sys.argv[1] == "--execute"))
