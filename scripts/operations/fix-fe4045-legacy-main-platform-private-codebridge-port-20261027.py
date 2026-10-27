#!/usr/bin/env python3
"""Production-guarded legacy CodeBridge PRIVATE PORT alignment.

Default is read-only. --apply requires explicit operator approval. Never prints
.env values, tokens or full upstream URLs. Does not restart a service, enable
public pairing, change DNS or activate a production release.
"""
import argparse
import fcntl
import ipaddress
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile
from urllib.parse import urlsplit

LIVE = Path("/home/kmjprod/current")
EXPECTED_LIVE = "/home/kmjprod/releases/platform-8070dad72c55"
ENV = LIVE / "apps/platform/.env"
SERVICES = LIVE / "apps/platform/config/services.php"
CONFIG_CACHE = LIVE / "apps/platform/bootstrap/cache/config.php"
UNIT = "kmj-codebridge-gateway-stage.service"
LOCK = "/run/lock/kmj-main-platform-production-release.lock"
KEY = "CODEBRIDGE_GATEWAY_URL"
EXPECTED_OLD_PORT = 8787
EXPECTED_NEW_PORT = 18787


def report(key, value):
    print(f"{key}={value}", flush=True)


def block(reason):
    report("KMJ_PRIVATE_GATEWAY_ALIGNMENT", f"BLOCKED_{reason}")
    raise SystemExit(2)


def command(*args):
    proc = subprocess.run(args, capture_output=True, text=True, timeout=8, check=False)
    return proc.returncode, proc.stdout.strip()


def parse_key(text):
    found = []
    for i, line in enumerate(text.splitlines(keepends=True)):
        if line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"\s*" + re.escape(KEY) + r"\s*=\s*(.*?)\s*(?:\r?\n)?", line)
        if match:
            raw = match.group(1)
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
                raw = raw[1:-1]
            found.append((i, raw))
    return found


def status():
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        block("ROOT_ON_ELITE_REQUIRED")
    if not LIVE.is_symlink() or str(LIVE.resolve()) != EXPECTED_LIVE:
        block("LIVE_POINTER_CHANGED")
    if ENV.is_symlink() or not ENV.is_file():
        block("LIVE_ENV_NOT_REGULAR")
    st = ENV.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o007:
        block("LIVE_ENV_INSECURE")
    if CONFIG_CACHE.exists() or CONFIG_CACHE.is_symlink():
        block("LARAVEL_CONFIG_CACHE_PRESENT")
    if not SERVICES.is_file():
        block("LARAVEL_SERVICES_FILE_MISSING")
    s = SERVICES.read_text("utf-8")
    if "codebridge_gateway" not in s or "CODEBRIDGE_GATEWAY_URL" not in s:
        block("LIVE_CODE_NOT_SUPPORTING_PRIVATE_GATEWAY")
    # In this older release, the public-agent origin key is not consumed.
    if "CODEBRIDGE_AGENT_PUBLIC_URL" in s:
        block("LIVE_CODE_VERSION_CHANGED_REVIEW_REQUIRED")
    raw = ENV.read_bytes()
    if len(raw) > 262144:
        block("ENV_EXCEEDS_SAFE_SIZE")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError:
        block("ENV_ENCODING")
    matches = parse_key(source)
    if len(matches) != 1:
        block("PRIVATE_GATEWAY_KEY_MISSING_OR_DUPLICATE")
    try:
        parsed = urlsplit(matches[0][1])
        host = parsed.hostname
        current_port = parsed.port
        if host != "localhost":
            if not ipaddress.ip_address(host).is_loopback:
                block("CURRENT_UPSTREAM_NOT_LOOPBACK")
        if (parsed.scheme != "http" or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.path not in ("", "/") or current_port is None):
            block("CURRENT_UPSTREAM_INVALID")
    except (ValueError, AttributeError, TypeError):
        block("CURRENT_UPSTREAM_INVALID")
    if current_port not in (EXPECTED_OLD_PORT, EXPECTED_NEW_PORT):
        block("CURRENT_PORT_DRIFT")

    rc, active = command("systemctl", "is-active", UNIT)
    if rc or active != "active":
        block("GATEWAY_SERVICE_NOT_ACTIVE")
    rc, pid_s = command("systemctl", "show", UNIT, "--property=MainPID", "--value")
    if rc or not pid_s.isdigit() or int(pid_s) <= 0:
        block("GATEWAY_PID_INVALID")
    gateway_pid = int(pid_s)
    rc, sockets = command("ss", "-H", "-ltnp")
    if rc:
        block("SOCKET_INVENTORY_UNAVAILABLE")
    bound = set()
    for line in sockets.splitlines():
        if f"pid={gateway_pid}," not in line:
            continue
        cols = line.split()
        if len(cols) < 5:
            continue
        match = re.search(r":(\d+)$", cols[3])
        if match is None:
            continue
        port = int(match.group(1))
        addr = cols[3][:match.start()]
        if addr.startswith("[") and addr.endswith("]"):
            addr = addr[1:-1]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            block("GATEWAY_BIND_INVALID")
        if not ip.is_loopback:
            block("GATEWAY_EXPOSED_NON_LOOPBACK")
        bound.add((str(ip), port))
    if len(bound) != 1:
        block("GATEWAY_LISTENER_AMBIGUOUS")
    actual_ip, actual_port = next(iter(bound))
    if actual_port != EXPECTED_NEW_PORT:
        block("GATEWAY_LISTENER_PORT_DRIFT")
    try:
        # Test with the unchanged original host, not merely another loopback IP.
        with socket.create_connection((host, EXPECTED_NEW_PORT), timeout=2):
            pass
    except OSError:
        block("TARGET_NOT_REACHABLE_VIA_APP_HOST")

    return st, raw, source, matches[0][0], parsed, host, current_port, gateway_pid, actual_ip


def atomic_replace(data, st):
    parent = ENV.parent
    fd, name = tempfile.mkstemp(prefix=".kmj-private-gateway-update-", dir=parent)
    staged = Path(name)
    try:
        with os.fdopen(fd, "wb") as out:
            os.fchown(out.fileno(), st.st_uid, st.st_gid)
            os.fchmod(out.fileno(), stat.S_IMODE(st.st_mode))
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(staged, ENV)
        dirfd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if staged.exists():
            staged.unlink()


def save_backup(raw):
    fd, backup_path = tempfile.mkstemp(prefix=".kmj-private-gateway-env-before-", dir="/root")
    with os.fdopen(fd, "wb") as backup:
        os.fchmod(backup.fileno(), 0o400)
        backup.write(raw)
        backup.flush()
        os.fsync(backup.fileno())
    return backup_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expect-old-port", type=int)
    parser.add_argument("--expect-new-port", type=int)
    args = parser.parse_args()
    state = status()
    st, before, text, keyline, url, host, configured, pid, bound_host = state
    report("EXACT_TARGET_RELEASE", "platform-8070dad72c55")
    report("GATEWAY_SYSTEMD", "ACTIVE")
    report("GATEWAY_PID_PRESENT", "YES")
    report("GATEWAY_BIND", "LOOPBACK_ONLY")
    report("ACTUAL_GATEWAY_PORT", EXPECTED_NEW_PORT)
    report("APP_CONFIGURED_PORT", configured)
    report("PORT_ALIGNMENT", "PASS" if configured == EXPECTED_NEW_PORT else "MISMATCH")
    report("LIVE_PUBLIC_AGENT_ORIGIN_SUPPORT", "NO_LEGACY_RELEASE")
    if not args.apply:
        report("SYSTEM_CHANGES", "NONE")
        report("KMJ_PRIVATE_GATEWAY_ALIGNMENT", "INSPECT_ONLY")
        return

    if (os.environ.get("KMJ_APPROVE_PRIVATE_PORT_CHANGE") != "YES"
        or args.expect_old_port != EXPECTED_OLD_PORT
        or args.expect_new_port != EXPECTED_NEW_PORT):
        block("EXPLICIT_PORT_SCOPED_APPROVAL_REQUIRED")

    lockfd = os.open(LOCK, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        block("RELEASE_LOCK_BUSY")
    # Reinspect after acquiring release lock.
    fresh = status()
    state = fresh
    st, latest_raw, current_text, keyline, url, host, current_port, newpid, bound_host = state
    if newpid != pid or latest_raw != before:
        block("GATEWAY_SERVICE_OR_ENV_CHANGED")
    if current_port == EXPECTED_NEW_PORT:
        report("ENV_UPDATE", "ALREADY_CORRECT")
        report("PRODUCTION_RELEASE", "UNCHANGED")
        report("KMJ_PRIVATE_GATEWAY_ALIGNMENT", "PASS_ALREADY_MATCHING")
        return
    if current_port != EXPECTED_OLD_PORT:
        block("UNEXPECTED_OLD_PORT")
    file_lines = current_text.splitlines(keepends=True)
    original_line = file_lines[keyline]
    # Preserve host, original URL syntax and all unrelated environment content.
    pos = original_line.find(KEY)
    if pos < 0:
        block("KEY_LINE_NOT_FOUND")
    newurl = f"http://{host if ':' not in host else '[' + host + ']'}:{EXPECTED_NEW_PORT}"
    new_line = original_line[:pos] + KEY + "=" + newurl + ("\r\n" if original_line.endswith("\r\n") else "\n" if original_line.endswith("\n") else "")
    file_lines[keyline] = new_line
    changed = "".join(file_lines).encode("utf-8")
    if len(parse_key(changed.decode("utf-8"))) != 1:
        block("RESULT_CONTAINS_DUPLICATE_KEYS")
    # Verify there was exactly one line change; do not touch public origin.
    if len(file_lines) != len(current_text.splitlines(keepends=True)):
        block("LINE_COUNT_CHANGED")
    if ENV.stat().st_ino != st.st_ino or ENV.read_bytes() != before or str(LIVE.resolve()) != EXPECTED_LIVE:
        block("ENV_CHANGED_BEFORE_REPLACE")
    save_backup(before)
    try:
        atomic_replace(changed, st)
        written = ENV.read_bytes()
        if written != changed or len(parse_key(written.decode("utf-8"))) != 1:
            raise RuntimeError("verification failed")
        result = status()
        if result[6] != EXPECTED_NEW_PORT or result[7] != pid:
            raise RuntimeError("gateway status drifted")
    except Exception:
        # Preserve original ownership/mode; do not restart any services.
        atomic_replace(before, st)
        report("ENV_AUTO_ROLLBACK", "ATTEMPTED")
        block("POST_UPDATE_VERIFICATION")
    report("ROOT_ONLY_ENV_BACKUP", "CREATED")
    report("PRIVATE_GATEWAY_PORT_CHANGE", "8787_TO_18787")
    report("PUBLIC_AGENT_ORIGIN_CHANGED", "NO")
    report("GATEWAY_SERVICE_RESTARTED", "NO")
    report("WEB_SERVICES_RESTARTED", "NO")
    report("PRODUCTION_POINTER_CHANGED", "NO")
    report("GUARDED_PRODUCTION_APPROVAL", "UNCHANGED")
    report("APPLICATION_ROUTE_QA", "NOT_VERIFIED")
    report("KMJ_PRIVATE_GATEWAY_ALIGNMENT", "PASS_CONFIG_ONLY")


if __name__ == "__main__":
    main()
