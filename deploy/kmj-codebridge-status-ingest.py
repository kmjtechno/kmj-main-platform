#!/usr/bin/python3
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

DEST = Path("/home/info/.local/state/kmj-autonomy/codebridge-status.json")
EXPECTED = {
    "schema_version", "repository", "device", "project", "branch",
    "connection", "version", "writable", "authorized", "effective_permissions",
    "gates", "gate_readiness", "checkout_sha", "observed_utc_epoch", "source",
}

raw = sys.stdin.buffer.read(65537)
if not raw or len(raw) > 65536:
    raise SystemExit(2)
try:
    data = json.loads(raw)
except Exception:
    raise SystemExit(2)
if not isinstance(data, dict) or set(data) != EXPECTED:
    raise SystemExit(2)
if data["schema_version"] != 1 or data["repository"] != "kmjtechno/kmj-main-platform":
    raise SystemExit(2)
if (data["device"], data["project"], data["branch"]) != (
    "main-platform-kmjtechnonetgmailcom", "kmj-main-platform", "main"
):
    raise SystemExit(2)
if (data["connection"] not in {"connected", "error"}
        or type(data["writable"]) is not bool or type(data["authorized"]) is not bool):
    raise SystemExit(2)
if (not isinstance(data["effective_permissions"], list)
        or len(data["effective_permissions"]) > 8
        or any(permission not in {"read", "write", "execute"}
               for permission in data["effective_permissions"])):
    raise SystemExit(2)
if not isinstance(data["gate_readiness"], dict) or set(data["gate_readiness"]) != {"fast", "platform", "full"}:
    raise SystemExit(2)
if any(value not in {"satisfied", "blocked", "not_configured"} for value in data["gate_readiness"].values()):
    raise SystemExit(2)
if not isinstance(data["version"], str) or not re.fullmatch(r"[0-9A-Za-z.+_-]{1,32}", data["version"]):
    raise SystemExit(2)
if (not isinstance(data["gates"], list) or len(data["gates"]) > 16
        or any(not isinstance(gate, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", gate)
               for gate in data["gates"])):
    raise SystemExit(2)
if not isinstance(data["checkout_sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", data["checkout_sha"]):
    raise SystemExit(2)
if data["source"] != "main-vps-restricted-exporter":
    raise SystemExit(2)
now = time.time()
observed = data["observed_utc_epoch"]
if not isinstance(observed, (int, float)) or abs(now - observed) > 180:
    raise SystemExit(2)

DEST.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
fd, temporary = tempfile.mkstemp(prefix=".codebridge-", dir=DEST.parent)
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(data, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, DEST)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
