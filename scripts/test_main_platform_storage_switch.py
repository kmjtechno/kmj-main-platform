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

    def require_ready(self):
        pass

    def frozen_count(self):
        return len(self.state)


def run(root, command, *extra):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = sw.main([command, "--app-dir", str(root / "rel/apps/platform"),
                        "--shared", str(root / "shared/storage"),
                        "--allowed-root", str(root), *extra])
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

    def journals(self):
        """Open journals only; closed ones are kept as .done-* receipts."""
        return sorted(p.name for p in (self.root / "shared").glob(".kmj-storage-switch-*.journal"))


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
        self.assertEqual((code, out["status"]), (2, "BLOCKED_ALREADY_IMMUTABLE_REVIEW"))


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
    def crash(self, phase):
        sw.FAULT = phase
        plan = self.plan()
        with self.assertRaises(sw.Crash):
            run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        sw.FAULT = None

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
        self.assertEqual((code, out["recovered_from"]), (0, "exchanged"))
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
        self.assertEqual((code, out["recovered_from"]), (0, "preserved"))
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
        self.assertEqual(self.fz.frozen_count(), 0)

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


@unittest.skipUnless(os.geteuid() == 0, "needs root + CAP_LINUX_IMMUTABLE")
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
                self.skipTest("filesystem does not support FS_IOC_GETFLAGS")
            writer = os.open(target, os.O_WRONLY)
            old = sw.FREEZER
            sw.FREEZER = real
            try:
                try:
                    sw.freeze(fd, include_top=True)
                except sw.Blocked as exc:
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


if __name__ == "__main__":
    unittest.main()
