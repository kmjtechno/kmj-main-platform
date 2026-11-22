#!/usr/bin/env python3
"""Collector 4: rollback-rehearsal receipt (source only until installed).

Runs the EXISTING isolated app HTTP + database migrate/rollback rehearsal as the
unprivileged project user against an owner-provisioned DISPOSABLE database and
the previous/candidate code trees named in a root-protected config, then accepts
the result only if every required marker says PASS and nothing says FAIL.

Scope, stated plainly: this proves code rollback on a migrated schema and exact
schema rollback/re-apply on a disposable DB. It does NOT prove storage continuity,
authenticated behaviour or restore from backup, so it issues ONLY the
`rollback-rehearsal` receipt, never `migration-storage`.

Config: /etc/kmj-codebridge/release-rehearsal.json  (root, 0600, single link):
  {"env": {"DB_...": "...", "KMJ_REHEARSAL_...": "..."}}   only those two prefixes.

  --check <sha> <expected-release> | --write <sha> <expected-release>
"""
import hashlib
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import release_admission_receipts as ra  # noqa: E402
import release_receipt_store as store  # noqa: E402
import elite_collect_staging_origin_receipt as common  # noqa: E402

CONFIG = Path("/etc/kmj-codebridge/release-rehearsal.json")
REHEARSAL = HERE / "rehearse-app-http-db-rollback-20261029.py"
ENV_KEY = re.compile(r"(DB|KMJ_REHEARSAL)_[A-Z0-9_]{1,60}\Z")
ALWAYS_PASS = (
    "PREVIOUS_MIGRATE", "CANDIDATE_MIGRATE", "SCHEMA_CHANGE_ADDITIVE_ONLY",
    "CODE_ROLLBACK_ON_MIGRATED_SCHEMA", "APP_HTTP_DB_ROLLBACK_REHEARSAL",
)
WHEN_NEW_MIGRATIONS = (
    "SCHEMA_ROLLBACK_RESTORES_BASELINE_EXACTLY", "SCHEMA_REAPPLY_MATCHES_FORWARD_EXACTLY",
)


def parse_markers(text):
    markers = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and re.fullmatch(r"[A-Z0-9_]{3,80}", key):
            if key in markers:
                raise ValueError("DUPLICATE_MARKER")
            markers[key] = value
    return markers


def rehearsal_passed(text):
    """Pure fail-closed check of the rehearsal output."""
    try:
        m = parse_markers(text)
    except ValueError:
        return False
    if any(v == "FAIL" or v.startswith("BLOCKED") for v in m.values()):
        return False
    if m.get("FAILURES") != "NONE" or m.get("PRODUCTION_DATABASE_TOUCHED") != "NO":
        return False
    if m.get("REHEARSAL_DATABASE") != "DISPOSABLE_ATTESTED":
        return False
    if any(m.get(k) != "PASS" for k in ALWAYS_PASS):
        return False
    new = m.get("NEW_MIGRATIONS", "")
    if not new.isdigit():
        return False
    if int(new) > 0 and any(m.get(k) != "PASS" for k in WHEN_NEW_MIGRATIONS):
        return False
    return True


def load_env(config=CONFIG, uid=0):
    data = store.read_protected(Path(config), uid)
    env = data.get("env") if isinstance(data, dict) and set(data) == {"env"} else None
    if (not isinstance(env, dict) or not env
            or any(not ENV_KEY.fullmatch(k) or not isinstance(v, str) or len(v) > 300
                   or "\n" in v or "\x00" in v for k, v in env.items())):
        raise ValueError("REHEARSAL_CONFIG_INVALID")
    return env


def run_rehearsal(env):
    argv = ["/usr/sbin/runuser", "-u", "kmjprod", "--", "/usr/bin/env", "-i",
            "PATH=/usr/local/bin:/usr/bin:/bin", "LANG=C"]
    argv += ["{}={}".format(k, v) for k, v in sorted(env.items())]
    argv += ["/usr/bin/python3", "-I", "-B", str(REHEARSAL)]
    out = subprocess.run(argv, cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C"},
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                         check=False, timeout=3600)
    return out.stdout


def collect(sha, expected, now, runner=run_rehearsal, env=None):
    output = runner(env if env is not None else load_env())
    if not rehearsal_passed(output):
        raise ValueError("REHEARSAL_NOT_PASS")
    return {"schema": ra.RECEIPT_SCHEMA, "kind": "rollback-rehearsal", "host": ra.HOST,
            "approvedSha": sha, "expectedCurrentRelease": expected, "capturedAt": int(now),
            "result": "pass", "artifactSha256": hashlib.sha256(output.encode()).hexdigest()}


def main(argv):
    if len(argv) != 4 or argv[1] not in ("--check", "--write"):
        print("usage: --check|--write <40-hex-sha> <platform-12hex>")
        return 2
    sha, expected = argv[2], argv[3]
    if not ra.SHA_RE.fullmatch(sha) or not ra.RELEASE_RE.fullmatch(expected):
        print("ROLLBACK_REHEARSAL_RECEIPT=BLOCKED_INPUT")
        return 2
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        print("ROLLBACK_REHEARSAL_RECEIPT=BLOCKED_OPERATOR_HOST")
        return 2
    live = Path("/home/kmjprod/current")
    try:
        if not live.is_symlink() or live.resolve(strict=True) != Path(
                "/home/kmjprod/releases") / expected:
            print("ROLLBACK_REHEARSAL_RECEIPT=BLOCKED_LIVE_POINTER")
            return 1
        receipt = collect(sha, expected, time.time())
        if argv[1] == "--write":
            common.write_receipt(receipt)
    except (OSError, ValueError, subprocess.SubprocessError, UnicodeError) as exc:
        print("ROLLBACK_REHEARSAL_RECEIPT=FAIL REASON=" + type(exc).__name__)
        return 1
    print("ROLLBACK_REHEARSAL_RECEIPT=PASS WRITTEN=" + ("YES" if argv[1] == "--write" else "NO"))
    print("MIGRATION_STORAGE_RECEIPT=NOT_ISSUED PRODUCTION_RELEASE=NOT_ATTEMPTED ADMISSION_WRITTEN=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
