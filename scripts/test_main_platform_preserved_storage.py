"""Adversarial tests for the journal-attested preserved-storage exemption (materializer, doctor, helper).

The fixtures run the REAL reviewed storage switch (fake freezer, so no root needed) to create the genuine
journal receipt and preserved directory, then try to forge/tamper around them."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OPS = REPO / "scripts/operations"
sys.path.insert(0, str(OPS))
import main_platform_storage_switch as sw  # noqa: E402
import main_platform_preserved_storage as ps  # noqa: E402

DOCTOR = OPS / "main-platform-release-readiness-doctor.py"
spec = importlib.util.spec_from_file_location("kmj_doctor_for_preserved", DOCTOR)
doctor = importlib.util.module_from_spec(spec)
sys.modules["kmj_doctor_for_preserved"] = doctor
spec.loader.exec_module(doctor)
MATERIALIZE = (OPS / "materialize-main-platform-candidate-runtime.sh").read_text()


class FakeFreezer(sw.Freezer):
    def __init__(self):
        self.state = {}

    def _k(self, fd):
        st = os.fstat(fd)
        return st.st_dev, st.st_ino

    def flags(self, fd):
        return self.state.get(self._k(fd), 0)

    def set_immutable(self, fd, on):
        if on:
            self.state[self._k(fd)] = sw.FS_IMMUTABLE_FL
        else:
            self.state.pop(self._k(fd), None)

    def require_ready(self, probe_dir=None):
        pass


def git(cwd, *args):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(cwd), "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True,
                          env=env).stdout.strip()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(os.path.realpath(self.tmp.name))
        self.home = base / "home"
        self.state = base / "state"
        self.state.mkdir(mode=0o700)
        (base / "proc").mkdir()
        self.cand = self.home / "releases/platform-aaaaaaaaaaaa"
        storage = self.cand / "apps/platform/storage"
        (storage / "app/private").mkdir(parents=True)
        (storage / "app/.gitignore").write_text("*\n!.gitignore\n")
        (storage / "app/private/a.txt").write_text("upload")
        git(self.cand, "init", "-q")
        git(self.cand, "config", "user.email", "t@example.invalid")
        git(self.cand, "config", "user.name", "t")
        git(self.cand, "add", "-f", "apps/platform/storage/app/.gitignore")
        git(self.cand, "commit", "-q", "-m", "c")
        self.shared = self.home / "shared/storage"
        (self.shared / "app").mkdir(parents=True)
        shutil.copy(storage / "app/private/a.txt", self.shared / "app") if False else None
        (self.shared / "app/private").mkdir()
        (self.shared / "app/private/a.txt").write_text("upload")
        for p in (self.home / "shared", self.shared, storage):
            p.chmod(0o700)
        self.app = self.cand / "apps/platform"
        self.fz = FakeFreezer()
        self._orig = (sw.FREEZER, sw.FAULT)
        sw.FREEZER, sw.FAULT = self.fz, None

    def tearDown(self):
        sw.FREEZER, sw.FAULT = self._orig
        self.tmp.cleanup()

    def run_sw(self, command, *extra):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = sw.main([command, "--app-dir", str(self.app), "--shared", str(self.shared),
                            "--allowed-root", str(self.home), "--state-dir", str(self.state),
                            "--proc-root", str(self.state.parent / "proc"), *extra])
        return code, json.loads(buf.getvalue())

    def do_switch(self):
        plan = self.run_sw("plan")[1]["plan_id"]
        code, out = self.run_sw("switch", "--apply", "--plan-id", plan)
        self.assertEqual((code, out["status"]), (0, "OK"), out)
        return out["preserved_dir"]

    def attest(self):
        return ps.attest(self.cand, self.state)

    def porcelain(self, *excludes):
        return git(self.cand, "status", "--porcelain", "--untracked-files=normal", "--", ".",
                   ":(exclude)apps/platform/storage", *excludes)

    def receipt(self):
        return next(self.state.glob("*.journal.done-*"))


class AttestationTests(Fixture):
    def test_genuine_switch_is_attested_and_git_is_clean_only_with_the_exact_exclusion(self):
        kept = self.do_switch()
        self.assertIn(f"?? apps/platform/{kept}/", self.porcelain())  # the reported blocker, reproduced
        self.assertEqual(self.attest(), ("ATTESTED", kept))
        self.assertEqual(self.porcelain(f":(exclude)apps/platform/{kept}"), "")

    def test_no_preserved_dir_means_no_exemption(self):
        self.assertEqual(self.attest(), ("NONE", None))

    def test_forged_directory_without_journal_is_rejected(self):
        self.do_switch()
        self.receipt().unlink()
        self.assertEqual(self.attest()[0], "UNATTESTED")

    def test_attacker_dir_with_plausible_name_but_no_receipt_is_rejected(self):
        (self.app / "storage.pre-shared-20261105T091800Z").mkdir()
        (self.app / "storage.pre-shared-20261105T091800Z/evil.php").write_text("<?php")
        self.assertEqual(self.attest(), ("UNATTESTED", "NO_COMPLETE_CLOSED_JOURNAL_RECEIPT_FOR_NAME"))

    def test_content_changed_after_the_switch_is_rejected(self):
        kept = self.do_switch()
        (self.app / kept / "app/private/a.txt").write_text("tampered")
        self.assertEqual(self.attest(), ("UNATTESTED", "PRESERVED_CONTENT_DIFFERS_FROM_JOURNAL"))

    def test_file_added_or_removed_after_the_switch_is_rejected(self):
        kept = self.do_switch()
        (self.app / kept / "app/private/new.php").write_text("x")
        self.assertEqual(self.attest()[0], "UNATTESTED")
        (self.app / kept / "app/private/new.php").unlink()
        self.assertEqual(self.attest()[0], "ATTESTED")  # restored => attests again
        (self.app / kept / "app/private/a.txt").unlink()
        self.assertEqual(self.attest()[0], "UNATTESTED")

    def test_two_preserved_entries_are_rejected(self):
        self.do_switch()
        (self.app / "storage.pre-shared-20200101T000000Z").mkdir()
        self.assertEqual(self.attest(), ("UNATTESTED", "MULTIPLE_PRESERVED_ENTRIES"))

    def test_symlink_in_place_of_the_directory_is_rejected(self):
        kept = self.do_switch()
        real = self.app / kept
        moved = self.app.parent / "elsewhere"
        real.rename(moved)
        (self.app / kept).symlink_to(moved)
        self.assertEqual(self.attest(), ("UNATTESTED", "PRESERVED_NOT_A_TRUSTED_DIRECTORY"))

    def test_renamed_directory_does_not_match_the_journalled_name(self):
        kept = self.do_switch()
        (self.app / kept).rename(self.app / "storage.pre-shared-20301231T235959Z")
        self.assertEqual(self.attest(), ("UNATTESTED", "NO_COMPLETE_CLOSED_JOURNAL_RECEIPT_FOR_NAME"))

    def test_open_journal_means_transaction_in_flight(self):
        self.do_switch()
        key = next(self.state.glob("*.journal.done-*")).name.split(".")[0]
        (self.state / f"{key}.journal").write_text('{"t":1,"phase":"begin"}\n')
        os.chmod(self.state / f"{key}.journal", 0o600)
        self.assertEqual(self.attest(), ("UNATTESTED", "OPEN_JOURNAL_TRANSACTION_IN_FLIGHT"))

    def test_receipt_that_is_unsafe_torn_or_incomplete_attests_nothing(self):
        self.do_switch()
        receipt = self.receipt()
        good = receipt.read_bytes()
        receipt.chmod(0o644)
        self.assertEqual(self.attest()[0], "UNATTESTED")
        receipt.chmod(0o600)
        receipt.write_bytes(good + b'{"t":')  # torn tail on a "closed" receipt
        self.assertEqual(self.attest()[0], "UNATTESTED")
        lines = good.splitlines(keepends=True)
        receipt.write_bytes(b"".join(l for l in lines if b'"complete"' not in l))
        self.assertEqual(self.attest()[0], "UNATTESTED")
        receipt.write_bytes(b"".join(l for l in lines if b'"verified"' not in l))
        self.assertEqual(self.attest()[0], "UNATTESTED")  # never verified => not attested

    def test_receipt_hardlinked_or_symlinked_is_rejected(self):
        self.do_switch()
        receipt = self.receipt()
        os.link(receipt, self.state / "alias")
        self.assertEqual(self.attest()[0], "UNATTESTED")
        (self.state / "alias").unlink()
        data = receipt.read_bytes()
        receipt.unlink()
        other = self.state.parent / "other"
        other.write_bytes(data)
        other.chmod(0o600)
        receipt.symlink_to(other)
        self.assertEqual(self.attest()[0], "UNATTESTED")

    def test_rollback_recorded_for_the_name_is_rejected(self):
        kept = self.do_switch()
        key = self.receipt().name.split(".")[0]
        extra = self.state / f"{key}.journal.done-9999999999"
        extra.write_text(json.dumps({"t": 1, "phase": "rollback_begin", "kept": kept}) + "\n")
        extra.chmod(0o600)
        self.assertEqual(self.attest(), ("UNATTESTED", "ROLLBACK_RECORDED_FOR_PRESERVED_DIR"))

    def test_state_dir_not_protected_is_rejected(self):
        self.do_switch()
        self.state.chmod(0o755)
        self.assertEqual(self.attest(), ("UNATTESTED", "STATE_DIR_NOT_PROTECTED"))

    def test_tracked_file_under_the_path_can_never_be_hidden(self):
        kept = self.do_switch()
        git(self.cand, "add", "-f", f"apps/platform/{kept}/app/.gitignore")
        self.assertEqual(self.attest(), ("UNATTESTED", "TRACKED_FILES_UNDER_PRESERVED_PATH"))

    def test_other_dirt_still_blocks_even_with_the_attested_exemption(self):
        kept = self.do_switch()
        (self.app / "extra-source.php").write_text("x")
        self.assertEqual(self.attest()[0], "ATTESTED")
        self.assertIn("extra-source.php", self.porcelain(f":(exclude)apps/platform/{kept}"))

    def test_cli_exit_codes(self):
        kept = self.do_switch()
        run = lambda: subprocess.run([sys.executable, "-I", str(OPS / "main_platform_preserved_storage.py"),
                                      str(self.cand), f"--state-dir={self.state}"], capture_output=True, text=True)
        out = run()
        self.assertEqual((out.returncode, out.stdout.strip()), (0, f"ATTESTED {kept}"))
        (self.app / kept / "x").write_text("x")
        out = run()
        self.assertEqual(out.returncode, 2)
        self.assertTrue(out.stdout.startswith("UNATTESTED"))


class DoctorIntegrationTests(Fixture):
    def make_doctor_world(self):
        kept = self.do_switch()
        live = self.home / "releases/platform-bbbbbbbbbbbb/apps/platform"
        live.mkdir(parents=True)
        (live / "storage").symlink_to(self.shared)
        (self.home / "current").symlink_to("releases/platform-bbbbbbbbbbbb")
        return kept, doctor.Paths(root=self.home, storage_state=self.state)

    def test_doctor_accepts_attested_preserved_dir_and_reports_clean(self):
        kept, paths = self.make_doctor_world()
        self.assertEqual(doctor._candidate_git_state(self.cand, paths), "PASS")

    def test_doctor_rejects_tampered_preserved_dir(self):
        kept, paths = self.make_doctor_world()
        (self.app / kept / "app/private/a.txt").write_text("tampered")
        self.assertEqual(doctor._candidate_git_state(self.cand, paths), "PRESERVED_STORAGE_UNATTESTED")

    def test_doctor_still_flags_other_untracked_files(self):
        kept, paths = self.make_doctor_world()
        (self.app / "extra.php").write_text("x")
        self.assertEqual(doctor._candidate_git_state(self.cand, paths), "DIRTY")

    def test_doctor_fails_closed_when_attestor_is_unavailable(self):
        kept, paths = self.make_doctor_world()
        real = doctor._preserved_storage
        doctor._preserved_storage = lambda c, p: ("UNATTESTED", "ATTESTOR_UNAVAILABLE")
        try:
            self.assertEqual(doctor._candidate_git_state(self.cand, paths), "PRESERVED_STORAGE_UNATTESTED")
        finally:
            doctor._preserved_storage = real


class MaterializerContractTests(unittest.TestCase):
    def test_exemption_is_exact_name_and_helper_gated(self):
        for token in ("main_platform_preserved_storage.py", "resolve_pathspec", "PRESERVED_STORAGE_UNATTESTED",
                      'PATHSPEC+=(":(exclude)apps/platform/$name")', "ATTEST_HELPER_UNSAFE",
                      "CANDIDATE_DIRTY_BEFORE", "CANDIDATE_DIRTY_AFTER"):
            self.assertIn(token, MATERIALIZE, token)
        self.assertEqual(MATERIALIZE.count("resolve_pathspec\n"), 2)  # root attests before AND after the sandbox
        self.assertIn('"$ORIGIN_LINE" "$ATTESTED_PRESERVED" <<', MATERIALIZE)  # sandbox gets the attested name only
        self.assertIn("CANDIDATE_DIRTY_FINAL", MATERIALIZE)
        for forbidden in ("storage.pre-shared-*'", ":(exclude)apps/platform/storage*", "info/exclude",
                          "--ignored", "update-index", "skip-worktree", "assume-unchanged"):
            self.assertNotIn(forbidden, MATERIALIZE, forbidden)


if __name__ == "__main__":
    unittest.main()
