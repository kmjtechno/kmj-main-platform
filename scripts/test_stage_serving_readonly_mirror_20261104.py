"""Synthetic disposable-root tests: never touch KMJ stage or production."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts/operations/KMJ_STAGE_SERVING_READONLY_MIRROR_20261104.py"
spec = importlib.util.spec_from_file_location("stage_serving_mirror", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def fixture(path):
    app = path / "app"
    (app / "public/build/assets").mkdir(parents=True)
    (app / "vendor").mkdir()
    (app / "bootstrap/cache").mkdir(parents=True)
    (app / "storage/app").mkdir(parents=True)
    (app / "node_modules/private").mkdir(parents=True)
    (app / ".env").write_text("DO_NOT_COPY=secret")
    (app / ".env.local").write_text("DO_NOT_COPY=secret")
    (app / ".env.example").write_text("APP_KEY=")
    (app / "storage/app/customer.txt").write_text("DO_NOT_COPY")
    (app / "bootstrap/cache/config.php").write_text("DO_NOT_COPY")
    (app / "node_modules/private/mod.js").write_text("DO_NOT_COPY")
    (app / "vendor/autoload.php").write_text("<?php")
    (app / "public/index.php").write_text("<?php require __DIR__.'/../vendor/autoload.php';")
    (app / "public/build/manifest.json").write_text(json.dumps({
        "resources/js/pages/services/codebridge-workspace.tsx": {
            "file": "assets/workspace-a979.js"
        }
    }))
    (app / "public/build/assets/workspace-a979.js").write_text("compiled asset")
    return app


@unittest.skipUnless(os.geteuid() == 0, "requires disposable CI root fixture")
class MirrorSourcePermissions(unittest.TestCase):
    def test_exact_pins_and_no_activation(self):
        s = SOURCE.read_text()
        compile(s, str(SOURCE), "exec")
        self.assertEqual(m.SHA, "a9796a25a2801cd303a69f5ad468aa9a704e5fff")
        self.assertIn("platform-574e443a2c75", s)
        self.assertIn("b2e69decab3acd861e94e11992cd8a4cff4f2b94", s)
        for forbidden in ("systemctl ", "php artisan", "nginx -s", "ssh ", "git reset ",
                          "git clean ", "os.symlink(", "subprocess.", "os.system(", "chmod 0777"):
            self.assertNotIn(forbidden, s)
        for required in ("NO_CLOBBER_", "SOURCE_LINK_OR_SPECIAL",
                         "STAGING_RUNTIME_ENV", "NOT_PRESENT", "STAGING_NGINX_ROUTE",
                         "NOT_CHANGED", "STAGING_ACTIVATION", "NOT_ATTEMPTED"):
            self.assertIn(required, s)

    def test_disposable_dual_copy_drops_secrets_and_static_separated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            from_app = fixture(root)
            code = root / "code"
            pub = root / "static"
            code.mkdir()
            pub.mkdir()
            fd = os.open(from_app, m.DIR_FLAGS)
            stats = {"files": 0, "bytes": 0}
            try:
                m.copy_dir(fd, code, os.getgid(), "", 0, os.fstat(fd).st_dev, stats)
                pubfd = os.open("public", m.DIR_FLAGS, dir_fd=fd)
                try:
                    m.copy_dir(pubfd, pub, os.getgid(), "", 0, os.fstat(fd).st_dev, stats)
                finally:
                    os.close(pubfd)
            finally:
                os.close(fd)
            self.assertGreater(stats["files"], 5)
            self.assertFalse((code / ".env").exists())
            self.assertFalse((code / ".env.local").exists())
            self.assertFalse((code / "storage").exists())
            self.assertFalse((code / "node_modules").exists())
            self.assertFalse((code / "bootstrap/cache").exists())
            self.assertTrue((code / "vendor/autoload.php").exists())
            self.assertFalse((pub / "vendor").exists())
            self.assertFalse((pub / "storage").exists())
            self.assertTrue((pub / "build/assets/workspace-a979.js").is_file())
            self.assertEqual(stat.S_IMODE((code / "vendor/autoload.php").stat().st_mode), 0o440)
            self.assertEqual(stat.S_IMODE((code / "vendor").stat().st_mode), 0o550)
            m.public_manifest_check(code, pub)

    def test_symlink_hardlink_and_writable_file_rejected(self):
        for unsafe in ("symlink", "hardlink", "writable"):
            with self.subTest(unsafe=unsafe), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                source = fixture(root)
                if unsafe == "symlink":
                    (source / "steal").symlink_to("/etc/passwd")
                elif unsafe == "hardlink":
                    (source / "one").write_text("file")
                    os.link(source / "one", source / "two")
                else:
                    (source / "world_writable").write_text("bad")
                    os.chmod(source / "world_writable", 0o666)
                out = root / "dest"
                out.mkdir()
                fd = os.open(source, m.DIR_FLAGS)
                try:
                    with self.assertRaises(SystemExit) as err:
                        m.copy_dir(fd, out, os.getgid(), "", 0, os.fstat(fd).st_dev,
                                   {"files": 0, "bytes": 0})
                    self.assertEqual(err.exception.code, 2)
                finally:
                    os.close(fd)

    def test_file_modes_never_group_write_and_ownership_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "input.txt"
            p.write_text("data")
            dirfd = os.open(root, m.DIR_FLAGS)
            dst = root / "out"
            try:
                m.copied_file(dirfd, p.name, dst, os.getgid(),
                              {"files": 0, "bytes": 0})
            finally:
                os.close(dirfd)
            s = os.lstat(dst)
            self.assertEqual(s.st_uid, 0)
            self.assertEqual(stat.S_IMODE(s.st_mode), 0o440)

    def test_atomic_no_clobber_refuses_existing_release(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scratch = root / "temp"
            scratch.mkdir()
            target = root / m.SHA
            target.mkdir()
            fd = os.open(root, m.DIR_FLAGS)
            try:
                with self.assertRaises(SystemExit):
                    m.rename_noreplace(scratch, fd, m.SHA)
                self.assertTrue(target.exists())
                self.assertTrue(scratch.exists())
            finally:
                os.close(fd)

    def test_nonroot_and_wrong_host_cannot_mutate(self):
        with patch.object(m.os, "geteuid", return_value=1000), \
             patch.object(m.os, "mkdir", side_effect=AssertionError("no writes")):
            with self.assertRaises(SystemExit):
                m.main()
        with patch.object(m.os, "geteuid", return_value=0), \
             patch.object(m.socket, "gethostname", return_value="otherhost"), \
             patch.object(m.os, "mkdir", side_effect=AssertionError("no writes")):
            with self.assertRaises(SystemExit):
                m.main()


if __name__ == "__main__":
    unittest.main()
