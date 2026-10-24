#!/usr/bin/env python3
"""Source-level no-deploy release-bound ACL contract tests."""
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/guard-codebridge-candidate-public-acl-20261024.sh"
CODE = SCRIPT.read_text("utf-8")

class GuardPublicACL(unittest.TestCase):
    def test_bash_parses(self):
        run = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_exact_source_pinning_and_live_pointer(self):
        self.assertIn("b1d672bbc83a51ca3f8271435692825072444c8e", CODE)
        self.assertIn("platform-8070dad72c55", CODE)
        self.assertIn("CANDIDATE_SHA_MISMATCH", CODE)
        self.assertIn("LIVE_RELEASE_CHANGED", CODE)
        self.assertIn("CANDIDATE_GIT_DIRTY", CODE)
        self.assertIn("CANDIDATE_DIRTY_AFTER_ACL", CODE)

    def test_only_public_nginx_scope(self):
        self.assertIn("setfacl -m 'u:www-data:--x' \"$dir\"", CODE)
        self.assertIn("setfacl -R -m 'u:www-data:rX' \"$CANDIDATE/apps/platform/public\"", CODE)
        self.assertNotIn("setfacl -R -m 'u:www-data:rX' \"$CANDIDATE\"", CODE)
        self.assertNotIn("chown -R", CODE)
        self.assertIn("PUBLIC_MANIFEST_UNREADABLE", CODE)

    def test_live_secret_rejected_not_copied(self):
        self.assertIn("NGINX_PRIVATE_ENV_EXPOSED", CODE)
        self.assertIn("NGINX_PRIVATE_ENV_ALREADY_EXPOSED", CODE)
        self.assertIn("ENV_OWNER_UNEXPECTED", CODE)
        self.assertNotIn("cat \"$ENVFILE\"", CODE)
        self.assertNotIn("cp \"$ENVFILE\"", CODE)

    def test_single_release_lock_and_symlink_guard(self):
        self.assertIn("/run/lock/kmj-main-platform-production-release.lock", CODE)
        self.assertIn("flock -n 9", CODE)
        self.assertIn("PUBLIC_ANCESTOR_UNSAFE", CODE)
        self.assertIn("PUBLIC_DIR_UNSAFE", CODE)
        self.assertIn("PUBLIC_STORAGE_REQUIRES_REVIEW", CODE)

    def test_no_production_activation_or_mutations(self):
        for bad in ("systemctl start", "systemctl restart", "systemctl reload",
                    "ln -s", "os.replace", "git reset", "artisan migrate",
                    "/etc/kmj-codebridge/main-platform-production-release.json",
                    "backupVerified", "rollbackVerified", "chmod 777",
                    "CODEBRIDGE_GATEWAY_URL=", "CODEBRIDGE_AGENT_PUBLIC_URL=",
                    "rsync", "cp -", "rm -rf"):
            self.assertNotIn(bad, CODE)
        self.assertIn("PRODUCTION_SWITCH=NOT_ATTEMPTED", CODE)
        self.assertIn("STORAGE_CONTINUITY=NOT_ATTESTED", CODE)

if __name__ == "__main__":
    unittest.main()
