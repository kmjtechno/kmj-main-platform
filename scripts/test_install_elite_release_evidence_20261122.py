#!/usr/bin/env python3
"""Offline negative tests for the reviewed-SHA KMJ-elite release evidence collectors and admission broker installer.

Never contacts GitHub or executes systemctl. Entire host mutation is mocked or
restricted to a disposable unittest.TemporaryDirectory.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import os
import stat
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[0] / "operations" / "install-elite-release-evidence-20261122.py"
spec = importlib.util.spec_from_file_location("elite_pinned_release_evidence", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class EliteEvidenceInstallerTests(unittest.TestCase):
    def test_source_is_exact_reviewed_commit_and_never_branched_latest(self):
        self.assertEqual(mod.SOURCE_COMMIT, "ee7bef15c82d16933ab0e7fe187d8aa1649790c6")
        self.assertEqual(mod.SOURCE_URL, "https://github.com/kmjtechno/kmj-main-platform.git")
        self.assertEqual(len(mod.TARGETS), 15)
        for source, path, mode, bound in mod.TARGETS:
            self.assertNotIn("..", Path(source).parts)
            self.assertTrue(path.is_absolute())
            self.assertTrue(str(path).startswith(("/opt/", "/etc/systemd/system/")))
            self.assertIn(mode, (0o500, 0o644))
            self.assertLessEqual(bound, 60000)
            self.assertFalse(str(path).startswith("/opt/kmj-main-platform-autopublish"))

    def test_private_dir_refuses_symlink_and_group_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real = root / "real"
            real.mkdir(mode=0o755)
            link = root / "link"
            link.symlink_to(real, target_is_directory=True)
            self.assertFalse(mod.protected_dir(link))
            os.chmod(real, 0o777)
            self.assertFalse(mod.protected_dir(real))
            self.assertFalse(mod.protected_dir(Path("not/absolute")))

    def test_untrusted_or_missing_fixed_installed_file_does_not_count_as_pin(self):
        with patch.object(mod, "protected_dir", return_value=True):
            with patch.object(mod.os, "lstat", side_effect=FileNotFoundError):
                self.assertEqual(mod.classify_file(Path("/tmp/not-there"), 0o644), "MISSING")
            info = SimpleNamespace(
                st_mode=stat.S_IFREG | 0o644, st_uid=0, st_nlink=1, st_size=50,
            )
            with patch.object(mod.os, "lstat", return_value=info):
                self.assertEqual(mod.classify_file(Path("/tmp/example"), 0o644),
                                 "PRESENT_UNATTESTED")
            info.st_nlink = 2
            with patch.object(mod.os, "lstat", return_value=info):
                self.assertEqual(mod.classify_file(Path("/tmp/example"), 0o644),
                                 "UNTRUSTED")
            info.st_nlink = 1
            info.st_mode = stat.S_IFLNK | 0o777
            with patch.object(mod.os, "lstat", return_value=info):
                self.assertEqual(mod.classify_file(Path("/tmp/example"), 0o644),
                                 "UNTRUSTED")

    def test_atomic_hardlink_install_no_overwrite_and_no_extra_link(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "trusted.service"
            data = b"[Unit]\nDescription=reviewed fixed service\n"
            expected = hashlib.sha256(data).hexdigest()

            def local_classify(path, mode, sha=None):
                try:
                    st = path.lstat()
                except FileNotFoundError:
                    return "MISSING"
                if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                    return "UNTRUSTED"
                if stat.S_IMODE(st.st_mode) != mode:
                    return "UNTRUSTED"
                result = hashlib.sha256(path.read_bytes()).hexdigest()
                return "PIN_MATCH" if result == sha else "DIFFERENT"

            with patch.object(mod, "protected_dir", return_value=True), patch.object(
                    mod, "classify_file", side_effect=local_classify):
                self.assertEqual(mod.install_new(dest, data, 0o644),
                                 "INSTALLED_PIN_MATCH")
                self.assertEqual(dest.read_bytes(), data)
                self.assertEqual(dest.lstat().st_nlink, 1)
                self.assertEqual(mod.install_new(dest, data, 0o644),
                                 "ALREADY_INSTALLED_PIN_MATCH")
                with self.assertRaisesRegex(mod.Blocked, "EXISTING_ARTIFACT_MISMATCH"):
                    mod.install_new(dest, b"[Unit]\nDescription=changed\n", 0o644)
                self.assertEqual(dest.read_bytes(), data)

    def test_default_inspect_is_strictly_read_only(self):
        with patch.object(mod, "require_operator"), patch.object(
                mod, "classify_file", return_value="MISSING"), patch.object(
                mod, "fixed_run", side_effect=AssertionError("external command in inspect")):
            self.assertEqual(mod.run("inspect"), 0)

    def _install(self, enable_timer, gate="PIN_MATCH"):
        calls = []

        def fake_run(argv, timeout=45):
            calls.append(tuple(argv))
            return b""

        contents = {
            target: (b"fixed reviewed file", mode)
            for _, target, mode, _ in mod.TARGETS
        }
        with patch.object(mod, "require_operator"), patch.object(
                mod, "ensure_dir"), patch.object(
                mod, "protected_dir", return_value=True), patch.object(
                mod, "classify_file", return_value=gate), patch.object(
                mod, "reviewed_bytes", return_value=contents), patch.object(
                mod, "install_new", return_value="INSTALLED_PIN_MATCH"), patch.object(
                mod, "fixed_run", side_effect=fake_run), patch.object(
                Path, "exists", return_value=True):
            code = mod.run("install", enable_timer)
        return code, calls

    def test_install_without_flag_never_enables_a_timer(self):
        code, calls = self._install(False)
        self.assertEqual(code, 0)
        self.assertFalse(any("enable" in args for args in calls))
        self.assertIn(("/usr/bin/systemctl", "daemon-reload"), calls)

    def test_enable_timer_flag_enables_only_the_broker_timer_and_never_the_release_unit(self):
        code, calls = self._install(True)
        self.assertEqual(code, 0)
        self.assertIn(
            ("/usr/bin/systemctl", "enable", "--now",
             "kmj-elite-release-admission-broker.timer"), calls,
        )
        self.assertTrue(all(
            "main-platform-production-release.service" not in " ".join(args)
            for args in calls
        ))
        self.assertTrue(all("start" not in args for args in calls))
        source = SCRIPT.read_text()
        for disallowed in (
            "backupVerified\": True", "rollbackVerified\": True",
            "os.symlink(", "git reset", "git clean", "ALTER DATABASE",
            "ln -s ", "shell=True",
        ):
            self.assertNotIn(disallowed, source)

    def test_install_blocks_when_the_protected_gate_is_missing(self):
        with self.assertRaisesRegex(mod.Blocked, "AUTOPUBLISH_GATE_MISSING"):
            self._install(False, gate="MISSING")

    def test_enable_timer_without_install_is_refused(self):
        with patch.object(mod.sys, "argv", ["x", "--inspect", "--enable-timer"]):
            self.assertEqual(mod.main(), 2)

    def test_install_fails_closed_on_unexpected_modes(self):
        with patch.object(mod, "require_operator"):
            with self.assertRaisesRegex(mod.Blocked, "UNSUPPORTED_MODE"):
                mod.run("override-release")

    def test_root_exact_host_required(self):
        for uid, hostname in ((1000, "KMJ-elite"), (0, "OTHER-HOST")):
            with patch.object(mod.os, "geteuid", return_value=uid), patch.object(
                    mod.socket, "gethostname", return_value=hostname):
                with self.assertRaisesRegex(mod.Blocked, "ROOT_ELITE_ONLY"):
                    mod.require_operator()

    def test_state_dirs_are_private_root_dirs_and_collectors_never_world_readable(self):
        for directory, mode in mod.DIRS:
            self.assertIn(mode, (0o700, 0o755))
            self.assertTrue(str(directory).startswith("/var/lib/"))
        order = [str(d) for d, _ in mod.DIRS]
        self.assertLess(order.index("/var/lib/kmj-main-platform"),
                        order.index("/var/lib/kmj-main-platform/admission-broker"))
        self.assertEqual(dict(mod.DIRS)[Path("/var/lib/kmj-release-receipts")], 0o700)
        self.assertEqual(dict(mod.DIRS)[Path("/var/lib/kmj-main-platform/admission-broker")], 0o700)
        for _, target, mode, _ in mod.TARGETS:
            if target.suffix == ".py":
                self.assertEqual(mode, 0o500)
                self.assertTrue(str(target).startswith("/opt/kmj-main-platform-release-evidence/"))

    def test_ensure_dir_refuses_loose_or_foreign_dir(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "state"
            with patch.object(mod, "protected_dir", return_value=True):
                if os.geteuid() != 0:
                    d.mkdir(mode=0o700)
                    with self.assertRaisesRegex(mod.Blocked, "STATE_DIR_UNTRUSTED"):
                        mod.ensure_dir(d, 0o700)
                else:
                    mod.ensure_dir(d, 0o700)
                    os.chmod(d, 0o755)
                    with self.assertRaisesRegex(mod.Blocked, "STATE_DIR_UNTRUSTED"):
                        mod.ensure_dir(d, 0o700)

    def test_installer_never_installs_the_gate_as_trust_anchor_or_writes_evidence(self):
        source = SCRIPT.read_text()
        self.assertIn("INSTALLED_GATE_DIFFERS_FROM_REVIEWED_COPY", source)
        for disallowed in ("main-platform-production-release.json", "main-platform-autopublish-",
                           "systemctl\", \"start", "rehearsal.json"):
            self.assertNotIn(disallowed, source)


if __name__ == "__main__":
    unittest.main()
