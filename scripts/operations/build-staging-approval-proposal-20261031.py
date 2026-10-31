#!/usr/bin/env python3
"""Read-only: print a staging-approval PROPOSAL bound to the committed runner/unit bytes.

It never writes to /etc, never installs a unit and never sets a verification flag to true: the four
*Verified fields are emitted as false, so the Supervisor rejects the proposal until the OWNER has
independently proven each one and edits the root-protected file by hand.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "deploy/staging/kmj-main-platform-staging-deploy.sh"
UNIT = ROOT / "deploy/staging/kmj-main-platform-staging-deploy.service"
SHA = re.compile(r"[a-f0-9]{40}\Z")
RELEASE = re.compile(r"[a-z0-9][a-z0-9_-]{3,100}\Z")


def proposal(approved, expected_current, production_release):
    if not SHA.match(approved) or not SHA.match(expected_current) or approved == expected_current:
        raise SystemExit("BLOCKED_SHA")
    if not RELEASE.match(production_release):
        raise SystemExit("BLOCKED_PRODUCTION_RELEASE")
    return {
        "schema": "kmj.main-platform.staging-approval.v1",
        "approvedSha": approved,
        "expectedCurrentSha": expected_current,
        "expectedProductionRelease": production_release,
        "runnerSha256": hashlib.sha256(RUNNER.read_bytes()).hexdigest(),
        "unitSha256": hashlib.sha256(UNIT.read_bytes()).hexdigest(),
        "backupVerified": False,
        "rollbackVerified": False,
        "storageVerified": False,
        "zeroAdditionalCostVerified": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approved-sha", required=True)
    p.add_argument("--expected-current-sha", required=True)
    p.add_argument("--expected-production-release", required=True)
    a = p.parse_args(argv)
    json.dump(proposal(a.approved_sha, a.expected_current_sha, a.expected_production_release),
              sys.stdout, indent=2, sort_keys=True)
    print()


if __name__ == "__main__":
    main()
