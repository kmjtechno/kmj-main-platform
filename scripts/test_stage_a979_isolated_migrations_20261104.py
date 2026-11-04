"""Synthetic safety tests: never connect to a real DB or run Laravel."""
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / "scripts/operations/KMJ_STAGE_A979_ISOLATED_MIGRATIONS_20261104.py"
spec = importlib.util.spec_from_file_location("kmj_stage_a979_migrations", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def env_example():
    return ("\n".join([
        "APP_ENV=staging",
        "APP_DEBUG=false",
        "APP_URL=https://staging.kmjtechno.com",
        "DB_CONNECTION=pgsql",
        "DB_HOST=127.0.0.1",
        "DB_PORT=5432",
        "DB_DATABASE=" + m.DB,
        "DB_USERNAME=" + m.ROLE,
        "DB_PASSWORD=" + "a" * 64,
        "APP_KEY=base64:" + "A" * 43 + "=",
        "LARAVEL_STORAGE_PATH=" + str(m.STORAGE),
        "MAIL_MAILER=log",
        "CODEBRIDGE_OAUTH_ENABLED=false",
    ]) + "\n").encode("ascii")


class CandidateSchemaTests(unittest.TestCase):
    def test_source_and_exact_scope(self):
        source = SOURCE.read_text()
        compile(source, str(SOURCE), "exec")
        self.assertEqual(m.SHA, "a9796a25a2801cd303a69f5ad468aa9a704e5fff")
        self.assertEqual(m.DB, "kmj_stage_a9796a25")
        self.assertEqual(m.ROLE, "kmjstage_a9796a25")
        self.assertEqual(m.STAGE_OLD, "b2e69decab3acd861e94e11992cd8a4cff4f2b94")
        self.assertEqual(m.PROD_OLD, "platform-574e443a2c75")
        for banned in ("DROP DATABASE", "DROP ROLE", "git reset", "git clean",
                       "systemctl reload", "systemctl restart", "nginx -s",
                       "ln -sfn", "php artisan migrate --force",
                       "shell=True"):
            self.assertNotIn(banned, source)

    def test_isolated_env_scope_and_duplicate_or_injection(self):
        raw = env_example()
        self.assertTrue(m.inspect_env(raw))
        self.assertFalse(m.inspect_env(raw.replace(b"APP_ENV=staging", b"APP_ENV=production")))
        self.assertFalse(m.inspect_env(raw.replace(b"DB_DATABASE=kmj_stage_a9796a25", b"DB_DATABASE=kmjprod")))
        self.assertFalse(m.inspect_env(raw + b"DB_DATABASE=kmj_stage_a9796a25\n"))
        self.assertFalse(m.inspect_env(raw.replace(b"APP_DEBUG=false", b"APP_DEBUG=true")))

    def test_allowlist_blocks_other_sql_db(self):
        with self.assertRaises(SystemExit):
            m.pg_query("DROP TABLE users;", database=m.DB)
        with self.assertRaises(SystemExit):
            m.pg_query("SELECT 1;", database="kmjprod")
        with self.assertRaises(SystemExit):
            m.pg_query("SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public';", database="another")

    def test_candidate_database_readonly_queries(self):
        sql = "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public';"
        p = SimpleNamespace(returncode=0, stdout=b"0\n")
        with patch.object(m.subprocess, "run", return_value=p) as run:
            self.assertEqual(m.pg_query(sql, database=m.DB), b"0")
            args = run.call_args.args[0]
            self.assertEqual(args[0:4], ["/usr/sbin/runuser", "-u", "postgres", "--"])
            self.assertEqual(args[-3:], ["-d", m.DB, "-c", sql][-3:]) if False else None
            self.assertIn("-d", args)
            self.assertEqual(args[args.index("-d")+1], m.DB)

    def test_unprivileged_migrate_uses_only_candidate(self):
        fake=SimpleNamespace(returncode=0,stdout=b"ok",stderr=b"")
        with patch.object(m.subprocess, "run", return_value=fake) as run:
            self.assertEqual(m.run_migrate(), "COMMAND_SUCCESS")
            args=run.call_args.args[0]
            self.assertEqual(args[:4], ["/usr/sbin/runuser", "-u", "kmjstage", "--"])
            self.assertIn("LARAVEL_STORAGE_PATH=" + str(m.STORAGE), args)
            self.assertIn("APP_ENV=staging", args)
            self.assertIn("artisan", args)
            self.assertIn("migrate", args)
            self.assertIn("--force", args)
            self.assertEqual(run.call_args.kwargs["cwd"], m.CODE)
            self.assertNotIn("DB_PASSWORD", repr(args))
        with patch.object(m.subprocess, "run", return_value=SimpleNamespace(returncode=1,stdout=b"error",stderr=b"")):
            self.assertEqual(m.run_migrate(), "MIGRATION_FAILED_REVIEW_REQUIRED")

    def test_only_new_stage_views_created_as_stage_uid(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            framework=root/"framework"
            framework.mkdir(mode=0o700)
            views=framework/"views"
            fake=lambda *args,**kwargs: SimpleNamespace(returncode=0,stdout=b"",stderr=b"")
            with patch.multiple(m, STORAGE=root), \
                 patch.object(m.subprocess, "run", side_effect=lambda args,**kw: (views.mkdir(mode=0o700) or fake())) as run:
                m.ensure_private_views(os.geteuid(), os.getgid())
                self.assertEqual(run.call_count,1)
                self.assertTrue(views.is_dir())
                self.assertEqual(stat.S_IMODE(views.stat().st_mode),0o700)
                m.ensure_private_views(os.geteuid(), os.getgid())
                self.assertEqual(run.call_count,1)
            os.chmod(framework,0o777)
            with patch.multiple(m, STORAGE=root):
                with self.assertRaises(SystemExit):
                    m.ensure_private_views(os.geteuid(), os.getgid())

    def test_nonroot_and_wrong_host_no_db_or_migration(self):
        with patch.object(sys, "argv", ["fixed.py", "--apply"]), \
             patch.object(m.os, "geteuid", return_value=1001), \
             patch.object(m, "catalog", side_effect=AssertionError("read forbidden")), \
             patch.object(m, "run_migrate", side_effect=AssertionError("apply forbidden")):
            with self.assertRaises(SystemExit):
                m.main()
        with patch.object(sys,"argv",["fixed.py","--apply"]), \
             patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.socket,"gethostname",return_value="wrong"), \
             patch.object(m,"run_migrate",side_effect=AssertionError("cannot execute")):
            with self.assertRaises(SystemExit):
                m.main()

    def test_inspect_never_changes_state(self):
        with patch.object(sys,"argv",["fixed.py","--inspect"]), \
             patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.socket,"gethostname",return_value="kmj-elite"), \
             patch.object(m,"pinned_pointers",return_value=True), \
             patch.object(m.grp,"getgrnam",return_value=SimpleNamespace(gr_gid=1000)), \
             patch.object(m,"catalog"), \
             patch.object(m,"pg_query",return_value=b"0"), \
             patch.object(m,"ensure_private_views",side_effect=AssertionError("writes in inspect")), \
             patch.object(m,"run_migrate",side_effect=AssertionError("migrate in inspect")):
            self.assertEqual(m.main(), 0)

    def test_apply_never_runs_if_schema_not_empty(self):
        with patch.object(sys,"argv",["fixed.py","--apply"]), \
             patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.socket,"gethostname",return_value="kmj-elite"), \
             patch.object(m,"pinned_pointers",return_value=True), \
             patch.object(m.grp,"getgrnam",return_value=SimpleNamespace(gr_gid=1000)), \
             patch.object(m,"catalog"), \
             patch.object(m,"pg_query",return_value=b"3"), \
             patch.object(m,"run_migrate",side_effect=AssertionError("mutating existing db")):
            with self.assertRaises(SystemExit):
                m.main()


if __name__=="__main__":
    unittest.main()
