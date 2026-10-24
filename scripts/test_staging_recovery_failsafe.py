"""Regression gates for safe staging deploy recovery."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
recovery = (ROOT / ".github/workflows/staging-deploy-recovery.yml").read_text(encoding="utf-8")
pinned = (ROOT / ".github/workflows/staging-tls-repair-execute.yml").read_text(encoding="utf-8")

assert "pull_request:" not in recovery
assert "github.event.workflow_run.run_attempt < 3" in recovery
assert "if: ${{ steps.classify.outputs.tls_repair == 'true' }}" in recovery
assert "if: ${{ steps.classify.outputs.tls_repair == 'false' }}" in recovery
assert "STAGING_CERT_RECOVERY=BLOCKED AWAIT_PINNED_OPERATOR_REPAIR" in recovery
assert "STAGING_RETRY=SKIPPED TERMINAL_TLS_ERROR" in recovery
assert "ssh-keyscan -" not in recovery
assert "StrictHostKeyChecking=no" not in recovery
assert "ssh -o " not in recovery
assert "sudo -n /root/KMJ_STAGE_TLS_REPAIR.sh" not in recovery
assert "environment: staging" in recovery
assert "environment: staging" in pinned
assert "StrictHostKeyChecking=yes" in pinned
assert "UserKnownHostsFile=" in pinned
assert "SCRIPT_SHA_MISMATCH" in pinned

m = re.search(r"if grep -Eiq '([^']+)' \"\$text\"; then", recovery)
assert m, "bounded terminal TLS classifier absent"
pattern = m.group(1)
assert len(pattern) < 500
examples = {
    "Staging TLS hostname mismatch: Certificate does not cover staging.kmjtechno.com": True,
    "curl: (60) SSL: no alternative certificate subject name matches target host name 'staging.kmjtechno.com'": True,
    "TLS validation failed; fix the staging certificate/vhost before deployment": True,
    "staging test: no route to host": False,
    "UI acceptance unrelated to staging TLS": False,
    "transient connection reset": False,
}
for log, expected in examples.items():
    got = subprocess.run(["grep", "-Eiq", pattern], input=log, capture_output=True, text=True, check=False).returncode == 0
    assert got is expected, f"TLS classifier mismatch: {log!r}: expected {expected}, got {got}"
print("STAGING_RECOVERY_TERMINAL_TLS_CONTRACT=PASS")
