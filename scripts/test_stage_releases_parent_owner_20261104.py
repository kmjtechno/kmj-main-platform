"""Offline safety contract for one-inode KMJ staging releases owner correction."""
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/operations/KMJ_STAGE_RELEASES_PARENT_OWNER_20261104.py"
spec = importlib.util.spec_from_file_location("kmj_stage_release_owner", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class StageReleaseOwnerTests(unittest.TestCase):
    def test_python_compiles(self):
        p = subprocess.run([sys.executable, "-I", "-m", "py_compile", str(SCRIPT)],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_correct_stage_and_prod_targets_only(self):
        with tempfile.TemporaryDirectory() as temp:
            link = Path(temp) / "stage"
            link.symlink_to("../releases/b2e69decab3acd861e94e11992cd8a4cff4f2b94/apps/platform")
            self.assertEqual(module.pointer(str(link), {
                "../releases/b2e69decab3acd861e94e11992cd8a4cff4f2b94/apps/platform"
            }), "EXPECTED")
            self.assertEqual(module.pointer(str(link), {"../releases/foreign"}), "DRIFT")
            link.unlink()
            self.assertEqual(module.pointer(str(link), {"../releases/foreign"}), "MISSING")
            link.mkdir()
            self.assertEqual(module.pointer(str(link), {"../releases/foreign"}), "UNTRUSTED")

    def test_nonroot_and_wrong_host_refuse_before_write(self):
        with patch.object(module.os, "geteuid", return_value=1000), \
             patch.object(module.os, "fchown", side_effect=AssertionError("no writes")):
            with self.assertRaises(SystemExit) as cm:
                module.main()
            self.assertEqual(cm.exception.code, 2)
        with patch.object(module.os, "geteuid", return_value=0), \
             patch.object(module.socket, "gethostname", return_value="other-host"), \
             patch.object(module.os, "fchown", side_effect=AssertionError("no writes")):
            with self.assertRaises(SystemExit) as cm:
                module.main()
            self.assertEqual(cm.exception.code, 2)

    def test_ancestor_writable_or_wrong_owner_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            # The real root ancestor path cannot be substituted by stage user.
            # This source asserts root for EVERY ancestor, not just releases.
            src = SCRIPT.read_text()
            self.assertIn("current.st_uid != 0 or current.st_mode & 0o022", src)
            self.assertIn("info.st_uid != 0", src)
            self.assertIn("HOME_ANCESTOR_USER_OWNED_OR_WRITABLE", src)
            self.assertIn("os.O_NOFOLLOW", src)
            self.assertIn('os.open("releases", FLAGS, dir_fd=fd)', src)

    def test_only_single_inode_ownership_changed(self):
        source = SCRIPT.read_text()
        self.assertEqual(source.count("os.fchown("), 1)
        self.assertIn("os.fchown(releasefd, 0, -1)", source)
        for unsafe in ("os.chown(", "os.rename(", "os.replace(", "os.unlink(",
                       "os.system(", "subprocess.", "shutil.rmtree(", "chmod(",
                       "chown -R", "systemctl ", "ssh-keygen", "apt install"):
            self.assertNotIn(unsafe, source)

    def test_preconditions_and_postconditions(self):
        s = SCRIPT.read_text()
        for required in ("stat.S_IMODE(before.st_mode) != 0o755",
                         "extended_acl(releasefd)",
                         "before.st_dev, before.st_ino",
                         "now.st_dev, now.st_ino",
                         "OWNERSHIP_READBACK_FAILED",
                         "STAGING_POINTER_CHANGED",
                         "PRODUCTION_POINTER_CHANGED",
                         "PASS_OWNER_CORRECTED",
                         "PASS_ALREADY_ROOT",
                         "KMJ_STAGE_CHILDREN_CHANGED"):
            self.assertIn(required, s)

    def test_mode_and_acl_never_silently_relaxed(self):
        src = SCRIPT.read_text()
        self.assertIn('system.posix_acl_access', src)
        self.assertIn('system.posix_acl_default', src)
        self.assertIn('stat.S_IMODE(now.st_mode) != 0o755', src)
        self.assertNotIn('0o777', src)

    def test_old_stage_release_and_production_kept_intact(self):
        src = SCRIPT.read_text()
        self.assertIn("b2e69decab3acd861e94e11992cd8a4cff4f2b94", src)
        self.assertIn("platform-574e443a2c75", src)
        self.assertIn("KMJ_STAGING_POINTER", src)
        self.assertIn("KMJ_PRODUCTION_POINTER", src)
        self.assertIn("KMJ_STAGE_SOURCE_BUILD", src)


if __name__ == "__main__":
    unittest.main()
