#!/usr/bin/env python3
"""Offline exact bce410 command SHA redaction + unsupported-policy negative tests."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SRC = Path(__file__).resolve().parent / "operations/09e8-live-unit-argv-fingerprint-readonly-20261109.py"
spec = importlib.util.spec_from_file_location("argv_bce410", SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def unit(unit: str, args: list[str], root: str) -> dict[str,str]:
    return {
        "ExecStart": "{ path=/usr/bin/php8.4 ; argv[]=" + " ".join(args) + " ; ignore_errors=no ; }",
        "WorkingDirectory": root,
        "User": "kmjprod",
        "ActiveState": "active" if unit == m.QUEUE else "inactive",
        "Restart": "always" if unit == m.QUEUE else "no",
        "KillMode": "control-group",
        "Type": "simple" if unit == m.QUEUE else "oneshot",
        "MainPID": "123" if unit == m.QUEUE else "0",
    }


class ExactArgvTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Path(self.tmp.name) / "apps/platform"
        self.app.mkdir(parents=True)
        (self.app / "artisan").write_text("placeholder")
        patch = mock.patch.object(m, "APP", str(self.app))
        patch.start()
        self.addCleanup(patch.stop)
        self.queue_args = ["/usr/bin/php8.4", "artisan", "queue:work",
                           "--sleep=3", "--tries=3", "--timeout=90"]
        self.scheduler_args = ["/usr/bin/php8.4", "artisan", "schedule:run"]

    def test_known_fixed_commands_match_native_json_argv_digest(self):
        q = m.fingerprint(m.QUEUE, unit(m.QUEUE, self.queue_args, str(self.app)))
        s = m.fingerprint(m.SCHEDULER, unit(m.SCHEDULER, self.scheduler_args, str(self.app)))
        self.assertEqual(q, hashlib.sha256(json.dumps(self.queue_args).encode()).hexdigest())
        self.assertEqual(s, hashlib.sha256(json.dumps(self.scheduler_args).encode()).hexdigest())

    def test_queue_denies_unknown_or_secret_bearing_options(self):
        for suffix in (
            ["--force"], ["--password=private-fixture"], ["--token=private"],
            ["--env=/root/private"], ["--sleep=3", "--sleep=3"],
            ["--sleep=1000000000"], ["--queue=foo/../bar"], ["-e", "PRIVATE=1"],
            ["--priority=highest"], ["--memory", "100"],
        ):
            with self.subTest(suffix=suffix), self.assertRaises(m.Refused):
                m.fingerprint(m.QUEUE, unit(m.QUEUE, self.queue_args[:3]+suffix, str(self.app)))

    def test_scheduler_does_not_accept_queue_flags(self):
        with self.assertRaises(m.Refused):
            m.fingerprint(m.SCHEDULER,
                          unit(m.SCHEDULER, self.scheduler_args + ["--sleep=3"], str(self.app)))

    def test_changed_owner_runtime_dir_pid_or_mode_fail(self):
        for k, v in (("User", "root"), ("Restart", "on-failure"),
                     ("ActiveState", "inactive"), ("MainPID", "0"),
                     ("KillMode", "process"), ("WorkingDirectory", "/tmp")):
            doc = unit(m.QUEUE, self.queue_args, str(self.app))
            doc[k] = v
            with self.subTest(k=k), self.assertRaises(m.Refused):
                m.fingerprint(m.QUEUE, doc)

    def test_reject_shell_expansion_multiple_argv_or_non_php(self):
        for command in ("{ path=/bin/sh ; argv[]=/bin/sh script ; ignore_errors=no ; }",
                        "{ path=/usr/bin/php8.4 ; argv[]=/usr/bin/php8.4 artisan queue:work $FLAGS ; }",
                        "{ path=/usr/bin/php8.4 ; argv[]=/usr/bin/php8.4 artisan queue:work ; argv[]=evil ; }"):
            doc = unit(m.QUEUE, self.queue_args, str(self.app))
            doc["ExecStart"] = command
            with self.subTest(command=command), self.assertRaises(m.Refused):
                m.fingerprint(m.QUEUE, doc)

    def test_fixed_service_commands_do_not_print_secret_raw_values(self):
        class Value:
            returncode = 0
            stdout = (b"ExecStart=PRIVATE_RAW_ARGV\nWorkingDirectory=/secret\n"
                      b"User=kmjprod\nActiveState=active\nRestart=always\n"
                      b"KillMode=control-group\nType=simple\nMainPID=123\n")
        with mock.patch.object(m.subprocess, "run", return_value=Value()) as run:
            parsed = m.show(m.QUEUE, m.FIELDS)
        self.assertIn("PRIVATE_RAW_ARGV", parsed["ExecStart"])
        argv = run.call_args.args[0]
        self.assertEqual(argv[0:4], ["/usr/bin/systemctl", "show", m.QUEUE, "--all"])
        self.assertNotIn("--property=Environment", str(argv))

    def test_systemd_show_invalid_or_duplicate_fields_refused(self):
        class Value:
            returncode = 0
            stdout = b"ActiveState=active\nActiveState=active\n"
        with mock.patch.object(m.subprocess, "run", return_value=Value()):
            with self.assertRaises(m.Refused):
                m.show(m.TIMER, ("ActiveState", "Triggers"))

    def test_twice_drift_blocks_argv_release(self):
        hashes = [("a"*64,"b"*64), ("c"*64,"d"*64)]
        with mock.patch.object(m.os, "geteuid", return_value=0), \
             mock.patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
             mock.patch.object(m, "attest_once", side_effect=hashes):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = m.main([])
        self.assertEqual(rc, 2)
        self.assertIn("ARGV_FINGERPRINT=BLOCKED_UNVERIFIABLE", out.getvalue())
        self.assertNotIn("QUEUE_ARGV_SHA256", out.getvalue())

    def test_exact_command_mismatch_reports_stage_and_safe_reason(self):
        with mock.patch.object(m.os, "geteuid", return_value=0), \
             mock.patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
             mock.patch.object(m, "live_pointer"), \
             mock.patch.object(m, "show") as show:
            def item(unit_id, fields):
                if unit_id == m.TIMER:
                    return {"ActiveState": "active", "Triggers": m.SCHEDULER}
                args = (self.queue_args if unit_id == m.QUEUE else self.scheduler_args)
                value = unit(unit_id, args, str(self.app))
                if unit_id == m.QUEUE:
                    value["Type"] = "notify"
                return value
            show.side_effect = item
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = m.main([])
        self.assertEqual(rc, 2)
        self.assertIn("ARGV_BLOCKER_STAGE=QUEUE_COMMAND", out.getvalue())
        self.assertIn("ARGV_BLOCKER_REASON=UNIT_POLICY_UNVERIFIED", out.getvalue())
        self.assertIn("STORAGE_APPLY_ALLOWED=NO", out.getvalue())
        self.assertNotIn("ExecStart=", out.getvalue())
        self.assertNotIn("QUEUE_ARGV_SHA256=", out.getvalue())

    def test_timer_missing_fields_identifies_stage_without_exposing_fields(self):
        with mock.patch.object(m.os, "geteuid", return_value=0), \
             mock.patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
             mock.patch.object(m, "live_pointer"), \
             mock.patch.object(m, "show", side_effect=[
                unit(m.QUEUE, self.queue_args, str(self.app)),
                unit(m.SCHEDULER, self.scheduler_args, str(self.app)),
                m.Refused("SYSTEMD_FIELDS_MISSING")
            ]):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = m.main([])
        self.assertEqual(rc, 2)
        self.assertIn("ARGV_BLOCKER_STAGE=TIMER_UNIT_READ", out.getvalue())
        self.assertIn("ARGV_BLOCKER_REASON=SYSTEMD_FIELDS_MISSING", out.getvalue())
        self.assertIn("PRODUCTION_MUTATION=NONE", out.getvalue())

    def test_raw_exception_text_and_unrecognized_refusal_never_leaks(self):
        for failure in (ValueError("SECRET_MY_TOKEN"), m.Refused("SECRET_MY_TOKEN")):
            with mock.patch.object(m.os, "geteuid", return_value=0), \
                 mock.patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
                 mock.patch.object(m, "live_pointer", side_effect=failure):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    rc = m.main([])
            self.assertEqual(rc, 2)
            self.assertIn("ARGV_BLOCKER_STAGE=LIVE_POINTER_BEFORE", out.getvalue())
            self.assertIn("ARGV_BLOCKER_REASON=RUNTIME_UNVERIFIABLE", out.getvalue())
            self.assertNotIn("SECRET", out.getvalue())
            self.assertNotIn("QUEUE_ARGV_SHA256", out.getvalue())

    def test_queue_and_scheduler_diagnostic_stage_is_distinct(self):
        self.assertEqual(m.at("QUEUE_UNIT_READ", lambda: True), True)
        with self.assertRaises(m.AuditBlocked) as caught:
            m.at("SCHEDULER_COMMAND", lambda: m.insist(False, "UNIT_POLICY_UNVERIFIED"))
        self.assertEqual(caught.exception.stage, "SCHEDULER_COMMAND")
        self.assertEqual(caught.exception.reason, "UNIT_POLICY_UNVERIFIED")

    def test_rejected_option_classification_is_finite_and_value_free(self):
        cases = {
            "database": "KNOWN_QUEUE_CONNECTION",
            "redis": "KNOWN_QUEUE_CONNECTION",
            "--sleep": "SPLIT_NUMERIC_OPTION",
            "3": "SPLIT_NUMERIC_VALUE",
            "--queue": "SPLIT_QUEUE_OPTION",
            "--verbose": "VERBOSITY_OPTION",
            "--queue=/private/secret": "SENSITIVE_OPTION",
            "--queue=with/slash": "QUEUE_NAME_REJECTED",
            "--password=SECRET_TOKEN": "SENSITIVE_OPTION",
            "--access-token=TOP_SECRET": "SENSITIVE_OPTION",
            "--foo=bar": "UNKNOWN_LONG_VALUE_OPTION",
            "--foo": "UNKNOWN_LONG_FLAG",
            "-x": "UNKNOWN_SHORT_FLAG",
            "customconnection": "UNKNOWN_POSITIONAL",
            "@!unknown": "UNKNOWN_SYNTAX",
        }
        for raw, shape in cases.items():
            with self.subTest(expected_shape=shape):
                result = m.classify_option_shape(raw)
                self.assertEqual(result, shape)
                self.assertIn(result, m.OPTION_SHAPES)
                self.assertNotIn(raw, m.OPTION_SHAPES)

    def test_one_known_positional_produces_sha_not_writer_admission(self):
        # The observed old-v834 blocker was a recognized Laravel queue driver.
        # A validated *command identity* SHA is not a writer-drain proof.
        actual = ["/usr/bin/php8.4", "artisan", "queue:work",
                  "database", "--sleep=3", "--tries=3"]
        with mock.patch.object(m.os, "geteuid", return_value=0), \
             mock.patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
             mock.patch.object(m, "live_pointer"), \
             mock.patch.object(m, "show") as mock_show:
            def observed(unit_id, fields):
                if unit_id == m.TIMER:
                    return {"ActiveState": "active", "Triggers": m.SCHEDULER}
                args = actual if unit_id == m.QUEUE else self.scheduler_args
                return unit(unit_id, args, str(self.app))
            mock_show.side_effect = observed
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = m.main([])
        self.assertEqual(rc, 0)
        self.assertIn("ARGV_FINGERPRINT=READ_ONLY_VERIFIED", out.getvalue())
        self.assertIn("QUEUE_ARGV_SHA256=" +
                      hashlib.sha256(json.dumps(actual).encode()).hexdigest(),
                      out.getvalue())
        self.assertNotIn("database", out.getvalue())
        self.assertNotIn("ARGV_UNREVIEWED_SHAPE", out.getvalue())
        self.assertIn("WRITER_ADMISSION=NOT_ATTESTED", out.getvalue())
        self.assertIn("STORAGE_APPLY_ALLOWED=NO", out.getvalue())
        self.assertIn("PRODUCTION_MUTATION=NONE", out.getvalue())

    def test_fixed_allowlist_one_connection_before_or_after_options(self):
        self.assertEqual(
            m.KNOWN_QUEUE_CONNECTIONS,
            frozenset({"database", "redis", "sqs", "sync", "beanstalkd"}))
        for name in sorted(m.KNOWN_QUEUE_CONNECTIONS):
            for args in (
                self.queue_args[:3] + [name] + self.queue_args[3:],
                self.queue_args + [name],
            ):
                with self.subTest(name=name, location=args.index(name)):
                    digest = m.fingerprint(m.QUEUE,
                                           unit(m.QUEUE, args, str(self.app)))
                    self.assertEqual(
                        digest, hashlib.sha256(json.dumps(args).encode()).hexdigest())

    def test_second_known_connection_or_unknown_positional_refused(self):
        for trailing in (
            ["database", "redis"], ["redis", "database"],
            ["database", "database"], ["database", "mysql"],
            ["mysql"], ["database", "--force"], ["database", "--token=private"],
        ):
            args = self.queue_args[:3] + trailing + self.queue_args[3:]
            with self.subTest(trailing=trailing), self.assertRaises(m.Refused):
                m.fingerprint(m.QUEUE, unit(m.QUEUE, args, str(self.app)))

    def test_scheduler_must_never_accept_connection_positional(self):
        for conn in sorted(m.KNOWN_QUEUE_CONNECTIONS):
            with self.subTest(connection=conn), self.assertRaises(m.Refused):
                m.fingerprint(m.SCHEDULER, unit(
                    m.SCHEDULER, self.scheduler_args + [conn], str(self.app)))

    def test_connection_shape_classification_stays_fixed_without_value_leaks(self):
        for conn in sorted(m.KNOWN_QUEUE_CONNECTIONS):
            self.assertEqual(m.classify_option_shape(conn), "KNOWN_QUEUE_CONNECTION")
        self.assertEqual(m.classify_option_shape("unknown_driver"),
                         "UNKNOWN_POSITIONAL")
        self.assertEqual(m.classify_option_shape("--password=SECRET"),
                         "SENSITIVE_OPTION")

    def test_secret_argv_never_leaks_any_raw_input(self):
        secret = "--password=PRIVATE-CUSTOMER-SUPERSECRET-DO-NOT-LOG"
        with mock.patch.object(m.os, "geteuid", return_value=0), \
             mock.patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
             mock.patch.object(m, "live_pointer"), \
             mock.patch.object(m, "show") as mock_show:
            def observed(unit_id, fields):
                if unit_id == m.TIMER:
                    return {"ActiveState": "active", "Triggers": m.SCHEDULER}
                args = self.queue_args + [secret] if unit_id == m.QUEUE else self.scheduler_args
                return unit(unit_id, args, str(self.app))
            mock_show.side_effect = observed
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = m.main([])
        self.assertEqual(rc, 2)
        self.assertIn("ARGV_UNREVIEWED_SHAPE=SENSITIVE_OPTION", out.getvalue())
        self.assertNotIn("PRIVATE", out.getvalue())
        self.assertNotIn("CUSTOMER", out.getvalue())
        self.assertNotIn("SECRET", out.getvalue())
        self.assertNotIn("QUEUE_ARGV_SHA256=", out.getvalue())

    def test_unreviewed_option_details_are_only_finite_constant_labels(self):
        self.assertEqual(
            m.at("QUEUE_COMMAND", lambda: 123),
            123
        )
        with self.assertRaises(m.AuditBlocked) as caught:
            m.at("QUEUE_COMMAND", lambda: m.safe_args(
                ["/usr/bin/php8.4", "artisan", "queue:work", "--some-unknown=value"], "queue:work"))
        self.assertEqual(caught.exception.reason, "UNREVIEWED_OPTION")
        self.assertEqual(caught.exception.option_shape, "UNKNOWN_LONG_VALUE_OPTION")
        self.assertNotIn("some-unknown", str(caught.exception))

    def test_verified_main_still_never_approves_storage(self):
        with mock.patch.object(m.os, "geteuid", return_value=0), \
             mock.patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
             mock.patch.object(m, "attest_once", return_value=("a"*64, "b"*64)):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = m.main([])
        self.assertEqual(rc, 0)
        self.assertIn("QUEUE_ARGV_SHA256="+"a"*64, out.getvalue())
        self.assertIn("SCHEDULER_ARGV_SHA256="+"b"*64, out.getvalue())
        self.assertIn("WRITER_ADMISSION=NOT_ATTESTED", out.getvalue())
        self.assertIn("STORAGE_APPLY_ALLOWED=NO", out.getvalue())

    def test_no_mutation_or_env_contents_read(self):
        import ast
        source = SRC.read_text("utf-8")
        module = ast.parse(source)
        for node in ast.walk(module):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"exec", "eval", "compile", "open", "__import__"})
        for bad in ("systemctl stop", "systemctl start", "nft add", "os.unlink(",
                    "os.rename(", "os.symlink(", "os.replace(", "git reset",
                    " --apply", "EnvironmentFiles", "/proc/self/environ"):
            self.assertNotIn(bad, source)


if __name__ == "__main__":
    unittest.main()
