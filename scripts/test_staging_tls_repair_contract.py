from pathlib import Path

W = Path(__file__).resolve().parents[1] / ".github/workflows/staging-tls-repair-pinned.yml"
EXECUTION = Path(__file__).resolve().parents[1] / ".github/workflows/staging-tls-repair-execute.yml"
S = Path(__file__).resolve().parents[1] / "infra/server/KMJ_STAGE_TLS_REPAIR.sh"
pr_workflow = W.read_text(encoding="utf-8")
workflow = EXECUTION.read_text(encoding="utf-8")
guard = S.read_text(encoding="utf-8")
required_workflow = (
    "infra/server/trust/kmj-elite-staging-known_hosts",
    "LOGIN_KEY_MISSING",
    "TRUSTED_HOSTS_FILE_INVALID",
    "SSH_HOST: '103.212.136.154'",
    "Fail closed if public staging DNS no longer targets reviewed VPS",
    "STAGING_TLS_REPAIR=BLOCKED DNS_CHANGED_OR_AMBIGUOUS",
    "STAGING_DNS_PIN=PASS",
    '[[ "${#resolved[@]}" -eq 1 && "${resolved[0]}" == "$expected_ipv4" ]]',
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
assert "pull_request:" in pr_workflow, "PR contract workflow required"
assert "staging-tls-repair-execute.yml" in pr_workflow, "PR must test execution source"
assert "repair:" not in pr_workflow, "staging mutation must never execute on PR"
assert "pull_request:" not in workflow, "repair workflow cannot be invoked by PR"
assert "environment: staging" in workflow, "protected staging environment required"
assert "branches: [main]" in workflow, "TLS repair requires protected main push"
assert "workflow_dispatch:" in workflow, "manual authorized recovery must remain available"
assert "STAGING_SSH_KNOWN_HOSTS" not in workflow, "source-pinned host key should not need GitHub secret"
assert "StrictHostKeyChecking=no" not in workflow
assert "curl -k" not in workflow
assert "ssl-no-revoke" not in workflow
assert "sudo -n bash \"$f\"" in workflow
assert "kmj-stage-deploy" not in workflow
assert 'CERTBOT_UNAVAILABLE' in guard, "certbot dependency must fail closed"
assert 'DEDICATED_STAGING_VHOST_MISSING' in guard, "Nginx staging vhost must be verified"
assert 'CERTBOT_NGINX_PLUGIN_MISSING' in guard, "certbot-nginx plugin must be verified"
assert 'certbot --nginx --non-interactive --agree-tos --no-redirect -d "$DOMAIN"' in guard
assert 'nginx -t' in guard, "Nginx syntax must be verified before reload"
assert 'production_before="$(readlink -f /home/kmjprod/current)"' in guard
assert 'STAGING_TLS_REPAIR=FAIL PRODUCTION_RELEASE_POINTER_CHANGED' in guard
assert 'if command -v clpctl >/dev/null 2>&1; then' in guard, "CloudPanel must remain supported"
assert 'server_name[[:space:]]+staging' in guard, "Require exact stage hostname"
assert 'certbot --nginx' in guard and 'certbot --apache' not in guard
assert 'curl -k' not in guard and '--insecure' not in guard
print("Guarded staging-only TLS repair contract PASS")
