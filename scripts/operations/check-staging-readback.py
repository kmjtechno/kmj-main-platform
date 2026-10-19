#!/usr/bin/env python3
"""Fail-closed interpretation of one TLS-validated staging HTTP readback.

This never deploys, authenticates, touches production DB or changes approvals.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

SHA = re.compile(r"[a-f0-9]{40}\Z")


def check_readback(expected: str, headers: str, status: str) -> str:
    if not SHA.fullmatch(expected):
        raise ValueError("candidate SHA is missing or invalid")
    if status != "200":
        raise ValueError("staging root HTTP status is not 200")

    # A tunnel/proxy can prepend an HTTP connection-established response.
    # Only the final response block may establish the live release identity.
    blocks = re.split(r"\r?\n\r?\n", headers.strip())
    final = [block for block in blocks if re.search(r"(?m)^HTTP/\S+\s+\d{3}", block)]
    if not final:
        raise ValueError("missing HTTP status line")
    actual_block = final[-1]
    first = actual_block.splitlines()[0].strip()
    if not re.match(r"^HTTP/\S+\s+200(?:\s|$)", first):
        raise ValueError("final HTTP response not 200")
    values = []
    for line in actual_block.splitlines()[1:]:
        name, separator, value = line.partition(":")
        if separator and name.lower().strip() == "x-kmj-deploy-sha":
            values.append(value.strip())
    if len(values) != 1:
        raise ValueError("missing or duplicated deployment identity header")
    if not SHA.fullmatch(values[0]):
        raise ValueError("deployment identity is not an immutable full SHA")
    if values[0] != expected:
        raise ValueError("staging is serving a different release SHA")
    return values[0]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--expected", required=True)
    p.add_argument("--headers", required=True, type=Path)
    p.add_argument("--status", required=True)
    a = p.parse_args()
    try:
        observed = check_readback(a.expected, a.headers.read_text(encoding="utf-8"), a.status)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"STAGING_DEPLOY_READBACK=FAIL REASON={type(exc).__name__}")
        raise SystemExit(1) from None
    print(f"STAGING_DEPLOY_READBACK=PASS SOURCE_SHA={observed}")
    print("PRODUCTION_RELEASE=NOT_VERIFIED")
    print("AUTHENTICATED_OWNER_BROWSER=NOT_VERIFIED")


if __name__ == "__main__":
    main()
