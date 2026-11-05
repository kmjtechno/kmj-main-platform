"""Offline tests for read-only, fixed-path KMJ staging home inventory."""
import ast
import importlib.util
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/operations/KMJ_STAGE_HOME_TRUST_AUDIT_20261104.py"
spec = importlib.util.spec_from_file_location("kmj_stage_home_audit", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class StageHomeAuditContract(unittest.TestCase):
    def test_source_compiles(self):
        compile(SCRIPT.read_text(), str(SCRIPT), "exec")

    def test_restricted_fixed_paths_and_known_pointers(self):
        data = SCRIPT.read_text()
        self.assertIn("b2e69decab3acd861e94e11992cd8a4cff4f2b94", data)
        self.assertIn("a9796a25a2801cd303a69f5ad468aa9a704e5fff", data)
        self.assertIn("platform-574e443a2c75", data)
        self.assertIn('Path("/home/kmjstage")', data)
        self.assertIn('Path("/var/lib")', data)
        self.assertIn('STAGING_MUTATIONS", "NONE"', data)
        self.assertIn('STAGING_OWNER_SEAL", "NOT_VERIFIED"', data)

    def test_source_never_changes_host_state(self):
        tree = ast.parse(SCRIPT.read_text())
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                    called.add(f.value.id + "." + f.attr)
                elif isinstance(f, ast.Name):
                    called.add(f.id)
        for forbidden in (
            "os.chown", "os.fchown", "os.chmod", "os.fchmod", "os.rename", "os.replace",
            "os.unlink", "os.mkdir", "os.makedirs", "os.system", "os.popen",
            "subprocess.run", "subprocess.Popen", "shutil.rmtree",
            "Path.write_text", "Path.unlink", "Path.mkdir", "Path.chmod",
        ):
            self.assertNotIn(forbidden, called)
        self.assertNotIn("open", called)
        self.assertNotIn("print_secret", called)

    def test_owner_classes(self):
        self.assertEqual(module.classify_owner(0, 1001), "ROOT")
        self.assertEqual(module.classify_owner(1001, 1001), "KMJSTAGE")
        self.assertEqual(module.classify_owner(1002, 1001), "OTHER")

    def test_pointer_detects_drift_and_nonlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp) / "current"
            self.assertEqual(module.pointer(t, {"good"}), "MISSING_OR_UNVERIFIED")
            t.symlink_to("good")
            self.assertEqual(module.pointer(t, {"good"}), "EXPECTED")
            self.assertEqual(module.pointer(t, {"bad"}), "DRIFT")
            t.unlink()
            t.mkdir()
            self.assertEqual(module.pointer(t, {"good"}), "NOT_SYMLINK")

    def test_metadata_only_and_no_directory_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "folder"
            d.mkdir(mode=0o700)
            row = module.meta_dir(d, -1)
            self.assertEqual(row[0], "DIRECTORY")
            self.assertEqual(row[3], "NO")
            self.assertIn(row[4], {"NONE", "UNKNOWN"})
            self.assertEqual(module.meta_dir(d / "missing", -1)[0], "ABSENT")

    def test_unprivileged_invocation_does_not_inspect(self):
        with patch.object(module.os, "geteuid", return_value=1000), \
             patch.object(module, "meta_dir", side_effect=AssertionError("must not inspect")):
            with self.assertRaises(SystemExit) as cm:
                module.main()
            self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
