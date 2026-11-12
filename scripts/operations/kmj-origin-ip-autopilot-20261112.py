#!/usr/bin/env python3
"""KMJ-elite Cloudflare IPv4 DNS reconciler, never an arbitrary DNS updater.

Modes: ddns (six exact A records + SPF), direct_only (mail + SSH A and SPF).
Runs unattended from a pinned systemd service after one-time private token
provisioning. External egress detection alone is not sufficient: HTTPS SNI
checks against the proposed address must pass for ddns mode. Always fail closed
on drift, unexpected Cloudflare records, identity mismatch or API failure.

Never changes MX, DKIM, DMARC, reverse PTR, SSH trust, certificates, services,
production release, application config or arbitrary DNS names.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ZONE_HOST = "kmjtechno.com"
WEB_HOSTS = (
    "kmjtechno.com",
    "www.kmjtechno.com",
    "staging.kmjtechno.com",
    "cloudos.kmjtechno.com",
)
MAIL_HOST = "mail.kmjtechno.com"
SSH_HOST = "elite-ssh.kmjtechno.com"
EXPECTED_HOSTS = WEB_HOSTS + (MAIL_HOST, SSH_HOST)
DETECTORS = ("https://api.ipify.org", "https://ipv4.icanhazip.com")
API_BASE = "https://api.cloudflare.com/client/v4"
CONFIG_FILE = Path("/etc/kmj-ip-autopilot/config.json")
TOKEN_FILE = Path("/etc/kmj-ip-autopilot/cloudflare-token")
PUBLIC_HOST_KEY = "AAAAC3NzaC1lZDI1NTE5AAAAINZMT7YHsS5qRX/ciXTbLxKZVCgpJS7m/L9Nwgr3RNZS"
PUBKEY_FILE = Path("/etc/ssh/ssh_host_ed25519_key.pub")
MAX_RESPONSE = 150_000


class Block(Exception):
    pass


def emit(key: str, value: str) -> None:
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,70}", key):
        raise Block("UNSAFE_REPORT_KEY")
    if not re.fullmatch(r"[A-Za-z0-9_.:+-]{1,180}", str(value)):
        raise Block("UNSAFE_REPORT_VALUE")
    print(f"{key}={value}", flush=True)


def public_ipv4(raw: str) -> str:
    if not isinstance(raw, str) or len(raw) > 48 or raw != raw.strip():
        raise Block("INVALID_PUBLIC_IPV4")
    try:
        addr = ipaddress.IPv4Address(raw)
    except ipaddress.AddressValueError:
        raise Block("INVALID_PUBLIC_IPV4") from None
    if not addr.is_global or addr.is_multicast or addr.is_reserved or addr.is_loopback:
        raise Block("NONPUBLIC_IPV4")
    return str(addr)


def root_owned(path: Path, *, regular: bool = False, mode: int = 0o022) -> None:
    p = path
    while True:
        if p.is_symlink():
            raise Block("SYMLINK_PROTECTED_PATH")
        st = p.lstat()
        if st.st_uid != 0 or st.st_mode & 0o022:
            raise Block("UNTRUSTED_FILE_OWNER_OR_MODE")
        if p == path:
            if regular and (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & mode):
                raise Block("UNSAFE_PRIVATE_FILE")
        elif not stat.S_ISDIR(st.st_mode):
            raise Block("UNSAFE_PARENT_DIRECTORY")
        if p.parent == p:
            break
        p = p.parent


def read_private(path: Path, *, limit: int, exact_mode: int | None = None) -> bytes:
    root_owned(path, regular=True, mode=0o077)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if before.st_size <= 0 or before.st_size > limit:
            raise Block("PRIVATE_FILE_SIZE")
        if exact_mode is not None and stat.S_IMODE(before.st_mode) != exact_mode:
            raise Block("PRIVATE_FILE_MODE")
        data = os.read(fd, limit + 1)
        after = os.fstat(fd)
        if (len(data) != before.st_size or
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            raise Block("PRIVATE_FILE_RACE")
        return data
    finally:
        os.close(fd)


def identity_guard() -> None:
    if os.geteuid() != 0 or socket.gethostname().split(".")[0].lower() != "kmj-elite":
        raise Block("WRONG_MACHINE_OR_USER")
    try:
        key = PUBKEY_FILE.read_text("ascii").split()
    except (OSError, UnicodeError):
        raise Block("HOST_PUBLIC_KEY_UNAVAILABLE") from None
    if len(key) < 2 or key[0] != "ssh-ed25519" or key[1] != PUBLIC_HOST_KEY:
        raise Block("HOST_PUBLIC_KEY_DRIFT")


def config() -> tuple[str, str, str]:
    data = read_private(CONFIG_FILE, limit=1024, exact_mode=0o600)
    try:
        cfg = json.loads(data.decode("ascii"))
    except (UnicodeError, ValueError):
        raise Block("CONFIG_NOT_JSON") from None
    if set(cfg) != {"zone_id", "mode"} or not re.fullmatch(r"[a-f0-9]{32}", str(cfg["zone_id"])):
        raise Block("CONFIG_SCOPE_INVALID")
    if cfg["mode"] not in ("ddns", "direct_only"):
        raise Block("CONFIG_MODE_INVALID")
    raw = read_private(TOKEN_FILE, limit=512, exact_mode=0o600)
    token = raw.decode("ascii", "strict").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,250}", token):
        raise Block("TOKEN_FORMAT_INVALID")
    return cfg["zone_id"], cfg["mode"], token


def url_text(url: str, *, limit: int, token: str | None = None,
             data: bytes | None = None, method: str = "GET") -> bytes:
    if not (url.startswith(API_BASE + "/") or url in DETECTORS):
        raise Block("URL_NOT_ALLOWLISTED")
    headers = {"User-Agent": "KMJ-IP-Autopilot/1.0", "Accept": "application/json"}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    # Never follow redirects: protects the zone-scoped Bearer token from
    # cross-origin forwarding and disallows IP probes silently moving hosts.
    class RefuseRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    # Do not inherit HTTP(S)_PROXY from systemd or environment.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), RefuseRedirect(),
    )
    try:
        with opener.open(request, timeout=12) as response:
            if response.geturl() != url:
                raise Block("HTTPS_UNEXPECTED_REDIRECT")
            if response.status < 200 or response.status >= 300:
                raise Block("HTTP_STATUS_NOT_SUCCESS")
            result = response.read(limit + 1)
            if len(result) > limit:
                raise Block("HTTP_RESPONSE_TOO_LARGE")
            return result
    except (urllib.error.URLError, TimeoutError, OSError):
        raise Block("HTTPS_REQUEST_UNAVAILABLE") from None


def cloudflare(zone: str, token: str, path: str, *, body: dict | None = None) -> dict:
    if not re.fullmatch(r"[a-f0-9]{32}", zone):
        raise Block("CF_ZONE_INVALID")
    method = "PATCH" if body is not None else "GET"
    request_data = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("ascii") if body is not None else None
    raw = url_text(API_BASE + "/zones/" + zone + "/dns_records" + path,
                   limit=MAX_RESPONSE, token=token, data=request_data, method=method)
    try:
        parsed = json.loads(raw)
    except (ValueError, UnicodeError):
        raise Block("CF_RESPONSE_NOT_JSON") from None
    if not isinstance(parsed, dict) or parsed.get("success") is not True:
        raise Block("CF_API_OPERATION_FAILED")
    return parsed


def records(zone: str, token: str, *, name: str, record_type: str) -> dict:
    if name not in EXPECTED_HOSTS or record_type not in ("A", "TXT"):
        raise Block("DNS_RECORD_SCOPE_NOT_ALLOWED")
    if record_type == "TXT" and name != ZONE_HOST:
        raise Block("TXT_SCOPE_NOT_ALLOWED")
    query = "?" + urllib.parse.urlencode({
        "name": name, "type": record_type, "per_page": 100, "page": 1,
    })
    reply = cloudflare(zone, token, query)
    rows = reply.get("result")
    page_info = reply.get("result_info")
    if (page_info is not None and
            (not isinstance(page_info, dict) or page_info.get("total_pages", 1) != 1)):
        raise Block("DNS_PAGINATION_AMBIGUOUS")
    if not isinstance(rows, list) or len(rows) > 100:
        raise Block("DNS_RECORD_SET_AMBIGUOUS")
    filtered = [r for r in rows if isinstance(r, dict) and r.get("name") == name and r.get("type") == record_type]
    if len(filtered) != len(rows):
        raise Block("DNS_RECORD_SET_DRIFT")
    if any(not isinstance(r.get("id"), str) or
           re.fullmatch(r"[a-f0-9]{32}", r["id"]) is None for r in filtered):
        raise Block("DNS_RECORD_ID_INVALID")
    by_id = {r["id"]: r for r in filtered}
    if len(by_id) != len(filtered):
        raise Block("DNS_RECORD_ID_DUPLICATE")
    return by_id


def exact_a(zone: str, token: str, name: str) -> dict:
    rows = records(zone, token, name=name, record_type="A")
    if len(rows) != 1:
        raise Block("A_RECORD_NOT_UNIQUE")
    r = next(iter(rows.values()))
    public_ipv4(r.get("content", ""))
    if r.get("proxied") is not False:
        raise Block("A_RECORD_PROXY_STATUS_DRIFT")
    return r


def exact_spf(zone: str, token: str) -> dict:
    txt = records(zone, token, name=ZONE_HOST, record_type="TXT")
    spf = [r for r in txt.values() if isinstance(r.get("content"), str)
           and r["content"].startswith("v=spf1 ")]
    if len(spf) != 1:
        raise Block("SPF_NOT_UNIQUE")
    return spf[0]


def spf_ipv4(content: str) -> str:
    pattern = r"^v=spf1 ip4:((?:[0-9]{1,3}\.){3}[0-9]{1,3}) include:_spf\.mx\.cloudflare\.net ~all$"
    match = re.fullmatch(pattern, content)
    if match is None:
        raise Block("SPF_POLICY_UNREVIEWED")
    return public_ipv4(match.group(1))


def detected_egress() -> str:
    vals = []
    for url in DETECTORS:
        raw = url_text(url, limit=80)
        try:
            vals.append(public_ipv4(raw.decode("ascii").strip()))
        except UnicodeError:
            raise Block("IP_PROBE_ENCODING_INVALID") from None
    if vals[0] != vals[1]:
        raise Block("EGRESS_IP_CONSENSUS_FAILED")
    return vals[0]


def origin_https(ip: str, *, mode: str) -> None:
    # Outbound IP consensus alone cannot establish that mail/SSH inbound
    # traffic reaches the same host. Even after the web Tunnel cutover,
    # direct_only mode MUST prove direct verified HTTPS reachability to
    # the proposed public IPv4 before editing mail or SSH records.
    # This is a conservative guard, not a guarantee of external reachability.
    if mode == "ddns":
        routes = ((ZONE_HOST, "/"), ("staging.kmjtechno.com", "/"),
                  ("cloudos.kmjtechno.com", "/info"))
    elif mode == "direct_only":
        routes = ((ZONE_HOST, "/"),)
    else:
        raise Block("ORIGIN_PROBE_MODE_UNREVIEWED")
    for host, route in routes:
        argv = ["/usr/bin/curl", "--noproxy", "*", "--proto", "=https",
                "--tlsv1.2", "--silent", "--output", "/dev/null",
                "--write-out", "%{http_code}", "--connect-timeout", "6",
                "--max-time", "15", "--resolve", f"{host}:443:{ip}",
                "https://" + host + route]
        try:
            p = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, timeout=19, check=False, env={
                                   "PATH": "/usr/bin:/bin", "HOME": "/",
                                   "LC_ALL": "C", "LANG": "C",
                               })
        except (OSError, subprocess.TimeoutExpired):
            raise Block("ORIGIN_HTTPS_PREFLIGHT_FAILED") from None
        code = p.stdout.decode("ascii", "replace")
        if p.returncode != 0 or code not in ("200", "204", "301", "302", "303", "307", "308", "401", "403"):
            raise Block("ORIGIN_HTTPS_PREFLIGHT_FAILED")


def patch_record(zone: str, token: str, row: dict, new_content: str) -> None:
    record_id = row["id"]
    if not re.fullmatch(r"[a-f0-9]{32}", record_id):
        raise Block("CF_RECORD_ID_INVALID")
    patched = cloudflare(zone, token, "/" + record_id, body={"content": new_content})
    obj = patched.get("result")
    if not isinstance(obj, dict) or obj.get("id") != record_id or obj.get("content") != new_content:
        raise Block("CF_READBACK_MISMATCH")


def reconcile(zone: str, mode: str, token: str, ip: str, *, apply: bool) -> dict:
    names = EXPECTED_HOSTS if mode == "ddns" else (MAIL_HOST, SSH_HOST)
    a = {name: exact_a(zone, token, name) for name in names}
    spf = exact_spf(zone, token)
    prior_spf_ip = spf_ipv4(spf["content"])
    current_ips = {name: public_ipv4(row["content"]) for name, row in a.items()}
    distinct_old = {v for v in current_ips.values() if v != ip}
    if len(distinct_old) > 1:
        raise Block("MIXED_OLD_A_RECORDS")
    if distinct_old and prior_spf_ip not in (ip, next(iter(distinct_old))):
        raise Block("SPF_IP_NOT_CONSISTENT_WITH_A")
    old_ip = next(iter(distinct_old), prior_spf_ip)
    if old_ip != ip and old_ip not in current_ips.values() and prior_spf_ip != old_ip:
        raise Block("UNREVIEWED_PRIOR_IP")
    changes = [name for name in names if current_ips[name] != ip]
    spf_changed = prior_spf_ip != ip
    if apply and (changes or spf_changed):
        # Fail closed if the intended web origin is not directly TLS reachable.
        # An already converged no-op never triggers incidental web probes.
        origin_https(ip, mode=mode)
        for name in changes:
            patch_record(zone, token, a[name], ip)
            checked = exact_a(zone, token, name)
            if checked["content"] != ip:
                raise Block("CF_A_CONFIRMATION_FAILED")
        if spf_changed:
            content = f"v=spf1 ip4:{ip} include:_spf.mx.cloudflare.net ~all"
            patch_record(zone, token, spf, content)
            if spf_ipv4(exact_spf(zone, token)["content"]) != ip:
                raise Block("CF_SPF_CONFIRMATION_FAILED")
    return {
        "zone": ZONE_HOST, "mode": mode, "discovered_ip": ip,
        "a_records_to_change": len(changes), "spf_change": spf_changed,
        "fully_converged": not changes and not spf_changed or apply,
    }


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    emit("SCHEMA", "KMJ_ORIGIN_IP_AUTOPILOT_V1")
    if args.inspect == args.apply:
        raise Block("MODE_REQUIRED")
    identity_guard()
    zone, mode, token = config()
    ip = detected_egress()
    result = reconcile(zone, mode, token, ip, apply=args.apply)
    emit("MODE", "APPLY" if args.apply else "INSPECT")
    emit("MANAGED_A", str(result["a_records_to_change"]))
    emit("SPF_CHANGE", "YES" if result["spf_change"] else "NO")
    emit("DNS_CONVERGED", "YES" if result["fully_converged"] else "NO")
    emit("PTR_AUTOMATED", "NO_PROVIDER_CONTROL")
    emit("SERVICE_RESTART", "NONE")
    emit("RESULT", "PASS" if result["fully_converged"] else "PLAN_ONLY")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Block, OSError, ValueError, UnicodeError, KeyError, TypeError):
        emit("RESULT", "BLOCKED_FAIL_CLOSED")
        raise SystemExit(3)
