"""Offline, non-root tests for fixed trusted stage runtime preflight."""
import ast
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "scripts/operations/KMJ_STAGE_ROOT_SNAPSHOT_RUNTIME_PREFLIGHT_20261104.py"
spec = importlib.util.spec_from_file_location("kmj_root_stage_runtime", SRC)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class FixedStageRuntimeTests(unittest.TestCase):
    def test_static_exact_source_and_paths(self):
        compile(SRC.read_text(), str(SRC), "exec")
        self.assertEqual(m.EXACT_SHA, "a9796a25a2801cd303a69f5ad468aa9a704e5fff")
        self.assertEqual(str(m.ANCHOR), "/var/lib/kmj-main-platform-stage-releases")
        self.assertEqual(m.STAGE_OLD, "b2e69decab3acd861e94e11992cd8a4cff4f2b94")
        self.assertEqual(m.PROD_OLD, "platform-574e443a2c75")

    def test_no_mutator_or_network_tool(self):
        tree = ast.parse(SRC.read_text())
        calls = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                    calls.add(f.value.id + "." + f.attr)
        for bad in (
            "os.chown", "os.fchown", "os.chmod", "os.fchmod", "os.mkdir",
            "os.makedirs", "os.rename", "os.replace", "os.unlink", "os.symlink",
            "os.system", "os.popen", "subprocess.Popen", "Path.write_text",
            "Path.mkdir", "Path.unlink", "socket.socket",
        ):
            self.assertNotIn(bad, calls)
        data = SRC.read_text()
        self.assertNotIn("shell=True", data)
        self.assertNotIn("nginx -s", data)
        self.assertNotIn("git reset", data)
        self.assertNotIn("git clean", data)
        self.assertIn("STAGING_MUTATIONS", data)

    def test_no_root_no_inspection(self):
        with patch.object(m.os, "geteuid", return_value=1000), \
             patch.object(m, "app_snapshot_status", side_effect=AssertionError("unexpected access")), \
             patch.object(m, "service_state", side_effect=AssertionError("unexpected unit probe")):
            self.assertEqual(m.main(), 2)

    def test_fixed_pointer_ignores_untrusted_symlinks(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "link"
            self.assertEqual(m.fixed_pointer(path, {"expected"}), "UNVERIFIED")
            path.symlink_to("expected")
            self.assertEqual(m.fixed_pointer(path, {"expected"}), "EXPECTED")
            self.assertEqual(m.fixed_pointer(path, {"different"}), "DRIFT")
            path.unlink()
            path.mkdir()
            self.assertEqual(m.fixed_pointer(path, {"expected"}), "DRIFT")

    def test_fpm_pool_no_raw_env_or_values(self):
        with patch.object(m, "read_fixed_root_file", return_value=(
            b"[kmjstage]\nuser = kmjstage\ngroup=kmjstage\n"
            b"listen = /run/php/kmjstage-php84-fpm.sock\n"
            b"env[SECRET] = MUST_NOT_PRINT\n")):
            self.assertEqual(m.fpm_pool_status(), "STAGE_USER_GROUP_SOCKET_MATCH")
        with patch.object(m, "read_fixed_root_file", return_value=(
            b"user=kmjstage\nuser=root\n"
            b"group=kmjstage\nlisten=/run/php/kmjstage-php84-fpm.sock\n")):
            self.assertEqual(m.fpm_pool_status(), "POOL_DUPLICATE_SETTING")
        with patch.object(m, "read_fixed_root_file", return_value=(
            b"user=www-data\ngroup=www-data\nlisten=/tmp/fpm.sock\n")):
            self.assertEqual(m.fpm_pool_status(), "POOL_EFFECTIVE_ROLE_UNVERIFIED")

    def test_snapshot_missing_untrusted_root(self):
        with patch.object(m, "root_dir", return_value="ABSENT_OR_UNREADABLE"):
            self.assertEqual(m.app_snapshot_status(), "BLOCKED_ANCHOR")
        with patch.object(m, "root_dir", side_effect=[
            "ROOT_OWNED_PRESENT", "ABSENT_OR_UNREADABLE"
        ]):
            self.assertEqual(m.app_snapshot_status(), "MISSING_OR_UNTRUSTED")

    def test_source_snapshot_exact_head_mismatch(self):
        with patch.object(m, "root_dir", return_value="ROOT_OWNED_PRESENT"), \
             patch.object(m, "read_fixed_root_file", return_value=b"wronghead\n"):
            self.assertEqual(m.app_snapshot_status(), "SOURCE_HEAD_UNVERIFIED")

    def test_only_fixed_root_and_systemd_read(self):
        s = SRC.read_text()
        self.assertIn('["/usr/bin/systemctl", "show", unit, "-P", "ActiveState"]', s)
        self.assertIn('("nginx.service", "php8.4-fpm.service")', s)
        self.assertIn("os.O_NOFOLLOW", s)
        self.assertIn("STAGE_FPM_SOURCE_ACCESS", s)
        self.assertIn("BLOCKED_ROOT_ONLY_0700", s)
        self.assertIn("STAGE_DATABASE_ISOLATION", s)
        self.assertIn("NOT_ATTESTED", s)
        self.assertEqual(m.service_state("ssh.service"), "UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
