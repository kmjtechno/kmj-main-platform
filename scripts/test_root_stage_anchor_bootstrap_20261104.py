"""Source-only contracts for protected staging root anchor bootstrap.

No test writes to /var/lib, no root operations, no production changes.
"""
import ast
import importlib.util
import pathlib
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "scripts/operations/KMJ_ROOT_STAGING_ANCHOR_BOOTSTRAP_20261104.py"
spec = importlib.util.spec_from_file_location("kmj_stage_anchor", SOURCE)
target = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = target
spec.loader.exec_module(target)


class RootStageAnchorContract(unittest.TestCase):
    def test_python_syntax(self):
        compile(SOURCE.read_text(), str(SOURCE), "exec")

    def test_exact_paths_and_candidate(self):
        self.assertEqual(target.ANCHOR, "/var/lib/kmj-main-platform-stage-releases")
        self.assertEqual(target.NEW_SHA, "a9796a25a2801cd303a69f5ad468aa9a704e5fff")
        self.assertIn("b2e69decab3acd861e94e11992cd8a4cff4f2b94", SOURCE.read_text())
        self.assertIn("platform-574e443a2c75", SOURCE.read_text())

    def test_root_gate_before_mutation(self):
        with patch.object(target.os, "geteuid", return_value=1000), \
             patch.object(target.os, "mkdir", side_effect=AssertionError("must not mutate")):
            with self.assertRaises(SystemExit) as e:
                target.main()
            self.assertEqual(e.exception.code, 2)
        with patch.object(target.os, "geteuid", return_value=0), \
             patch.object(target.socket, "gethostname", return_value="not-kmj-elite"), \
             patch.object(target.os, "mkdir", side_effect=AssertionError("must not mutate")):
            with self.assertRaises(SystemExit) as e:
                target.main()
            self.assertEqual(e.exception.code, 2)

    def test_only_one_tightly_bound_mkdir_mutation(self):
        t = ast.parse(SOURCE.read_text())
        calls = []
        for n in ast.walk(t):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name):
                calls.append(f"{n.func.value.id}.{n.func.attr}")
        self.assertEqual(calls.count("os.mkdir"), 1)
        for forbidden in ("os.chown", "os.fchown", "os.chmod", "os.fchmod", "os.rename",
                          "os.replace", "os.unlink", "os.remove", "os.makedirs", "os.system",
                          "os.popen", "subprocess.run", "subprocess.Popen"):
            self.assertNotIn(forbidden, calls)
        s = SOURCE.read_text()
        self.assertIn("os.mkdir(NAME, mode=0o700, dir_fd=fd)", s)
        self.assertIn("os.O_NOFOLLOW", s)
        self.assertIn("st.st_uid != 0", s)
        self.assertIn("st.st_dev != named.st_dev or st.st_ino != named.st_ino", s)
        self.assertIn("system.posix_acl_access", s)
        self.assertIn("system.posix_acl_default", s)

    def test_pointer_classifier_refuses_nonlinks_and_drift(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "current"
            self.assertFalse(target.exact_link(str(p), ("expected",)))
            p.symlink_to("expected")
            self.assertTrue(target.exact_link(str(p), ("expected",)))
            self.assertFalse(target.exact_link(str(p), ("wrong",)))
            p.unlink()
            p.mkdir()
            self.assertFalse(target.exact_link(str(p), ("expected",)))

    def test_anchor_is_not_a_deployment_or_owner_seal(self):
        s = SOURCE.read_text()
        for key in (
            "KMJ_ROOT_STAGE_RELEASE_CANDIDATE",
            "KMJ_ROOT_STAGE_WEB_SERVING",
            "NOT_PREPARED",
            "NOT_CONFIGURED",
            "KMJ_STAGING_APPROVAL",
            "NOT_MODIFIED",
            "KMJ_STAGING_POINTER",
            "KMJ_PRODUCTION_POINTER",
            "UNCHANGED",
            "KMJ_OFFSITE_BACKUP_SERVICE",
            "PASS_PRIVATE_DIRECTORY_ONLY",
        ):
            self.assertIn(key, s)
        for forbidden in ("systemctl ", "nginx -s", "git reset", "git clean", "os.symlink("):
            self.assertNotIn(forbidden, s)

    def test_traversal_and_owner_preconditions(self):
        s = SOURCE.read_text()
        self.assertIn('for component in ("var", "lib")', s)
        self.assertIn("ROOT_ANCESTOR_UNTRUSTED", s)
        self.assertIn("ROOT_PARENT_UNTRUSTED", s)
        self.assertIn("STAGE_HOME_SCOPE_CHANGED", s)
        self.assertIn("POST_CREATE_STAGE_HOME_DRIFT", s)
        self.assertIn("CURRENT_RELEASE_POINTER_DRIFT", s)


if __name__ == "__main__":
    unittest.main()
