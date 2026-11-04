"""Offline contracts for immutable private root stage source-only materializer.

All filesystem test mutations occur inside TemporaryDirectory on CI, never
on connected servers. No network, privileged commands or deployment.
"""
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[1] / "scripts/operations/KMJ_ROOT_STAGE_CODE_MATERIALIZE_20261104.py"
spec = importlib.util.spec_from_file_location("kmj_root_stage_source", FILE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def make_fixture(root):
    s = root / "from"
    s.mkdir()
    (s / ".git").mkdir()
    (s / ".git/HEAD").write_text(m.SHA + "\n")
    (s / ".git/config").write_text("[core]\nfsmonitor = /tmp/arbitrary\n")
    (s / ".git/hooks").mkdir()
    (s / ".git/hooks/post-checkout").write_text("DO_NOT_COPY")
    app = s / "apps/platform"
    (app / "public/build/assets").mkdir(parents=True)
    (app / "vendor").mkdir()
    (app / "storage/app").mkdir(parents=True)
    (app / "bootstrap/cache").mkdir(parents=True)
    (app / "node_modules/private").mkdir(parents=True)
    (app / "vendor/bin").mkdir()
    (app / ".env").write_text("APP_KEY=DO_NOT_COPY")
    (app / ".env.local").write_text("DB_PASSWORD=DO_NOT_COPY")
    (app / ".env.example").write_text("APP_KEY=\n")
    (app / "storage/app/customer_private.txt").write_text("DO_NOT_COPY")
    (app / "bootstrap/cache/config.php").write_text("DO_NOT_COPY")
    (app / "node_modules/private/mod.js").write_text("DO_NOT_COPY")
    (app / "vendor/bin/tool").write_text("DO_NOT_COPY")
    (app / "vendor/autoload.php").write_text("<?php")
    (app / "public/build/manifest.json").write_text(json.dumps({
        "resources/js/pages/services/codebridge-workspace.tsx": {
            "file": "assets/workspace-a979.js"
        }
    }))
    (app / "public/build/assets/workspace-a979.js").write_text("safe compiled fixture")
    return s


class PrivateSourceTests(unittest.TestCase):
    def test_compiles_and_is_pinned(self):
        src = FILE.read_text()
        compile(src, str(FILE), "exec")
        self.assertEqual(m.SHA, "a9796a25a2801cd303a69f5ad468aa9a704e5fff")
        self.assertEqual(m.ANCHOR, Path("/var/lib/kmj-main-platform-stage-releases"))
        self.assertIn("platform-574e443a2c75", src)
        self.assertIn("b2e69decab3acd861e94e11992cd8a4cff4f2b94", src)
        self.assertIn("PASS_CODE_SNAPSHOT_ONLY", src)
        self.assertIn("STAGING_RUNTIME_ENV", src)
        self.assertIn("NOT_PRESENT", src)

    def test_fixture_source_only_copy_excludes_private_storage_and_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = make_fixture(root)
            dest = root / "to"
            dest.mkdir()
            fd = os.open(source, m.DIR_FLAGS)
            seen = {"files": 0, "bytes": 0, "digest_checks": 0}
            try:
                m.copy_tree(fd, dest, "", 0, seen, os.fstat(fd).st_dev)
            finally:
                os.close(fd)
            self.assertTrue(m.inspect_copy(dest))
            self.assertGreater(seen["files"], 3)
            self.assertEqual(seen["files"], seen["digest_checks"])
            self.assertFalse((dest / "apps/platform/.env").exists())
            self.assertFalse((dest / "apps/platform/.env.local").exists())
            self.assertFalse((dest / ".git/config").exists())
            self.assertFalse((dest / ".git/hooks").exists())
            self.assertTrue((dest / "apps/platform/.env.example").exists())
            self.assertFalse((dest / "apps/platform/storage/app/customer_private.txt").exists())
            self.assertFalse((dest / "apps/platform/bootstrap/cache/config.php").exists())
            self.assertFalse((dest / "apps/platform/node_modules").exists())
            self.assertFalse((dest / "apps/platform/vendor/bin").exists())
            self.assertTrue((dest / "apps/platform/vendor/autoload.php").exists())

    def test_symlink_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = make_fixture(root)
            (source / "evil").symlink_to("/etc/passwd")
            dest = root / "copy"
            dest.mkdir()
            fd = os.open(source, m.DIR_FLAGS)
            try:
                with self.assertRaises(SystemExit) as e:
                    m.copy_tree(fd, dest, "", 0,
                                {"files": 0, "bytes": 0, "digest_checks": 0},
                                os.fstat(fd).st_dev)
                self.assertEqual(e.exception.code, 2)
            finally:
                os.close(fd)

    def test_hardlink_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = make_fixture(root)
            (source / "source.txt").write_text("owned")
            os.link(source / "source.txt", source / "hardlinked.txt")
            dest = root / "copy"
            dest.mkdir()
            fd = os.open(source, m.DIR_FLAGS)
            try:
                with self.assertRaises(SystemExit):
                    m.copy_tree(fd, dest, "", 0,
                                {"files": 0, "bytes": 0, "digest_checks": 0},
                                os.fstat(fd).st_dev)
            finally:
                os.close(fd)

    def test_private_anchor_publication_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            temp = root / "candidate"
            temp.mkdir()
            target = root / m.SHA
            target.mkdir()
            fd = os.open(root, m.DIR_FLAGS)
            try:
                with self.assertRaises(SystemExit):
                    m.publish_noclobber(temp, fd)
                self.assertTrue(target.is_dir())
                self.assertTrue(temp.is_dir())
            finally:
                os.close(fd)

    def test_wrong_host_or_unprivileged_does_not_copy(self):
        with patch.object(m.os, "geteuid", return_value=1000), \
             patch.object(m, "git_probe", side_effect=AssertionError("no probe")), \
             patch.object(m, "trusted_anchor", side_effect=AssertionError("no write")):
            with self.assertRaises(SystemExit):
                m.main()

    def test_no_live_or_privilege_bypass(self):
        s = FILE.read_text()
        for forbidden in (
            "systemctl ", "nginx -s", "php artisan", "pg_dump ",
            "git reset ", "git clean ", "os.symlink(", "os.chown(",
            "os.fchown(", "subprocess.Popen(", "shell=True", "chmod 0777",
        ):
            self.assertNotIn(forbidden, s)
        for required in (
            "os.O_NOFOLLOW", "os.O_EXCL", "renameat2", "NO_CLOBBER_",
            "SOURCE_SYMLINK_OR_SPECIAL", "SOURCE_FILE_CHANGED",
            "SOURCE_GIT_NOT_EXACT_CLEAN", "SOURCE_CHANGED_POSTCOPY",
            "STAGING_WEB_ROUTE", "NOT_CHANGED",
            "STAGING_APPROVAL", "NOT_CREATED", "STAGING_SEAL",
        ):
            self.assertIn(required, s)


if __name__ == "__main__":
    unittest.main()
