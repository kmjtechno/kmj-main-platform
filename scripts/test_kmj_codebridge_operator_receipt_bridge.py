"""Source-only test of the root-to-CodeBridge sanitized receipt adapter."""
from pathlib import Path
import ast
import importlib.util
import re
import subprocess
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts/operations/kmj_codebridge_operator_receipt_bridge_20261027.py"
SOURCE = PATH.read_text(encoding="utf-8")
class OperatorReceiptBridge(unittest.TestCase):
    def test_python_help_without_operator_access(self):
        ast.parse(SOURCE)
        response = subprocess.run(["python3","-B",str(PATH),"--help"],capture_output=True,text=True,timeout=10)
        self.assertEqual(response.returncode,0,response.stderr)
        self.assertIn("gateway-port-verify",response.stdout)
        self.assertNotIn("--script",response.stdout)
        self.assertNotIn("--command",response.stdout)
        self.assertNotIn("--shell",response.stdout)

    def test_command_is_fixed_and_sha256_pinned(self):
        for value in (
            'TASK="gateway-port-verify"',
            'PINNED_SHA256="79c21f19c6f86da7af97927491c81644e18fefc9c36d291475f33fd48bfe9279"',
            'PINNED_SOURCE=QA/"KMJ_P0_LEGACY_CODEBRIDGE_PRIVATE_PORT_18787_GUARDED_FIX_20261027.py"',
            'hashlib.sha256(raw).hexdigest()!=PINNED_SHA256',
            'with os.fdopen(fd,"wb") as out',
            'os.fchmod(out.fileno(),0o400)',
            '[sys.executable,"-B",str(temp)]',
            'cwd="/"',
            'timeout=25',
            "args=parser.parse_args()",
        ):
            self.assertIn(value,SOURCE)
        self.assertNotIn("shell=True",SOURCE)

    def test_root_and_release_guards(self):
        for value in (
            "ROOT_ON_ELITE_REQUIRED", "PRODUCTION_RELEASE_DRIFT",
            "PROJECT_DIRECTORY", "QA_DIRECTORY", "RECEIPTS_SYMLINK",
            "RECEIPTS_DIRECTORY_INSECURE", "SOURCE_MISSING_OR_SYMLINK",
            'CURRENT="/home/kmjprod/releases/platform-8070dad72c55"'):
            self.assertIn(value,SOURCE)

    def test_safe_marker_filter_and_no_raw_log_leak(self):
        spec=importlib.util.spec_from_file_location("receipt_bridge",PATH)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.TASK,"gateway-port-verify")
        self.assertTrue(re.fullmatch(module.PATTERNS["PORT_ALIGNMENT"],"PASS"))
        self.assertFalse(re.fullmatch(module.PATTERNS["APP_CONFIGURED_PORT"],"token=secret"))
        self.assertFalse(re.fullmatch(module.PATTERNS["GATEWAY_SYSTEMD"],"Authorization: Bearer secret"))
        self.assertFalse(re.fullmatch(module.PATTERNS["KMJ_PRIVATE_GATEWAY_ALIGNMENT"],"PASS_CONFIG_ONLY"))
        for value in ("RECEIPT_TOO_LARGE","RECEIPTS_DIRECTORY_NOT_TRAVERSABLE",
                      "operator_execution","codebridge_automated_approval",
                      "receipt_is_not_release_approval",
                      'atomic_receipt(args.task+".json",payload)',
                      'atomic_receipt("latest.json",payload)',
                      'os.fchmod(out.fileno(),0o644)'):
            self.assertIn(value,SOURCE)
        self.assertNotIn('print(result.stdout)',SOURCE)
        self.assertNotIn('print(result.stderr)',SOURCE)
        self.assertNotIn('result.stdout, "a"',SOURCE)

    def test_no_approval_bypass_or_live_mutation(self):
        for bad in ("git reset --hard","ln -sfn", "artisan migrate", "systemctl restart",
                    "systemctl reload", "chown -R", "rm -rf",
                    "/etc/kmj-codebridge/main-platform-production-release.json"):
            self.assertNotIn(bad,SOURCE)
        self.assertIn("PRODUCTION_ACTIVATION=NOT_ATTEMPTED",SOURCE)

if __name__=="__main__":
    unittest.main()
