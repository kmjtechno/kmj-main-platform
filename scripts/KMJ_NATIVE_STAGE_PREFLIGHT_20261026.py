#!/usr/bin/env python3
"""Read-only existing-production-host staging readiness inspection.

Never creates a site, acquires a certificate, copies production data, installs
packages, modifies Nginx/PHP/PostgreSQL, or authorizes a release. The dedicated
fresh-VPS bootstrap is prohibited on KMJ-elite.
"""
from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path
import re
import shutil
import subprocess

TARGET = "staging.kmjtechno.com"
PRODUCTION = Path("/home/kmjprod/current")
SITE = Path("/home/kmjstage/htdocs") / TARGET


def command(args: list[str], *, seconds: int = 12) -> tuple[int, str]:
    try:
        done = subprocess.run(
            args, capture_output=True, text=True, errors="replace",
            check=False, timeout=seconds,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    # Ignore stderr: command tools can include paths, configuration or secrets.
    return done.returncode, done.stdout


def classify_server_names(configuration: str, domain: str = TARGET) -> str:
    matches: list[list[str]] = []
    for raw in configuration.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            continue
        result = re.fullmatch(r"server_name\s+([^;]+);(?:\s*#.*)?", line)
        if result:
            names = result.group(1).split()
            if domain in names:
                matches.append(names)
    if not matches:
        return "MISSING"
    if len(matches) == 1 and matches[0] == [domain]:
        return "DEDICATED"
    return "SHARED_OR_DUPLICATED"


def classify_site(path: Path) -> str:
    if path.is_symlink():
        return "BLOCKED_SYMLINK"
    if path.is_dir():
        return "PRESENT"
    if path.exists():
        return "BLOCKED_NON_DIRECTORY"
    return "MISSING"


def check() -> int:
    rc, hostname = command(["hostname", "-s"])
    if rc or hostname.strip() != "KMJ-elite":
        print("KMJ_NATIVE_STAGE_PREFLIGHT=BLOCKED_WRONG_HOST")
        return 2
    if os.geteuid() != 0:
        print("KMJ_NATIVE_STAGE_PREFLIGHT=BLOCKED_ROOT_REQUIRED")
        return 2
    if not (PRODUCTION.exists() and PRODUCTION.is_dir()):
        print("KMJ_NATIVE_STAGE_PREFLIGHT=BLOCKED_PRODUCTION_BASELINE_UNKNOWN")
        return 2
    before = PRODUCTION.resolve(strict=True)
    print("PRODUCTION_BASELINE=PRESENT")

    rc, config = command(["nginx", "-T"], seconds=20)
    if rc:
        print("NGINX_EFFECTIVE_CONFIG=BLOCKED_UNREADABLE")
        return 3
    print("NGINX_EFFECTIVE_CONFIG=PASS")
    vhost = classify_server_names(config)
    del config
    print(f"STAGING_VHOST={vhost}")
    print(f"STAGING_SITE_DIRECTORY={classify_site(SITE)}")

    socket_paths = sorted(glob.glob("/run/php/php*-fpm.sock"))
    if socket_paths:
        versions = [
            match.group(1)
            for path in socket_paths
            if (match := re.search(r"php([0-9]+\.[0-9]+)-fpm\.sock$", path))
        ]
        print("PHP_FPM_SOCKET_VERSIONS=" + (",".join(sorted(set(versions))) or "OTHER"))
    else:
        print("PHP_FPM_SOCKET_VERSIONS=NONE")

    binaries = sorted(glob.glob("/usr/bin/php[0-9]*"))
    cli = sorted(set(
        m.group(1) for p in binaries
        if (m := re.fullmatch(r"/usr/bin/php([0-9]+\.[0-9]+)", p))
    ))
    print("PHP_CLI_VERSIONS=" + (",".join(cli) if cli else "NONE"))

    print("COMPOSER=" + ("PRESENT" if shutil.which("composer") else "MISSING"))
    print("NODE=" + ("PRESENT" if shutil.which("node") else "MISSING"))
    print("CERTBOT=" + ("PRESENT" if shutil.which("certbot") else "MISSING"))
    print("CLOUDPANEL=" + ("PRESENT" if shutil.which("clpctl") else "MISSING"))

    if shutil.which("pg_isready"):
        pg_rc, _ = command(["pg_isready", "-h", "127.0.0.1", "-p", "5432"], seconds=8)
        print("POSTGRES_LOCAL=" + ("ACCEPTING" if pg_rc == 0 else "NOT_VERIFIED"))
    else:
        print("POSTGRES_LOCAL=CLIENT_UNAVAILABLE")

    rc, state = command(["systemctl", "is-active", "kmj-stage-deploy.timer"], seconds=8)
    print("STAGING_DEPLOY_TIMER=" + ("ACTIVE" if rc == 0 and state.strip() == "active" else "INACTIVE_OR_ABSENT"))

    if PRODUCTION.resolve(strict=True) != before:
        print("PRODUCTION_POINTER=CHANGED_DURING_INSPECTION")
        return 4
    print("PRODUCTION_POINTER=UNCHANGED")
    print("NATIVE_STAGE_INSPECTION=PASS_READ_ONLY")
    print("STAGING_DEPLOYED_SHA=NOT_VERIFIED")
    print("FULL_STAGING_READINESS=NOT_YET_PROVEN")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect", action="store_true", required=True)
    args = parser.parse_args()
    raise SystemExit(check())
