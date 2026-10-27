#!/usr/bin/env python3
"""Bounded operator-run real HTTP old/candidate/old rollback test, NEVER prod cutover.

Adapts the previously reviewed exact-hash 625f isolated HTTP test to the
06caf candidate inside root-private scratch. Preserves source unchanged.
Publishes only fixed-key statuses to a CodeBridge-readable receipt.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile

OLD = "platform-8070dad72c55"
SHA = "06caf93699c0e791df22c6679aac87a1c14c6332"
SHORT = SHA[:12]
SOURCE = Path("/srv/kmj-codebridge-projects/kmj-main-platform/scripts/KMJ_625F_REAL_HTTP_ISOLATED_APP_ROLLBACK_20261025.py")
SOURCE_SHA256 = "0c5c97cb2c0eb66e059dc5f41f95757b7760da6409535fedc99e99d13a011caf"
CURRENT = Path("/home/kmjprod/current")
RELEASES = Path("/home/kmjprod/releases")
OUTPUT = Path("/srv/kmj-codebridge-projects/kmj-main-platform/work/qa/KMJ_06CAF_ISOLATED_HTTP_ROLLBACK_RECEIPT_20261027.json")
REQUIRED = {
    "KMJ_BACKUP_AND_CONTROLLER": "PINNED_PASS",
    "KMJ_LOCAL_DATABASE_ISOLATION": "PASS_BOTH_REAL_APPS",
    "KMJ_OLD_BASELINE_REAL_HTTP": "PASS",
    "KMJ_CANDIDATE_REAL_HTTP": "PASS",
    "KMJ_OLD_ROLLBACK_REAL_HTTP": "PASS",
    "KMJ_ISOLATED_HTTP_ROLLBACK": "PASS_REAL_HTTP_FAULT_INJECTION",
    "KMJ_PRODUCTION_RELEASE": "UNCHANGED",
    "KMJ_PRODUCTION_DB_WRITES": "NONE",
    "KMJ_NGINX_PHP_FPM": "UNCHANGED",
    "KMJ_LIVE_PRODUCTION_ROLLBACK": "NOT_PERFORMED",
    "KMJ_PRODUCTION_APPROVAL": "UNCHANGED",
}
ACCEPT = set(REQUIRED) | {"KMJ_AUTHENTICATED_OWNER_QA"}

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def fail(message):
    raise RuntimeError(message)

def atomic_receipt(doc):
    qa = OUTPUT.parent
    if not qa.is_dir() or qa.is_symlink() or OUTPUT.is_symlink():
        fail("RECEIPT_PATH_UNSAFE")
    if OUTPUT.exists():
        st = OUTPUT.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0:
            fail("RECEIPT_DEST_UNSAFE")
    fd, name = tempfile.mkstemp(prefix=".kmj-rollback-receipt-", dir=qa)
    try:
        with os.fdopen(fd, "w", encoding="ascii") as out:
            os.fchmod(out.fileno(), 0o644)
            out.write(json.dumps(doc, sort_keys=True, indent=2) + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, OUTPUT)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def main():
    if len(sys.argv) != 1:
        fail("NO_ARGUMENTS_ALLOWED")
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        fail("ROOT_ON_KMJ_ELITE_REQUIRED")
    if not CURRENT.is_symlink() or CURRENT.resolve(strict=True) != RELEASES / OLD:
        fail("PRODUCTION_RELEASE_DRIFT")
    target = RELEASES / ("platform-" + SHORT)
    if not target.is_dir() or target.is_symlink():
        fail("EXACT_CANDIDATE_MISSING")
    if not SOURCE.is_file() or SOURCE.is_symlink() or sha(SOURCE) != SOURCE_SHA256:
        fail("PINNED_REHEARSAL_SOURCE_MISMATCH")

    receipt = {
        "schema": "kmj-isolated-real-http-rollback-v1",
        "observed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidate_sha": SHA, "previous_release": OLD,
        "status": "BLOCKED", "tests": {}, "process_exit_code": None,
        "live_production_rollback": "NOT_PERFORMED",
        "protected_approval": "UNCHANGED",
        "independent_offsite_restore": "ATTESTED_SEPARATELY",
        "limits": "Real loopback HTTP old-candidate-old rehearsal in disposable tree, not a live production rollback or owner authenticated QA.",
    }
    with tempfile.TemporaryDirectory(prefix=".kmj-06caf-rollback-", dir="/root") as work:
        root = Path(work)
        text = SOURCE.read_text(encoding="utf-8")
        original_sha = "625ffeaaab20af612b2693bf0d43e3f7e4922c14"
        original_short = original_sha[:12]
        if text.count(original_sha) != 1 or text.count(original_short) < 2:
            fail("REHEARSAL_TEMPLATE_CONTRACT")
        updated = text.replace(original_sha, SHA).replace(original_short, SHORT)
        # Avoid false passes from outdated hardcoded fault-route names.
        updated = updated.replace("kmj-isolated-intentional-unhealthy-path-625f",
                                  "kmj-isolated-intentional-unhealthy-path-06caf")
        script = root / "rehearsal.py"
        script.write_text(updated, encoding="utf-8")
        script.chmod(0o400)
        try:
            r = subprocess.run(
                [sys.executable, "-B", str(script)], cwd="/",
                env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                     "HOME": "/root", "LANG": "C.UTF-8"},
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=240, check=False,
            )
            receipt["process_exit_code"] = r.returncode
            if len(r.stdout) > 16384:
                fail("EXCESSIVE_TEST_OUTPUT")
            facts = {}
            for line in r.stdout.splitlines():
                key, sep, value = line.partition("=")
                if sep and key in ACCEPT and re.fullmatch(r"[A-Za-z0-9_]{1,100}", value):
                    if key in facts:
                        fail("DUPLICATE_TEST_GATE")
                    facts[key] = value
            receipt["tests"] = facts
            if r.returncode == 0 and all(facts.get(k) == v for k, v in REQUIRED.items()):
                receipt["status"] = "PASS_ISOLATED_REAL_HTTP_ROLLBACK"
            else:
                receipt["status"] = "BLOCKED_REAL_HTTP_GATE"
        except subprocess.TimeoutExpired:
            receipt["status"] = "BLOCKED_TIMEOUT"
        if not CURRENT.is_symlink() or CURRENT.resolve(strict=True) != RELEASES / OLD:
            fail("LIVE_RELEASE_POINTER_CHANGED")
    atomic_receipt(receipt)
    print("CODEBRIDGE_ROLLBACK_RECEIPT=WRITTEN")
    print("KMJ_ISOLATED_HTTP_ROLLBACK_RESULT=" + receipt["status"])
    print("PRODUCTION_POINTER=UNCHANGED")
    print("PRODUCTION_ACTIVATION=NOT_PERFORMED")
    if receipt["status"] != "PASS_ISOLATED_REAL_HTTP_ROLLBACK":
        raise SystemExit(2)

if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as e:
        reason = str(e)
        safe = reason if re.fullmatch("[A-Z0-9_]{1,100}", reason) else "UNVERIFIED"
        # Unlike earlier operator scripts, publish an attested failure receipt
        # whenever the fixed authorized receipt directory is available.
        if os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite":
            try:
                atomic_receipt({
                    "schema": "kmj-isolated-real-http-rollback-v1",
                    "observed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "candidate_sha": SHA, "previous_release": OLD,
                    "status": "BLOCKED_PRECHECK", "reason_code": safe,
                    "live_production_rollback": "NOT_PERFORMED",
                    "protected_approval": "UNCHANGED",
                    "tests": {},
                    "limits": "Preflight failed: no rollback completion evidence.",
                })
                print("CODEBRIDGE_ROLLBACK_RECEIPT=WRITTEN")
            except (OSError, RuntimeError):
                print("CODEBRIDGE_ROLLBACK_RECEIPT=NOT_WRITTEN")
        print("KMJ_ISOLATED_HTTP_ROLLBACK=BLOCKED_" + safe)
        raise SystemExit(2)
