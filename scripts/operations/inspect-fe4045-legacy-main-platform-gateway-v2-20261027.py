#!/usr/bin/env python3
"""KMJ Main Platform: inspect legacy gateway port (v2); no apply unless code supports both keys.

Never restarts CodeBridge, PHP or nginx; never prints private URL, credentials or .env.
Production activation and deployment approval are deliberately out of scope.
"""
import argparse
import fcntl
import ipaddress
import os
from pathlib import Path
import re
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

SITE = Path("/home/kmjprod/current")
EXPECTED_LIVE = "/home/kmjprod/releases/platform-8070dad72c55"
ENV = SITE / "apps/platform/.env"
UNIT = "kmj-codebridge-gateway-stage.service"
PUBLIC = "https://kmjtechno.com"
SOURCE_SHA = "fe4045acd08d50a7438dbfc6fee0610b02e1df50"


def status(name, val):
    print(f"{name}={val}", flush=True)


def stop(reason):
    status("KMJ_GATEWAY_ENV_FIX", "BLOCKED_" + reason)
    raise SystemExit(2)


def run(*args):
    p = subprocess.run(list(args), capture_output=True, text=True, timeout=8, check=False)
    return p.returncode, p.stdout


def lines_of_value(data, name):
    found = []
    for i, line in enumerate(data.splitlines(keepends=True)):
        if line.lstrip().startswith("#"):
            continue
        m = re.fullmatch(r"\s*" + re.escape(name) + r"\s*=\s*(.*?)\s*(?:\r?\n)?", line)
        if m:
            raw = m.group(1).strip()
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
                raw = raw[1:-1]
            found.append((i, raw))
    return found


def preflight():
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        stop("ROOT_ELITE_REQUIRED")
    if not SITE.is_symlink() or str(SITE.resolve()) != EXPECTED_LIVE:
        stop("LIVE_POINTER_DRIFT")
    if ENV.is_symlink() or not ENV.is_file():
        stop("LIVE_ENV_MISSING_OR_LINK")
    s = ENV.stat()
    if s.st_mode & 0o007 or not stat.S_ISREG(s.st_mode):
        stop("LIVE_ENV_PERMISSIONS")
    if (SITE / "apps/platform/bootstrap/cache/config.php").exists():
        stop("LARAVEL_CONFIG_CACHED")
    services = SITE / "apps/platform/config/services.php"
    if not services.is_file():
        stop("LARAVEL_SERVICES_CONFIG_MISSING")
    config_text = services.read_text("utf-8")
    if not all(v in config_text for v in ("codebridge_gateway", "CODEBRIDGE_GATEWAY_URL")):
        stop("LARAVEL_PRIVATE_GATEWAY_KEY_NOT_PRESENT")
    public_supported = "CODEBRIDGE_AGENT_PUBLIC_URL" in config_text
    code, active = run("systemctl", "is-active", UNIT)
    if code != 0 or active.strip() != "active":
        stop("GATEWAY_NOT_ACTIVE")
    code, raw_pid = run("systemctl", "show", UNIT, "--property=MainPID", "--value")
    if code != 0 or not raw_pid.strip().isdigit() or int(raw_pid.strip()) <= 0:
        stop("GATEWAY_PID_UNAVAILABLE")
    pid = int(raw_pid.strip())
    code, listen = run("ss", "-H", "-ltnp")
    if code != 0:
        stop("LISTENERS_UNAVAILABLE")
    bound = set()
    nonloop = False
    for line in listen.splitlines():
        if f"pid={pid}," not in line:
            continue
        cols = line.split()
        if len(cols) < 5:
            continue
        m = re.search(r":(\d+)$", cols[3])
        if not m:
            continue
        port = int(m.group(1))
        addr = cols[3][:m.start()]
        if addr.startswith("[") and addr.endswith("]"):
            addr = addr[1:-1]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            stop("GATEWAY_BIND_NOT_IP")
        if not ip.is_loopback:
            nonloop = True
        else:
            bound.add((str(ip), port))
    if nonloop or len(bound) != 1:
        stop("AMBIGUOUS_OR_EXPOSED_GATEWAY_LISTENER")
    host, port = next(iter(bound))
    if not (1024 <= port <= 65535):
        stop("GATEWAY_PORT_OUT_OF_RANGE")
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
    except OSError:
        stop("GATEWAY_LOOPBACK_TCP_NOT_REACHABLE")
    lines = ENV.read_text("utf-8")
    current = lines_of_value(lines, "CODEBRIDGE_GATEWAY_URL")
    origins = lines_of_value(lines, "CODEBRIDGE_AGENT_PUBLIC_URL")
    if len(current) != 1 or len(origins) > 1:
        stop("MISSING_OR_DUPLICATE_ENV_KEYS")
    try:
        url = urlsplit(current[0][1])
        old_host = url.hostname
        old_port = url.port
        if old_host != "localhost" and not ipaddress.ip_address(old_host).is_loopback:
            stop("CURRENT_UPSTREAM_NOT_LOOPBACK")
        if url.scheme not in ("http", "https") or url.username or url.password or url.query or url.fragment or url.path not in ("", "/") or not old_port:
            stop("CURRENT_UPSTREAM_INVALID")
    except (ValueError, TypeError):
        stop("CURRENT_UPSTREAM_INVALID")
    if origins and origins[0][1] not in ("", PUBLIC):
        stop("PUBLIC_ORIGIN_CONFLICT")
    return s, lines, current, origins, url.scheme, old_port, host, port, public_supported


def tls_public():
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection(("kmjtechno.com", 443), timeout=4) as sock:
            with ctx.wrap_socket(sock, server_hostname="kmjtechno.com") as tls:
                return tls.version() is not None
    except (OSError, ssl.SSLError):
        return False


def durable_write(data, original_stat, expected_text):
    parent = ENV.parent
    backup_dir = Path("/root")
    fd, backup_name = tempfile.mkstemp(prefix=".kmj-gateway-env-backup-", dir=backup_dir)
    backup = Path(backup_name)
    fd2, tmp_name = tempfile.mkstemp(prefix=".kmj-gateway-env-update-", dir=parent)
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(ENV.read_bytes())
            f.flush()
            os.fsync(f.fileno())
        with os.fdopen(fd2, "wb") as f:
            os.fchmod(f.fileno(), stat.S_IMODE(original_stat.st_mode))
            os.fchown(f.fileno(), original_stat.st_uid, original_stat.st_gid)
            f.write(data.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        if ENV.is_symlink() or ENV.stat().st_ino != original_stat.st_ino or ENV.read_text("utf-8") != expected_text:
            stop("ENV_CHANGED_CONCURRENTLY")
        os.replace(tmp, ENV)
        directory_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if tmp.exists():
            tmp.unlink()
    return backup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", default=False)
    parser.add_argument("--expect-port", type=int)
    args = parser.parse_args()
    st, lines, current, origins, scheme, previous, host, port, public_supported = preflight()
    status("EXPECTED_CANDIDATE_SHA", SOURCE_SHA)
    status("GATEWAY_SERVICE_TCP", "PASS_LOOPBACK_ONLY")
    status("ACTUAL_GATEWAY_LOOPBACK_PORT", port)
    status("APP_CONFIGURED_LOOPBACK_PORT", previous)
    status("APP_ENDPOINT_MATCH", "PASS" if previous == port else "MISMATCH")
    status("PUBLIC_ORIGIN_CONFIGURED", "YES" if origins and origins[0][1] == PUBLIC else "NO")
    status("LIVE_CODE_PRIVATE_GATEWAY_SUPPORT", "YES")
    status("LIVE_CODE_PUBLIC_AGENT_ORIGIN_SUPPORT", "YES" if public_supported else "NO_LEGACY_RELEASE")
    status("PRIVATE_ONLY_CONFIG_ALIGNMENT", "ELIGIBLE_FOR_SEPARATE_APPROVAL" if previous != port else "ALREADY_MATCHING")
    status("PUBLIC_TLS_CERTIFICATE", "PASS" if tls_public() else "NOT_VERIFIED")
    if not args.apply:
        status("SYSTEM_CHANGES", "NONE")
        status("KMJ_GATEWAY_ENV_FIX", "INSPECT_ONLY")
        return

    if not public_supported:
        stop("LIVE_RELEASE_LACKS_PUBLIC_AGENT_ORIGIN_SUPPORT")

    if os.environ.get("KMJ_APPROVE_CONFIG_ONLY") != "YES" or args.expect_port != port:
        stop("EXPLICIT_CONFIG_ONLY_PORT_APPROVAL_REQUIRED")
    # Same lock used by guarded release build: never race a cutover or another release.
    lock_fd = os.open("/run/lock/kmj-main-platform-production-release.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        stop("PRODUCTION_RELEASE_BUSY")
    if str(SITE.resolve()) != EXPECTED_LIVE or ENV.stat().st_ino != st.st_ino:
        stop("LIVE_OR_ENV_DRIFT")
    if not tls_public():
        stop("PUBLIC_HTTPS_CERT_NOT_VERIFIED")
    if not (SITE / "apps/platform/config/services.php").is_file():
        stop("SERVICES_CONFIG_INVALID")
    if scheme != "http":
        stop("NON_HTTP_GATEWAY_SCHEME_REQUIRES_REVIEW")
    # Preserve all unrelated values and bytes; change only these two literal keys.
    url_value = f"http://{host if ':' not in host else '[' + host + ']'}:{port}"
    file_lines = lines.splitlines(keepends=True)
    file_lines[current[0][0]] = "CODEBRIDGE_GATEWAY_URL=" + url_value + "\n"
    if origins:
        file_lines[origins[0][0]] = "CODEBRIDGE_AGENT_PUBLIC_URL=" + PUBLIC + "\n"
    else:
        file_lines.append(("\n" if lines and not lines.endswith("\n") else "") + "CODEBRIDGE_AGENT_PUBLIC_URL=" + PUBLIC + "\n")
    updated = "".join(file_lines)
    if len(updated) > 262144:
        stop("ENV_TOO_LARGE")
    if len(lines_of_value(updated, "CODEBRIDGE_GATEWAY_URL")) != 1 or len(lines_of_value(updated, "CODEBRIDGE_AGENT_PUBLIC_URL")) != 1:
        stop("UPDATE_ENV_DUPLICATE")
    if ENV.stat().st_ino != st.st_ino:
        stop("ENV_CHANGED")
    backup = durable_write(updated, st, lines)
    status("ENV_BACKUP_ROOT_ONLY", "CREATED")
    status("PRODUCTION_ENV_KEYS_CHANGED", "ONLY_CODEBRIDGE_GATEWAY_AND_PUBLIC_AGENT_ORIGIN")
    status("GATEWAY_SERVICE_RESTARTED", "NO")
    status("NGINX_RESTARTED", "NO")
    status("PRODUCTION_RELEASE", "UNCHANGED")
    status("PRODUCTION_APPROVAL", "UNCHANGED")
    status("PUBLIC_AGENT_PAIRING", "NOT_VERIFIED")
    status("KMJ_GATEWAY_ENV_FIX", "APPLIED_CONFIG_ONLY_REQUIRES_OWNER_QA")


if __name__ == "__main__":
    main()
