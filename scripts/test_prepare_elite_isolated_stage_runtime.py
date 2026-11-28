import importlib.util
import pathlib
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent / "operations"

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

runtime = load("prepare-elite-isolated-stage-runtime-20261128.py")
env = load("prepare-elite-isolated-stage-env-20261128.py")
fpm = load("prepare-elite-isolated-stage-fpm-20261128.py")

class StageRuntimeTests(unittest.TestCase):
    def test_candidate_fpm_exact_scope(self):
        raw = env.env_bytes("a"*64, "base64:"+"A"*43+"=")
        self.assertTrue(fpm.valid_candidate_env(raw))
        self.assertFalse(fpm.valid_candidate_env(raw+b"DB_URL=postgres://unexpected\n"))
        self.assertFalse(fpm.valid_candidate_env(raw.replace(b"MAIL_MAILER=log", b"MAIL_MAILER=smtp")))
        self.assertFalse(fpm.valid_candidate_env(raw.replace(runtime.DB.encode(), b"other_db")))
        self.assertEqual(fpm.STORAGE, runtime.STORAGE)
        self.assertNotEqual(fpm.NEW_SOCKET, fpm.OLD_SOCKET)
        config = fpm.config_bytes().decode()
        self.assertIn("clear_env = yes", config)
        self.assertIn("env[LARAVEL_STORAGE_PATH] = "+str(runtime.STORAGE), config)
        self.assertIn("listen = "+str(fpm.NEW_SOCKET), config)
        self.assertNotIn(str(fpm.OLD_SOCKET), config)
        self.assertIn("pm.max_children = 2", config)

    def test_candidate_scope(self):
        self.assertEqual(runtime.SHA, "710c6f3ca10310457bc7243caabc0e48476ec110")
        self.assertEqual(runtime.OLD_PROD, "platform-72e7c9ada190")
        self.assertEqual(runtime.DB, env.DB)
        self.assertEqual(runtime.ROLE, env.ROLE)
        self.assertEqual(runtime.RUNTIME, env.RT)
        self.assertNotEqual(runtime.DB, "kmj_stage_a9796a25")

    def test_public_cross_database_privilege_refused(self):
        with patch.object(runtime, "pg", return_value=b"1") as pg:
            self.assertFalse(runtime.public_connect_isolated())
            query = pg.call_args.args[0][-1]
            self.assertIn("a.grantee=0", query)
            self.assertIn("'CONNECT','CREATE','TEMPORARY'", query)
        with patch.object(runtime, "pg", return_value=b"0"):
            self.assertTrue(runtime.public_connect_isolated())

    def test_env_uses_only_new_candidate_and_local_mail(self):
        text = env.env_bytes("a"*64, "base64:"+"A"*43+"=").decode()
        fields = dict(line.split("=", 1) for line in text.splitlines())
        self.assertEqual(fields["DB_DATABASE"], runtime.DB)
        self.assertEqual(fields["DB_USERNAME"], runtime.ROLE)
        self.assertEqual(fields["DB_HOST"], "127.0.0.1")
        self.assertEqual(fields["DB_URL"], "")
        self.assertEqual(fields["APP_ENV"], "staging")
        self.assertEqual(fields["MAIL_MAILER"], "log")
        self.assertEqual(fields["QUEUE_CONNECTION"], "sync")
        self.assertEqual(fields["CODEBRIDGE_OAUTH_ENABLED"], "false")
        self.assertEqual(fields["LARAVEL_STORAGE_PATH"], str(runtime.STORAGE))

if __name__ == "__main__":
    unittest.main()
