"""Static safety contract for the exact-owner stage CODE snapshot builder.

This is an operator-reviewed source-only operation. CI never executes it as
root, launches composer/npm, or changes a connected host.
"""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/KMJ_ELITE_STAGE_SOURCE_BUILD_20261104.sh"


class SafeSourcePrep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text()

    def test_bash_syntax(self):
        p = subprocess.run(["bash", "-n", str(SCRIPT)],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_exact_candidate_and_current_pointers(self):
        s = self.script
        self.assertIn("SHA=a9796a25a2801cd303a69f5ad468aa9a704e5fff", s)
        self.assertIn("OLD=b2e69decab3acd861e94e11992cd8a4cff4f2b94", s)
        self.assertIn("platform-574e443a2c75", s)
        self.assertIn("BLOCKED_%s", s)
        self.assertIn("block PRODUCTION_POINTER", s)
        self.assertIn("block STAGING_POINTER", s)
        self.assertIn("block POST_POINTER_CHANGED", s)

    def test_root_only_stage_parent_and_atomic_no_overwrite(self):
        s = self.script
        self.assertIn("RELEASES_PARENT_NOT_ROOT_OWNED", s)
        self.assertIn("RELEASES_WRITABLE", s)
        self.assertIn("ALREADY_EXISTS_NO_OVERWRITE", s)
        self.assertIn("renameat2", s)
        self.assertIn("BLOCKED_NO_ATOMIC_NOREPLACE", s)
        self.assertIn("EXACT_SHA_ATOMIC_NO_OVERWRITE", s)
        self.assertIn("PREP_BUSY", s) if False else self.assertIn("block BUSY", s)

    def test_root_does_not_execute_composer_node_or_php(self):
        s = self.script
        self.assertIn("runuser -u kmjstage -- env", s)
        self.assertIn("npm ci --ignore-scripts", s)
        self.assertIn("composer install --no-dev", s)
        self.assertIn("npm run build", s)
        self.assertNotIn("runuser -u kmjprod", s)
        self.assertNotIn("php artisan migrate", s)
        self.assertNotIn("systemctl ", s)

    def test_no_stage_credentials_or_activation(self):
        s = self.script
        self.assertIn("trap 'rm -f -- .env' EXIT", s)
        self.assertIn('[[ ! -e "$scratch/repo/apps/platform/.env"', s)
        self.assertIn("STAGING_RUNTIME_ENV=NOT_COPIED", s)
        self.assertIn("STAGING_SEAL=NOT_CREATED", s)
        self.assertIn("STAGING_APPROVAL=NOT_CREATED", s)
        self.assertIn("STAGING_ACTIVATION=NOT_ATTEMPTED", s)
        self.assertIn("PRODUCTION_POINTER=UNCHANGED", s)
        self.assertIn("STAGING_EXACT_CANDIDATE=SOURCE_PREPARED_UNSEALED", s)

    def test_staging_source_attested_and_build_artifact_exists(self):
        s = self.script
        self.assertIn("fetch --depth 1 --no-tags origin", s)
        self.assertIn('git -C "$dest" rev-parse HEAD', s)
        self.assertIn("codebridge-workspace.tsx", s)
        self.assertIn("STAGING_WORKSPACE_ASSET", s) if False else self.assertIn("KMJ_STAGE_BUILT_AI_WORKSPACE", s)
        self.assertIn("UNSAFE_OBJECT_IN_SERVED_TREE", s)
        self.assertIn('[[ "$(cat -- "$scratch/repo/.git/HEAD")" == "$SHA" ]]', s)

    def test_no_release_or_user_data_mutation(self):
        s = self.script
        self.assertNotIn("rm -rf -- \"$RELEASES\"", s)
        self.assertNotIn("rm -rf -- \"$TARGET\"", s)
        self.assertNotIn("ln -sfn", s)
        self.assertNotIn("systemctl restart", s)
        self.assertNotIn("ssh ", s)
        self.assertNotIn("psql ", s)
        self.assertNotIn("pg_dump ", s)
        self.assertNotIn("git reset ", s)
        self.assertNotIn("git clean ", s)


if __name__ == "__main__":
    unittest.main()
