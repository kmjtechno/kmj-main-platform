import importlib.util
from pathlib import Path
import unittest
import shutil
import subprocess
import tempfile
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location(
    "refresh", Path(__file__).parent / "operations/refresh_production_release_sha_map.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class TransactionTests(unittest.TestCase):
    def test_success(self):
        write, validate, reload = Mock(), Mock(), Mock()
        self.assertEqual(m.transaction("old", "new", lambda: True, write,
                                       validate, reload, lambda: True), "MAP_REFRESHED")
        write.assert_called_once_with("new")
        self.assertEqual(validate.call_count, 2)
        reload.assert_called_once()

    def test_initial_witness_blocks_write(self):
        write = Mock()
        with self.assertRaisesRegex(ValueError, "PREVIOUS_LIVE"):
            m.transaction("old", "new", lambda: True, write, Mock(), Mock(), lambda: False)
        write.assert_not_called()

    def test_failed_config_restores_previous(self):
        write, reload = Mock(), Mock()
        validate = Mock(side_effect=[None, RuntimeError("syntax"), None])
        with self.assertRaisesRegex(RuntimeError, "syntax"):
            m.transaction("old", "new", lambda: True, write, validate, reload, lambda: True)
        self.assertEqual([c.args for c in write.call_args_list], [("new",), ("old",)])
        reload.assert_called_once()

    def test_failed_post_witness_restores_previous(self):
        write, reload = Mock(), Mock()
        witness = Mock(side_effect=[True, False, True])
        with self.assertRaisesRegex(ValueError, "POST_MAP_WITNESS"):
            m.transaction("old", "new", lambda: True, write, Mock(), reload, witness)
        self.assertEqual([c.args for c in write.call_args_list], [("new",), ("old",)])
        self.assertEqual(reload.call_count, 2)

    def test_failed_rollback_is_not_pass(self):
        witness = Mock(side_effect=[True, False, False])
        with self.assertRaisesRegex(RuntimeError, "ROLLBACK_WITNESS"):
            m.transaction("old", "new", lambda: True, Mock(), Mock(), Mock(), witness)

    def test_idempotent_no_reload(self):
        write, reload = Mock(), Mock()
        self.assertEqual(m.transaction("old", "old", lambda: True, write, Mock(), reload, lambda: True),
                         "MAP_ALREADY_READY")
        write.assert_not_called()
        reload.assert_not_called()

class UnitContractTests(unittest.TestCase):
    def test_admission_depends_on_fixed_preparation_unit(self):
        root = Path(__file__).resolve().parents[1] / "infra/server/systemd"
        unit = (root / "kmj-elite-production-sha-map.service").read_text()
        dep = (root / "kmj-elite-release-admission-broker.service.d/20-production-sha-map.conf").read_text()
        self.assertIn("Requires=kmj-elite-production-sha-map.service", dep)
        self.assertIn("After=kmj-elite-production-sha-map.service", dep)
        self.assertIn("refresh_production_release_sha_map.py --apply", unit)
        self.assertIn("ReadWritePaths=/etc/nginx/conf.d", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertNotIn("production-release.service", unit)
        self.assertNotIn("RemainAfterExit=true", unit)

    @unittest.skipUnless(shutil.which("nginx"), "Nginx not installed on local test host")
    def test_real_nginx_accepts_long_regex_map(self):
        planner_spec = importlib.util.spec_from_file_location(
            "planner", Path(__file__).parent / "operations/production_release_sha_map.py")
        planner = importlib.util.module_from_spec(planner_spec)
        planner_spec.loader.exec_module(planner)
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p / "map.conf").write_text(planner.render(["a" * 40, "b" * 40]))
            conf = (
                "pid " + str(p / "nginx.pid") + ";\n"
                "error_log stderr;\nevents {}\nhttp {\n"
                "access_log off;\ninclude " + str(p / "map.conf") + ";\n"
                "server { listen 127.0.0.1:18081; "
                "root /home/kmjprod/current/apps/platform/public; "
                "add_header X-KMJ-Deploy-SHA $kmj_production_release_sha; "
                "location / { return 200 ok; } }\n}\n"
            )
            (p / "nginx.conf").write_text(conf)
            r = subprocess.run([shutil.which("nginx"), "-t", "-p", folder + "/",
                                "-c", str(p / "nginx.conf")],
                               capture_output=True, text=True, timeout=15)
            self.assertEqual(r.returncode, 0, r.stderr)

if __name__ == "__main__":
    unittest.main()
