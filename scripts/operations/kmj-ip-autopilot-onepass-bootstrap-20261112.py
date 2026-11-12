#!/usr/bin/env python3
"""KMJ-elite one-time zero-touch origin bootstrap. User executes ONCE as root.

No credentials from ChatGPT or GitHub. Inputs are read silently from the
owner's terminal and written to private local root-owned files. No production
DNS, MX, PTR, Nginx, PHP, Postfix, staging pointer or backup mutation.

--preflight: only inventory/pins; never root writes or requests credentials.
--activate: hash-pinned offline tests, optional signed APT cloudflared
install, secure local token capture, DNS agent inspect, canary-only Tunnel
start and (only after canary passes) enable the 5-min DNS-only agent timer.

Preflight is intentionally conservative; any drift blocks. This script does
not execute arbitrary commands or permit a caller-selected service/URL/path.
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time

SRC = Path("/srv/kmj-codebridge-projects/kmj-main-platform/work/qa/KMJ_IP_AUTOPILOT_20261112")
FILES = {
    "kmj-origin-ip-autopilot-20261112.py": "a5aa10bd19957e42ec91e5515f42b62186e1c7a78075afdeacb364d2366604ab",
    "test_kmj_origin_ip_autopilot_20261112.py": "0db9ec9d1c836e2f8efa585d68ec2b1aaaf1b90f49c77e67bba638bcb9bbedc5",
    "test_kmj_ip_autopilot_onepass_bootstrap_20261112.py": "dd72064953d5c38916352386355f24b241e50960524a2e14a363d89d2e3ffaff",
    "kmj-ip-autopilot.service": "ccf3f40ed779c0cc5e0e85c3caeab57f910e749bbfa8ec2a8b528ab31a82c058",
    "kmj-ip-autopilot.timer": "b0f7f80575d715c09419dd1f68cc1e282307e7ec93f314f32fd1ccb98d6f5b2f",
    "cloudflared-kmj-elite.example.service": "e51ba357ec86b5e33be6789d4f7ce7951d3d42cdfdcf80d545c9c47ce4af5fe4",
}
HOST_PUBLIC_KEY = "AAAAC3NzaC1lZDI1NTE5AAAAINZMT7YHsS5qRX/ciXTbLxKZVCgpJS7m/L9Nwgr3RNZS"
ZONE = "49f7523905736979a04e93497d8ccd43"
TUNNEL_ID = "b18c637f-2700-442a-a12e-b225c43dfc72"
CONF_DIR = Path("/etc/kmj-ip-autopilot")
CF_API_TOKEN = CONF_DIR / "cloudflare-token"
CONFIG = CONF_DIR / "config.json"
TUN_DIR = Path("/etc/cloudflared")
TUN_TOKEN = TUN_DIR / "kmj-elite-ip-independent.token"
AGENT_DST = Path("/usr/local/libexec/kmj-origin-ip-autopilot.py")
UNIT_DNS = Path("/etc/systemd/system/kmj-ip-autopilot.service")
UNIT_TIMER = Path("/etc/systemd/system/kmj-ip-autopilot.timer")
UNIT_TUN = Path("/etc/systemd/system/kmj-cloudflared-tunnel.service")
CF_BIN = Path("/usr/bin/cloudflared")
CANARY = "https://tunnel-canary.kmjtechno.com/"
TIMEOUT = 150
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
       "HOME": "/root", "LC_ALL": "C", "LANG": "C"}
REPO_ENTRY = ("deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] "
              "https://pkg.cloudflare.com/cloudflared any main\n")


class Stop(Exception):
    pass


def report(key: str, value: str) -> None:
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", key):
        raise Stop("REPORT_KEY_UNSAFE")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,140}", value):
        raise Stop("REPORT_VALUE_UNSAFE")
    print(f"{key}={value}", flush=True)


def run(argv: list[str], *, timeout: int = TIMEOUT,
        capture: bool = False) -> str:
    p = subprocess.run(
        argv, check=False, cwd="/", env=ENV,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, timeout=timeout,
    )
    if p.returncode:
        raise Stop("APPROVED_SUBPROCESS_FAILED_" + Path(argv[0]).name.upper().replace("-", "_"))
    return p.stdout.decode("utf-8", "replace")[:4096] if capture else ""


def fixed_host_identity() -> None:
    if os.geteuid() != 0 or socket.gethostname().split(".")[0].lower() != "kmj-elite":
        raise Stop("NOT_EXACT_ROOT_KMJ_ELITE")
    release = Path("/etc/os-release").read_text("utf-8", errors="replace")
    if 'ID=ubuntu' not in release or 'VERSION_ID="24.04"' not in release:
        raise Stop("OS_VERSION_UNREVIEWED")
    pub = Path("/etc/ssh/ssh_host_ed25519_key.pub")
    if pub.is_symlink() or not pub.is_file():
        raise Stop("SSH_HOST_PUBKEY_NOT_REGULAR")
    v = pub.read_text("ascii").split()
    if len(v) < 2 or v[0] != "ssh-ed25519" or v[1] != HOST_PUBLIC_KEY:
        raise Stop("KMJ_ELITE_HOST_IDENTITY_DRIFT")
    report("KMJ_ELITE_IDENTITY", "PASS")


def regular_nosymlink(path: Path) -> os.stat_result:
    if path.is_symlink():
        raise Stop("UNSAFE_SYMLINK")
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise Stop("NOT_ONE_REGULAR_FILE")
    return st


def root_dir(directory: Path, mode: int) -> None:
    if directory.is_symlink():
        raise Stop("PRIVATE_DIR_SYMLINK")
    if directory.exists():
        st = directory.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            raise Stop("DIR_OWNER_OR_MODE_DRIFT")
        return
    directory.mkdir(mode=mode)
    st = directory.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0:
        raise Stop("DIR_CREATION_UNVERIFIED")


def read_pinned(file: Path, expected: str) -> bytes:
    st = regular_nosymlink(file)
    if st.st_size < 1 or st.st_size > 130_000:
        raise Stop("QA_SOURCE_SIZE_UNREVIEWED")
    fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        data = bytearray()
        while len(data) < before.st_size:
            b = os.read(fd, min(8192, before.st_size - len(data)))
            if not b:
                break
            data.extend(b)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if (len(data) != before.st_size or
            (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size) !=
            (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size)):
        raise Stop("QA_SOURCE_RACE")
    if hashlib.sha256(data).hexdigest() != expected:
        raise Stop("QA_SOURCE_SHA256_MISMATCH")
    return bytes(data)


def write_new(path: Path, content: bytes, mode: int) -> None:
    if path.exists() or path.is_symlink():
        st = regular_nosymlink(path)
        if st.st_uid != 0 or stat.S_IMODE(st.st_mode) != mode or path.read_bytes() != content:
            raise Stop("EXISTING_TARGET_NOT_PINNED")
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        os.fchown(fd, 0, 0)
        os.fchmod(fd, mode)
        view = memoryview(content)
        while len(view):
            n = os.write(fd, view)
            if n <= 0:
                raise Stop("TARGET_SHORT_WRITE")
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    if path.read_bytes() != content:
        raise Stop("TARGET_READBACK_FAILED")


def capture_token(path: Path, *, prompt: str, pattern: str) -> None:
    if path.exists() or path.is_symlink():
        st = regular_nosymlink(path)
        if st.st_uid != 0 or stat.S_IMODE(st.st_mode) != 0o600:
            raise Stop("TOKEN_FILE_OWNER_OR_MODE")
        data = path.read_bytes()
        if not re.fullmatch(pattern, data.decode("ascii", "strict").strip()):
            raise Stop("EXISTING_TOKEN_FORMAT_BAD")
        report("TOKEN", "PRIVATE_EXISTING")
        return
    if not Path("/dev/tty").exists():
        raise Stop("OWNER_TTY_REQUIRED_FOR_TOKEN")
    # Private prompt, never echo or print the actual token. The reader must
    # copy the API token/Tunnel token directly from the Cloudflare dashboard.
    secret = getpass.getpass(prompt=prompt)
    if not re.fullmatch(pattern, secret):
        raise Stop("NEW_TOKEN_FORMAT_INVALID")
    write_new(path, secret.encode("ascii"), 0o600)
    secret = ""
    report("TOKEN", "PRIVATE_CREATED")


def cloudflared_package() -> None:
    if CF_BIN.is_file() and not CF_BIN.is_symlink():
        version = run([str(CF_BIN), "--version"], timeout=10, capture=True)
    else:
        report("CLOUDFLARED_PACKAGE", "APT_SIGNED_INSTALL")
        root_dir(Path("/usr/share/keyrings"), 0o755)
        root_dir(Path("/etc/apt/sources.list.d"), 0o755)
        key = Path("/usr/share/keyrings/cloudflare-main.gpg")
        repo = Path("/etc/apt/sources.list.d/cloudflared.list")
        if key.exists() or key.is_symlink():
            st = regular_nosymlink(key)
            if st.st_uid != 0 or st.st_mode & 0o022:
                raise Stop("APT_SIGNING_KEY_UNTRUSTED")
        else:
            # GPG key may be BINARY: never decode it to text, or truncate
            # subprocess stdout. Curl saves it into a random root-private file.
            with tempfile.NamedTemporaryFile(
                    prefix="cloudflare-apt-key-", dir="/run", delete=True) as tmpkey:
                run(["/usr/bin/curl", "--fail", "--silent", "--show-error",
                     "--proto", "=https", "--max-time", "30",
                     "--output", tmpkey.name,
                     "https://pkg.cloudflare.com/cloudflare-main.gpg"],
                    timeout=40)
                data = Path(tmpkey.name).read_bytes()
                if not 400 <= len(data) <= 200_000:
                    raise Stop("APT_KEY_RESPONSE_SIZE_UNREVIEWED")
                write_new(key, data, 0o644)
        write_new(repo, REPO_ENTRY.encode(), 0o644)
        run(["/usr/bin/apt-get", "update", "-qq"], timeout=300)
        run(["/usr/bin/apt-get", "install", "-y", "-qq",
             "--no-install-recommends", "cloudflared"], timeout=300)
        if not CF_BIN.is_file() or CF_BIN.is_symlink():
            raise Stop("SIGNED_CLOUDFLARED_INSTALL_NOT_VERIFIED")
        version = run([str(CF_BIN), "--version"], timeout=10, capture=True)
    match = re.search(r"version\s+([0-9]{4})\.([0-9]{1,2})\.[0-9]+", version)
    if match is None or (int(match[1]), int(match[2])) < (2025, 4):
        raise Stop("CLOUDFLARED_VERSION_BELOW_TOKEN_FILE_SUPPORT")
    report("CLOUDFLARED_BIN", "PASS")
    report("CLOUDFLARED_TOKEN_FILE", "SUPPORTED")


def offline_tests(staged: dict[str, bytes], scratch: Path) -> None:
    for filename in ("kmj-origin-ip-autopilot-20261112.py",
                     "test_kmj_origin_ip_autopilot_20261112.py",
                     "kmj-ip-autopilot-onepass-bootstrap-20261112.py",
                     "test_kmj_ip_autopilot_onepass_bootstrap_20261112.py"):
        # The bootstrap file is pinned by the owner's *external* SHA-256
        # launcher and is copied from this running private file. It is never
        # loaded as untrusted input from a project checkout.
        contents = (Path(__file__).read_bytes()
                    if filename == "kmj-ip-autopilot-onepass-bootstrap-20261112.py"
                    else staged[filename])
        write_new(scratch / filename, contents, 0o600)
        # Python syntax check only, never import from mutable project sources.
        run(["/usr/bin/python3", "-I", "-B", "-c",
             "import ast,pathlib,sys;ast.parse(pathlib.Path(sys.argv[1]).read_bytes())",
             str(scratch / filename)], timeout=12)
    run(["/usr/bin/python3", "-I", "-B",
         str(scratch / "test_kmj_origin_ip_autopilot_20261112.py"),
         "-q"], timeout=45)
    # Independently test the installer itself before any package or service
    # mutation. Tests import a pinned copy from the private scratch folder.
    run(["/usr/bin/python3", "-I", "-B", "-c",
         "import ast,pathlib,sys;ast.parse(pathlib.Path(sys.argv[1]).read_bytes())",
         str(scratch / "test_kmj_ip_autopilot_onepass_bootstrap_20261112.py")],
        timeout=12)
    run(["/usr/bin/python3", "-I", "-B",
         str(scratch / "test_kmj_ip_autopilot_onepass_bootstrap_20261112.py"),
         "-q"], timeout=45)
    report("OFFLINE_PYTHON_TESTS", "PASS")


def config_and_tokens() -> None:
    root_dir(CONF_DIR, 0o700)
    root_dir(TUN_DIR, 0o700)
    cfg = (json.dumps({"zone_id": ZONE, "mode": "direct_only"},
                      sort_keys=True) + "\n").encode("ascii")
    write_new(CONFIG, cfg, 0o600)
    capture_token(TUN_TOKEN, prompt="Cloudflare named Tunnel token (hidden): ",
                  pattern=r"[A-Za-z0-9_.-]{50,4096}")
    capture_token(CF_API_TOKEN, prompt="Cloudflare KMJ zone DNS Read/Edit token (hidden): ",
                  pattern=r"[A-Za-z0-9_-]{32,250}")
    report("CONFIG_MODE", "DIRECT_ONLY")


def read_agent_inspect() -> None:
    result = run(["/usr/bin/python3", "-I", "-B", str(AGENT_DST), "--inspect"],
                 timeout=150, capture=True)
    required = {"DNS_CONVERGED=YES", "RESULT=PASS", "SPF_CHANGE=NO"}
    if not required.issubset(set(result.splitlines())):
        raise Stop("DNS_AGENT_INITIAL_INSPECT_NOT_CONVERGED")
    report("DNS_AGENT_INSPECT", "PASS_NO_CHANGES")


def install_units(staged: dict[str, bytes]) -> None:
    write_new(AGENT_DST, staged["kmj-origin-ip-autopilot-20261112.py"], 0o500)
    write_new(UNIT_DNS, staged["kmj-ip-autopilot.service"], 0o644)
    write_new(UNIT_TIMER, staged["kmj-ip-autopilot.timer"], 0o644)
    write_new(UNIT_TUN, staged["cloudflared-kmj-elite.example.service"], 0o644)
    run(["/usr/bin/systemd-analyze", "verify",
         str(UNIT_DNS), str(UNIT_TIMER), str(UNIT_TUN)], timeout=35)
    run(["/usr/bin/systemctl", "daemon-reload"], timeout=30)
    report("SYSTEMD_UNITS", "PINNED_INSTALLED")


def canary_ready() -> bool:
    for _ in range(8):
        try:
            result = run(["/usr/bin/curl", "--noproxy", "*", "--fail",
                          "--silent", "--show-error", "--proto", "=https",
                          "--connect-timeout", "8", "--max-time", "18",
                          "--output", "/dev/null", "--write-out", "%{http_code}",
                          CANARY], timeout=21, capture=True).strip()
            if result == "200":
                return True
        except Stop:
            pass
        time.sleep(3)
    return False


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("--preflight", "--activate"):
        raise Stop("USAGE_PREFLIGHT_OR_ACTIVATE")
    fixed_host_identity()
    pinned = {name: read_pinned(SRC / name, expected) for name, expected in FILES.items()}
    report("QA_PINNED_SOURCES", "6_PASS")
    if sys.argv[1] == "--preflight":
        report("MODE", "READ_ONLY")
        report("CLOUDFLARED_INSTALLED", "YES" if CF_BIN.exists() else "NO")
        report("ZONE_TOKEN_PRESENT", "YES" if CF_API_TOKEN.is_file() else "NO")
        report("TUNNEL_TOKEN_PRESENT", "YES" if TUN_TOKEN.is_file() else "NO")
        report("RESULT", "PREFLIGHT_PASS")
        return

    if not sys.stdin.isatty() and not Path("/dev/tty").exists():
        raise Stop("OWNER_CONSOLE_REQUIRED")
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="kmj-ip-private-", dir="/run") as t:
        scratch = Path(t)
        staged = pinned
        offline_tests(staged, scratch)
        cloudflared_package()
        config_and_tokens()
        root_dir(AGENT_DST.parent, 0o755)
        install_units(staged)
        read_agent_inspect()
        run(["/usr/bin/systemctl", "enable", "--now",
             "kmj-cloudflared-tunnel.service"], timeout=50)
        report("TUNNEL_SERVICE", "START_REQUESTED")
        if not canary_ready():
            report("DNS_CUTOVER", "NOT_ATTEMPTED")
            raise Stop("TUNNEL_CANARY_NOT_READY")
        report("TUNNEL_CANARY", "HTTPS_200_PASS")
        # Only direct mail+SSH DNS maintenance; never touches public web A.
        run(["/usr/bin/systemctl", "enable", "--now",
             "kmj-ip-autopilot.timer"], timeout=40)
        report("DNS_AGENT_TIMER", "ACTIVE_REQUESTED")
        report("PRODUCTION_DNS_CUTOVER", "NOT_ATTEMPTED")
        report("RESULT", "BOOTSTRAP_READY_FOR_WEB_CNAME_CUTOVER")


if __name__ == "__main__":
    try:
        main()
    except (Stop, OSError, ValueError, UnicodeError, subprocess.TimeoutExpired) as exc:
        reason = str(exc) if isinstance(exc, Stop) else "SYSTEM_OR_RUNTIME_UNAVAILABLE"
        if not re.fullmatch(r"[A-Z0-9_]{3,120}", reason):
            reason = "BLOCKED_SAFE"
        report("BLOCKER", reason)
        report("RESULT", "BLOCKED_NO_WEB_CUTOVER")
        raise SystemExit(3)
