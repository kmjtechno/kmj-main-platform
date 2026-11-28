import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
OPS = ROOT / "scripts" / "operations"
sys.path.insert(0, str(OPS))
import elite_admission_broker as br  # noqa: E402
import elite_collect_all_receipts as allc  # noqa: E402

SHA = "a" * 40
PREV = "platform-" + "b" * 12
APPROVAL = {"approvedSha": SHA, "expectedCurrentRelease": PREV,
            "backupVerified": True, "rollbackVerified": True}
UNITS = ROOT / "infra" / "server" / "systemd"


class CollectAllTests(unittest.TestCase):
    def test_runs_fixed_steps_in_order_with_approval_identity_only(self):
        calls = []
        rc = allc.main(lambda s, m, sha, exp: (calls.append((s, m, sha, exp)), True)[1], APPROVAL)
        self.assertEqual(rc, 0)
        self.assertEqual([(c[0], c[1]) for c in calls], [(s, m) for _, s, m in allc.STEPS])
        self.assertTrue(all(c[2:] == (SHA, PREV) for c in calls))
        modes = [m for _, _, m in allc.STEPS]
        self.assertLess(modes.index("--cleanup"), len(modes))
        labels = [l for l, _, _ in allc.STEPS]
        self.assertLess(labels.index("REHEARSAL_WORKSPACE"), labels.index("ROLLBACK_REHEARSAL"))
        self.assertLess(labels.index("ROLLBACK_REHEARSAL"), labels.index("REHEARSAL_CLEANUP"))

    def test_failing_step_does_not_stop_others_and_exit_nonzero(self):
        calls = []

        def runner(script, mode, sha, exp):
            calls.append(script)
            return script != "elite_collect_public_qa_receipt.py"
        self.assertEqual(allc.main(runner, APPROVAL), 1)
        self.assertEqual(len(calls), len(allc.STEPS))

    def test_failed_workspace_never_runs_rehearsal_cleanup_or_derivation(self):
        calls = []
        def runner(script, mode, sha, exp):
            calls.append((script, mode))
            return script != "elite_prepare_rehearsal.py"
        self.assertEqual(allc.main(runner, APPROVAL), 1)
        self.assertIn(("elite_prepare_rehearsal.py", "--write"), calls)
        self.assertNotIn(("elite_prepare_rehearsal.py", "--cleanup"), calls)
        self.assertNotIn(("elite_collect_rollback_rehearsal_receipt.py", "--write"), calls)
        self.assertNotIn(("elite_derive_migration_storage_receipt.py", "--write"), calls)

    def test_failed_rehearsal_still_cleans_its_own_workspace_but_never_derives(self):
        calls = []
        def runner(script, mode, sha, exp):
            calls.append((script, mode))
            return script != "elite_collect_rollback_rehearsal_receipt.py"
        self.assertEqual(allc.main(runner, APPROVAL), 1)
        self.assertIn(("elite_prepare_rehearsal.py", "--cleanup"), calls)
        self.assertNotIn(("elite_derive_migration_storage_receipt.py", "--write"), calls)

    def test_bad_approval_runs_nothing(self):
        for bad in (None, {}, dict(APPROVAL, backupVerified=False),
                    dict(APPROVAL, approvedSha="zz"), dict(APPROVAL, extra=1)):
            calls = []
            self.assertEqual(allc.main(lambda *a: calls.append(a) or True, bad if bad is not None else "x"), 2)
            self.assertEqual(calls, [])

    def test_refuses_off_elite_when_no_approval_injected(self):
        if os.geteuid() != 0:
            self.assertEqual(allc.main(), 2)

    def test_source_takes_no_arguments_and_no_shell(self):
        src = (OPS / "elite_collect_all_receipts.py").read_text()
        for bad in ("shell=True", "os.system", "sys.argv", "systemctl"):
            self.assertNotIn(bad, src)


class ConsumeIntentTests(unittest.TestCase):
    def test_consume_removes_regular_file_and_refuses_open_parent(self):
        with tempfile.TemporaryDirectory() as d:
            os.chmod(d, 0o700)
            p = pathlib.Path(d) / "i.json"
            p.write_text("x")
            self.assertTrue(br.consume_intent(p, os.getuid()))
            self.assertFalse(p.exists())
            p.write_text("x")
            os.chmod(d, 0o777)
            self.assertFalse(br.consume_intent(p, os.getuid()))
            self.assertTrue(p.exists())
            os.chmod(d, 0o700)
            self.assertFalse(br.consume_intent(p, os.getuid() + 1))


class UnitSafetyTests(unittest.TestCase):
    def test_service_is_fixed_and_cannot_start_a_release(self):
        s = (UNITS / "kmj-elite-release-admission-broker.service").read_text()
        self.assertIn("elite_admission_broker.py --execute", s)
        for needed in ("NoNewPrivileges=true", "ProtectSystem=strict", "UMask=0077",
                       "ConditionPathExists=/home/kmjprod/shared/storage/app/private/ops/release-admission-request.json"):
            self.assertIn(needed, s)
        for bad in ("production-release", "systemctl", "ExecStartPre", "EnvironmentFile"):
            self.assertNotIn(bad, s)

    def test_timer_points_at_the_service(self):
        t = (UNITS / "kmj-elite-release-admission-broker.timer").read_text()
        self.assertIn("Unit=kmj-elite-release-admission-broker.service", t)


if __name__ == "__main__":
    unittest.main()
