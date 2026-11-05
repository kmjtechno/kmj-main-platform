import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "operations"))
import main_platform_storage_switch as sw  # noqa: E402


def run(root, command, *extra):
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = sw.main([command, "--app-dir", str(root / "rel/apps/platform"),
                        "--shared", str(root / "shared/storage"),
                        "--allowed-root", str(root), *extra])
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

    def test_paths_outside_allowed_root_and_symlinked_roots_are_refused(self):
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = sw.main(["plan", "--app-dir", str(self.root / "rel/apps/platform"),
                            "--shared", str(self.root / "shared/storage"),
                            "--allowed-root", str(self.root / "shared")])
        self.assertEqual(code, 2)
        self.assertIn("PATH_OUTSIDE_ALLOWED_ROOT", buf.getvalue())

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
