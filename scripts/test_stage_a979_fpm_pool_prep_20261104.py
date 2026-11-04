"""Disposable source + root-mock contracts; never modify real FPM pool."""
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts/operations/KMJ_STAGE_A979_FPM_POOL_PREP_20261104.py"
spec = importlib.util.spec_from_file_location("kmj_stage_fpm_pool", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

OLD = b"""[kmjstage]
user = kmjstage
group = kmjstage
listen = /run/php/kmjstage-php84-fpm.sock
listen.owner = www-data
pm = ondemand
"""


class DedicatedPoolTests(unittest.TestCase):
    def test_source_compiles_pinned(self):
        compile(SOURCE.read_text(), str(SOURCE), "exec")
        self.assertEqual(m.SHA, "a9796a25a2801cd303a69f5ad468aa9a704e5fff")
        self.assertEqual(m.NEW_NAME, "kmjstage-a979.conf")
        self.assertEqual(m.OLD_POOL.name, "kmjstage.conf")
        self.assertEqual(str(m.NEW_SOCKET), "/run/php/kmjstage-a979-php84-fpm.sock")

    def test_new_config_separate_user_and_early_path(self):
        conf = m.config_bytes().decode()
        self.assertIn("[kmjstage-a979]\n", conf)
        self.assertIn("user = kmjstage\n", conf)
        self.assertIn("group = kmjstage\n", conf)
        self.assertIn("env[APP_ENV] = staging\n", conf)
        self.assertIn("env[LARAVEL_STORAGE_PATH] = " + str(m.STORAGE) + "\n", conf)
        self.assertIn("listen = /run/php/kmjstage-a979-php84-fpm.sock\n", conf)
        self.assertNotIn("listen = /run/php/kmjstage-php84-fpm.sock\n", conf)
        self.assertIn("clear_env = yes\n", conf)
        self.assertIn("security.limit_extensions = .php\n", conf)
        self.assertIn("pm = ondemand\n", conf)
        self.assertNotIn("DB_PASSWORD", conf)
        self.assertNotIn("APP_KEY", conf)

    def test_legacy_pool_scope(self):
        self.assertTrue(m.no_legacy_pool_change(OLD))
        self.assertFalse(m.no_legacy_pool_change(OLD.replace(
            b"user = kmjstage", b"user = www-data")))
        self.assertFalse(m.no_legacy_pool_change(OLD + b"user = kmjstage\n"))
        self.assertFalse(m.no_legacy_pool_change(OLD.replace(
            b"kmjstage-php84-fpm.sock", b"another.sock")))

    def test_unprivileged_host_gate_before_file_write(self):
        with patch.object(sys, "argv", ["prepare.py"]), \
             patch.object(m.os, "geteuid", return_value=1001), \
             patch.object(m, "candidate_scope", side_effect=AssertionError("no target access")):
            with self.assertRaises(SystemExit):
                m.main()
        with patch.object(sys, "argv", ["prepare.py"]), \
             patch.object(m.os, "geteuid", return_value=0), \
             patch.object(m.socket, "gethostname", return_value="not-kmj-elite"), \
             patch.object(m, "candidate_scope", side_effect=AssertionError("no target access")):
            with self.assertRaises(SystemExit):
                m.main()

    @unittest.skipUnless(os.geteuid() == 0, "requires disposable root CI")
    def test_create_once_validated_no_restart_and_no_old_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "kmjstage.conf"
            old.write_bytes(OLD)
            old.chmod(0o644)
            orig = old.read_bytes()
            def valid_dir_fd(path):
                self.assertEqual(path, root)
                return os.open(root, m.DIRFLAGS)
            with patch.object(sys, "argv", ["prepare.py"]), \
                 patch.multiple(m, FPM_DIR=root, OLD_POOL=old,
                                NEW_SOCKET=root/"new-unix.sock"), \
                 patch.object(m.os, "geteuid", return_value=0), \
                 patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
                 patch.object(m, "original_pointers", return_value=True), \
                 patch.object(m, "candidate_scope"), \
                 patch.object(m, "validate_service", return_value=True), \
                 patch.object(m, "root_chain_fd", side_effect=valid_dir_fd), \
                 patch.object(m, "validate_php_config", return_value=True) as validator, \
                 patch.object(m.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=1001)), \
                 patch.object(m.grp, "getgrnam", return_value=SimpleNamespace(gr_gid=1001)):
                self.assertEqual(m.main(), 0)
                validator.assert_called_once()
                with self.assertRaises(SystemExit):
                    m.main()
            new = root / m.NEW_NAME
            self.assertTrue(new.is_file())
            self.assertEqual(new.read_bytes(), m.config_bytes())
            self.assertEqual(stat.S_IMODE(new.stat().st_mode), 0o644)
            self.assertEqual(new.stat().st_uid, 0)
            self.assertEqual(old.read_bytes(), orig)

    @unittest.skipUnless(os.geteuid() == 0, "requires disposable root CI")
    def test_invalid_fpm_conf_removes_only_own_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "kmjstage.conf"
            old.write_bytes(OLD)
            old.chmod(0o644)
            def fd(path):
                self.assertEqual(path, root)
                return os.open(root, m.DIRFLAGS)
            with patch.object(sys, "argv", ["prepare.py"]), \
                 patch.multiple(m, FPM_DIR=root, OLD_POOL=old,
                                NEW_SOCKET=root/"new-unix.sock"), \
                 patch.object(m.os, "geteuid", return_value=0), \
                 patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
                 patch.object(m, "original_pointers", return_value=True), \
                 patch.object(m, "candidate_scope"), \
                 patch.object(m, "validate_service", return_value=True), \
                 patch.object(m, "root_chain_fd", side_effect=fd), \
                 patch.object(m, "validate_php_config", return_value=False), \
                 patch.object(m.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=1001)), \
                 patch.object(m.grp, "getgrnam", return_value=SimpleNamespace(gr_gid=1001)):
                with self.assertRaises(SystemExit) as exc:
                    m.main()
                self.assertEqual(exc.exception.code, 2)
            self.assertFalse((root / m.NEW_NAME).exists())
            self.assertEqual(old.read_bytes(), OLD)

    def test_config_validation_is_read_only_and_no_service_reload(self):
        with patch.object(m.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            self.assertTrue(m.validate_php_config())
            self.assertEqual(run.call_args.args[0], ["/usr/sbin/php-fpm8.4", "-t"])
        source = SOURCE.read_text()
        for forbidden in (
            "systemctl reload", "systemctl restart", "php artisan",
            "nginx -s", "git reset", "git clean",
            "DROP ROLE", "DROP DATABASE", "os.chown(", "os.symlink(",
        ):
            self.assertNotIn(forbidden, source)
        for label in ("LEGACY_STAGING_POOL", "UNTOUCHED", "PHP_FPM_SERVICE",
                      "NOT_RELOADED", "STAGING_DATABASE_MIGRATIONS", "NOT_RUN",
                      "STAGING_ACTIVATION", "NOT_ATTEMPTED"):
            self.assertIn(label, source)


if __name__ == "__main__":
    unittest.main()
