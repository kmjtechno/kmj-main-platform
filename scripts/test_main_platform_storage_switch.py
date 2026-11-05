import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "operations"))
import main_platform_storage_switch as sw  # noqa: E402


def run(root, command, *extra, proc=None):
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = sw.main([command, "--app-dir", str(root / "rel/apps/platform"),
                        "--shared", str(root / "shared/storage"),
                        "--allowed-root", str(root),
                        "--proc-root", str(proc or (root / "proc")), *extra])
    return code, json.loads(buf.getvalue())


class StorageSwitchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.live = self.root / "rel/apps/platform/storage"
        self.shared = self.root / "shared/storage"
        for p in (self.live / "app/private", self.live / "framework/views", self.live / "logs",
                  self.shared / "app/private", self.shared / "framework/views"):
            p.mkdir(parents=True)
        (self.root / "proc").mkdir()
        (self.root / "shared").chmod(0o700)
        self.shared.chmod(0o700)
        (self.live / "app/private/art.png").write_bytes(b"artwork")
        (self.live / "app/private/live-only.json").write_bytes(b"{}")
        (self.shared / "app/private/art.png").write_bytes(b"artwork")
        (self.live / "framework/views/x.php").write_bytes(b"live-compiled")
        (self.shared / "framework/views/x.php").write_bytes(b"cand-compiled")

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self):
        return run(self.root, "plan")[1]

    def test_plan_is_read_only_and_ignores_regenerable_differences(self):
        before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*"))
        plan = self.plan()
        self.assertTrue(plan["ready"])
        self.assertEqual(plan["to_copy"], 1)
        self.assertFalse(plan["mutated"])
        self.assertEqual(before, sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*")))

    def test_switch_is_lossless_atomic_and_preserves_original(self):
        plan = self.plan()
        code, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        self.assertEqual((code, out["status"]), (0, "OK"))
        self.assertTrue(self.live.is_symlink())
        self.assertEqual(self.live.resolve(), self.shared.resolve())
        self.assertEqual((self.shared / "app/private/live-only.json").read_bytes(), b"{}")
        kept = self.root / "rel/apps/platform" / out["preserved_dir"]
        self.assertEqual((kept / "app/private/art.png").read_bytes(), b"artwork")
        self.assertEqual((kept / "framework/views/x.php").read_bytes(), b"live-compiled")
        self.assertFalse(out["deleted_anything"])

    def test_divergent_persistent_file_blocks_and_never_overwrites(self):
        (self.shared / "app/private/art.png").write_bytes(b"DIFFERENT")
        plan = self.plan()
        self.assertFalse(plan["ready"])
        self.assertEqual(plan["persistent_conflicts"], ["app/private/art.png"])
        code, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        self.assertEqual(code, 2)
        self.assertTrue(out["status"].startswith("BLOCKED"))
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())
        self.assertEqual((self.shared / "app/private/art.png").read_bytes(), b"DIFFERENT")

    def test_switch_requires_apply_and_fresh_plan_id(self):
        self.assertEqual(run(self.root, "switch")[0], 2)
        plan = self.plan()
        (self.live / "app/private/new.bin").write_bytes(b"written after review")
        code, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        self.assertEqual((code, out["status"]), (2, "BLOCKED_PLAN_ID_STALE_REVIEW_AGAIN"))
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())

    def test_straggler_written_to_old_dir_after_switch_is_reconciled(self):
        plan = self.plan()
        _, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        kept = out["preserved_dir"]
        (self.root / "rel/apps/platform" / kept / "app/private/late-upload.png").write_bytes(b"late")
        code, rec = run(self.root, "reconcile", "--apply", "--src-dir", kept)
        self.assertEqual((code, rec["status"]), (0, "OK"))
        self.assertEqual((self.shared / "app/private/late-upload.png").read_bytes(), b"late")

    def test_rollback_restores_directory_and_copies_new_uploads_back(self):
        plan = self.plan()
        _, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        (self.shared / "app/private/after-switch.png").write_bytes(b"new release upload")
        code, back = run(self.root, "rollback", "--apply")
        self.assertEqual((code, back["status"]), (0, "OK"))
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())
        self.assertEqual((self.live / "app/private/after-switch.png").read_bytes(), b"new release upload")
        self.assertEqual((self.live / "app/private/live-only.json").read_bytes(), b"{}")
        self.assertTrue((self.shared / "app/private/after-switch.png").exists())

    def test_symlink_special_and_hardlink_entries_are_refused(self):
        os.symlink("/etc/passwd", self.live / "app/evil")
        code, out = run(self.root, "plan")
        self.assertEqual((code, out["status"]), (2, "BLOCKED_SYMLINK_OR_SPECIAL_ENTRY"))
        os.unlink(self.live / "app/evil")
        os.link(self.live / "app/private/art.png", self.live / "app/private/hard.png")
        code, out = run(self.root, "plan")
        self.assertEqual((code, out["status"]), (2, "BLOCKED_UNSAFE_FILE"))

    def test_paths_outside_allowed_root_are_refused(self):
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = sw.main(["plan", "--app-dir", str(self.root / "rel/apps/platform"),
                            "--shared", str(self.root / "shared/storage"),
                            "--allowed-root", str(self.root / "shared")])
        self.assertEqual(code, 2)
        self.assertIn("PATH_OUTSIDE_ALLOWED_ROOT", buf.getvalue())

    def test_dotdot_and_symlinked_paths_are_not_canonical(self):
        import io
        import contextlib

        sneaky = str(self.root / "shared/../rel/apps/platform")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = sw.main(["plan", "--app-dir", sneaky, "--shared", str(self.shared),
                            "--allowed-root", str(self.root / "shared")])
        self.assertEqual(code, 2)
        self.assertIn("PATH_NOT_CANONICAL", buf.getvalue())

    def test_nested_shared_target_is_refused(self):
        inner = self.root / "rel/apps/platform/storage/app/shared-inside"
        inner.mkdir()
        inner.chmod(0o700)
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = sw.main(["plan", "--app-dir", str(self.root / "rel/apps/platform"),
                            "--shared", str(self.root / "rel/apps/platform"),
                            "--allowed-root", str(self.root), "--proc-root", str(self.root / "proc")])
        self.assertEqual(code, 2)
        self.assertIn("NESTED_OR_SAME_TARGET", buf.getvalue())

    def _fake_holder(self, target, kind="fd"):
        d = self.root / "proc/4242"
        (d / "fd").mkdir(parents=True, exist_ok=True)
        (d / "maps").write_text("")
        for n in ("cwd", "root"):
            if not (d / n).is_symlink():
                (d / n).symlink_to("/")
        if kind == "fd":
            (d / "fd/7").symlink_to(str(target))
        else:
            (d / "cwd").unlink()
            (d / "cwd").symlink_to(str(target))

    def test_open_handle_in_live_tree_blocks_switch(self):
        plan = self.plan()
        self._fake_holder(self.live / "app/private/art.png")
        code, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        self.assertEqual((code, out["status"]), (2, "BLOCKED_WRITERS_NOT_PROVEN_QUIET"))
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())

    def test_cwd_inside_live_tree_blocks_switch(self):
        plan = self.plan()
        self._fake_holder(self.live / "logs", kind="cwd")
        self.assertEqual(run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])[1]["status"],
                         "BLOCKED_WRITERS_NOT_PROVEN_QUIET")

    def test_unreadable_process_means_quiet_is_unproven(self):
        plan = self.plan()
        d = self.root / "proc/99"
        d.mkdir()
        (d / "cwd").write_text("x")  # readlink -> EINVAL -> unreadable, not "exited"
        code, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        self.assertEqual((code, out["status"]), (2, "BLOCKED_WRITERS_NOT_PROVEN_QUIET"))

    def test_real_proc_unprivileged_cannot_prove_quiet(self):
        if os.geteuid() == 0:
            self.skipTest("root can read all of /proc")
        self.assertFalse(sw.open_handles(self.live)["proven_quiet"])

    def test_writer_appearing_after_exchange_reverts_the_swap(self):
        plan = self.plan()
        real = sw.open_handles
        calls = []

        def fake(tree, proc_root="/proc"):
            calls.append(str(tree))
            if len(calls) == 2:
                return {"holders": [1], "unreadable_processes": 0, "proven_quiet": False}
            return real(tree, proc_root)

        sw.open_handles = fake
        try:
            code, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        finally:
            sw.open_handles = real
        self.assertEqual((code, out["status"]), (2, "BLOCKED_WRITER_APPEARED_REVERTED"))
        self.assertTrue(self.live.is_dir() and not self.live.is_symlink())
        self.assertEqual((self.live / "app/private/live-only.json").read_bytes(), b"{}")

    def test_short_writes_are_completed_and_verified(self):
        real = os.write
        big = os.urandom(300000)
        (self.live / "app/private/big.bin").write_bytes(big)
        os.write = lambda fd, data: real(fd, bytes(data)[:7]) if len(data) > 7 else real(fd, data)
        try:
            plan = self.plan()
            code, out = run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
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
        with self.assertRaises(sw.Blocked):
            sw._write_all = boom
            try:
                sw.copy_create_only(a, b, "app/private/x.bin", (hashlib.sha256(b"data").hexdigest(), 4, 0o600))
            finally:
                sw._write_all = real
        names = [p.name for p in (self.shared / "app/private").iterdir()]
        self.assertNotIn("x.bin", names)
        self.assertFalse([n for n in names if n.startswith(".kmj-tmp")])

    def test_reconcile_src_must_be_preserved_basename(self):
        for bad in ("../x", "storage", "storage.pre-shared-a/b", ""):
            self.assertEqual(run(self.root, "reconcile", "--src-dir", bad)[0], 2)

    def test_rollback_blocks_when_persistent_file_was_updated_or_deleted(self):
        plan = self.plan()
        run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        (self.shared / "app/private/art.png").write_bytes(b"updated by new release")
        code, out = run(self.root, "rollback", "--apply")
        self.assertEqual((code, out["status"]), (2, "BLOCKED_UPDATED_OR_DELETED_SINCE_SWITCH"))
        self.assertEqual(out["updated"], ["app/private/art.png"])
        self.assertTrue(self.live.is_symlink())
        (self.shared / "app/private/art.png").write_bytes(b"artwork")
        (self.shared / "app/private/live-only.json").unlink()
        code, out = run(self.root, "rollback", "--apply")
        self.assertEqual(out["deleted"], ["app/private/live-only.json"])
        self.assertTrue(self.live.is_symlink())

    def test_empty_directories_and_modes_are_preserved(self):
        (self.live / "app/public").mkdir()
        (self.live / "app/public").chmod(0o750)
        plan = self.plan()
        run(self.root, "switch", "--apply", "--plan-id", plan["plan_id"])
        made = self.shared / "app/public"
        self.assertTrue(made.is_dir())
        self.assertEqual(made.stat().st_mode & 0o777, 0o750)

    def test_recover_is_read_only(self):
        code, out = run(self.root, "recover")
        self.assertEqual((code, out["status"], out["mutated"]), (0, "OK", False))

    def test_copy_never_clobbers_a_file_created_concurrently(self):
        meta = (hashlib.sha256(b"mine").hexdigest(), 4, 0o600)
        (self.live / "app/private/race.bin").write_bytes(b"mine")
        (self.shared / "app/private/race.bin").write_bytes(b"theirs")
        a, b = sw.open_dir(self.live), sw.open_dir(self.shared)
        with self.assertRaises(sw.Blocked):
            sw.copy_create_only(a, b, "app/private/race.bin", meta)
        self.assertEqual((self.shared / "app/private/race.bin").read_bytes(), b"theirs")
        self.assertEqual([p.name for p in (self.shared / "app/private").iterdir() if p.name.startswith(".kmj-tmp")], [])


if __name__ == "__main__":
    unittest.main()
