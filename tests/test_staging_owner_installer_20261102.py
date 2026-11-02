"""Fail-closed staging owner installer contract (no root install is ever tested)."""
from __future__ import annotations
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/install-main-platform-staging-unit-20261102.sh"
RUNNER = ROOT / "deploy/staging/kmj-main-platform-staging-deploy.sh"
UNIT = ROOT / "deploy/staging/kmj-main-platform-staging-deploy.service"

class StagingOwnerInstallerTests(unittest.TestCase):
    def invoke(self, root: pathlib.Path):
        script = root / "scripts/operations/install-main-platform-staging-unit-20261102.sh"
        p = subprocess.run(["/bin/bash", "-p", str(script), "--inspect"],
                           cwd="/", capture_output=True, text=True, timeout=15)
        return p

    def fixture(self, d: pathlib.Path):
        scripts = d / "scripts/operations"
        deploy = d / "deploy/staging"
        scripts.mkdir(parents=True)
        deploy.mkdir(parents=True)
        shutil.copy2(SCRIPT, scripts / SCRIPT.name)
        shutil.copy2(RUNNER, deploy / RUNNER.name)
        shutil.copy2(UNIT, deploy / UNIT.name)

    def test_original_source_inspects_without_mutation(self):
        result = self.invoke(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout[-500:])
        self.assertIn("KMJ_STAGING_OWNER_SOURCE=EXACT_GIT_BLOBS_AND_SHA256_PASS", result.stdout)
        self.assertIn("KMJ_STAGING_OWNER_INSTALL=INSPECT_ONLY", result.stdout)
        self.assertIn("KMJ_STAGING_ACTIVATION=NOT_ATTEMPTED", result.stdout)

    def test_mutated_runner_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            self.fixture(d)
            with (d / "deploy/staging" / RUNNER.name).open("a") as f:
                f.write("\n# integrity break\n")
            p = self.invoke(d)
            self.assertEqual(p.returncode, 2)
            self.assertIn("BLOCKED_RUNNER_SOURCE_BLOB", p.stdout)
            self.assertNotIn("INSPECT_ONLY", p.stdout)

    def test_mutated_unit_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            self.fixture(d)
            with (d / "deploy/staging" / UNIT.name).open("a") as f:
                f.write("\n# integrity break\n")
            p = self.invoke(d)
            self.assertEqual(p.returncode, 2)
            self.assertIn("BLOCKED_UNIT_SOURCE_BLOB", p.stdout)

    def test_missing_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            self.fixture(d)
            (d / "deploy/staging" / UNIT.name).unlink()
            p = self.invoke(d)
            self.assertEqual(p.returncode, 2)
            self.assertIn("BLOCKED_SOURCE_ABSENT_OR_LINKED", p.stdout)

    def test_linked_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            self.fixture(d)
            unit = d / "deploy/staging" / UNIT.name
            unit.unlink()
            unit.symlink_to(UNIT)
            p = self.invoke(d)
            self.assertEqual(p.returncode, 2)
            self.assertIn("BLOCKED_SOURCE_ABSENT_OR_LINKED", p.stdout)

    def test_script_is_bash_valid_and_install_requires_owner_host(self):
        syntax = subprocess.run(["/bin/bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        text = SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "PRIVILEGED_BASH_REQUIRED", "OWNER_HOST", "SNAPSHOT_PATH",
            "RUNNER_SOURCE_SHA256", "UNIT_SOURCE_SHA256", "TARGET_HASHES",
            "SOURCE_OR_TARGET_ANCESTOR", "RUNNER_ALREADY_EXISTS",
            "UNIT_ALREADY_EXISTS", "NO_CLOBBER_LINK",
            "INSTALLED_INACTIVE_PENDING_APPROVAL", "STAGING_ACTIVATION=NOT_ATTEMPTED",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("systemctl start", text)
        self.assertNotIn("systemctl enable", text)
        self.assertNotIn("ln -sfn", text)
        self.assertNotIn("git reset", text)

if __name__ == "__main__":
    unittest.main()
