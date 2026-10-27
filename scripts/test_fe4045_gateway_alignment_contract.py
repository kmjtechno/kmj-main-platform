"""Offline safety tests for Main Platform CodeBridge gateway alignment tool.

No operator commands, live .env reading, gateway probes or mutations in CI.
"""
from pathlib import Path
import ast
import subprocess
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/operations/inspect-or-guard-fix-fe4045-main-platform-gateway-20261027.py"
CODE = SOURCE.read_text(encoding="utf-8")

class GatewayDoctorSafety(unittest.TestCase):
    def test_python_parse_and_help(self):
        ast.parse(CODE)
        p=subprocess.run(["python3","-B",str(SOURCE),"--help"],capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,0)
        self.assertIn("--apply",p.stdout)
        self.assertIn("--expect-port",p.stdout)

    def test_readonly_default_and_explicit_port_approval(self):
        for marker in ("default=False","if not args.apply:",
                       'status("SYSTEM_CHANGES", "NONE")',
                       '"KMJ_APPROVE_CONFIG_ONLY"', "args.expect_port != port",
                       "PRODUCTION_RELEASE_BUSY","fcntl.flock",
                       "EXPLICIT_CONFIG_ONLY_PORT_APPROVAL_REQUIRED"):
            self.assertIn(marker,CODE)

    def test_pin_current_live_config_and_service_listener(self):
        for marker in ("platform-8070dad72c55",
                       "kmj-codebridge-gateway-stage.service",
                       "CODEBRIDGE_GATEWAY_URL", "CODEBRIDGE_AGENT_PUBLIC_URL",
                       "LARAVEL_UPSTREAM_KEYS_NOT_PRESENT",
                       "AMBIGUOUS_OR_EXPOSED_GATEWAY_LISTENER",
                       "GATEWAY_LOOPBACK_TCP_NOT_REACHABLE",
                       "LIVE_OR_ENV_DRIFT", "ENV_CHANGED_CONCURRENTLY",
                       "tls_public()", "APP_CONFIGURED_LOOPBACK_PORT",
                       "ACTUAL_GATEWAY_LOOPBACK_PORT"):
            self.assertIn(marker,CODE)

    def test_two_keys_only_and_safe_backup(self):
        for token in ("mkstemp(prefix=\".kmj-gateway-env-backup-\"",
                      "os.fchmod(fd, 0o600)",
                      "os.fchown(f.fileno(), original_stat.st_uid, original_stat.st_gid)",
                      "os.replace(tmp, ENV)",
                      "ENV_BACKUP_ROOT_ONLY",
                      "ONLY_CODEBRIDGE_GATEWAY_AND_PUBLIC_AGENT_ORIGIN",
                      "GATEWAY_SERVICE_RESTARTED",
                      "PRODUCTION_APPROVAL"):
            self.assertIn(token,CODE)
        self.assertIn("PUBLIC_AGENT_PAIRING",CODE)
        self.assertIn("NOT_VERIFIED",CODE)

    def test_no_service_restart_or_deployment(self):
        for forbidden in ("systemctl\", \"restart", "systemctl restart",
                          "systemctl reload", "nginx -s reload",
                          "git reset --hard", "ln -sfn",
                          "/etc/kmj-codebridge/main-platform-production-release.json",
                          "artisan migrate", "fchmod(fd, 0o644)", "print(lines)",
                          "print(upstream)", "print(origin)"):
            self.assertNotIn(forbidden,CODE)

if __name__=="__main__":
    unittest.main()
