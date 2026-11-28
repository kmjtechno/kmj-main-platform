import json
import os
import pathlib
import sys
import tempfile
import unittest

OPS = pathlib.Path(__file__).resolve().parent / "operations"
sys.path.insert(0, str(OPS))
import elite_collect_rollback_rehearsal_receipt as col  # noqa: E402
import release_admission_receipts as ra  # noqa: E402

SHA = "a" * 40
EXP = "platform-" + "b" * 12
NOW = 1_800_000_000
TEST_ENV = {"DB_USERNAME": "kmj_rehearsal_" + SHA[:12], "DB_PASSWORD": "c" * 32,
            "KMJ_REHEARSAL_DB_NONCE": "d" * 32}
GOOD = "\n".join([
    "REHEARSAL_DATABASE=DISPOSABLE_ATTESTED", "PREVIOUS_MIGRATE=PASS", "CANDIDATE_MIGRATE=PASS",
    "NEW_MIGRATIONS=2", "SCHEMA_CHANGE_ADDITIVE_ONLY=PASS",
    "CODE_ROLLBACK_ON_MIGRATED_SCHEMA=PASS",
    "SCHEMA_ROLLBACK_RESTORES_BASELINE_EXACTLY=PASS", "SCHEMA_REAPPLY_MATCHES_FORWARD_EXACTLY=PASS",
    "PRODUCTION_DATABASE_TOUCHED=NO", "ROLLBACK_VERIFIED_FLAG=NOT_SET_BY_THIS_SCRIPT",
    "FAILURES=NONE", "APP_HTTP_DB_ROLLBACK_REHEARSAL=PASS"]) + "\n"


class RehearsalTests(unittest.TestCase):
    def test_good_output_issues_valid_receipt_only_for_rollback(self):
        checks = []
        r = col.collect(SHA, EXP, NOW, lambda e: GOOD, TEST_ENV, lambda *a: checks.append(a))
        self.assertEqual(checks, [tuple(TEST_ENV.values())] * 2)
        self.assertIsNone(ra.receipt_problem(r, SHA, EXP, NOW))
        self.assertEqual(r["kind"], "rollback-rehearsal")

    def test_isolation_failure_blocks_runner_or_receipt(self):
        def fail(*a):
            raise ValueError("HBA_BLOCKED")
        with self.assertRaisesRegex(ValueError, "HBA_BLOCKED"):
            col.collect(SHA, EXP, NOW, lambda e: self.fail("runner started"),
                        TEST_ENV, fail)
        checks = []
        def drift(*a):
            checks.append(a)
            if len(checks) == 2:
                fail()
        with self.assertRaisesRegex(ValueError, "HBA_BLOCKED"):
            col.collect(SHA, EXP, NOW, lambda e: GOOD, TEST_ENV, drift)

    def test_zero_new_migrations_needs_no_schema_rollback_markers(self):
        out = GOOD.replace("NEW_MIGRATIONS=2", "NEW_MIGRATIONS=0")
        out = "\n".join(l for l in out.splitlines() if "SCHEMA_R" not in l) + "\n"
        self.assertTrue(col.rehearsal_passed(out))

    def test_each_defect_is_refused(self):
        defects = [
            GOOD.replace("=PASS", "=FAIL", 1),
            GOOD.replace("FAILURES=NONE", "FAILURES=PREVIOUS_HTTP"),
            GOOD.replace("PRODUCTION_DATABASE_TOUCHED=NO", "PRODUCTION_DATABASE_TOUCHED=YES"),
            GOOD.replace("DISPOSABLE_ATTESTED", "UNATTESTED"),
            GOOD.replace("APP_HTTP_DB_ROLLBACK_REHEARSAL=PASS", "APP_HTTP_DB_ROLLBACK_REHEARSAL=BLOCKED:X"),
            GOOD.replace("CODE_ROLLBACK_ON_MIGRATED_SCHEMA=PASS\n", ""),
            GOOD.replace("SCHEMA_REAPPLY_MATCHES_FORWARD_EXACTLY=PASS", "SCHEMA_REAPPLY_MATCHES_FORWARD_EXACTLY=FAIL"),
            GOOD + "FAILURES=NONE\n",
            GOOD.replace("NEW_MIGRATIONS=2", "NEW_MIGRATIONS=x"),
            "",
        ]
        for out in defects:
            self.assertFalse(col.rehearsal_passed(out), out[:60])
            with self.assertRaises(ValueError):
                col.collect(SHA, EXP, NOW, lambda e, o=out: o, TEST_ENV, lambda *a: None)

    def test_config_is_strict(self):
        with tempfile.TemporaryDirectory() as d:
            os.chmod(d, 0o700)
            p = pathlib.Path(d) / "c.json"

            def write(obj, mode=0o600):
                p.write_text(json.dumps(obj))
                os.chmod(p, mode)
            name = "kmj_rehearsal_" + SHA[:12]
            base = "/var/lib/kmj-release-rehearsal/" + SHA[:12]
            good = {"approvedSha": SHA, "expectedCurrentRelease": EXP, "env": {
                "DB_DATABASE": name, "DB_USERNAME": name, "DB_HOST": "127.0.0.1", "DB_PORT": "5432",
                "DB_PASSWORD": "c" * 32, "KMJ_REHEARSAL_DB_NONCE": "d" * 32,
                "KMJ_REHEARSAL_PREVIOUS_APP": base + "/previous",
                "KMJ_REHEARSAL_CANDIDATE_APP": base + "/candidate"}}
            write(good)
            self.assertEqual(col.load_env(p, os.getuid(), SHA, EXP), good["env"])
            with self.assertRaises(ValueError):
                col.load_env(p, os.getuid(), "f" * 40, EXP)
            with self.assertRaises(ValueError):
                col.load_env(p, os.getuid(), SHA, "platform-" + "f" * 12)
            write(dict(good, env=dict(good["env"], DB_HOST="external")))
            with self.assertRaises(ValueError):
                col.load_env(p, os.getuid(), SHA, EXP)
            for bad in ({"env": {"PATH": "/x"}}, {"env": {"DB_A": "a\nb"}}, {"env": {}},
                        {"env": {"DB_A": 1}}, {"env": {"DB_A": "a"}, "x": 1}):
                write(bad)
                with self.assertRaises(ValueError):
                    col.load_env(p, os.getuid(), SHA, EXP)
            write({"env": {"DB_A": "a"}}, 0o644)
            with self.assertRaises(ValueError):
                col.load_env(p, os.getuid(), SHA, EXP)

    def test_sandbox_scope_and_private_payload(self):
        argv = col.sandbox_argv()
        for flag in ("DynamicUser=yes", "ProtectHome=yes", "ProtectSystem=strict",
                     "IPAddressDeny=any", "IPAddressAllow=localhost", "PrivateTmp=yes"):
            self.assertIn("--property=" + flag, argv)
        self.assertNotIn("kmjprod", argv)
        password = "c" * 32
        self.assertFalse(any(password in arg for arg in argv))
        payload = col.runner_payload({"DB_PASSWORD": password}, "print('ok')")
        self.assertIn(password, payload)
        compile(payload, "<test>", "exec")

    def test_cli_guards_and_source_safety(self):
        self.assertEqual(col.main(["x", "--check", "bad", EXP]), 2)
        if os.geteuid() != 0:
            self.assertEqual(col.main(["x", "--write", SHA, EXP]), 2)
        src = (OPS / "elite_collect_rollback_rehearsal_receipt.py").read_text()
        for bad in ("shell=True", "os.system", "systemctl", "production-release.json", "rollbackVerified"):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
