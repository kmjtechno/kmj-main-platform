"""Non-production source contracts for exact CodeBridge legacy port repair."""
from pathlib import Path
import ast
import importlib.util
import subprocess
import unittest

BASE=Path(__file__).resolve().parents[1]
FILE=BASE/"scripts/operations/fix-fe4045-legacy-main-platform-private-codebridge-port-20261027.py"
CODE=FILE.read_text(encoding="utf-8")

class LegacyPrivateGatewayPort(unittest.TestCase):
    def test_valid_python_and_help(self):
        ast.parse(CODE)
        r=subprocess.run(["python3","-B",str(FILE),"--help"],capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("--apply",r.stdout)
        self.assertIn("--expect-old-port",r.stdout)
        self.assertIn("--expect-new-port",r.stdout)

    def test_exact_scope_and_real_service(self):
        for literal in (
            "platform-8070dad72c55",
            "kmj-codebridge-gateway-stage.service",
            "CODEBRIDGE_GATEWAY_URL",
            "EXPECTED_OLD_PORT = 8787",
            "EXPECTED_NEW_PORT = 18787",
            "GATEWAY_LISTENER_PORT_DRIFT",
            "GATEWAY_EXPOSED_NON_LOOPBACK",
            "LIVE_CODE_VERSION_CHANGED_REVIEW_REQUIRED",
            "TARGET_NOT_REACHABLE_VIA_APP_HOST"):
            self.assertIn(literal,CODE)
        self.assertNotIn("CODEBRIDGE_AGENT_PUBLIC_URL=",CODE)

    def test_explicit_scoped_approval_and_atomic_config_write(self):
        for literal in (
            'parser.add_argument("--apply", action="store_true")',
            'if not args.apply:',
            'report("SYSTEM_CHANGES", "NONE")',
            '"KMJ_APPROVE_PRIVATE_PORT_CHANGE"',
            "args.expect_old_port != EXPECTED_OLD_PORT",
            "args.expect_new_port != EXPECTED_NEW_PORT",
            'fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)',
            "GATEWAY_SERVICE_OR_ENV_CHANGED",
            "ENV_CHANGED_BEFORE_REPLACE",
            'tempfile.mkstemp(prefix=".kmj-private-gateway-env-before-", dir="/root")',
            "os.fchmod(backup.fileno(), 0o400)",
            "os.fchmod(out.fileno(), stat.S_IMODE(st.st_mode))",
            "os.replace(staged, ENV)",
            "ENV_AUTO_ROLLBACK",
            "PASS_CONFIG_ONLY"):
            self.assertIn(literal,CODE)

    def test_no_unauthorized_mutations(self):
        for forbidden in (
            "systemctl restart", "systemctl reload", "nginx -s reload",
            "git reset --hard", "ln -sfn", "artisan migrate",
            "/etc/kmj-codebridge/main-platform-production-release.json",
            "print(raw)", "print(source)", "print(current_text)",
            "CODEBRIDGE_AGENT_PUBLIC_URL="):
            self.assertNotIn(forbidden,CODE)
        self.assertIn('report("PUBLIC_AGENT_ORIGIN_CHANGED", "NO")',CODE)
        self.assertIn('report("PRODUCTION_POINTER_CHANGED", "NO")',CODE)
        self.assertIn('report("APPLICATION_ROUTE_QA", "NOT_VERIFIED")',CODE)

    def test_key_parser_is_exact_and_rejects_duplicates(self):
        spec=importlib.util.spec_from_file_location("kmj_legacy_port",FILE)
        m=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        src=(
            "# CODEBRIDGE_GATEWAY_URL=http://127.0.0.1:9999\n"
            "CODEBRIDGE_GATEWAY_URL='http://127.0.0.1:8787'\n"
            "ANOTHER_ENV_KEY=private\n"
        )
        self.assertEqual(m.parse_key(src),[(1,"http://127.0.0.1:8787")])
        self.assertEqual(len(m.parse_key(src+"CODEBRIDGE_GATEWAY_URL=http://127.0.0.1:18787\n")),2)

if __name__=="__main__":unittest.main()
