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


    def test_rollback_only_removes_exact_created_inode_and_digest(self):
        # Execute the real cleanup function against disposable test files.
        # Model root ownership in the stat result because CI runs nonroot.
        # The production installer/unit/systemctl are never invoked here.
        import hashlib
        source = SCRIPT.read_text(encoding="utf-8")
        start = source.index("remove_if_ours() {")
        end = source.index("rollback_partial_install() {", start)
        helper = source[start:end]
        bash = r'''
set -Eeuo pipefail
sha_file() { /usr/bin/sha256sum -- "$1" | /usr/bin/cut -d ' ' -f1; }
stat() {
  if [[ "$1" == -c && "$2" == '%d:%i:%u:%g:%h' ]]; then
    local pair
    pair="$(/usr/bin/stat -c '%d:%i' -- "$4")"
    printf '%s:0:0:1\n' "$pair"
  else /usr/bin/stat "$@"; fi
}
''' + helper + '\nremove_if_ours "$1" "$2" "$3"\n'
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            for label, inode_valid, digest_valid, link in [
                ("valid", True, True, False),
                ("wrong_inode", False, True, False),
                ("wrong_digest", True, False, False),
                ("linked", True, True, True),
            ]:
                target = d / (label + ".txt")
                payload = d / (label + ".payload")
                payload.write_text("owned data", encoding="ascii")
                if link:
                    target.symlink_to(payload)
                else:
                    target.write_text("owned data", encoding="ascii")
                stat_info = target.stat()
                inode = f"{stat_info.st_dev}:{stat_info.st_ino}"
                if not inode_valid:
                    inode = "999:999"
                digest = hashlib.sha256(b"owned data").hexdigest()
                if not digest_valid:
                    digest = "0" * 64
                p = subprocess.run(["/bin/bash", "-p", "-c", bash, "_",
                                    str(target), inode, digest],
                                   capture_output=True, text=True, timeout=10)
                self.assertEqual(p.returncode, 0, (label, p.stderr))
                self.assertEqual(target.exists() or target.is_symlink(),
                                 not (inode_valid and digest_valid and not link),
                                 label)

    def test_failure_rollback_is_inactive_and_tracks_both_created_inodes(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("trap rollback_partial_install EXIT", source)
        self.assertIn("created_runner_inode=", source)
        self.assertIn("created_unit_inode=", source)
        self.assertIn('if [[ "$install_committed" != YES ]]', source)
        self.assertIn('remove_if_ours "$target_unit" "$created_unit_inode" "$unit_sha256"', source)
        self.assertIn('remove_if_ours "$target_runner" "$created_runner_inode" "$runner_sha256"', source)
        self.assertIn("install_committed=YES", source)
        # The original implementation registered the published inode *after*
        # ln, leaving an interrupted no-clobber publication untracked.
        publish = source[source.index("publish() {"):]
        link = publish.index('if ! /usr/bin/ln -T -- "$tmp" "$dest"')
        self.assertLess(publish.index('created_runner_inode="$published_inode"'), link)
        self.assertLess(publish.index('created_unit_inode="$published_inode"'), link)

if __name__ == "__main__":
    unittest.main()
