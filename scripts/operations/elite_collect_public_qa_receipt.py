#!/usr/bin/env python3
"""Collector 5: public-qa receipt = HTTP smoke of fixed public routes on the staged origin.

Each fixed route must answer one final HTTP 200 with exactly one x-kmj-deploy-sha equal
to the approved SHA, with no redirects and no shell. This is an HTTP smoke, NOT a
browser or viewport test; it does not claim visual QA. No authentication, no
production touch, no deploy.

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
import elite_collect_staging_origin_receipt as common  # noqa: E402

ORIGIN = "https://staging.kmjtechno.com"
ROUTES = ("/", "/products", "/login")


def probe_route(route):
    out = subprocess.run(
        ["/usr/bin/curl", "--proto", "=https", "--silent", "--show-error",
         "--connect-timeout", "5", "--max-time", "18", "--max-redirs", "0",
         "--dump-header", "-", "--output", "/dev/null",
         "--write-out", "KMJ_HTTP_STATUS=%{http_code}", ORIGIN + route],
        cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C"}, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, check=False, timeout=23).stdout
    m = re.search(r"KMJ_HTTP_STATUS=(\d{3})\Z", out)
    if not m:
        raise ValueError("missing status marker")
    return m.group(1), out[:m.start()]


def make_receipt(sha, expected, now, fetch=probe_route):
    digest = hashlib.sha256()
    for route in ROUTES:
        status, headers = fetch(route)
        common.readback.check_readback(sha, headers, status)
        digest.update(route.encode() + b"\0" + headers.encode("utf-8") + b"\0")
    return {"schema": ra.RECEIPT_SCHEMA, "kind": "public-qa", "host": ra.HOST,
            "approvedSha": sha, "expectedCurrentRelease": expected, "capturedAt": int(now),
            "result": "pass", "artifactSha256": digest.hexdigest()}


def main(argv):
    if len(argv) != 4 or argv[1] not in ("--check", "--write"):
        print("usage: --check|--write <40-hex-sha> <platform-12hex>")
        return 2
    sha, expected = argv[2], argv[3]
    if not ra.SHA_RE.fullmatch(sha) or not ra.RELEASE_RE.fullmatch(expected):
        print("PUBLIC_QA_RECEIPT=BLOCKED_INPUT")
        return 2
    if argv[1] == "--write" and (os.geteuid() != 0
                                 or socket.gethostname().split(".")[0] != "KMJ-elite"):
        print("PUBLIC_QA_RECEIPT=BLOCKED_OPERATOR_HOST")
        return 2
    try:
        receipt = make_receipt(sha, expected, time.time())
        if argv[1] == "--write":
            common.write_receipt(receipt)
    except (OSError, ValueError, subprocess.SubprocessError, UnicodeError) as exc:
        print("PUBLIC_QA_RECEIPT=FAIL REASON=" + type(exc).__name__)
        return 1
    print("PUBLIC_QA_RECEIPT=PASS WRITTEN=" + ("YES" if argv[1] == "--write" else "NO"))
    print("BROWSER_VIEWPORT_QA=NOT_VERIFIED PRODUCTION_RELEASE=NOT_ATTEMPTED ADMISSION_WRITTEN=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
