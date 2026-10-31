#!/usr/bin/env python3
"""Read-only: print the tree seal for a prepared staging candidate (apps/platform).

It extracts and runs the EXACT digest program embedded in the guarded runner, so there is a single algorithm
covered by runnerSha256. It never writes anything. The OWNER decides whether the printed digest is trustworthy
(review the candidate, freeze it) and, as root, writes it to
/etc/kmj-codebridge/main-platform-staging-seal-<approvedSha>.sha256 (root:root, mode 0644, one line).
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[2] / "deploy/staging/kmj-main-platform-staging-deploy.sh"


def digest_program(runner: Path) -> str:
    text = runner.read_text()
    m = re.search(r"<<'DIGEST_PY'\n(.*?)\nDIGEST_PY\n", text, re.S)
    if not m:
        raise SystemExit("BLOCKED_RUNNER_FORMAT")
    return m.group(1)


def seal(tree: str, runner: Path = RUNNER) -> str:
    out = subprocess.run(["python3", "-I", "-c", digest_program(runner), tree],
                         capture_output=True, text=True, check=True).stdout.strip()
    if not re.fullmatch(r"OK [a-f0-9]{64}", out):
        raise SystemExit("BLOCKED_" + out.replace(" ", "_"))
    return out[3:]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tree", required=True, help="prepared candidate apps/platform directory")
    p.add_argument("--runner", default=str(RUNNER))
    a = p.parse_args(argv)
    print(seal(a.tree, Path(a.runner)))


if __name__ == "__main__":
    main()
