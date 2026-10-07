#!/usr/bin/python3
from pathlib import Path
import subprocess

EXPORTER = "/usr/local/sbin/kmj-codebridge-status-export"
STATUS = Path("/var/lib/kmj-codebridge-status-export/status.json")
DEST = "info@34.63.5.14"
KEY = "/etc/kmj-codebridge-status/id_ed25519"
KNOWN_HOSTS = "/etc/kmj-codebridge-status/known_hosts"

export = subprocess.run([EXPORTER], capture_output=True, timeout=30)
if not STATUS.is_file() or STATUS.is_symlink() or STATUS.stat().st_size > 65536:
    raise SystemExit("sanitized status unavailable")
raw = STATUS.read_bytes()
completed = subprocess.run(
    [
        "/usr/bin/ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
        "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", "UserKnownHostsFile=" + KNOWN_HOSTS, "-i", KEY, DEST,
    ],
    input=raw,
    capture_output=True,
    timeout=15,
)
if completed.returncode:
    raise SystemExit("status push failed")
if export.returncode:
    raise SystemExit("CodeBridge readiness failed; error status pushed")
