"""Source safety tests for the owner-only, read-only staging inspector."""
import ast
import runpy
import tempfile
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/operations/kmj_main_platform_stage_readonly_preflight_20261028.py"
TEXT = SOURCE.read_text(encoding="utf-8")

class ReadonlyReleasePreflight(unittest.TestCase):
    def test_staging_vhost_canonical_symlink_and_guards(self):
        check = runpy.run_path(str(SOURCE), run_name="staging_preflight_test")[
            "safe_staging_vhost"
        ]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            allowed = root / "sites-available" / "staging.kmjtechno.com.conf"
            enabled = root / "sites-enabled" / "staging.kmjtechno.com.conf"
            allowed.parent.mkdir()
            enabled.parent.mkdir()
            allowed.write_text("server { listen 443 ssl; }", encoding="utf-8")
            # The canonical Ubuntu layout must not become a false blocker.
            enabled.symlink_to(allowed)
            self.assertTrue(check(enabled, allowed))
            # Only the precise approved sites-available target is accepted.
            impostor = root / "wrong.conf"
            impostor.write_text("server {}", encoding="utf-8")
            enabled.unlink()
            enabled.symlink_to(impostor)
            self.assertFalse(check(enabled, allowed))
            enabled.unlink()
            enabled.symlink_to(root / "missing.conf")
            self.assertFalse(check(enabled, allowed))
            enabled.unlink()
            self.assertFalse(check(enabled, allowed))
            # Plain regular staging configuration remains supported.
            enabled.write_text("server { listen 443 ssl; }", encoding="utf-8")
            self.assertTrue(check(enabled, allowed))
            # A symlink-hop under sites-available is not a safe target.
            enabled.unlink()
            allowed.unlink()
            allowed.symlink_to(impostor)
            enabled.symlink_to(allowed)
            self.assertFalse(check(enabled, allowed))

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
            '"KMJ_MAIN_PLATFORM_STAGE_PREFLIGHT_V3_20261028.json"',
            'RECEIPTS = ROOT / "work/qa"',
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
