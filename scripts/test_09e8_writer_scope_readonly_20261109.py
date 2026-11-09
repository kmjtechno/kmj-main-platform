#!/usr/bin/env python3
"""Offline tests for fixed read-only 09e8 writer admission audit."""
from __future__ import annotations
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parent / "operations/audit-09e8-writer-scope-readonly-20261109.py"
spec = importlib.util.spec_from_file_location("writer_scope_09e8", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class GateTests(unittest.TestCase):
    def test_known_candidate_and_source_bound(self):
        self.assertEqual(mod.TARGET, "09e8a224cd37445c42588a073a6b52d207475a09")
        self.assertEqual(mod.CURRENT, "platform-bce4100d005e")
        self.assertEqual(mod.SCANNER_SHA, "f4d01f6e3b40c9ad774c8ada5129b241cee93dac782ce75bb0e229b26bbc95ba")

    def test_fixed_unit_scope_and_policy(self):
        sample = {
            "LoadState": "loaded", "ActiveState": "active", "SubState": "running",
            "MainPID": "234", "Restart": "always", "KillMode": "control-group",
            "TimeoutStopUSec": "2min", "User": "kmjprod", "Triggers": ""
        }
        q = mod.unit_assessment(sample, mod.QUEUE)
        self.assertEqual(q["QUEUE_STATE"], "ACTIVE")
        self.assertEqual(q["QUEUE_RESTART_ALWAYS"], "YES")
        self.assertEqual(q["QUEUE_KILL_CONTROL_GROUP"], "YES")
        self.assertEqual(q["QUEUE_PROCESS_RUNNING"], "YES")
        self.assertEqual(q["QUEUE_SERVICE_IDENTITY"], "EXPECTED")
        sample["Restart"] = "on-failure"
        self.assertEqual(mod.unit_assessment(sample, mod.QUEUE)["QUEUE_RESTART_ALWAYS"], "NO_OR_UNVERIFIED")
        sample["Triggers"] = mod.SCHEDULER
        self.assertEqual(mod.unit_assessment(sample, mod.TIMER)["TIMER_TRIGGERS_EXPECTED_SCHEDULER"], "YES")
        sample["Triggers"] = "unexpected.service"
        self.assertEqual(mod.unit_assessment(sample, mod.TIMER)["TIMER_TRIGGERS_EXPECTED_SCHEDULER"], "NO_OR_UNVERIFIED")

    def test_service_and_timer_request_different_properties(self):
        class Result:
            returncode = 0
            stdout = (b"LoadState=loaded\\nActiveState=active\\nSubState=running\\n"
                      b"MainPID=234\\nRestart=always\\nKillMode=control-group\\n"
                      b"TimeoutStopUSec=120000000\\nUser=kmjprod\\n")

        with mock.patch.object(mod.subprocess, "run", return_value=Result()) as run:
            values, missing = mod.unit_properties(mod.QUEUE)
        self.assertEqual(missing, ())
        self.assertEqual(values["Restart"], "always")
        argv = run.call_args.args[0]
        self.assertNotIn("Triggers", argv[4])
        self.assertIn("Restart", argv[4])
        self.assertNotIn("Triggers", values)

        class TimerResult:
            returncode = 0
            stdout = (b"LoadState=loaded\\nActiveState=active\\n"
                      b"SubState=waiting\\n"
                      b"Triggers=kmj-main-platform-scheduler.service\\n")

        with mock.patch.object(mod.subprocess, "run", return_value=TimerResult()) as run:
            values, missing = mod.unit_properties(mod.TIMER)
        self.assertEqual(missing, ())
        argv = run.call_args.args[0]
        self.assertIn("Triggers", argv[4])
        self.assertNotIn("MainPID", argv[4])
        self.assertNotIn("Restart", argv[4])
        self.assertEqual(mod.unit_assessment(values, mod.TIMER)[
            "TIMER_TRIGGERS_EXPECTED_SCHEDULER"], "YES")

    def test_missing_service_policy_is_unverified_not_success(self):
        class Result:
            returncode = 0
            stdout = (b"LoadState=loaded\\nActiveState=active\\n"
                      b"SubState=running\\nMainPID=234\\n"
                      b"Restart=always\\nTimeoutStopUSec=120000000\\n"
                      b"User=kmjprod\\n")
        with mock.patch.object(mod.subprocess, "run", return_value=Result()):
            rows, missing = mod.unit_properties(mod.QUEUE)
        self.assertEqual(missing, ("KillMode",))
        self.assertEqual(mod.unit_assessment(rows, mod.QUEUE)[
            "QUEUE_KILL_CONTROL_GROUP"], "NO_OR_UNVERIFIED")

    def test_timer_missing_triggers_never_passes(self):
        class Result:
            returncode = 0
            stdout = b"LoadState=loaded\\nActiveState=active\\nSubState=waiting\\n"
        with mock.patch.object(mod.subprocess, "run", return_value=Result()):
            rows, missing = mod.unit_properties(mod.TIMER)
        self.assertEqual(missing, ("Triggers",))
        self.assertEqual(mod.unit_assessment(rows, mod.TIMER)[
            "TIMER_TRIGGERS_EXPECTED_SCHEDULER"], "NO_OR_UNVERIFIED")

    def test_unit_duplicate_unexpected_value_rejected(self):
        for bad in (b"LoadState=loaded\\nLoadState=loaded\\n",
                    b"Unexpected=value\\n"):
            class Result:
                returncode = 0
                stdout = bad
            with mock.patch.object(mod.subprocess, "run", return_value=Result()):
                with self.assertRaises(mod.Blocked):
                    mod.unit_properties(mod.TIMER)

    def test_missing_fields_report_partial_never_apply(self):
        with mock.patch.object(mod, "execute", return_value={
            "STORAGE_PLAN_READY": "YES",
            "SYSTEMD_FIELDS_COMPLETE": "NO",
            "QUEUE_MISSING_FIELDS": "1"
        }):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                status = mod.main()
        self.assertEqual(status, 0)
        self.assertIn("WRITER_SCOPE_AUDIT=PARTIAL_READ_ONLY", out.getvalue())
        self.assertIn("WRITER_EXCLUSION=NOT_ATTESTED", out.getvalue())
        self.assertIn("STORAGE_APPLY_ALLOWED=NO", out.getvalue())

    def test_plan_sanitized_counts_no_conflict_names(self):
        plan = {"command": "plan", "mutated": False, "inventory_only_not_release_readiness": True,
                "ready": True, "live_files": 3, "shared_files": 26, "to_copy": 0,
                "persistent_conflicts": [], "plan_id": "c651c450b3941f3a"}
        report = mod.storage_plan(json.dumps(plan), 0)
        self.assertEqual(report["STORAGE_PLAN_READY"], "YES")
        self.assertEqual(report["STORAGE_PLAN_ID"], "c651c450b3941f3a")
        self.assertEqual(report["STORAGE_PERSISTENT_CONFLICT_COUNT"], "0")
        plan["persistent_conflicts"] = ["private/customer-secret"]
        self.assertNotIn("customer-secret", str(mod.storage_plan(json.dumps(plan), 0)))

    def test_plan_rejects_missing_or_false_attestations(self):
        plan = {"command": "plan", "mutated": False, "inventory_only_not_release_readiness": True,
                "ready": True, "live_files": 3, "shared_files": 26, "to_copy": 0,
                "persistent_conflicts": [], "plan_id": "c651c450b3941f3a"}
        for field, wrong in (
            ("mutated", True), ("inventory_only_not_release_readiness", False),
            ("ready", "True"), ("live_files", "3"), ("plan_id", "wrong"),
            ("persistent_conflicts", "[]"), ("command", "switch")
        ):
            modified = dict(plan, **{field: wrong})
            with self.subTest(field=field), self.assertRaises(mod.Blocked):
                mod.storage_plan(json.dumps(modified), 0)
        with self.assertRaises(mod.Blocked):
            mod.storage_plan(json.dumps(plan), 2)

    def test_main_always_refuses_apply_even_success(self):
        with mock.patch.object(mod, "execute", return_value={"STORAGE_PLAN_READY":"YES"}):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                status = mod.main()
        self.assertEqual(status, 0)
        self.assertIn("STORAGE_APPLY_ALLOWED=NO", out.getvalue())
        self.assertIn("WRITER_EXCLUSION=NOT_ATTESTED", out.getvalue())
        self.assertIn("PRODUCTION_MUTATION=NONE", out.getvalue())
        with mock.patch.object(mod, "execute", side_effect=mod.Blocked("TEST")):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                status = mod.main()
        self.assertEqual(status, 2)
        self.assertIn("WRITER_SCOPE_AUDIT=BLOCKED_TEST", out.getvalue())
        self.assertIn("STORAGE_APPLY_ALLOWED=NO", out.getvalue())

    def test_source_only_read_commands(self):
        source = SOURCE.read_text(encoding="utf-8")
        for forbidden in (
            "os.unlink(", "os.rename(", "os.replace(", "os.symlink(",
            "systemctl stop", "systemctl restart", "systemctl start",
            "subprocess.Popen(", "subprocess.call(", "shell=True",
            " --apply", '"switch"', "flock(", "kill(", "chattr",
            "git reset", "chmod(", "chown(",
            "/etc/kmj-codebridge/main-platform-production-release.json"
        ):
            self.assertNotIn(forbidden, source, forbidden)
        self.assertIn("WRITER_EXCLUSION=NOT_ATTESTED", source)
        self.assertIn("STORAGE_APPLY_ALLOWED=NO", source)


if __name__ == "__main__":
    unittest.main()
