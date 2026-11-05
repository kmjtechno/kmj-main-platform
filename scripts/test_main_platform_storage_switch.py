import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "operations"))
import main_platform_storage_switch as sw  # noqa: E402


class FakeFreezer(sw.Freezer):
    """Tracks the immutable flag per inode so logic is testable without root."""

    def __init__(self):
        self.state = {}

    def _key(self, fd):
        st = os.fstat(fd)
        return st.st_dev, st.st_ino

    def flags(self, fd):
        return self.state.get(self._key(fd), 0)

    def set_immutable(self, fd, on):
        if on:
            self.state[self._key(fd)] = sw.FS_IMMUTABLE_FL
        else:
            self.state.pop(self._key(fd), None)

    def require_ready(self, probe_dir=None):
        pass

    def frozen_count(self):
        return len(self.state)


def run(root, command, *extra):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = sw.main([command, "--app-dir", str(root / "rel/apps/platform"),
                        "--shared", str(root / "shared/storage"),
                        "--allowed-root", str(root), "--state-dir", str(root / "state"),
                        "--proc-root", str(root / "proc"), *extra])
    return code, json.loads(buf.getvalue())


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.live = self.root / "rel/apps/platform/storage"
        self.shared = self.root / "shared/storage"
        for p in (self.live / "app/private", self.live / "framework/views", self.live / "logs",
                  self.shared / "app/private", self.shared / "framework/views"):
            p.mkdir(parents=True)
        (self.root / "shared").chmod(0o700)
        self.shared.chmod(0o700)
        self.live.chmod(0o700)
        (self.root / "state").mkdir(mode=0o700)
        (self.root / "proc").mkdir()
        (self.live / "app/private/art.png").write_bytes(b"artwork")
        (self.live / "app/private/live-only.json").write_bytes(b"{}")
        (self.shared / "app/private/art.png").write_bytes(b"artwork")
        (self.live / "framework/views/x.php").write_bytes(b"live-compiled")
        (self.shared / "framework/views/x.php").write_bytes(b"cand-compiled")
        self.fz = FakeFreezer()
        self._orig = (sw.FREEZER, sw.FAULT)
        sw.FREEZER, sw.FAULT = self.fz, None

    def tearDown(self):
        sw.FREEZER, sw.FAULT = self._orig
        self.tmp.cleanup()

    def plan(self):
        return run(self.root, "plan")[1]

    def switch(self):
        return run(self.root, "switch", "--apply", "--plan-id", self.plan()["plan_id"])

    def crash(self, phase):
        sw.FAULT = phase
        plan = self.plan()
        with self.assertRaises(sw.Crash):
            run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        sw.FAULT = None

    def journals(self):
        """Open journals only; closed ones are kept as .done-* receipts."""
        return sorted(p.name for p in (self.root / "state").glob("*.journal"))


class PlanTests(Base):
    def test_plan_is_read_only_and_plan_id_ignores_logs_and_views(self):
        before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*"))
        plan = self.plan()
        self.assertTrue(plan["ready"] and not plan["mutated"])
        self.assertEqual(plan["to_copy"], 1)
        self.assertEqual(before, sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*")))
        (self.live / "logs/laravel.log").write_text("noise")
        (self.live / "framework/views/y.php").write_text("noise")
        self.assertEqual(self.plan()["plan_id"], plan["plan_id"])

    def test_plan_id_binds_mode_of_persistent_file(self):
        first = self.plan()["plan_id"]
        (self.live / "app/private/art.png").chmod(0o640)
        self.assertNotEqual(self.plan()["plan_id"], first)

    def test_conflict_listed_in_plan(self):
        (self.shared / "app/private/art.png").write_bytes(b"DIFFERENT")
        plan = self.plan()
        self.assertFalse(plan["ready"])
        self.assertEqual(plan["persistent_conflicts"], ["app/private/art.png"])


class SwitchTests(Base):
    def test_switch_is_lossless_and_leaves_old_frozen_and_shared_thawed(self):
        code, out = self.switch()
        self.assertEqual((code, out["status"]), (0, "OK"))
        self.assertTrue(self.live.is_symlink())
        self.assertEqual(self.live.resolve(), self.shared.resolve())
        self.assertEqual((self.shared / "app/private/live-only.json").read_bytes(), b"{}")
        kept = self.root / "rel/apps/platform" / out["preserved_dir"]
        self.assertEqual((kept / "app/private/art.png").read_bytes(), b"artwork")
        self.assertEqual((kept / "framework/views/x.php").read_bytes(), b"live-compiled")
        self.assertTrue(self.fz.frozen_count() > 0)  # preserved copy stays frozen
        shared_ids = {(os.stat(p).st_dev, os.stat(p).st_ino) for p in [self.shared, *self.shared.rglob("*")]}
        self.assertFalse(shared_ids & set(self.fz.state))  # shared is thawed again
        self.assertEqual(self.journals(), [])  # journal closed (renamed .done-*)
        self.assertFalse(out["deleted_anything"])

    def test_live_is_frozen_before_it_is_read(self):
        seen = {}
        real = sw.scan

        def spy(fd, dirs=None):
            seen.setdefault("frozen_at_first_scan", self.fz.frozen_count())
            return real(fd, dirs)

        plan = self.plan()
        sw.scan = spy
        try:
            run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        finally:
            sw.scan = real
        self.assertGreater(seen["frozen_at_first_scan"], 0)

    def test_deleted_or_changed_persistent_file_after_review_is_stale(self):
        plan = self.plan()
        (self.live / "app/private/live-only.json").unlink()
        code, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        self.assertEqual((code, out["status"]), (2, "BLOCKED_PLAN_ID_STALE_REVIEW_AGAIN"))
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())
        self.assertEqual(self.fz.frozen_count(), 0)  # thawed on abort
        self.assertFalse((self.shared / "app/private/live-only.json").exists())

    def test_conflict_blocks_thaws_and_never_overwrites(self):
        (self.shared / "app/private/art.png").write_bytes(b"DIFFERENT")
        plan = self.plan()
        code, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        self.assertEqual(code, 2)
        self.assertIn("BLOCKED_PERSISTENT_CONFLICT", out["status"])
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())
        self.assertEqual(self.fz.frozen_count(), 0)
        self.assertEqual((self.shared / "app/private/art.png").read_bytes(), b"DIFFERENT")

    def test_requires_apply_and_plan_id(self):
        self.assertEqual(run(self.root, "switch")[0], 2)
        self.assertEqual(run(self.root, "switch", "--apply")[0], 2)

    def test_shared_path_swapped_during_transaction_is_detected(self):
        real = sw.sync_additive

        def swap_after(src, dst):
            out = real(src, dst)
            os.rename(self.shared, self.root / "shared/moved-away")
            self.shared.mkdir(mode=0o700)
            return out

        sw.sync_additive = swap_after
        try:
            code, out = self.switch()
        finally:
            sw.sync_additive = real
        self.assertEqual((code, out["status"]), (2, "BLOCKED_SHARED_PATH_REPLACED"))
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())

    def test_failure_after_exchange_swaps_back_while_both_frozen(self):
        real = sw.renameat2
        calls = []

        def flaky(dfd, old, new, flags):
            calls.append(flags)
            if flags == sw.RENAME_NOREPLACE and old.startswith(sw.LINK):
                raise OSError(5, "boom")
            return real(dfd, old, new, flags)

        sw.renameat2 = flaky
        try:
            code, out = self.switch()
        finally:
            sw.renameat2 = real
        self.assertEqual(code, 2)
        self.assertTrue(out["reverted"])
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())
        self.assertEqual((self.live / "app/private/live-only.json").read_bytes(), b"{}")
        self.assertEqual(self.fz.frozen_count(), 0)
        self.assertTrue(any(p.name.startswith(sw.PARKED) for p in (self.root / "rel/apps/platform").iterdir()))

    def test_no_double_hardlink_left_after_copy(self):
        self.switch()
        for p in self.shared.rglob("*"):
            if p.is_file():
                self.assertEqual(p.stat().st_nlink, 1, p)

    def test_empty_directories_and_modes_are_preserved(self):
        (self.live / "app/public").mkdir()
        (self.live / "app/public").chmod(0o750)
        self.switch()
        self.assertEqual((self.shared / "app/public").stat().st_mode & 0o777, 0o750)

    def test_short_writes_are_completed(self):
        real = os.write
        big = os.urandom(300000)
        (self.live / "app/private/big.bin").write_bytes(big)
        os.write = lambda fd, data: real(fd, bytes(data)[:7]) if len(data) > 7 else real(fd, data)
        try:
            code, out = self.switch()
        finally:
            os.write = real
        self.assertEqual(code, 0, out)
        self.assertEqual((self.shared / "app/private/big.bin").read_bytes(), big)

    def test_failed_copy_leaves_no_temp_and_no_published_file(self):
        real = sw._write_all

        def boom(fd, data):
            raise sw.Blocked("WRITE_FAILED")

        (self.live / "app/private/x.bin").write_bytes(b"data")
        a, b = sw.open_dir(self.live), sw.open_dir(self.shared)
        sw._write_all = boom
        try:
            with self.assertRaises(sw.Blocked):
                sw.copy_create_only(a, b, "app/private/x.bin",
                                    (hashlib.sha256(b"data").hexdigest(), 4, 0o600, os.getuid(), os.getgid()))
        finally:
            sw._write_all = real
        names = [p.name for p in (self.shared / "app/private").iterdir()]
        self.assertNotIn("x.bin", names)
        self.assertFalse([n for n in names if n.startswith(".kmj-tmp")])

    def test_xattr_is_refused_not_dropped(self):
        try:
            os.setxattr(self.live / "app/private/art.png", "user.review", b"1")
        except OSError:
            self.skipTest("filesystem has no user xattrs")
        code, out = run(self.root, "plan")
        self.assertEqual((code, out["status"]), (2, "BLOCKED_XATTR_OR_ACL_PRESENT_NOT_SUPPORTED"))

    def test_symlink_and_hardlink_entries_refused(self):
        os.symlink("/etc/passwd", self.live / "app/evil")
        self.assertEqual(run(self.root, "plan")[1]["status"], "BLOCKED_SYMLINK_OR_SPECIAL_ENTRY")
        os.unlink(self.live / "app/evil")
        os.link(self.live / "app/private/art.png", self.live / "app/private/hard.png")
        self.assertEqual(run(self.root, "plan")[1]["status"], "BLOCKED_UNSAFE_FILE")

    def test_already_immutable_tree_is_not_adopted(self):
        fd = sw.open_dir(self.live / "app/private")
        self.fz.set_immutable(fd, True)
        plan = self.plan()
        code, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        self.assertEqual((code, out["status"]), (2, "BLOCKED_ALREADY_IMMUTABLE_OR_APPEND_REVIEW"))


class PathTests(Base):
    def _plan_with(self, app, shared, allowed):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = sw.main(["plan", "--app-dir", str(app), "--shared", str(shared), "--allowed-root", str(allowed)])
        return code, buf.getvalue()

    def test_outside_allowed_root(self):
        code, text = self._plan_with(self.root / "rel/apps/platform", self.shared, self.root / "shared")
        self.assertEqual(code, 2)
        self.assertIn("PATH_OUTSIDE_ALLOWED_ROOT", text)

    def test_dotdot_is_not_canonical(self):
        code, text = self._plan_with(self.root / "shared/../rel/apps/platform", self.shared, self.root)
        self.assertIn("PATH_NOT_CANONICAL", text)

    def test_nested_or_same_target(self):
        app = self.root / "rel/apps/platform"
        self.assertIn("NESTED_OR_SAME_TARGET", self._plan_with(app, app, self.root)[1])

    def test_root_is_required_for_mutation_without_fake(self):
        sw.FREEZER = sw.Freezer()
        if os.geteuid() == 0:
            self.skipTest("running as root")
        code, out = run(self.root, "switch", "--apply", "--plan-id", "x")
        self.assertEqual(out["status"], "BLOCKED_ROOT_REQUIRED_FOR_ENFORCED_FREEZE")


class CrashRecoveryTests(Base):
    def test_recover_is_read_only_without_apply(self):
        self.crash("exchanged")
        n_before = self.fz.frozen_count()
        code, out = run(self.root, "recover")
        self.assertEqual((code, out["journal_phase"], out["mutated"]), (0, "exchanged", False))
        self.assertTrue(self.live.is_symlink())
        self.assertEqual(self.fz.frozen_count(), n_before)

    def test_crash_after_exchange_recovers_to_original_and_thaws(self):
        self.crash("exchanged")
        self.assertTrue(self.live.is_symlink())
        code, out = run(self.root, "recover", "--apply")
        self.assertEqual((code, out["recovered"]), (0, "switch_reverted"))
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())
        self.assertEqual((self.live / "app/private/live-only.json").read_bytes(), b"{}")
        self.assertEqual(self.fz.frozen_count(), 0)
        self.assertEqual(self.journals(), [])

    def test_crash_while_frozen_before_exchange_thaws(self):
        self.crash("both_frozen")
        self.assertGreater(self.fz.frozen_count(), 0)
        code, out = run(self.root, "recover", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.fz.frozen_count(), 0)
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())

    def test_crash_after_preserve_keeps_switch_and_thaws_shared(self):
        self.crash("preserved")
        code, out = run(self.root, "recover", "--apply")
        self.assertEqual((code, out["recovered"]), (0, "switch_complete"))
        self.assertTrue(self.live.is_symlink())

    def test_crash_during_rollback_after_exchange_recovers(self):
        self.switch()
        sw.FAULT = "rollback_exchanged"
        with self.assertRaises(sw.Crash):
            run(self.root, "rollback", "--apply")
        sw.FAULT = None
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())
        code, out = run(self.root, "recover", "--apply")
        self.assertEqual((code, out["recovered"]), (0, "rollback_exchanged"))
        self.assertEqual(self.journals(), [])
        shared_ids = {(os.stat(p).st_dev, os.stat(p).st_ino) for p in [self.shared, *self.shared.rglob("*")]}
        self.assertTrue(shared_ids <= set(self.fz.state))  # deactivated shared remains protected after recovery

    def test_crash_before_final_thaw_recovers_as_complete(self):
        self.crash("before_thaw")
        code, out = run(self.root, "recover", "--apply")
        self.assertEqual((code, out["recovered"]), (0, "switch_complete"))
        self.assertTrue(self.live.is_symlink())

    def test_journal_blocks_a_second_switch(self):
        self.crash("begin")
        code, out = run(self.root, "switch", "--apply", "--plan-id", "x")
        self.assertEqual(out["status"], "BLOCKED_JOURNAL_PRESENT_RUN_RECOVER")


class RollbackTests(Base):
    def test_rollback_restores_directory_and_copies_new_files_back(self):
        self.switch()
        (self.shared / "app/private/after-switch.png").write_bytes(b"new release upload")
        code, back = run(self.root, "rollback", "--apply")
        self.assertEqual((code, back["status"]), (0, "OK"))
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())
        self.assertEqual((self.live / "app/private/after-switch.png").read_bytes(), b"new release upload")
        self.assertEqual((self.live / "app/private/live-only.json").read_bytes(), b"{}")
        self.assertTrue(back["deactivated_shared_left_frozen"])
        live_ids = {(os.stat(p).st_dev, os.stat(p).st_ino) for p in [self.live, *self.live.rglob("*")]}
        self.assertFalse(live_ids & set(self.fz.state))  # restored storage is writable again
        shared_ids = {(os.stat(p).st_dev, os.stat(p).st_ino) for p in [self.shared, *self.shared.rglob("*")]}
        self.assertTrue(shared_ids <= set(self.fz.state))  # deactivated shared stays fully frozen

    def test_rollback_blocks_on_update_or_delete_and_restores_freeze_state(self):
        self.switch()
        (self.shared / "app/private/art.png").write_bytes(b"updated by new release")
        code, out = run(self.root, "rollback", "--apply")
        self.assertEqual(code, 2)
        self.assertIn("UPDATED_OR_DELETED_SINCE_SWITCH", out["status"])
        self.assertIn("app/private/art.png", out["status"])
        self.assertTrue(self.live.is_symlink())
        (self.shared / "app/private/art.png").write_bytes(b"artwork")
        (self.shared / "app/private/live-only.json").unlink()
        code, out = run(self.root, "rollback", "--apply")
        self.assertIn("live-only.json", out["status"])
        self.assertTrue(self.live.is_symlink())


class HardeningTests(Base):
    def test_partial_freeze_failure_restores_exact_state_and_journal_stays_clean(self):
        real = self.fz.set_immutable
        calls = {"n": 0}

        def flaky(fd, on):
            if on:
                calls["n"] += 1
                if calls["n"] == 2:
                    raise OSError(5, "EIO")
            return real(fd, on)

        self.fz.set_immutable = flaky
        code, out = self.switch()
        self.fz.set_immutable = real
        self.assertEqual(code, 2)
        self.assertEqual(self.fz.frozen_count(), 0)  # nothing stranded
        self.assertEqual(self.journals(), [])  # closed only because the trees verified clean
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())

    def test_failed_thaw_keeps_journal_open_for_recovery(self):
        real = self.fz.set_immutable

        def stuck(fd, on):
            if not on:
                raise OSError(5, "EIO")
            return real(fd, on)

        plan = self.plan()
        self.fz.set_immutable = stuck
        (self.shared / "app/private/art.png").write_bytes(b"DIFFERENT")  # force a revert path
        code, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        self.fz.set_immutable = real
        self.assertEqual(out["status"], "BLOCKED_RECOVERY_REQUIRED_JOURNAL_OPEN")
        self.assertEqual(len(self.journals()), 1)

    def test_late_top_level_entry_before_exchange_is_detected_and_reverted(self):
        real = sw.fault

        def hook(name):
            if name == "both_frozen":
                (self.live / "late-top-entry.json").write_bytes(b"late")
            return real(name)

        sw.fault = hook
        try:
            code, out = self.switch()
        finally:
            sw.fault = real
        self.assertEqual((code, out["status"]), (2, "BLOCKED_LIVE_CHANGED_UNDER_FREEZE"))
        self.assertTrue(self.live.is_dir() and (self.live / "late-top-entry.json").exists())
        self.assertEqual(self.fz.frozen_count(), 0)

    def test_late_entry_via_retained_top_fd_after_exchange_is_detected_and_reverted(self):
        real = sw.renameat2

        def hook(dfd, old, new, flags):
            if flags == sw.RENAME_NOREPLACE and old.startswith(sw.LINK):
                (self.root / "rel/apps/platform" / old / "late-after-exchange.json").write_bytes(b"late")
            return real(dfd, old, new, flags)

        sw.renameat2 = hook
        try:
            code, out = self.switch()
        finally:
            sw.renameat2 = real
        self.assertEqual((code, out["status"]), (2, "BLOCKED_PRESERVED_TREE_CHANGED"))
        self.assertTrue(out["reverted"])
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())
        self.assertTrue((self.live / "late-after-exchange.json").exists())  # not lost: old dir is live again
        self.assertEqual(self.fz.frozen_count(), 0)

    def test_failure_after_commit_never_reverts(self):
        sw.FAULT = None
        real = self.fz.set_immutable
        state = {"armed": False}

        def fail_thaw_once(fd, on):
            if not on and state["armed"]:
                state["armed"] = False
                raise OSError(5, "EIO")
            return real(fd, on)

        orig_fault = sw.fault

        def arm(name):
            if name == "before_thaw":
                state["armed"] = True
            return orig_fault(name)

        self.fz.set_immutable = fail_thaw_once
        sw.fault = arm
        try:
            code, out = self.switch()
        finally:
            sw.fault = orig_fault
            self.fz.set_immutable = real
        self.assertEqual(out["status"], "OK")
        self.assertIn("thaw needed a retry", out["note"])
        self.assertTrue(self.live.is_symlink())

    def test_top_dir_mode_mismatch_blocks(self):
        self.shared.chmod(0o750)
        plan = self.plan()
        self.assertFalse(plan["ready"])
        code, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        self.assertEqual(out["status"], "BLOCKED_TOP_DIR_MODE_OWNER_MISMATCH_LIVE_VS_SHARED")

    def test_top_dir_held_open_by_a_process_blocks(self):
        d = self.root / "proc/77"
        (d / "fd").mkdir(parents=True)
        (d / "cwd").symlink_to(str(self.live))
        plan = self.plan()
        code, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        self.assertEqual(out["status"], "BLOCKED_LIVE_TOP_DIR_HELD_OPEN")

    def test_state_dir_must_be_protected_and_outside_trees(self):
        plan = self.plan()
        (self.root / "state").chmod(0o755)
        self.assertEqual(run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])[1]["status"],
                         "BLOCKED_STATE_DIR_NOT_PROTECTED")
        (self.root / "state").chmod(0o700)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sw.main(["switch", "--apply", "--plan-id", plan["plan_id"],
                     "--app-dir", str(self.root / "rel/apps/platform"), "--shared", str(self.shared),
                     "--allowed-root", str(self.root), "--state-dir", str(self.shared / "state")])
        self.assertIn("STATE_DIR_INSIDE_TREES", buf.getvalue())

    def test_journal_symlink_wrong_mode_or_garbage_is_rejected(self):
        self.crash_begin()
        jfile = next((self.root / "state").glob("*.journal"))
        jfile.chmod(0o644)
        self.assertEqual(run(self.root, "recover")[1]["status"], "BLOCKED_JOURNAL_FILE_UNSAFE")
        jfile.chmod(0o600)
        jfile.write_text('{"phase":"rm -rf /","t":1}\n')
        self.assertEqual(run(self.root, "recover")[1]["status"], "BLOCKED_JOURNAL_INVALID")
        jfile.write_text('{"phase":"begin","t":1,"link":"../../etc"}\n')
        self.assertEqual(run(self.root, "recover")[1]["status"], "BLOCKED_JOURNAL_INVALID")
        target = self.root / "elsewhere"
        target.write_text("{}")
        jfile.unlink()
        jfile.symlink_to(target)
        self.assertNotEqual(run(self.root, "recover")[0], 0)

    def crash_begin(self):
        sw.FAULT = "begin"
        plan = self.plan()
        with self.assertRaises(sw.Crash):
            run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        sw.FAULT = None

    def test_traversal_uses_bounded_descriptors(self):
        import resource
        deep = self.live / "app/private"
        for i in range(400):
            (deep / f"f{i}.bin").write_bytes(b"x")
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        in_use = len(os.listdir('/proc/self/fd'))
        resource.setrlimit(resource.RLIMIT_NOFILE, (in_use + 40, hard))
        try:
            code, out = self.switch()
        finally:
            resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
        self.assertEqual((code, out["status"]), (0, "OK"))


class TransactionBlockerTests(Base):
    """Regressions for the b820d20b re-review blockers 2-5 (blocker 1 is in RealTransactionTests)."""

    def ids(self, root):
        return {(os.stat(p).st_dev, os.stat(p).st_ino) for p in [root, *root.rglob("*")]}

    def test_preexisting_immutable_state_is_preserved_exactly_when_blocked(self):
        for victim, name in ((self.live / "app/private", "live"), (self.shared / "app/private", "shared")):
            with self.subTest(victim=name):
                self.fz.state.clear()
                fd = sw.open_dir(victim)
                self.fz.set_immutable(fd, True)
                os.close(fd)
                before = dict(self.fz.state)
                plan = self.plan()
                code, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
                self.assertEqual((code, out["status"]), (2, "BLOCKED_ALREADY_IMMUTABLE_OR_APPEND_REVIEW"))
                self.assertEqual(self.fz.state, before)  # original bit NOT cleared, nothing else frozen
                self.assertEqual(self.journals(), [])
                self.assertTrue(self.live.is_dir() and not self.live.is_symlink())

    def _inject_late_top_entry_and_crash(self, fault_name):
        real = sw.pinned
        done = []

        def hook(c, live_fd):
            if not done:
                done.append(1)
                (self.live / "late-top-entry.json").write_bytes(b"late persistent record")
            return real(c, live_fd)

        sw.pinned = hook
        sw.FAULT = fault_name
        plan = self.plan()
        try:
            with self.assertRaises(sw.Crash):
                run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        finally:
            sw.pinned = real
            sw.FAULT = None

    def test_recover_after_crash_at_preserved_does_not_commit_unverified_tree(self):
        self._inject_late_top_entry_and_crash("preserved")
        self.assertTrue(self.live.is_symlink())
        code, out = run(self.root, "recover", "--apply")
        self.assertEqual((code, out["recovered"]), (0, "switch_reverted_unverified"))
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())
        self.assertEqual((self.live / "late-top-entry.json").read_bytes(), b"late persistent record")  # not lost
        self.assertEqual(self.journals(), [])
        self.assertFalse(self.ids(self.live) & set(self.fz.state))
        self.assertFalse(self.ids(self.shared) & set(self.fz.state))

    def test_recover_after_crash_at_verified_completes_without_reverting(self):
        self.crash("before_thaw")  # journal already says verified
        code, out = run(self.root, "recover", "--apply")
        self.assertEqual((code, out["recovered"]), (0, "switch_complete"))
        self.assertTrue(self.live.is_symlink())
        self.assertFalse(self.ids(self.shared) & set(self.fz.state))

    def test_recover_rejects_tampered_old_tree_even_if_layout_looks_complete(self):
        self.crash("preserved")
        kept = next(p for p in (self.root / "rel/apps/platform").iterdir() if p.name.startswith(sw.PRE))
        fd = sw.open_dir(kept)
        self.fz.set_immutable(fd, False)  # simulate a writer that slipped in through a retained top FD
        os.close(fd)
        (kept / "slipped-in.json").write_bytes(b"x")
        code, out = run(self.root, "recover", "--apply")
        self.assertEqual(out["recovered"], "switch_reverted_unverified")
        self.assertTrue((self.live / "slipped-in.json").exists())

    def test_shared_stays_frozen_after_rollback_so_stale_handles_cannot_write(self):
        self.switch()
        writer = os.open(self.shared / "app/private/art.png", os.O_WRONLY)
        try:
            code, out = run(self.root, "rollback", "--apply")
            self.assertEqual(code, 0)
            self.assertTrue(self.ids(self.shared) <= set(self.fz.state))
        finally:
            os.close(writer)

    def test_release_shared_is_explicit_and_refused_while_linked(self):
        self.switch()
        self.assertEqual(run(self.root, "release-shared", "--apply")[1]["status"], "BLOCKED_STORAGE_IS_LINKED_TO_SHARED")
        run(self.root, "rollback", "--apply")
        code, out = run(self.root, "release-shared", "--apply")
        self.assertEqual((code, out["status"]), (0, "OK"))
        self.assertFalse(self.ids(self.shared) & set(self.fz.state))

    def _rollback_crash(self, point):
        self.switch()
        sw.FAULT = point
        with self.assertRaises(sw.Crash):
            run(self.root, "rollback", "--apply")
        sw.FAULT = None

    def test_rollback_recovery_is_idempotent_at_every_crash_point(self):
        for point in ("rollback_begin", "rollback_shared_frozen", "rollback_old_thawed", "rollback_exchanged"):
            with self.subTest(point=point):
                self.tearDown()
                self.setUp()
                self._rollback_crash(point)
                code, out = run(self.root, "recover", "--apply")
                self.assertEqual(code, 0, out)
                self.assertEqual(self.journals(), [])
                again = run(self.root, "recover", "--apply")  # second run: nothing left, still OK
                self.assertEqual(again[0], 0)
                if point == "rollback_exchanged":
                    self.assertTrue(self.live.is_dir() and not self.live.is_symlink())
                    self.assertTrue(self.ids(self.shared) <= set(self.fz.state))
                    self.assertFalse(self.ids(self.live) & set(self.fz.state))
                else:
                    self.assertTrue(self.live.is_symlink())
                    self.assertFalse(self.ids(self.shared) & set(self.fz.state))
                    kept = next(p for p in (self.root / "rel/apps/platform").iterdir() if p.name.startswith(sw.PRE))
                    self.assertTrue(self.ids(kept) <= set(self.fz.state))  # evidence copy fully re-frozen

    def test_rollback_recovery_after_partial_old_tree_thaw(self):
        self.switch()
        real = self.fz.set_immutable
        kept = next(p for p in (self.root / "rel/apps/platform").iterdir() if p.name.startswith(sw.PRE))
        old_ids = self.ids(kept)
        n = {"thaws": 0}

        def dying(fd, on):
            st = os.fstat(fd)
            if not on and (st.st_dev, st.st_ino) in old_ids:
                n["thaws"] += 1
                if n["thaws"] == 3:
                    raise sw.Crash("mid-thaw")
            return real(fd, on)

        self.fz.set_immutable = dying
        with self.assertRaises(sw.Crash):
            run(self.root, "rollback", "--apply")
        self.fz.set_immutable = real
        partly = old_ids & set(self.fz.state)
        self.assertTrue(0 < len(partly) < len(old_ids))  # genuinely half-thawed
        code, out = run(self.root, "recover", "--apply")
        self.assertEqual(code, 0, out)
        self.assertTrue(old_ids <= set(self.fz.state))
        self.assertTrue(self.live.is_symlink())


def force_thaw(root):
    """Test cleanup only: clear any immutable bit left by a failed assertion so the tmpdir can be removed."""
    real = sw.Freezer()
    for dirpath, dirs, files in os.walk(root):
        for name in [dirpath, *[os.path.join(dirpath, n) for n in dirs + files]]:
            try:
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            except OSError:
                continue
            try:
                real.set_immutable(fd, False)
            except OSError:
                pass
            finally:
                os.close(fd)


@unittest.skipUnless(os.geteuid() == 0 or os.environ.get("KMJ_REQUIRE_REAL_IMMUTABLE"), "needs root + CAP_LINUX_IMMUTABLE")
class RealTransactionTests(Base):
    """Real chattr end to end: real freeze, real crash, real recover (the fake freezer cannot catch these)."""

    def setUp(self):
        super().setUp()
        sw.FREEZER = sw.Freezer()

    def tearDown(self):
        force_thaw(self.root)
        super().tearDown()

    def real_flags(self, path):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            return sw.Freezer().flags(fd) & sw.FS_IMMUTABLE_FL
        finally:
            os.close(fd)

    def test_recover_works_while_shared_top_is_really_immutable(self):
        self.crash("both_frozen")
        self.assertTrue(self.real_flags(self.shared))  # probe used to live here and died with EPERM
        with self.assertRaises(OSError):
            open(self.shared / "probe-here", "w")
        code, out = run(self.root, "recover", "--apply")
        self.assertEqual((code, out["recovered"]), (0, "switch_reverted"))
        self.assertFalse(self.real_flags(self.shared))
        self.assertFalse(self.real_flags(self.live / "app/private/art.png"))
        self.assertEqual(self.journals(), [])
        self.assertEqual([p.name for p in (self.root / "rel/apps/platform").iterdir() if p.name.startswith(".kmj-probe")], [])

    def test_real_crash_at_preserved_with_late_file_reverts_not_commits(self):
        real = sw.pinned
        done = []

        def hook(c, live_fd):
            if not done:
                done.append(1)
                (self.live / "late.json").write_bytes(b"late")
            return real(c, live_fd)

        sw.pinned, sw.FAULT = hook, "preserved"
        plan = self.plan()
        try:
            with self.assertRaises(sw.Crash):
                run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        finally:
            sw.pinned, sw.FAULT = real, None
        code, out = run(self.root, "recover", "--apply")
        self.assertEqual((code, out["recovered"]), (0, "switch_reverted_unverified"))
        self.assertEqual((self.live / "late.json").read_bytes(), b"late")
        self.assertFalse(self.real_flags(self.live / "app/private/art.png"))

    def test_real_stale_shared_handle_cannot_write_after_rollback(self):
        self.assertEqual(self.switch()[1]["status"], "OK")
        writer = os.open(self.shared / "app/private/art.png", os.O_WRONLY)
        try:
            self.assertEqual(run(self.root, "rollback", "--apply")[1]["status"], "OK")
            with self.assertRaises(OSError):
                os.write(writer, b"late write through retained fd")
            self.assertEqual((self.shared / "app/private/art.png").read_bytes(), b"artwork")
        finally:
            os.close(writer)

    def test_real_rollback_crash_after_exchange_recovers(self):
        self.switch()
        sw.FAULT = "rollback_old_thawed"
        with self.assertRaises(sw.Crash):
            run(self.root, "rollback", "--apply")
        sw.FAULT = None
        code, out = run(self.root, "recover", "--apply")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.live.is_symlink())
        self.assertFalse(self.real_flags(self.shared))
        self.assertTrue(self.real_flags(next(p for p in (self.root / "rel/apps/platform").iterdir()
                                             if p.name.startswith(sw.PRE))))


@unittest.skipUnless(os.geteuid() == 0 or os.environ.get("KMJ_REQUIRE_REAL_IMMUTABLE"), "needs root + CAP_LINUX_IMMUTABLE")
class RealImmutableTests(unittest.TestCase):
    def test_real_freeze_blocks_preopened_writer_rename_unlink_and_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "d").mkdir()
            target = root / "d/f"
            target.write_bytes(b"x")
            try:
                fd = sw.open_dir(root / "d")
                real = sw.Freezer()
                real.flags(fd)
            except OSError:
                if os.environ.get("KMJ_REQUIRE_REAL_IMMUTABLE"):
                    self.fail("real immutable test required but FS_IOC_GETFLAGS unsupported")
                self.skipTest("filesystem does not support FS_IOC_GETFLAGS")
            writer = os.open(target, os.O_WRONLY)
            old = sw.FREEZER
            sw.FREEZER = real
            try:
                try:
                    sw.freeze(fd, include_top=True)
                except sw.Blocked as exc:
                    if os.environ.get("KMJ_REQUIRE_REAL_IMMUTABLE"):
                        self.fail("real immutable test required: " + str(exc))
                    self.skipTest(str(exc))
                for action in (lambda: os.write(writer, b"y"), lambda: os.rename(target, root / "d/g"),
                               lambda: os.unlink(target), lambda: open(root / "d/new", "w")):
                    with self.assertRaises(OSError):
                        action()
                self.assertEqual(target.read_bytes(), b"x")
            finally:
                sw.thaw(fd, include_top=True)
                sw.FREEZER = old
                os.close(writer)
            os.write(os.open(target, os.O_WRONLY), b"z")  # writable again after thaw

    def test_real_require_ready_probe_proves_capability(self):
        with tempfile.TemporaryDirectory() as tmp:
            sw.Freezer().require_ready(tmp)
            self.assertEqual(os.listdir(tmp), [])


if __name__ == "__main__":
    unittest.main()
