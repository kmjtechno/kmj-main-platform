#!/usr/bin/env python3
"""Root-only, secret-free CodeBridge upstream diagnostic. Read-only."""
from pathlib import Path
from urllib.parse import urlsplit
import ipaddress
import os
import re
import socket
import subprocess
import sys

LIVE = Path("/home/kmjprod/current")
EXPECTED = "/home/kmjprod/releases/platform-8070dad72c55"
ENV = LIVE / "apps/platform/.env"
SERVICE = "kmj-codebridge-gateway-stage.service"

def emit(k, v): print(f"{k}={v}", flush=True)
def fail(v): emit("KMJ_GATEWAY_READONLY_DIAG", f"BLOCKED_{v}"); raise SystemExit(2)
def cmd(*a):
    p=subprocess.run(list(a), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                     text=True, timeout=8, check=False)
    return p.returncode, p.stdout.strip()
def value(name, lines):
    pairs=[]
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"): continue
        match=re.fullmatch(r"\s*"+re.escape(name)+r"\s*=\s*(.*?)\s*",line)
        if match:
            result=match.group(1)
            if len(result)>=2 and result[0] in "\"'" and result[0]==result[-1]:
                result=result[1:-1]
            pairs.append(result)
    return pairs[0] if len(pairs)==1 else None

if os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":
    fail("ROOT_ELITE_REQUIRED")
if not LIVE.is_symlink() or str(LIVE.resolve())!=EXPECTED:
    fail("LIVE_RELEASE_DRIFT")
if ENV.is_symlink() or not ENV.is_file() or ENV.stat().st_mode & 0o007:
    fail("ENV_NOT_SECURE")
lines=ENV.read_text(encoding="utf-8").splitlines()
origin=value("CODEBRIDGE_AGENT_PUBLIC_URL",lines)
upstream=value("CODEBRIDGE_GATEWAY_URL",lines)
emit("PUBLIC_AGENT_ORIGIN", "PINNED" if origin=="https://kmjtechno.com" else "MISSING" if not origin else "PRESENT_BUT_NOT_PINNED")
emit("LARAVEL_CONFIG_CACHED", "YES" if (LIVE/"apps/platform/bootstrap/cache/config.php").exists() else "NO")
port=None
host=None
if upstream:
    try:
        url=urlsplit(upstream)
        host=url.hostname
        port=url.port
        is_loopback=(host=="localhost") or ipaddress.ip_address(host).is_loopback
        if url.scheme not in ("http","https") or not is_loopback or port is None or port<=1023 or port>65535 or url.username or url.password or url.query or url.fragment or url.path not in ("","/"):
            port=None
    except (AttributeError, ValueError):
        port=None
emit("APPLICATION_PRIVATE_GATEWAY", "VALID_LOOPBACK_URL" if port else "MISSING_OR_INVALID")
rc,active=cmd("systemctl","is-active",SERVICE)
emit("GATEWAY_SERVICE", "ACTIVE" if rc==0 and active=="active" else "NOT_ACTIVE")
rc,pidraw=cmd("systemctl","show",SERVICE,"--property=MainPID","--value")
pid=int(pidraw) if rc==0 and pidraw.isdigit() else 0
emit("GATEWAY_PID_PRESENT", "YES" if pid>0 else "NO")
rc,ss=cmd("ss","-H","-ltnp")
if rc!=0:fail("SS_UNAVAILABLE")
ports=set()
nonsafe=False
if pid:
    for line in ss.splitlines():
        if f"pid={pid}," not in line: continue
        cols=line.split()
        if len(cols)<5:continue
        local=cols[3]
        m=re.search(r":(\d+)$",local)
        if not m:continue
        p=int(m.group(1))
        if local.startswith(("127.","[::1]:","::1:")):ports.add(p)
        else:nonsafe=True
emit("GATEWAY_LOOPBACK_LISTENER_COUNT",str(len(ports)))
emit("GATEWAY_NON_LOOPBACK_LISTENER", "DETECTED_REVIEW_REQUIRED" if nonsafe else "NOT_DETECTED")
emit("APP_PORT_MATCHES_GATEWAY_PROCESS","YES" if port is not None and port in ports else "NO")
if port and host:
    try:
        with socket.create_connection((host,port),timeout=1):tcp=True
    except OSError:tcp=False
    emit("APP_CONFIGURED_LOOPBACK_TCP","PASS" if tcp else "NOT_REACHABLE")
else:emit("APP_CONFIGURED_LOOPBACK_TCP","NOT_CONFIGURED")
if port and port not in ports:
    emit("GATEWAY_DIAGNOSIS","CONFIGURED_PORT_NOT_OWNED_BY_GATEWAY")
elif port and origin!="https://kmjtechno.com":
    emit("GATEWAY_DIAGNOSIS","PUBLIC_AGENT_ORIGIN_REQUIRES_REVIEW")
elif port and port in ports:
    emit("GATEWAY_DIAGNOSIS","PORT_MATCH_FOUND_RECHECK_LARAVEL_CACHED_CONFIG")
else:
    emit("GATEWAY_DIAGNOSIS","INCOMPLETE_CONFIGURATION")
emit("ENV_VALUES_OR_SECRETS_OUTPUT","NONE")
emit("SYSTEM_CHANGES","NONE")
