import importlib.util
import os
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "rehearse", ROOT / "scripts/operations/rehearse-app-http-db-rollback-20261029.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def tree(base: Path, name: str, extra=()):
    root = base / name
    (root / "vendor").mkdir(parents=True)
    (root / "public").mkdir()
    for f in ("artisan", "vendor/autoload.php", "public/index.php", *extra):
        (root / f).write_text("x")
    return root


class Guards(unittest.TestCase):
    def test_database_name_must_be_disposable(self):
        for bad in ("kmj_main", "kmj_production", "kmj_rehearsal;drop", "KMJ_REHEARSAL", ""):
            with self.assertRaises(mod.Blocked, msg=bad):
                mod.validate_database({"DB_DATABASE": bad, "DB_USERNAME": "u", "DB_HOST": "127.0.0.1"})
        ok = mod.validate_database({"DB_DATABASE": "kmj_release_qa", "DB_USERNAME": "kmj_qa", "DB_HOST": "127.0.0.1"})
        self.assertEqual(ok["DB_DATABASE"], "kmj_release_qa")

    def test_remote_host_refused(self):
        for host in ("db.example.com", "10.0.0.5", "/nonexistent/socket", "/tmp/../etc"):
            with self.assertRaises(mod.Blocked, msg=host):
                mod.validate_database({"DB_DATABASE": "kmj_rehearsal", "DB_USERNAME": "u", "DB_HOST": host})

    def test_socket_directory_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            got = mod.validate_database({"DB_DATABASE": "kmj_rehearsal_a1", "DB_USERNAME": "u", "DB_HOST": d})
            self.assertEqual(got["DB_HOST"], d)

    def test_tree_requires_complete_laravel_and_no_env(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            good = tree(base, "good")
            self.assertEqual(mod.validate_tree(str(good), "X"), good.resolve())
            with self.assertRaises(mod.Blocked):
                mod.validate_tree(str(tree(base, "withenv", (".env",))), "X")
            with self.assertRaises(mod.Blocked):
                mod.validate_tree(str(tree(base, "withenvprod", (".env.production",))), "X")
            tree(base, "withexample", (".env.example",))
            mod.validate_tree(str(base / "withexample"), "X")
            (base / "empty").mkdir()
            with self.assertRaises(mod.Blocked):
                mod.validate_tree(str(base / "empty"), "X")
            (base / "link").symlink_to(good)
            with self.assertRaises(mod.Blocked):
                mod.validate_tree(str(base / "link"), "X")
            with self.assertRaises(mod.Blocked):
                mod.validate_tree("", "X")

    def test_live_release_pointer_refused(self):
        with self.assertRaises(mod.Blocked):
            mod.validate_tree("/home/kmjprod/current/apps/platform", "X")


    def test_resolved_live_release_and_symlinked_parent_are_rejected(self):
        # CI cannot rely on a real /home/kmjprod release being present.
        # Substitute disposable roots and exercise the exact same path guard.
        self.assertIn(Path("/home/kmjprod"), mod.FORBIDDEN_RUNTIME_ROOTS)
        self.assertIn(Path("/home/kmjstage"), mod.FORBIDDEN_RUNTIME_ROOTS)
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            prod, stage = base / "prod", base / "stage"
            with patch.object(mod, "FORBIDDEN_RUNTIME_ROOTS", (prod, stage)):
                for root in (prod, stage):
                    apps = root / "releases" / "platform-test" / "apps"
                    apps.mkdir(parents=True)
                    live = tree(apps, "platform")
                    with self.assertRaisesRegex(mod.Blocked, "TREE_IS_LIVE_RELEASE_POINTER"):
                        mod.validate_tree(str(live), "X")

                    # The path itself is not a symlink, but an ancestor is.
                    alias = base / ("alias-prod" if root == prod else "alias-stage")
                    alias.symlink_to(apps, target_is_directory=True)
                    with self.assertRaisesRegex(mod.Blocked, "TREE_IS_LIVE_RELEASE_POINTER"):
                        mod.validate_tree(str(alias / "platform"), "X")

                # A similarly prefixed sibling is not a forbidden child.
                sibling = tree(base, "prod-sibling")
                self.assertEqual(mod.validate_tree(str(sibling), "X"), sibling.resolve())


class Env(unittest.TestCase):
    def test_clean_env_does_not_inherit_secrets(self):
        os.environ["STRIPE_SECRET"] = "sk_live_should_not_leak"
        os.environ["APP_KEY"] = "base64:leak"
        try:
            with tempfile.TemporaryDirectory() as d:
                env = mod.clean_env({"DB_DATABASE": "kmj_rehearsal", "DB_USERNAME": "u",
                                     "DB_HOST": "127.0.0.1", "DB_PORT": "5432", "DB_PASSWORD": ""}, Path(d), 1234)
                self.assertNotIn("STRIPE_SECRET", env)
                self.assertNotEqual(env["APP_KEY"], "base64:leak")
                self.assertEqual(env["MAIL_MAILER"], "array")
                self.assertEqual(env["QUEUE_CONNECTION"], "sync")
                self.assertEqual(env["APP_DEBUG"], "false")
                self.assertTrue(env["LARAVEL_STORAGE_PATH"].startswith(d))
        finally:
            del os.environ["STRIPE_SECRET"]
            os.environ.pop("APP_KEY", None)


class Schema(unittest.TestCase):
    def test_additive_only(self):
        s0 = frozenset({("column", "a", "id"), ("index", "a", "pk")})
        self.assertTrue(mod.additive_only(s0, s0 | {("column", "b", "id")}))
        self.assertTrue(mod.additive_only(s0, s0))
        self.assertFalse(mod.additive_only(s0, frozenset({("column", "a", "id")})))
        # An altered column shows up as remove+add and must fail.
        self.assertFalse(mod.additive_only(s0, frozenset({("column", "a", "id2"), ("index", "a", "pk")})))

    def test_script_never_claims_rollback_verified_flag(self):
        text = (ROOT / "scripts/operations/rehearse-app-http-db-rollback-20261029.py").read_text()
        self.assertNotIn("rollbackVerified=true", text)
        self.assertIn("ROLLBACK_VERIFIED_FLAG", text)
        self.assertIn("NOT_SET_BY_THIS_SCRIPT", text)
        for forbidden in ("shell=True", "os.system(", "migrate:fresh", "db:wipe", "DROP DATABASE"):
            self.assertNotIn(forbidden, text)



class FailureEvidence(unittest.TestCase):
    def test_cached_runtime_config_is_rejected_even_when_env_is_absent(self):
        with tempfile.TemporaryDirectory() as d:
            app = tree(Path(d), "cached")
            cache = app / "bootstrap/cache"
            cache.mkdir(parents=True)
            config = cache / "config.php"
            for broken_link in (False, True):
                if broken_link:
                    config.unlink()
                    config.symlink_to(cache / "absent.php")
                else:
                    config.write_text("production cached settings")
                with self.assertRaisesRegex(mod.Blocked, "TREE_HAS_CACHED_CONFIG"):
                    mod.validate_tree(str(app), "X")

    def test_schema_query_error_never_reports_pass(self):
        with tempfile.TemporaryDirectory() as d, ExitStack() as stack:
            previous, candidate = Path(d) / "previous", Path(d) / "candidate"
            stack.enter_context(patch.object(mod.os, "geteuid", return_value=1000))
            stack.enter_context(patch.object(mod.sys, "argv", ["rehearsal.py"]))
            stack.enter_context(patch.object(mod.shutil, "which", return_value="/usr/bin/tool"))
            stack.enter_context(patch.object(mod, "validate_database", return_value={"DB_DATABASE": "kmj_rehearsal"}))
            stack.enter_context(patch.object(mod, "validate_tree", side_effect=[previous, candidate]))
            stack.enter_context(patch.object(mod, "psql_rows", return_value=[("kmj_rehearsal",)]))
            stack.enter_context(patch.object(mod, "attest_disposable"))
            stack.enter_context(patch.object(mod, "clean_env", return_value={}))
            stack.enter_context(patch.object(mod, "artisan", return_value=True))
            stack.enter_context(patch.object(mod, "schema_snapshot", side_effect=RuntimeError("PSQL_FAILED")))
            output = StringIO()
            with redirect_stdout(output):
                result = mod.main()
            self.assertEqual(result, 1)
            self.assertIn("APP_HTTP_DB_ROLLBACK_REHEARSAL=FAIL", output.getvalue())
            self.assertNotIn("APP_HTTP_DB_ROLLBACK_REHEARSAL=PASS", output.getvalue())


class Attestation(unittest.TestCase):
    NONCE = "ab" * 24

    def attest(self, rows, nonce=None):
        original = mod.psql_rows
        mod.psql_rows = lambda _db, _sql: rows
        try:
            mod.attest_disposable({}, self.NONCE if nonce is None else nonce)
        finally:
            mod.psql_rows = original

    def test_matching_comment_is_accepted(self):
        self.attest([(f"kmj-disposable-rehearsal:{self.NONCE}",)])

    def test_unstamped_shared_or_wrong_nonce_database_is_refused(self):
        for rows in ([("",)], [("kmj-disposable-rehearsal:" + "cd" * 24,)], [("production",)], []):
            with self.assertRaisesRegex(mod.Blocked, "DB_NOT_ATTESTED_DISPOSABLE"):
                self.attest(rows)

    def test_missing_or_malformed_nonce_is_refused(self):
        for nonce in ("x", "ZZ" * 20, "ab" * 8):
            with self.assertRaisesRegex(mod.Blocked, "DB_ATTESTATION_NONCE_MISSING"):
                self.attest([("anything",)], nonce)

    def test_requirement_env_is_validated_and_main_enforces_it(self):
        os.environ["KMJ_X"] = "abc"
        try:
            with self.assertRaises(mod.Blocked):
                mod.env_int("KMJ_X", 0)
        finally:
            del os.environ["KMJ_X"]
        self.assertEqual(mod.env_int("KMJ_NOT_SET_X", 3), 3)
        text = (ROOT / "scripts/operations/rehearse-app-http-db-rollback-20261029.py").read_text()
        self.assertIn("MIN_NEW_MIGRATIONS_NOT_MET", text)
        self.assertIn("WORKSPACE_ROUTES_REQUIRED_BUT_ABSENT", text)
        self.assertLess(text.index("attest_disposable(db"), text.index("schema_snapshot(db)"))
        ci = (ROOT / "scripts/ci/rehearse-app-rollback-ci.sh").read_text()
        self.assertIn("COMMENT ON DATABASE", ci)
        self.assertIn("merge-base --is-ancestor", ci)
        wf = (ROOT / ".github/workflows/app-http-db-rollback-rehearsal.yml").read_text()
        self.assertIn("KMJ_REHEARSAL_MIN_NEW_MIGRATIONS: '1'", wf)
        self.assertIn("39b88b36d071d3f78f2392d609d3febc2c530165", wf)


if __name__ == "__main__":
    unittest.main()
