"""Fixed CodeBridge-readable read-only production approval receipt runner contract."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/publish-production-readonly-codebridge-receipt-20261027.sh"


class OwnerReceiptRunnerContract(unittest.TestCase):
    def test_shell_parses(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True, timeout=8)

    def test_bad_host_rejected_before_network_or_write(self):
        for args in ([], ["arbitrary"], ["--run", "rm -rf"]):
            with self.subTest(args=args):
                p = subprocess.run(["bash", str(SCRIPT), *args],
                                   capture_output=True, text=True, timeout=8)
                self.assertEqual(p.returncode, 2)
                self.assertIn("BLOCKED_HOST", p.stdout)

    def test_exact_source_and_only_fixed_read_audits(self):
        content = SCRIPT.read_text(encoding="utf-8")
        required = (
            "KMJ_PRODUCTION_RELEASE_RECEIPT_LATEST_20261027.json",
            "scripts/operations/audit-production-approval-blockers-20261027.py",
            "scripts/operations/audit-production-candidate-storage-20261027.py",
            "2967eb9875ed3b9d76a75a0949864707b72056eb",
            "888c670a26523a083a3096306b745043148dc5df",
            "git hash-object", "staging-approved", "readlink -f /home/kmjprod/current",
            "KMJ_PROD_RECEIPT=WRITTEN_CODEBRIDGE_READABLE",
            "KMJ_PROD_STORAGE_AUDIT", "PROD_GATE_RESULT",
            "READ_ONLY_COMPLETE", "FAILED_OR_INCOMPLETE",
            "root-private", "allowlisted keys", "RECEIPT_SYMLINK",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, content)

    def test_no_generic_host_execution_or_sensitive_capture(self):
        content = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "eval ", "bash -c", "sh -c", "curl | bash", "curl -k",
            "source .env", "cat .env", "printenv", "env |",
            "systemctl restart", "systemctl reload", "artisan migrate",
            "rm -rf /home", "ln -sfn", "git reset", "git clean",
            "os.system", "APP_KEY=", "DB_PASSWORD=", "SSH_PRIVATE_KEY",
            "approval['backupVerified'] = True",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, content)


if __name__ == "__main__":
    unittest.main()
