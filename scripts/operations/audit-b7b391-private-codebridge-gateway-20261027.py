#!/usr/bin/env python3
"""Read-only release origin and private CodeBridge listener preflight. No credentials printed."""
import ipaddress
import os
from pathlib import Path
import re
import socket
import sys
from urllib.parse import urlsplit

CANDIDATE_SHA="b7b39174f5fdf47dd25890ece85c54eef29b4a96"
LIVE_EXPECTED="/home/kmjprod/releases/platform-8070dad72c55"
ENV=Path("/home/kmjprod/current/apps/platform/.env")
CANDIDATE=Path("/home/kmjprod/releases/platform-"+CANDIDATE_SHA[:12])
def mark(key,state): print(key+"="+state,flush=True)
def fail(code):
    mark("KMJ_CODEBRIDGE_PREFLIGHT","BLOCKED_"+code)
    sys.exit(2)
if os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":
    fail("WRONG_HOST_OR_OPERATOR")
live=Path("/home/kmjprod/current")
if not live.is_symlink() or str(live.resolve())!=LIVE_EXPECTED:
    fail("PRODUCTION_RELEASE_DRIFT")
if ENV.is_symlink() or not ENV.is_file() or ENV.stat().st_mode & 0o007:
    fail("LIVE_ENV_INSECURE_OR_MISSING")
if not CANDIDATE.is_dir() or CANDIDATE.is_symlink():
    fail("CANDIDATE_NOT_STAGED")
if (CANDIDATE/"apps/platform/.env").exists():
    fail("CANDIDATE_ENV_SHOULD_BE_ABSENT")
lines=ENV.read_text("utf-8").splitlines()
def get(key):
    entries=[]
    for line in lines:
        if re.match(r"^\s*#",line): continue
        match=re.fullmatch(r"\s*"+re.escape(key)+r"\s*=\s*(.*?)\s*",line)
        if match:
            value=match.group(1)
            if len(value)>=2 and value[0]==value[-1] and value[0] in "\"'":
                value=value[1:-1]
            entries.append(value)
    if len(entries)!=1: return None
    return entries[0]
origin=get("CODEBRIDGE_AGENT_PUBLIC_URL")
if origin=="https://kmjtechno.com":
    mark("PUBLIC_AGENT_ORIGIN","PASS")
else:
    mark("PUBLIC_AGENT_ORIGIN","BLOCKED_NOT_PINNED")
gateway=get("CODEBRIDGE_GATEWAY_URL")
if not gateway:
    mark("PRIVATE_GATEWAY_ENV","BLOCKED_MISSING_OR_EMPTY")
    fail("PRIVATE_GATEWAY_NOT_CONFIGURED")
try:
    url=urlsplit(gateway)
    valid_userinfo=url.username is None and url.password is None
    host=url.hostname or ""
    port=url.port
    if url.scheme not in ("http","https") or not port or not valid_userinfo or url.path not in ("","/") or url.query or url.fragment:
        fail("PRIVATE_GATEWAY_INVALID_URL")
    if host!="localhost":
        if not ipaddress.ip_address(host).is_loopback:
            fail("PRIVATE_GATEWAY_NOT_LOOPBACK")
    if not (1024<=port<=65535):
        fail("PRIVATE_GATEWAY_INVALID_PORT")
except (ValueError,AttributeError):
    fail("PRIVATE_GATEWAY_INVALID_URL")
mark("PRIVATE_GATEWAY_ENV","PASS_LOOPBACK_ONLY")
try:
    with socket.create_connection((host,port),timeout=3):
        pass
except (TimeoutError,OSError):
    mark("PRIVATE_GATEWAY_TCP","BLOCKED_NOT_REACHABLE")
    fail("LOOPBACK_LISTENER")
mark("PRIVATE_GATEWAY_TCP","PASS")
mark("PRIVATE_GATEWAY_SECRET_OUTPUT","NONE")
mark("PRODUCTION_CONFIGURATION_CHANGED","NO")
mark("KMJ_CODEBRIDGE_PREFLIGHT","PASS" if origin=="https://kmjtechno.com" else "BLOCKED_PUBLIC_ORIGIN")
if origin!="https://kmjtechno.com":sys.exit(2)
