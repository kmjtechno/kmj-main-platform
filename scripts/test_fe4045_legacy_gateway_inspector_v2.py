"""Legacy-aware, non-deploying gateway config inspection contract."""
from pathlib import Path
import ast
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/operations/inspect-fe4045-legacy-main-platform-gateway-v2-20261027.py"
CODE=SCRIPT.read_text(encoding="utf-8")

class LegacyGatewayInspector(unittest.TestCase):
    def test_python_valid_and_readonly_default(self):
        ast.parse(CODE)
        self.assertIn('parser.add_argument("--apply", action="store_true", default=False)', CODE)
        self.assertIn('if not args.apply:', CODE)
        self.assertIn('status("SYSTEM_CHANGES", "NONE")', CODE)
        self.assertIn('status("KMJ_GATEWAY_ENV_FIX", "INSPECT_ONLY")',CODE)

    def test_legacy_config_read_allowed(self):
        self.assertIn('("codebridge_gateway", "CODEBRIDGE_GATEWAY_URL")',CODE)
        self.assertIn('public_supported = "CODEBRIDGE_AGENT_PUBLIC_URL" in config_text',CODE)
        self.assertIn('"NO_LEGACY_RELEASE"',CODE)
        self.assertIn('if not public_supported:\n        stop("LIVE_RELEASE_LACKS_PUBLIC_AGENT_ORIGIN_SUPPORT")', CODE)
        self.assertNotIn('LARAVEL_UPSTREAM_KEYS_NOT_PRESENT',CODE)

    def test_do_not_change_live_without_explicit_guarded_approval(self):
        for marker in ('"KMJ_APPROVE_CONFIG_ONLY"', 'args.expect_port != port',
                       'fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)',
                       'AMBIGUOUS_OR_EXPOSED_GATEWAY_LISTENER',
                       'LIVE_OR_ENV_DRIFT', 'ENV_CHANGED_CONCURRENTLY',
                       'ENV_BACKUP_ROOT_ONLY','PUBLIC_AGENT_PAIRING',
                       'APP_CONFIGURED_LOOPBACK_PORT','ACTUAL_GATEWAY_LOOPBACK_PORT'):
            self.assertIn(marker,CODE)
        for forbidden in ('systemctl restart','ln -sfn','git reset --hard',
                          'systemctl reload','artisan migrate',
                          '/etc/kmj-codebridge/main-platform-production-release.json'):
            self.assertNotIn(forbidden,CODE)

    def test_env_read_parser_without_host_access(self):
        spec=importlib.util.spec_from_file_location("gateway_v2",SCRIPT)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sample='''CODEBRIDGE_GATEWAY_URL=http://127.0.0.1:18881
# CODEBRIDGE_AGENT_PUBLIC_URL=https://invalid.example
OTHER_SECRET="do-not-print"
'''
        self.assertEqual(module.lines_of_value(sample,"CODEBRIDGE_GATEWAY_URL"),[(0,"http://127.0.0.1:18881")])
        self.assertEqual(module.lines_of_value(sample,"CODEBRIDGE_AGENT_PUBLIC_URL"),[])
        self.assertEqual(module.lines_of_value(sample+'CODEBRIDGE_GATEWAY_URL=http://127.0.0.1:18882\n',"CODEBRIDGE_GATEWAY_URL"),[(0,"http://127.0.0.1:18881"),(3,"http://127.0.0.1:18882")])

if __name__=="__main__":
    unittest.main()
