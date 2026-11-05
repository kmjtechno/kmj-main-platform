import hashlib
import importlib.util
import json
import os
import pwd
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
HELPER = next(p for p in (HERE / "snapshot_attestation.py", HERE / "operations/main_platform_storage_snapshot_attestation.py") if p.is_file())
SPEC = importlib.util.spec_from_file_location("snapshot_attestation", HELPER)
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)
SCANNER = next(p for p in (HERE / "operations/main_platform_storage_switch.py",
                          HERE.parent / "review812v6/scripts/operations/main_platform_storage_switch.py") if p.is_file())
SNAPSHOT = "storage.pre-shared-20261105T091800Z"


class AttestationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.release = self.root / "release"
        self.app = self.release / "apps/platform"
        self.snap = self.app / SNAPSHOT
        self.shared = self.root / "shared"
        self.state = self.root / "state"
        self.trusted_scanner = self.root / "trusted-scanner.py"
        self.trusted_scanner.write_bytes(SCANNER.read_bytes())
        self.trusted_scanner.chmod(0o600)
        for p in (self.snap / "private", self.shared / "private", self.state):
            p.mkdir(parents=True, mode=0o700)
        self.state.chmod(0o700)
        (self.snap / "private/record").write_bytes(b"original")
        (self.shared / "private/record").write_bytes(b"new live content")
        (self.app / "storage").symlink_to(self.shared)
        subprocess.run(["git", "init", "-q", str(self.release)], check=True)
        subprocess.run(["git", "-C", str(self.release), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "commit", "-q", "--allow-empty", "-m", "fixture"], check=True)
        self.sha = subprocess.check_output(["git", "-C", str(self.release), "rev-parse", "HEAD"], text=True).strip()
        self.account = pwd.getpwnam("nobody")
        self.root.chmod(0o755)
        self.kw = dict(release_root=str(self.release), app_dir=str(self.app), expected_sha=self.sha,
                       shared_dir=str(self.shared), snapshot_name=SNAPSHOT, state_dir=str(self.state), scanner_path=str(self.trusted_scanner))
        self.loader = a.load_scanner
        self.scanner = self.loader(str(self.trusted_scanner), self.release, self.shared, self.state)
        fd = a.open_dir(self.snap)
        try:
            dirs = {}
            files = self.scanner.scan(fd, dirs)
            self.plan = self.scanner.plan_id(files, dirs)
        finally:
            os.close(fd)
        self.key = hashlib.sha256(str(self.app).encode()).hexdigest()[:12]
        self.receipt = self.state / (self.key + ".journal.done-1762334400")
        phases = ["begin", "live_frozen", "both_frozen", "link_created", "exchanged", "preserved", "verified", "complete"]
        self.entries = [{"t": 1, "phase": phase} for phase in phases]
        self.entries[0].update(kept=SNAPSHOT, link=".kmj-storage-link-0123456789abcdef", plan=self.plan)
        self.write_receipt()
        self.flags = lambda fd: 16 if os.readlink(f"/proc/self/fd/{fd}").startswith(str(self.snap)) else 0
        self.scanner.FREEZER.flags = lambda fd: self.flags(fd)
        fixture_run = subprocess.run
        def fixture_subprocess(*args, **kwargs):
            # This user namespace disallows setgroups even for its uid 0.
            # Only logic fixtures substitute their own identity; the command
            # contract and optional real credential-drop test remain separate.
            if kwargs.get("user") == os.getuid():
                for k in ("user", "group", "extra_groups", "preexec_fn"):
                    kwargs.pop(k, None)
            return fixture_run(*args, **kwargs)
        self.patches = [patch.object(a, "ROOT_UID", os.getuid()), patch.object(a, "SERVICE_ACCOUNT", "nobody"),
                        patch.object(a, "load_scanner", return_value=self.scanner),
                        patch.object(a, "git_credentials", return_value=(os.getuid(), os.getgid())),
                        patch.object(a.subprocess, "run", side_effect=fixture_subprocess)]
        self.real_credentials = a.git_credentials
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def write_receipt(self):
        self.receipt.write_text("".join(json.dumps(e) + "\n" for e in self.entries))
        self.receipt.chmod(0o600)

    def reject(self, reason=None, **override):
        with self.assertRaises(a.Rejected) as c:
            a.attest(**(self.kw | override))
        if reason:
            self.assertEqual(str(c.exception), reason)

    def test_valid_completed_snapshot_returns_exact_path_read_only(self):
        before = [(str(p), p.lstat().st_ino, p.lstat().st_mtime_ns) for p in self.root.rglob("*")]
        self.assertEqual(a.attest(**self.kw), f"apps/platform/{SNAPSHOT}/")
        self.assertEqual(before, [(str(p), p.lstat().st_ino, p.lstat().st_mtime_ns) for p in self.root.rglob("*")])

    def test_recovered_verified_receipt_is_valid(self):
        self.entries.pop()
        self.write_receipt()
        self.assertTrue(a.attest(**self.kw).endswith(SNAPSHOT + "/"))

    def test_recovery_after_preserve_before_phase_record_is_valid(self):
        self.entries = [e for e in self.entries if e["phase"] not in ("preserved", "complete")]
        self.write_receipt()
        self.assertTrue(a.attest(**self.kw).endswith(SNAPSHOT + "/"))

    def test_source_check_passes_only_snapshot(self):
        self.assertEqual(a.check_source(**self.kw), f"apps/platform/{SNAPSHOT}/")

    def test_source_check_blocks_unrelated_untracked_file(self):
        (self.release / "other.txt").write_text("dirt")
        with self.assertRaisesRegex(a.Rejected, "other_source_changes"):
            a.check_source(**self.kw)

    def test_source_check_reattests_after_git(self):
        original = a.git_read
        def read(release, *args, **kwargs):
            result = original(release, *args, **kwargs)
            if args[0] == "status":
                (self.snap / "private/record").write_bytes(b"changed during child")
            return result
        with patch.object(a, "git_read", side_effect=read):
            with self.assertRaisesRegex(a.Rejected, "snapshot_plan_mismatch"):
                a.check_source(**self.kw)

    def test_git_command_contract_for_service_owned_checkout(self):
        result = subprocess.CompletedProcess([], 0, stdout=self.sha + "\n")
        with patch.object(a, "git_credentials", return_value=(self.account.pw_uid, self.account.pw_gid)), \
             patch.object(a.subprocess, "run", return_value=result) as run:
            a.git_read(self.release, "rev-parse", "--verify", "HEAD")
        args, kwargs = run.call_args
        self.assertIn("safe.directory=" + str(self.release), args[0])
        self.assertIn("core.fsmonitor=false", args[0])
        self.assertIn("core.untrackedCache=false", args[0])
        self.assertEqual(kwargs["timeout"], 15)
        self.assertEqual(kwargs["env"]["GIT_OPTIONAL_LOCKS"], "0")
        self.assertEqual(kwargs["user"], self.account.pw_uid)
        self.assertEqual(kwargs["group"], self.account.pw_gid)
        self.assertEqual(kwargs["extra_groups"], [])
        self.assertIs(kwargs["preexec_fn"], a.no_new_privileges)

    def test_append_only_shared_blocks(self):
        self.flags = lambda fd: 16 if os.readlink(f"/proc/self/fd/{fd}").startswith(str(self.snap)) else 32
        self.reject("shared_append_only")

    def test_wrong_sha(self):
        self.reject("wrong_candidate_sha", expected_sha="0" * 40)

    def test_missing_receipt(self):
        self.receipt.unlink()
        self.reject("missing_or_ambiguous_receipt")

    def test_other_candidate_receipt(self):
        self.receipt.rename(self.state / ("0" * 12 + ".journal.done-1"))
        self.reject("missing_or_ambiguous_receipt")

    def test_duplicate_receipt(self):
        p = self.state / (self.key + ".journal.done-2")
        p.write_bytes(self.receipt.read_bytes())
        p.chmod(0o600)
        self.reject("missing_or_ambiguous_receipt")

    def test_active_journal_blocks(self):
        (self.state / (self.key + ".journal")).write_bytes(b"torn")
        self.reject("active_transaction")

    def test_torn_receipt_blocks(self):
        with self.receipt.open("ab") as f:
            f.write(b'{"phase":')
        self.reject("incomplete_closed_receipt")

    def test_malformed_complete_receipt_blocks(self):
        self.receipt.write_bytes(b'{"phase":\n')
        self.reject("invalid_receipt")

    def test_incomplete_transaction_blocks(self):
        self.entries = self.entries[:6]
        self.write_receipt()
        self.reject("not_completed_switch")

    def test_reordered_history_blocks(self):
        self.entries[2], self.entries[3] = self.entries[3], self.entries[2]
        self.write_receipt()
        self.reject("invalid_switch_history")

    def test_mutable_snapshot_blocks(self):
        self.flags = lambda fd: 0
        self.reject("snapshot_not_immutable")

    def test_frozen_shared_blocks(self):
        self.flags = lambda fd: 16
        self.reject("shared_still_frozen")

    def test_changed_snapshot_blocks(self):
        (self.snap / "private/record").write_bytes(b"tampered")
        self.reject("snapshot_plan_mismatch")

    def test_extra_snapshot_blocks(self):
        (self.app / "storage.pre-shared-other").mkdir()
        self.reject("unexpected_snapshot")

    def test_wrong_target_blocks(self):
        (self.app / "storage").unlink()
        (self.app / "storage").symlink_to(self.snap)
        self.reject("wrong_live_storage_link")

    def test_receipt_permissions_block(self):
        self.receipt.chmod(0o644)
        self.reject("unprotected_state")

    def test_receipt_symlink_blocks(self):
        target = self.root / "receipt"
        self.receipt.rename(target)
        self.receipt.symlink_to(target)
        with self.assertRaises(OSError):
            a.attest(**self.kw)

    def test_receipt_hardlink_blocks(self):
        os.link(self.receipt, self.root / "receipt-alias")
        self.reject("unsafe_receipt")

    def test_snapshot_symlink_blocks(self):
        target = self.root / "moved-snapshot"
        self.snap.rename(target)
        self.snap.symlink_to(target)
        with self.assertRaises(OSError):
            a.attest(**self.kw)

    def test_source_check_blocks_tracked_snapshot(self):
        subprocess.run(["git", "-c", "safe.directory=" + str(self.release), "-C", str(self.release), "add", "--", "apps/platform/" + SNAPSHOT], check=True)
        # Staging an attested runtime snapshot must not be excused as untracked.
        with self.assertRaisesRegex(a.Rejected, "other_source_changes"):
            a.check_source(**self.kw)

    def test_source_check_blocks_tracked_source_modification(self):
        p = self.release / "source.txt"
        p.write_text("base")
        subprocess.run(["git", "-c", "safe.directory=" + str(self.release), "-C", str(self.release), "add", "source.txt"], check=True)
        subprocess.run(["git", "-c", "safe.directory=" + str(self.release), "-C", str(self.release), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "commit", "-q", "-m", "source"], check=True)
        self.kw["expected_sha"] = subprocess.check_output(["git", "-c", "safe.directory=" + str(self.release), "-C", str(self.release), "rev-parse", "HEAD"], text=True).strip()
        p.write_text("modified")
        with self.assertRaisesRegex(a.Rejected, "other_source_changes"):
            a.check_source(**self.kw)

    def test_git_filter_never_executes_as_root(self):
        try:
            os.chown(self.release, self.account.pw_uid, self.account.pw_gid)
        except OSError as exc:
            if os.environ.get("KMJ_REQUIRE_REAL_CREDENTIAL_DROP") == "1":
                self.fail("required real credential-drop fixture unavailable: " + str(exc))
            self.skipTest("local user namespace cannot chown service fixture: " + str(exc))
        for p in self.release.rglob("*"):
            if not p.is_symlink():
                os.chown(p, self.account.pw_uid, self.account.pw_gid)
        def git(*args):
            return subprocess.run(["git", "-c", "safe.directory=" + str(self.release), "-C", str(self.release), *args],
                                  check=True, capture_output=True)
        tracked = self.release / "filtered.txt"
        tracked.write_text("original\n")
        (self.release / ".gitattributes").write_text("filtered.txt filter=probe\n")
        git("add", "filtered.txt", ".gitattributes")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "filter fixture")
        marker = self.release / "filter-uid"
        git("config", "filter.probe.clean", "id -u > '" + str(marker) + "'; cat")
        tracked.write_text("modified\n")  # equal size forces Git's content/filter path
        with patch.object(a, "git_credentials", self.real_credentials):
            a.git_read(self.release, "status", "--porcelain=v1", "-z", "--untracked-files=all", text=False)
        self.assertEqual(marker.read_text().strip(), str(self.account.pw_uid))
        self.assertNotEqual(marker.stat().st_uid, 0)

    def test_root_git_identity_rejected(self):
        with patch.object(a.pwd, "getpwnam", return_value=pwd.getpwuid(0)):
            with self.assertRaisesRegex(a.Rejected, "wrong_git_owner"):
                self.real_credentials(self.release)

    def test_checkout_owner_mismatch_rejected(self):
        with self.assertRaisesRegex(a.Rejected, "wrong_git_owner"):
            self.real_credentials(self.release)

    def test_noncanonical_and_traversal_block(self):
        self.reject("noncanonical_path", app_dir=str(self.app) + "/../platform")
        self.reject("invalid_snapshot_name", snapshot_name=SNAPSHOT + "/../other")

    def test_dependency_verified_from_bytes(self):
        altered = self.root / "scanner.py"
        altered.write_bytes(SCANNER.read_bytes() + b"\n# changed\n")
        with self.assertRaisesRegex(a.Rejected, "dependency_hash_mismatch"):
            self.loader(str(altered), self.release, self.shared, self.state)


class StatusTests(unittest.TestCase):
    path = "apps/platform/" + SNAPSHOT + "/"

    def test_only_attested_untracked_subtree_removed(self):
        raw = b"?? " + os.fsencode(self.path) + b"private/file\0 M source.py\0?? unrelated\0"
        self.assertEqual(a.filter_porcelain_z(raw, self.path), b" M source.py\0?? unrelated\0")

    def test_tracked_snapshot_change_never_removed(self):
        raw = b" M " + os.fsencode(self.path) + b"private/file\0"
        self.assertEqual(a.filter_porcelain_z(raw, self.path), raw)

    def test_newline_filename_cannot_inject_status(self):
        raw = b"?? other\n?? " + os.fsencode(self.path) + b"/file\0"
        self.assertEqual(a.filter_porcelain_z(raw, self.path), raw)

    def test_rename_source_field_preserved_even_when_looks_untracked(self):
        raw = b"R  destination\0?? " + os.fsencode(self.path) + b"file\0"
        self.assertEqual(a.filter_porcelain_z(raw, self.path), raw)

    def test_sibling_and_traversal_preserved(self):
        for path in (self.path[:-1] + "-other/x", self.path + "../source.py", "/" + self.path + "x"):
            raw = b"?? " + os.fsencode(path) + b"\0"
            self.assertEqual(a.filter_porcelain_z(raw, self.path), raw)

    def test_malformed_and_unterminated_rejected(self):
        for raw in (b"?? file", b"R  file\0", b"x\0", b"XY file\0"):
            with self.assertRaises(a.Rejected):
                a.filter_porcelain_z(raw, self.path)


if __name__ == "__main__":
    unittest.main()
