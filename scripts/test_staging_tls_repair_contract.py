from pathlib import Path

W = Path(__file__).resolve().parents[1] / ".github/workflows/staging-tls-repair-pinned.yml"
S = Path(__file__).resolve().parents[1] / "infra/server/KMJ_STAGE_TLS_REPAIR.sh"
workflow = W.read_text(encoding="utf-8")
guard = S.read_text(encoding="utf-8")
required_workflow = (
    "infra/server/trust/kmj-elite-staging-known_hosts",
    "LOGIN_KEY_MISSING",
    "TRUSTED_HOSTS_FILE_INVALID",
    "SSH_HOST: '103.212.136.154'",
    "StrictHostKeyChecking=yes",
    "UserKnownHostsFile=",
    "HOST_KEY_NOT_PINNED",
    "SCRIPT_SHA_MISMATCH",
    "sha256sum infra/server/KMJ_STAGE_TLS_REPAIR.sh",
    "/root/KMJ_STAGE_TLS_REPAIR.sh",
    "readlink -f /home/kmjprod/current",
    "PRODUCTION_RELEASE_POINTER_CHANGED",
    "staging.kmjtechno.com/",
    "PRODUCTION_DEPLOYMENT=NOT_ATTEMPTED",
    "environment: staging",
)
required_guard = (
    '[[ "$DOMAIN" == "staging.kmjtechno.com" ]]',
    '[[ "$DOMAIN" != "$PRODUCTION_DOMAIN" ]]',
    "clpctl lets-encrypt:install:certificate",
    "systemctl reload nginx",
)
for s in required_workflow:
    assert s in workflow, f"missing required staging repair protection: {s}"
for s in required_guard:
    assert s in guard, f"existing staging guard missing: {s}"
HOST_KEY_FILE = Path(__file__).resolve().parents[1] / "infra/server/trust/kmj-elite-staging-known_hosts"
EXPECTED_HOST_KEY = "103.212.136.154 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINZMT7YHsS5qRX/ciXTbLxKZVCgpJS7m/L9Nwgr3RNZS"
assert HOST_KEY_FILE.read_text(encoding="utf-8").strip() == EXPECTED_HOST_KEY, "reviewed host key drift"
assert "STAGING_SSH_KNOWN_HOSTS" not in workflow, "source-pinned host key should not need GitHub secret"
assert "StrictHostKeyChecking=no" not in workflow
assert "curl -k" not in workflow
assert "ssl-no-revoke" not in workflow
assert "sudo -n bash \"$f\"" in workflow
assert "kmj-stage-deploy" not in workflow
print("Guarded staging-only TLS repair contract PASS")
