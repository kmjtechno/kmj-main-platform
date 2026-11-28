import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

OPS = pathlib.Path(__file__).resolve().parent / "operations"
sys.path.insert(0, str(OPS))
import elite_prepare_rehearsal as pr  # noqa: E402
import elite_collect_rollback_rehearsal_receipt as rc  # noqa: E402

SHA = "a" * 40
EXP = "platform-" + "b" * 12


def make_tree(root):
    for f in ("artisan", "vendor/autoload.php", "public/index.php", ".env", ".env.production",
              ".env.example", "bootstrap/cache/config.php", "storage/app/secret.txt", "app/x.php"):
        p = root / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    (root / "public" / "storage").symlink_to("/etc")


class PrepareTests(unittest.TestCase):
    def test_exact_full_sha_staging_path(self):
        prev, cand = pr.tree_paths(SHA, EXP)
        self.assertEqual(prev, pr.PREV_ROOT / EXP / 'apps' / 'platform')
        self.assertEqual(cand, pr.CAND_ROOT / SHA / 'apps' / 'platform')
        self.assertNotEqual(cand, pr.CAND_ROOT / ('platform-' + SHA[:12]) / 'apps' / 'platform')

    def test_sql_is_fixed_shape_and_rejects_unsafe_values(self):
        name = pr.names(SHA)
        sql = pr.sql_create(name, "c" * 32, "d" * 32)
        self.assertEqual(len(sql), 3)
        self.assertIn("NOSUPERUSER NOCREATEDB NOCREATEROLE", sql[0])
        self.assertIn("kmj-disposable-rehearsal:" + "d" * 32, sql[2])
        for bad in (("x; DROP", "c" * 32, "d" * 32), (name, "c'; --" + "c" * 26, "d" * 32),
                    (name, "c" * 32, "NOTHEX" * 6), ("production_db", "c" * 32, "d" * 32)):
            with self.assertRaises(ValueError):
                pr.sql_create(*bad)
        with self.assertRaises(ValueError):
            pr.sql_drop("kmj_platform")

    def test_config_is_accepted_by_the_rehearsal_collector_and_names_pass_its_pattern(self):
        cfg = pr.make_config(pr.names(SHA), "c" * 32, "d" * 32, "/p", "/c")
        for key in cfg["env"]:
            self.assertRegex(key, rc.ENV_KEY)
        import importlib.util
        spec = importlib.util.spec_from_file_location("reh", OPS / "rehearse-app-http-db-rollback-20261029.py")
        reh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reh)
        db = reh.validate_database(cfg["env"])
        self.assertEqual(db["DB_HOST"], "127.0.0.1")

    @unittest.skipUnless(shutil.which("rsync"), "rsync not installed")
    def test_real_rsync_copy_excludes_secrets_caches_storage_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = pathlib.Path(d) / "src", pathlib.Path(d) / "dst"
            make_tree(src)
            dst.mkdir()
            subprocess.run(pr.rsync_argv(src, dst), check=True)
            for kept in ("artisan", "vendor/autoload.php", "public/index.php", ".env.example", "app/x.php"):
                self.assertTrue((dst / kept).is_file(), kept)
            for gone in (".env", ".env.production", "bootstrap/cache/config.php",
                         "storage/app/secret.txt", "public/storage"):
                self.assertFalse(os.path.lexists(dst / gone), gone)

    def test_prepare_never_cleans_before_creating(self):
        with tempfile.TemporaryDirectory() as d:
            base = pathlib.Path(d) / "base"
            base.mkdir()
            cfg = pathlib.Path(d) / "release-rehearsal.json"
            runs, sqls = [], []
            pr.prepare(SHA, EXP, lambda a, u=None: runs.append(a), lambda s: sqls.append(s), base, cfg,
                       lambda p, r: True)
            self.assertEqual(sqls[0][0].split()[0:2], ["CREATE", "ROLE"])
            self.assertEqual(len(sqls), 1)
            self.assertFalse(any("DROP " in statement for batch in sqls for statement in batch))
            self.assertTrue(any(a[0] == '/usr/bin/chown' for a in runs))
            self.assertEqual(sum(1 for a in runs if a[0] == '/usr/bin/rsync'), 2)
            self.assertEqual(oct(cfg.stat().st_mode & 0o777), "0o600")
            self.assertEqual(json.loads(cfg.read_text())["env"]["DB_HOST"], "127.0.0.1")

    def test_existing_state_and_cleanup_fail_without_sql(self):
        with tempfile.TemporaryDirectory() as d:
            base = pathlib.Path(d)
            cfg = base / "release-rehearsal.json"
            cfg.write_text("existing")
            sqls = []
            with self.assertRaisesRegex(ValueError, "BLOCKED_EXISTING_REHEARSAL"):
                pr.prepare(SHA, EXP, lambda *a: None, sqls.append, base, cfg, lambda p, r: True)
            with self.assertRaisesRegex(ValueError, "BLOCKED_CLEANUP_OWNERSHIP_UNVERIFIED"):
                pr.cleanup(SHA, lambda *a: None, sqls.append, base, cfg)
            self.assertEqual(sqls, [])
            self.assertEqual(cfg.read_text(), "existing")

    def test_untrusted_tree_blocks_before_any_database_change(self):
        sqls = []
        with self.assertRaises(ValueError):
            pr.prepare(SHA, EXP, lambda *a: None, lambda s: sqls.append(s), pathlib.Path("/nonexistent"),
                       pathlib.Path("/nonexistent/c.json"), lambda p, r: False)
        self.assertEqual(sqls, [])

    def test_real_tree_rejects_symlink_and_foreign_root(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d) / "releases"
            tree = root / EXP / "apps" / "platform"
            make_tree(tree)
            self.assertTrue(pr.real_tree(tree, root))
            self.assertFalse(pr.real_tree(tree, pathlib.Path(d) / "other"))
            link = root / "link"
            link.symlink_to(root / EXP)
            self.assertFalse(pr.real_tree(link / "apps" / "platform", root))

    def test_cli_guards_and_source_safety(self):
        self.assertEqual(pr.main(["x", "--write", "bad", EXP]), 2)
        self.assertEqual(pr.main(["x", "--nope", SHA, EXP]), 2)
        if os.geteuid() != 0:
            self.assertEqual(pr.main(["x", "--write", SHA, EXP]), 2)
        src = (OPS / "elite_prepare_rehearsal.py").read_text()
        for bad in ("shell=True", "os.system", "systemctl", "DROP DATABASE kmj", "production-release"):
            self.assertNotIn(bad, src)
        self.assertEqual(pr.PREV_ROOT, pathlib.Path("/home/kmjprod/releases"))


if __name__ == "__main__":
    unittest.main()
