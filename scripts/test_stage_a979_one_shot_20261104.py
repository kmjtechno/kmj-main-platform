from pathlib import Path
import subprocess
import unittest

SOURCE = Path(__file__).parent / 'operations/kmj-a979-guarded-one-shot-20261104.sh'

class OneShotSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = SOURCE.read_text()

    def test_bash_syntax(self):
        self.assertEqual(subprocess.run(['/usr/bin/bash', '-n', str(SOURCE)], capture_output=True).returncode, 0)

    def test_pinned_immutable_source_and_sha256(self):
        for token in (
            '1e2ab0f4a7cfee0746b48d9b9295db9ee89c4774',
            '6a18b9c7a407d787a9eef40aa92d7d1f75560d32',
            'bd52f881e74f2464bd25194cd44ec17e5e87a50910c5c2e9ed8fa976588cf881',
            'c95d67b00543528ae193aee421ea282e9def3d97fe8c40cc27edb2a52a8a69a2',
            'sha256sum --check --status',
        ):
            self.assertIn(token, self.src)

    def test_inspect_is_default_and_apply_requires_explicit_opt_in(self):
        self.assertIn('MODE="${1:---inspect}"', self.src)
        self.assertIn('"$#" -gt 1', self.src)
        self.assertIn('if [[ "$MODE" == "--inspect" ]]', self.src)
        self.assertIn('"$D/migrate.py" --apply', self.src)
        self.assertLess(
            self.src.index('KMJ_STAGE_ONE_SHOT=PASS_READ_ONLY_NO_MIGRATION'),
            self.src.index('"$D/migrate.py" --apply'),
        )

    def test_root_and_host_enforced(self):
        self.assertIn('$(id -u)', self.src)
        self.assertIn('kmj-elite', self.src)
        self.assertIn('BLOCKED_OWNER_ROOT_HOST', self.src)
        self.assertIn('mktemp -d -p /root', self.src)
        self.assertIn('umask 077', self.src)

    def test_read_only_gates_before_migration(self):
        gate = self.src.index('KMJ_STAGE_A979_MIGRATIONS=READ_ONLY_READY')
        apply = self.src.index('"$D/migrate.py" --apply')
        self.assertLess(gate, apply)
        for token in (
            'LIVE_POINTERS=EXPECTED',
            'STAGING_VHOST_SOURCE_TRUST=ROOT_TRUSTED',
            'NGINX_CONFIG_SYNTAX=PASS',
            'PHP_FPM_CONFIG_SYNTAX=PASS',
            'PASS_CANDIDATE_DB_SCHEMA_ONLY',
            'PASS_ISOLATED_DB_ONLY_NOT_LIVE',
        ):
            self.assertIn(token, self.src)

    def test_no_production_changes_or_bypass(self):
        for bad in ('git reset', 'git clean', 'curl -k', 'ssh -o StrictHostKeyChecking=no',
                    'systemctl restart', 'systemctl reload', 'nginx -s reload',
                    'DROP DATABASE', 'DROP ROLE', 'rm -rf', 'ln -sfn'):
            self.assertNotIn(bad, self.src)

if __name__ == '__main__':
    unittest.main()
