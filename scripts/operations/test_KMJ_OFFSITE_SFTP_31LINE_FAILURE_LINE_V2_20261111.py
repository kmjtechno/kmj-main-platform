#!/usr/bin/env python3
"""Offline regression tests for the v32 offsite local-prefix failure-line observer.

Only harmless synthetic bash snippets are executed in disposable tempdirs.
No SSH, SFTP, production service, database or remote file is accessed.
"""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "KMJ_OFFSITE_SFTP_31LINE_FAILURE_LINE_V2_20261111.py"
spec = importlib.util.spec_from_file_location("kmj_offsite_prefix_line_v32", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def prefix(*, fail_line=None, value=b"false", explicit_exit=False):
    lines = [b"#!/bin/bash\n", b"set -Eeuo pipefail\n"] + [b"true\n"] * 26
    if fail_line is not None:
        if not 3 <= fail_line <= 28:
            raise ValueError("TEST_LINE_UNREVIEWED")
        lines[fail_line - 1] = (b"exit 7\n" if explicit_exit else value + b"\n")
    assert len(lines) == 28
    return b"".join(lines)


class PrefixLineObserverTests(unittest.TestCase):
    def invoke(self, data, *, env=None):
        with tempfile.TemporaryDirectory(prefix="kmj-prefix-mock-") as td:
            captured = []
            with patch.object(mod, "emit", side_effect=lambda k, v: captured.append((k, v))):
                try:
                    mod.execute_local_prefix_with_line_marker(
                        data, Path(td), env or {
                            "PATH": "/usr/bin:/bin",
                            "HOME": td, "LC_ALL": "C", "LANG": "C",
                        }, timeout=12,
                    )
                    error = None
                except mod.Block as e:
                    error = str(e)
                script = Path(td) / "local-prefix.sh"
                self.assertTrue(script.is_file())
                self.assertEqual(script.stat().st_mode & 0o777, 0o600)
                return error, captured

    def test_harmless_success_returns_without_false_failure_marker(self):
        err, output = self.invoke(prefix())
        self.assertIsNone(err)
        self.assertEqual(output, [])

    def test_exact_failure_lines_are_bounded_to_1_to_28(self):
        for line in (3, 9, 21, 28):
            with self.subTest(line=line):
                err, output = self.invoke(prefix(fail_line=line))
                self.assertEqual(err, "LOCAL_BACKUP_PREFIX_FAILED")
                self.assertEqual(output, [
                    ("LOCAL_PREFIX_ERR_TRAP_LINE_CANDIDATE", f"LINE_{line:02}")
                ])

    def test_explicit_exit_without_err_trap_is_unknown(self):
        err, output = self.invoke(prefix(fail_line=12, explicit_exit=True))
        self.assertEqual(err, "LOCAL_BACKUP_PREFIX_FAILED")
        self.assertEqual(output, [
            ("LOCAL_PREFIX_ERR_TRAP_LINE_CANDIDATE", "UNKNOWN")
        ])

    def test_sensitive_stderr_and_stdout_are_not_forwarded(self):
        dangerous = b'echo SECRET_PASSWORD=[REDACTED] >&2; echo NEVER_LEAKED; false'
        err, output = self.invoke(prefix(fail_line=8, value=dangerous))
        self.assertEqual(err, "LOCAL_BACKUP_PREFIX_FAILED")
        self.assertEqual(output, [("LOCAL_PREFIX_ERR_TRAP_LINE_CANDIDATE", "LINE_08")])
        self.assertNotIn("SECRET_PASSWORD", repr(output))
        self.assertNotIn("NEVER_LEAKED", repr(output))

    def test_no_private_stdin(self):
        err, output = self.invoke(prefix(fail_line=5, value=b"read -r UNTRUSTED_INPUT"))
        self.assertEqual(err, "LOCAL_BACKUP_PREFIX_FAILED")
        self.assertEqual(output, [("LOCAL_PREFIX_ERR_TRAP_LINE_CANDIDATE", "LINE_05")])

    def test_not_a_pinned_shell_script_rejected_before_execution(self):
        with tempfile.TemporaryDirectory(prefix="kmj-prefix-mock-") as td:
            with self.assertRaisesRegex(mod.Block, "LOCAL_PREFIX_SOURCE_NOT_APPROVED"):
                mod.execute_local_prefix_with_line_marker(
                    b"echo UNAUTHORIZED\n", Path(td),
                    {"PATH": "/usr/bin:/bin"}, timeout=5)
            self.assertFalse((Path(td) / "local-prefix.sh").exists())

    def test_duplicate_script_path_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="kmj-prefix-mock-") as td:
            (Path(td) / "local-prefix.sh").write_bytes(b"kept")
            with self.assertRaisesRegex(mod.Block, "LOCAL_PREFIX_SCRIPT_ALREADY_EXISTS"):
                mod.execute_local_prefix_with_line_marker(
                    prefix(), Path(td), {"PATH": "/usr/bin:/bin"}, timeout=5)
            self.assertEqual((Path(td) / "local-prefix.sh").read_bytes(), b"kept")

    def test_service_config_is_distinct_from_prior_failed_v31(self):
        self.assertTrue(str(mod.REPAIR_FILE).endswith("v32-20261111.py"))
        self.assertTrue(str(mod.DROPIN).endswith("v32-20261111.conf"))
        self.assertNotIn("v31-20261111", str(mod.REPAIR_FILE))
        self.assertEqual(mod.LEGACY_SHA,
             "d66fd2c2cc33c53c1d0a82f1c259640ee642b666feb2c4aaee6cf887dfe98848")
        self.assertEqual(mod.UNIT, "kmj-elite-offsite-backup.service")

    def test_trace_channel_is_anonymous_and_no_debug_xtrace(self):
        source = SOURCE.read_text("utf8")
        self.assertIn("tempfile.TemporaryFile(dir=scratch)", source)
        self.assertIn("pass_fds=(fd,)", source)
        self.assertIn("stderr=subprocess.DEVNULL", source)
        self.assertIn("stdout=subprocess.DEVNULL", source)
        self.assertNotIn("set -x", source)
        self.assertIn("LOCAL_PREFIX_ERR_TRAP_LINE_CANDIDATE", source)
        self.assertIn("LOCAL_BACKUP_PREFIX_FAILED", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
