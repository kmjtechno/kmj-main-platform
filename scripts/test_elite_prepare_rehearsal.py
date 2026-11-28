import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

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
        self.assertEqual(len(sql), 5)
        self.assertIn('SCRAM-SHA-256$4096:', sql[0])
        self.assertNotIn('c' * 32, sql[0])
        self.assertIn('REVOKE ALL ON DATABASE', sql[4])
        self.assertIn("NOSUPERUSER NOCREATEDB NOCREATEROLE", sql[0])
        self.assertIn("kmj-disposable-rehearsal:" + "d" * 32, sql[2])
        for bad in (("x; DROP", "c" * 32, "d" * 32), (name, "c'; --" + "c" * 26, "d" * 32),
                    (name, "c" * 32, "NOTHEX" * 6), ("production_db", "c" * 32, "d" * 32)):
            with self.assertRaises(ValueError):
                pr.sql_create(*bad)
        with self.assertRaises(ValueError):
            pr.sql_drop("kmj_platform", "d" * 32)

    def test_psql_secret_not_in_argv(self):
        sql = pr.sql_create(pr.names(SHA), "c" * 32, "d" * 32)[0]
        with patch.object(pr.subprocess, "run") as run:
            run.return_value.returncode = 0
            pr.psql([sql])
            args, kwargs = run.call_args
            self.assertNotIn("-c", args[0])
            self.assertNotIn(sql, args[0])
            self.assertIn(b"SCRAM-SHA-256", kwargs["input"])
            self.assertNotIn(b"c" * 32, kwargs["input"])

    def test_hba_prefix_and_fail_closed_before_workspace(self):
        name = pr.names(SHA)
        old = b"local all all peer\n"
        planned = pr.isolation.proposal(old, name)
        self.assertTrue(planned.endswith(old))
        self.assertTrue(planned.startswith(pr.isolation.prefix(name)))
        for rule in (f"host {name} {name} 127.0.0.1/32 scram-sha-256",
                     f"local replication {name} reject", f"local all {name} reject",
                     f"host replication {name} all reject", f"host all {name} all reject"):
            self.assertIn(rule.encode(), planned)
        with self.assertRaises(ValueError):
            pr.isolation.proposal(planned, name)
        with tempfile.TemporaryDirectory() as d:
            base = pathlib.Path(d)
            with self.assertRaisesRegex(ValueError, "ISOLATION_FAILED"):
                def fail(*args):
                    raise ValueError("ISOLATION_FAILED")
                pr.prepare(SHA, EXP, lambda *a: self.fail("ran copy"),
                           lambda *a: self.fail("ran SQL"), base, base / "config",
                           lambda *a: True, isolation_check=fail)
            self.assertFalse((base / SHA[:12]).exists())

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
            runs, sqls, seals = [], [], []
            pr.prepare(SHA, EXP, lambda a, u=None: runs.append(a), lambda s: sqls.append(s), base, cfg,
                       lambda p, r: True, seal=seals.append, isolation_check=lambda *a: None)
            self.assertEqual(sqls[0][0].split()[0:2], ["CREATE", "ROLE"])
            self.assertEqual(len(sqls), 1)
            self.assertFalse(any("DROP " in statement for batch in sqls for statement in batch))
            self.assertEqual(seals, [base / SHA[:12]])
            self.assertFalse(any(a[0] == '/usr/bin/chown' for a in runs))
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
            with self.assertRaises(ValueError):
                pr.cleanup(SHA, EXP, lambda *a: None, sqls.append, base, cfg, uid=os.getuid(), parent_check=lambda *a: True)
            self.assertEqual(sqls, [])
            self.assertEqual(cfg.read_text(), "existing")

    def test_cleanup_requires_both_nonce_comments_and_never_forces(self):
        name, nonce = pr.names(SHA), "d" * 32
        query = pr.cleanup_query(name, nonce)
        self.assertIn("pg_database", query)
        self.assertIn("pg_authid", query)
        self.assertIn("pg_auth_members", query)
        self.assertEqual(query.count("kmj-disposable-rehearsal:" + nonce), 2)
        self.assertEqual(pr.sql_drop(name, nonce), ['DROP DATABASE "' + name + '"', 'DROP ROLE "' + name + '"'])
        with self.assertRaises(ValueError):
            pr.sql_drop(name, "bad")

    def test_cleanup_preserves_state_without_owner_and_on_sql_error(self):
        with tempfile.TemporaryDirectory() as d:
            base = pathlib.Path(d)
            cfg = base / "release-rehearsal.json"
            work = base / SHA[:12]
            work.mkdir()
            name, nonce = pr.names(SHA), "d" * 32
            fixed = pathlib.Path("/var/lib/kmj-release-rehearsal") / SHA[:12]
            record = pr.make_config(name, "c" * 32, nonce, fixed / "previous", fixed / "candidate")
            record.update(approvedSha=SHA, expectedCurrentRelease=EXP)
            cfg.write_text(json.dumps(record))
            cfg.chmod(0o600)
            sqls = []
            with self.assertRaisesRegex(ValueError, "BLOCKED_CLEANUP_OWNERSHIP_UNVERIFIED"):
                pr.cleanup(SHA, EXP, sql_runner=sqls.append, base=base, config_path=cfg,
                           owner_query=lambda *a: False, uid=os.getuid(), parent_check=lambda *a: True)
            self.assertEqual(sqls, [])
            self.assertTrue(work.exists() and cfg.exists())
            def fail(sql):
                raise ValueError("active database")
            with self.assertRaises(ValueError):
                pr.cleanup(SHA, EXP, sql_runner=fail, base=base, config_path=cfg,
                           owner_query=lambda *a: True, uid=os.getuid(), parent_check=lambda *a: True)
            self.assertTrue(work.exists() and cfg.exists())
            pr.cleanup(SHA, EXP, sql_runner=sqls.append, base=base, config_path=cfg,
                       owner_query=lambda *a: True, uid=os.getuid(), parent_check=lambda *a: True)
            self.assertFalse(work.exists() or cfg.exists())
            self.assertEqual(len(sqls), 1)

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
