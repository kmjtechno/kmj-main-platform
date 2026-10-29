import importlib.util
import os
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
