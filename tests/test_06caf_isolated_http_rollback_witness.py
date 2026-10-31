"""Release rollback witness contract: no real production switch or service changes."""
import ast
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/operations/verify-06caf-isolated-http-rollback-20261027.py"


class IsolatedRealHTTPRollbackWitness(unittest.TestCase):
    def test_syntax(self):
        ast.parse(SCRIPT.read_text())

    def test_no_args_and_privilege_required(self):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT)],
                                capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 2)
        self.assertIn("ROOT_ON_KMJ_ELITE_REQUIRED", result.stdout)

    def test_pins_original_test_and_target(self):
        source = SCRIPT.read_text()
        for required in (
            "625ffeaaab20af612b2693bf0d43e3f7e4922c14",
            "0c5c97cb2c0eb66e059dc5f41f95757b7760da6409535fedc99e99d13a011caf",
            "06caf93699c0e791df22c6679aac87a1c14c6332",
            "KMJ_OLD_BASELINE_REAL_HTTP",
            "KMJ_CANDIDATE_REAL_HTTP",
            "KMJ_OLD_ROLLBACK_REAL_HTTP",
            "KMJ_LOCAL_DATABASE_ISOLATION",
            "KMJ_PRODUCTION_DB_WRITES",
            "KMJ_LIVE_PRODUCTION_ROLLBACK",
            "BLOCKED_REAL_HTTP_GATE",
            "PRODUCTION_ACTIVATION=NOT_PERFORMED",
            "ATTESTED_SEPARATELY",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)

    def test_no_real_deployment_commands(self):
        source = SCRIPT.read_text()
        for illegal in (
            "systemctl restart", "systemctl reload", "nginx -s",
            "ln -sfn", "os.symlink(", "os.system(",
            "git reset", "git clean", "artisan migrate",
            "pg_restore", "scp ", "ssh ", "rclone copy", "chmod 777",
            "APPROVAL.write_text", "DESTRUCTIVE",
        ):
            with self.subTest(illegal=illegal):
                self.assertNotIn(illegal, source)


if __name__ == "__main__":
    unittest.main()
