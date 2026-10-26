"""Static + negative tests for the nonproduction PG18 Laravel rehearsal."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ci/verify-postgres18-laravel.sh"
WORKFLOW = ROOT / ".github/workflows/disposable-postgres18-laravel.yml"


class PG18Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_bash_syntax(self):
        p = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_refuses_invalid_sha_without_running_docker(self):
        env = dict(os.environ, GITHUB_ACTIONS="true", RUNNER_TEMP="/tmp")
        p = subprocess.run(["bash", str(SCRIPT), "not-a-commit"],
                           cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("invalid source SHA", p.stdout)
        self.assertNotIn("docker pull", p.stdout)

    def test_requires_github_actions_context(self):
        env = dict(os.environ, GITHUB_ACTIONS="false", RUNNER_TEMP="/tmp")
        p = subprocess.run(["bash", str(SCRIPT), "a" * 40],
                           cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("GitHub-hosted CI context required", p.stdout)

    def test_strict_network_and_actual_pg18_are_checked(self):
        for marker in ("--network none", "listen_addresses=''",
                       "unix_socket_directories=/var/run/postgresql",
                       "PG18_PDO_PRIVATE_SOCKET=PASS",
                       "server_version", "server_version_num",
                       "pg_uid=", "sudo chown"):
            self.assertIn(marker, self.script, marker)

    def test_full_application_and_rollback_are_required(self):
        for marker in ("php artisan migrate --force",
                       "php artisan test --testsuite=Feature",
                       "php artisan migrate:rollback",
                       "PG18_LARAVEL_ISOLATED_ACCEPTANCE=PASS",
                       "PG18_FULL_LARAVEL_FEATURE_SUITE=PASS",
                       "PG18_LARAVEL_ROLLBACK=PASS"):
            self.assertIn(marker, self.script, marker)

    def test_no_production_deploy_or_credentials(self):
        for prohibited in ("systemctl ", "ln -sfn ", "pg_dump ", "psql -h kmjtechno.com",
                           "artisan db:wipe", "DB_HOST=kmjtechno.com",
                           "POSTGRES_HOST_AUTH_METHOD=trust"):
            self.assertNotIn(prohibited, self.script)
        self.assertIn("PRODUCTION_DATABASE_TOUCHED=NO", self.script)
        self.assertEqual(self.script.count("psql -h /var/run/postgresql"), 3)
        self.assertNotIn("psql -h 127.0.0.1", self.script)

    def test_workflow_is_read_only_and_exact_head(self):
        self.assertIn("contents: read", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertIn("pull_request:", self.workflow)
        self.assertIn("timeout-minutes: 30", self.workflow)
        self.assertIn("SOURCE_SHA:", self.workflow)
        self.assertIn("verify-postgres18-laravel.sh", self.workflow)


if __name__ == "__main__":
    unittest.main()
