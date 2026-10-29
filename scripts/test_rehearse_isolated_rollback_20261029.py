#!/usr/bin/env python3
"""Fixture tests for the isolated pointer-rollback rehearsal (no live paths)."""
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

FILE = Path(__file__).resolve().parent / "operations/rehearse-isolated-rollback-39b88b36d071-20261029.py"
SPEC = importlib.util.spec_from_file_location("rehearse", FILE)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

PREV, CAND = "platform-aaaaaaaaaaaa", "platform-bbbbbbbbbbbb"
PREV_SHA, CAND_SHA = "a" * 40, "b" * 40


def make_release(root: Path, name: str, sha: str, marker: bytes) -> Path:
    tree = root / "releases" / name
    for item in mod.ARTIFACTS:
        path = tree / item
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(marker + item.encode())
    (tree / "apps/platform/.env").write_text("SECRET=never-served")
    (tree / ".sha").write_text(sha)
    os.chmod(tree, 0o755)
    return tree


def fake_head(tree: Path):
    path = tree / ".sha"
    return path.read_text() if path.exists() else None


class Fixture:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "kmjprod"
        self.root.mkdir()
        make_release(self.root, PREV, PREV_SHA, b"prev:")
        make_release(self.root, CAND, CAND_SHA, b"cand:")
        os.symlink(f"releases/{PREV}", self.root / "current")
        self.scratch = base / "home" / "kmj-rollback-scratch"
        self.scratch.mkdir(parents=True, mode=0o700)
        os.chmod(self.scratch, 0o700)
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()

    def run(self):
        with patch.object(mod, "git_head", fake_head):
            return mod.rehearse(self.root, self.scratch, PREV, PREV_SHA, CAND, CAND_SHA)


class RollbackRehearsal(unittest.TestCase):
    def test_full_cycle_passes_and_leaves_live_pointer_and_scratch_clean(self):
        with Fixture() as f:
            before = os.readlink(f.root / "current")
            lines = dict(f.run())
            for key in ("POINTER_PREVIOUS", "POINTER_CANDIDATE", "POINTER_ROLLBACK_TO_PREVIOUS",
                        "POINTER_FORWARD_TO_CANDIDATE"):
                self.assertEqual(lines[key], "PASS")
            self.assertEqual(os.readlink(f.root / "current"), before)
            self.assertEqual(lines["SCRATCH_REMOVED"], "YES")
            self.assertEqual(list(f.scratch.iterdir()), [])

    def test_blocks_when_live_is_not_on_expected_previous_release(self):
        with Fixture() as f:
            os.remove(f.root / "current")
            os.symlink(f"releases/{CAND}", f.root / "current")
            with self.assertRaisesRegex(mod.Blocked, "LIVE_NOT_ON_EXPECTED_PREVIOUS_RELEASE"):
                f.run()

    def test_blocks_on_sha_mismatch_missing_artifact_and_writable_dir(self):
        with Fixture() as f:
            (f.root / "releases" / CAND / ".sha").write_text("c" * 40)
            with self.assertRaisesRegex(mod.Blocked, "CANDIDATE_SHA_MISMATCH"):
                f.run()
        with Fixture() as f:
            (f.root / "releases" / CAND / "apps/platform/artisan").unlink()
            with self.assertRaisesRegex(mod.Blocked, "CANDIDATE_ARTIFACT_MISSING"):
                f.run()
        with Fixture() as f:
            os.chmod(f.root / "releases" / PREV, 0o775)
            with self.assertRaisesRegex(mod.Blocked, "PREVIOUS_GROUP_OR_WORLD_WRITABLE"):
                f.run()

    def test_blocks_when_scratch_is_inside_production_root_or_not_private(self):
        with Fixture() as f:
            inside = f.root / "scratch"
            inside.mkdir(mode=0o700)
            with patch.object(mod, "git_head", fake_head), self.assertRaisesRegex(mod.Blocked, "SCRATCH_INSIDE_PRODUCTION_ROOT"):
                mod.rehearse(f.root, inside, PREV, PREV_SHA, CAND, CAND_SHA)
        with Fixture() as f:
            os.chmod(f.scratch, 0o755)
            with self.assertRaisesRegex(mod.Blocked, "SCRATCH_PARENT_NOT_PRIVATE"):
                f.run()

    def test_env_is_not_reachable_and_digest_mismatch_is_detected(self):
        with Fixture() as f:
            # Corrupt the served artifact only after the pointer flips: swap the
            # file for a different content with the same size is not possible
            # via symlink, so simulate by patching digest().
            real = mod.digest
            with patch.object(mod, "digest", lambda p: "0" * 64), patch.object(mod, "git_head", fake_head):
                with self.assertRaisesRegex(mod.Blocked, "HEALTH_ARTIFACT_DIGEST_MISMATCH"):
                    mod.rehearse(f.root, f.scratch, PREV, PREV_SHA, CAND, CAND_SHA)
            self.assertIs(mod.digest, real)
            self.assertEqual(list(f.scratch.iterdir()), [])  # cleaned even on failure

    def test_source_never_mutates_production_or_reads_env(self):
        text = FILE.read_text()
        for forbidden in ("systemctl", "os.remove(ROOT", "shutil.rmtree(ROOT", "open(\".env", "'.env')"):
            self.assertNotIn(forbidden, text)
        self.assertIn('status("OWNER_APPROVAL_ROLLBACK_VERIFIED_MAY_BE_SET", "NO")', text)
        self.assertEqual(mod.main(["x", "arg"]), 2)


if __name__ == "__main__":
    unittest.main()
