"""Source safety tests for the owner-only, read-only staging inspector."""
import ast
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/operations/kmj_main_platform_stage_readonly_preflight_20261028.py"
TEXT = SOURCE.read_text(encoding="utf-8")

class ReadonlyReleasePreflight(unittest.TestCase):
    def test_source_is_valid_python(self):
        ast.parse(TEXT)

    def test_profile_is_fixed_and_fails_closed(self):
        for marker in (
            "EXPECTED_SHA = \"ad4cfa68291ec6a05e88f30ed0a93b2d15af40fe\"",
            'HOST = "staging.kmjtechno.com"',
            '"hostname_guard"',
            '"root_guard"',
            '"nginx_config_valid"',
            '"staging_tls_valid"',
            '"staging_exact_sha"',
            '"customer_storage_present"',
            '"approval_issued":False',
            '"production_mutated":False',
            '"RECEIPT_ALREADY_EXISTS"',
            'os.link(temp,dest)',
        ):
            self.assertIn(marker, TEXT)

    def test_executable_scope_has_no_mutation_or_approval(self):
        for forbidden in (
            "shell=True", "subprocess.Popen", "os.system(",
            "migrate:fresh", "artisan migrate",
            "systemctl restart", "systemctl reload",
            "certbot --nginx", "ln -sfn", "rm -rf",
            "/etc/kmj-codebridge/main-platform-production-release.json",
            "curl -k", "--insecure", "git reset --hard",
        ):
            self.assertNotIn(forbidden, TEXT)

    def test_no_root_on_ci_runner_rejected_before_receipt(self):
        process = subprocess.run(
            ["python3", "-B", str(SOURCE)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(process.returncode, 2)
        self.assertIn("BLOCKED_WRONG_OPERATOR_OR_HOST", process.stdout)
        self.assertNotIn("SECRET", process.stdout)

if __name__ == "__main__":
    unittest.main()
