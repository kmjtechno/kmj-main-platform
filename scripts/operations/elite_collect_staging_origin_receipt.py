#!/usr/bin/env python3
"""Collector 1: staging-origin exact-SHA receipt (source only until installed).

Reads ONLY the fixed staging HTTPS origin (no redirects, no shell), requires one
final HTTP 200 and exactly one x-kmj-deploy-sha equal to the approved SHA, then
atomically writes a root-owned 0600 receipt for the admission logic. It never
deploys, authenticates, touches production data, approvals or any pointer.

  --check  <sha> <expected-release>   probe and print result, write nothing
  --write  <sha> <expected-release>   probe and write the receipt (root, KMJ-elite)
"""
import hashlib
import importlib.util
import json
import os
import re
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import release_admission_receipts as ra  # noqa: E402

_spec = importlib.util.spec_from_file_location("readback", HERE / "check-staging-readback.py")
readback = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(readback)

URL = "https://staging.kmjtechno.com/"
RECEIPT_DIR = Path("/var/lib/kmj-release-receipts")
KIND = "staging-origin"


def probe():
    """Return (status, raw_headers) from one bounded, no-redirect HTTPS request."""
    out = subprocess.run(
        ["/usr/bin/curl", "--proto", "=https", "--silent", "--show-error",
         "--connect-timeout", "5", "--max-time", "18", "--max-redirs", "0",
         "--dump-header", "-", "--output", "/dev/null",
         "--write-out", "KMJ_HTTP_STATUS=%{http_code}", URL],
        cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C"}, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, check=False, timeout=23).stdout
    m = re.search(r"KMJ_HTTP_STATUS=(\d{3})\Z", out)
    if not m:
        raise ValueError("missing status marker")
    return m.group(1), out[:m.start()]


def make_receipt(sha, expected, now, fetch=probe):
    """Return a receipt dict, or raise ValueError when the staged origin is not exact."""
    status, headers = fetch()
    readback.check_readback(sha, headers, status)
    return {
        "schema": ra.RECEIPT_SCHEMA, "kind": KIND, "host": ra.HOST,
        "approvedSha": sha, "expectedCurrentRelease": expected,
        "capturedAt": int(now), "result": "pass",
        "artifactSha256": hashlib.sha256(headers.encode("utf-8")).hexdigest(),
    }


def write_receipt(receipt, directory=RECEIPT_DIR, trusted_uid=0):
    """Atomic no-clobber-by-temp write into a trusted, private directory."""
    directory = Path(directory)
    info = directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != trusted_uid
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise ValueError("BLOCKED_RECEIPT_DIR")
    final = directory / "{}-{}.json".format(KIND, receipt["approvedSha"][:12])
    tmp = directory / ("." + final.name + ".tmp")
    data = (json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, final)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return final


def main(argv):
    if len(argv) != 4 or argv[1] not in ("--check", "--write"):
        print("usage: --check|--write <40-hex-sha> <platform-12hex>")
        return 2
    sha, expected = argv[2], argv[3]
    if not ra.SHA_RE.fullmatch(sha) or not ra.RELEASE_RE.fullmatch(expected):
        print("STAGING_ORIGIN_RECEIPT=BLOCKED_INPUT")
        return 2
    if argv[1] == "--write" and (os.geteuid() != 0
                                 or socket.gethostname().split(".")[0] != "KMJ-elite"):
        print("STAGING_ORIGIN_RECEIPT=BLOCKED_OPERATOR_HOST")
        return 2
    try:
        receipt = make_receipt(sha, expected, time.time())
    except (OSError, ValueError, subprocess.SubprocessError, UnicodeError) as exc:
        print("STAGING_ORIGIN_RECEIPT=FAIL REASON=" + type(exc).__name__)
        return 1
    if argv[1] == "--write":
        try:
            write_receipt(receipt)
        except (OSError, ValueError) as exc:
            print("STAGING_ORIGIN_RECEIPT=BLOCKED_WRITE REASON=" + type(exc).__name__)
            return 1
    print("STAGING_ORIGIN_RECEIPT=PASS WRITTEN=" + ("YES" if argv[1] == "--write" else "NO"))
    print("PRODUCTION_RELEASE=NOT_ATTEMPTED APPROVAL_UPDATED=NO ADMISSION_WRITTEN=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
