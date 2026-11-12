#!/usr/bin/env python3
"""Read-only KMJ-elite Cloudflare Tunnel canary diagnostic.

No tokens are opened, no raw journal lines are printed, and no service/DNS
settings are changed. Only exact allowlisted public names and localhost:443.
"""
from __future__ import annotations

import os
import re
import socket
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

PUBKEY = "AAAAC3NzaC1lZDI1NTE5AAAAINZMT7YHsS5qRX/ciXTbLxKZVCgpJS7m/L9Nwgr3RNZS"
UNIT = "kmj-cloudflared-tunnel.service"
FIXED = (
    ("ORIGIN_MAIN", "kmjtechno.com", "/", True),
    ("ORIGIN_WWW", "www.kmjtechno.com", "/", True),
    ("ORIGIN_STAGE", "staging.kmjtechno.com", "/", True),
    ("ORIGIN_CLOUDOS", "cloudos.kmjtechno.com", "/info", True),
    ("TUNNEL_CANARY", "tunnel-canary.kmjtechno.com", "/", False),
)
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/",
       "LC_ALL": "C", "LANG": "C"}


def say(key: str, value: str) -> None:
    if (re.fullmatch(r"[A-Z][A-Z0-9_]{1,64}", key) is None or
            re.fullmatch(r"[A-Z0-9_.-]{1,80}", value) is None):
        raise RuntimeError("REPORT_NOT_SAFE")
    print(f"{key}={value}", flush=True)


def command(argv: list[str], timeout: int = 20) -> tuple[int, bytes]:
    try:
        p = subprocess.run(argv, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           cwd="/", env=ENV, check=False, timeout=timeout)
        return p.returncode, p.stdout[:65_537]
    except (OSError, subprocess.TimeoutExpired):
        return 125, b""


def classify_http(rc: int, output: bytes) -> str:
    if rc not in range(0, 126) or len(output) > 256:
        return "UNAVAILABLE"
    try:
        code, sslcode = output.decode("ascii").strip().split("|")
    except (UnicodeError, ValueError):
        return "UNAVAILABLE"
    if not re.fullmatch(r"[0-9]{3}", code) or not re.fullmatch(r"[0-9]{1,5}", sslcode):
        return "UNAVAILABLE"
    if rc == 6:
        return "DNS_RESOLUTION_FAILED"
    if rc == 7:
        return "TCP_CONNECTION_FAILED"
    if rc == 28:
        return "TIMEOUT"
    if rc in (35, 51, 58, 59, 60):
        return "TLS_CERTIFICATE_OR_HANDSHAKE_FAILED"
    if rc != 0:
        return "CURL_ERROR_" + str(rc)
    if sslcode != "0":
        return "TLS_CERTIFICATE_VALIDATION_FAILED"
    if code == "200":
        return "HTTP_200_PASS"
    if code in ("301", "302", "303", "307", "308"):
        return "HTTP_REDIRECT_" + code
    return "HTTP_" + code


def curl_https(host: str, route: str, local: bool, *, health_ua: bool = False) -> str:
    argv = ["/usr/bin/curl", "--noproxy", "*", "--silent",
            "--proto", "=https", "--connect-timeout", "5",
            "--max-time", "14", "--output", "/dev/null",
            "--write-out", "%{http_code}|%{ssl_verify_result}"]
    if health_ua:
        # The zone's existing Smart WAF challenges default curl User-Agent.
        # Compare both UAs without changing WAF policy or disabling TLS.
        argv += ["--user-agent", "KMJ-Origin-Health/1.0"]
    if local:
        argv += ["--resolve", f"{host}:443:127.0.0.1"]
    argv.append(f"https://{host}{route}")
    rc, out = command(argv, timeout=17)
    return classify_http(rc, out)


def classify_edge_probe(rc: int, output: bytes, headers: bytes) -> str:
    base = classify_http(rc, output)
    if base != "HTTP_200_PASS":
        return base
    if not isinstance(headers, bytes) or len(headers) > 16_384:
        return "EDGE_HEADERS_UNAVAILABLE"
    # A successful origin-direct request is NOT evidence of Cloudflare
    # Tunnel routing. Require Cloudflare edge headers for the exact public URL.
    ray = re.search(rb"(?im)^cf-ray:[ \t]*[A-Za-z0-9-]{6,100}[ \t]*\r?$", headers)
    server = re.search(rb"(?im)^server:[ \t]*cloudflare[ \t]*\r?$", headers)
    return "HTTP_200_EDGE_PASS" if ray and server else "EDGE_NOT_ATTESTED"


PUBLIC_EDGE_TARGETS = (
    ("STAGING_PUBLIC_EDGE", "staging.kmjtechno.com", "/"),
    ("CLOUDOS_PUBLIC_EDGE", "cloudos.kmjtechno.com", "/info"),
    ("WWW_PUBLIC_EDGE", "www.kmjtechno.com", "/"),
    ("MAIN_PUBLIC_EDGE", "kmjtechno.com", "/"),
)


def public_edge_https(host: str, route: str) -> str:
    if (host, route) not in {(name, path) for _, name, path in PUBLIC_EDGE_TARGETS}:
        raise RuntimeError("PUBLIC_EDGE_TARGET_UNREVIEWED")
    with tempfile.NamedTemporaryFile(
            mode="w+b", prefix="kmj-tunnel-edge-", dir="/run",
            delete=True) as file:
        argv = ["/usr/bin/curl", "--noproxy", "*", "--silent",
                "--proto", "=https", "--connect-timeout", "5",
                "--max-time", "14", "--user-agent",
                "KMJ-Origin-Health/1.0", "--output", "/dev/null",
                "--dump-header", file.name,
                "--write-out", "%{http_code}|%{ssl_verify_result}",
                "https://" + host + route]
        rc, output = command(argv, timeout=17)
        file.seek(0)
        headers = file.read(16_385)
        return classify_edge_probe(rc, output, headers)


def journal_class(raw: bytes) -> str:
    if not isinstance(raw, bytes) or len(raw) > 65_536:
        return "UNAVAILABLE"
    text = raw.decode("utf-8", "replace").lower()
    # Never return source text or arbitrary path/IP/token; only a fixed class.
    if "x509:" in text or "certificate signed by unknown authority" in text:
        return "ORIGIN_TLS_CERTIFICATE_ERROR"
    if "certificate is valid for" in text or "tls: handshake failure" in text:
        return "ORIGIN_TLS_HANDSHAKE_ERROR"
    if "connection refused" in text or "connect: connection refused" in text:
        return "ORIGIN_TCP_REFUSED"
    if "no route to host" in text or "network is unreachable" in text:
        return "ORIGIN_NETWORK_UNREACHABLE"
    if "malformed http response" in text:
        return "ORIGIN_PROTOCOL_MISMATCH"
    if "authentication failed" in text or "invalid tunnel secret" in text:
        return "TUNNEL_AUTHENTICATION_ERROR"
    if "unable to reach the origin service" in text:
        return "ORIGIN_UNREACHABLE"
    if "error" in text:
        return "OTHER_REDACTED_JOURNAL_ERROR"
    return "NO_RECOGNIZED_ERROR"


def identity() -> None:
    if os.geteuid() != 0 or socket.gethostname().split(".")[0].lower() != "kmj-elite":
        raise RuntimeError("WRONG_MACHINE_OR_USER")
    p = Path("/etc/ssh/ssh_host_ed25519_key.pub")
    if p.is_symlink():
        raise RuntimeError("UNTRUSTED_PUBLIC_KEY_PATH")
    st = p.stat()
    if st.st_uid != 0 or not stat.S_ISREG(st.st_mode):
        raise RuntimeError("UNTRUSTED_PUBLIC_KEY")
    k = p.read_text("ascii").split()
    if len(k) < 2 or k[0] != "ssh-ed25519" or k[1] != PUBKEY:
        raise RuntimeError("HOST_IDENTITY_DRIFT")


def self_test() -> None:
    tests = [
        (0, b"200|0", "HTTP_200_PASS"),
        (0, b"301|0", "HTTP_REDIRECT_301"),
        (0, b"502|0", "HTTP_502"),
        (0, b"403|0", "HTTP_403"),
        (6, b"000|0", "DNS_RESOLUTION_FAILED"),
        (7, b"000|0", "TCP_CONNECTION_FAILED"),
        (28, b"000|0", "TIMEOUT"),
        (60, b"000|20", "TLS_CERTIFICATE_OR_HANDSHAKE_FAILED"),
    ]
    for rc, value, expected in tests:
        if classify_http(rc, value) != expected:
            raise RuntimeError("TEST_HTTP_CLASSIFIER_FAILED")
    tests2 = [
        (b"tls: failed to verify certificate: x509: unknown authority",
         "ORIGIN_TLS_CERTIFICATE_ERROR"),
        (b"dial tcp 127.0.0.1:443: connect: connection refused",
         "ORIGIN_TCP_REFUSED"),
        (b"net/http: HTTP/1.x transport connection broken: malformed HTTP response",
         "ORIGIN_PROTOCOL_MISMATCH"),
        (b"no recognized journal problem", "NO_RECOGNIZED_ERROR"),
    ]
    for value, expected in tests2:
        if journal_class(value) != expected:
            raise RuntimeError("TEST_JOURNAL_CLASSIFIER_FAILED")
    edge_headers = b"HTTP/2 200\r\nserver: cloudflare\r\ncf-ray: a593b319f9373f85-BOM\r\n"
    edge_checks = [
        (0, b"200|0", edge_headers, "HTTP_200_EDGE_PASS"),
        (0, b"200|0", b"HTTP/1.1 200 OK\r\n", "EDGE_NOT_ATTESTED"),
        (0, b"403|0", edge_headers, "HTTP_403"),
        (60, b"000|20", edge_headers, "TLS_CERTIFICATE_OR_HANDSHAKE_FAILED"),
        (0, b"200|0", b"x" * 16_385, "EDGE_HEADERS_UNAVAILABLE"),
    ]
    for rc, result, headers, expected in edge_checks:
        if classify_edge_probe(rc, result, headers) != expected:
            raise RuntimeError("TEST_EDGE_CLASSIFIER_FAILED")
    for key, hostname, route in PUBLIC_EDGE_TARGETS:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{3,30}", key):
            raise RuntimeError("TEST_EDGE_KEY_UNSAFE")
        if hostname not in ("staging.kmjtechno.com", "cloudos.kmjtechno.com",
                            "www.kmjtechno.com", "kmjtechno.com"):
            raise RuntimeError("TEST_EDGE_HOST_UNREVIEWED")
        if route not in ("/", "/info"):
            raise RuntimeError("TEST_EDGE_ROUTE_UNREVIEWED")
    say("OFFLINE_CLASSIFIER_TESTS", "21_PASS")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("--self-test", "--inspect"):
        raise RuntimeError("MODE_INVALID")
    say("SCHEMA", "KMJ_TUNNEL_CANARY_SAFE_DIAG_V1")
    self_test()
    if sys.argv[1] == "--self-test":
        say("RESULT", "SELF_TEST_PASS")
        return
    identity()
    say("KMJ_ELITE_IDENTITY", "PASS")
    for service, unit in (("CLOUDFLARED", UNIT), ("NGINX", "nginx.service"),
                          ("DNS_AGENT_TIMER", "kmj-ip-autopilot.timer")):
        rc, value = command(["/usr/bin/systemctl", "is-active", unit], timeout=9)
        if rc == 0 and value.strip() == b"active":
            say(service + "_SERVICE", "ACTIVE")
        else:
            say(service + "_SERVICE", "NOT_ACTIVE_OR_UNAVAILABLE")
    for key, host, route, local in FIXED:
        say(key, curl_https(host, route, local))
        if key == "TUNNEL_CANARY":
            say("TUNNEL_CANARY_HEALTH_UA", curl_https(host, route, local, health_ua=True))
    for key, host, route in PUBLIC_EDGE_TARGETS:
        say(key, public_edge_https(host, route))
    rc, value = command(["/usr/bin/journalctl", "--no-pager",
                         "--output=cat", "--unit=" + UNIT,
                         "--lines=120"], timeout=12)
    say("CLOUDFLARED_JOURNAL_CLASS",
        journal_class(value) if rc == 0 else "UNAVAILABLE")
    say("PRODUCTION_DNS_MUTATION", "NONE")
    say("SERVICE_MUTATION", "NONE")
    say("RESULT", "READ_ONLY_DIAGNOSTIC_COMPLETE")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, UnicodeError):
        say("RESULT", "BLOCKED_FAIL_CLOSED")
        raise SystemExit(3)
