"""No network, no root, no shared-checkout mutation, no production operations."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "operations"))
from prepare_fresh_main_worktree_20261031 import prepare, Blocked, main


def git(path, *args):
    r = subprocess.run(["git", "-C", str(path), *args], text=True, capture_output=True, check=True)
    return r.stdout.strip()


class IsolatedWorktreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="kmj-fresh-lane-"))
        self.addCleanup(shutil.rmtree, self.temp, True)
        self.repo = self.temp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "checkout", "-q", "-b", "main")
        (self.repo / "a.txt").write_text("tracked\n")
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-q", "-m", "initial")
        self.sha = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "update-ref", "refs/remotes/origin/main", self.sha)
        (self.repo / "dirty-untracked.txt").write_text("must remain")

    def call(self, lane="ci_lane", sha=None, fetch=False):
        with patch("prepare_fresh_main_worktree_20261031.os.geteuid", return_value=os.getuid() or 1000):
            return prepare(self.repo, sha or self.sha, lane, fetch=fetch)

    def test_cached_exact_sha_creates_detached_lane_preserves_dirty(self):
        result = self.call()
        self.assertEqual(result["status"], "PREPARED_SOURCE_ONLY")
        self.assertFalse(result["remoteRefreshed"])
        self.assertFalse(result["productionReleaseAttested"])
        self.assertEqual(git(Path(result["path"]), "rev-parse", "HEAD"), self.sha)
        self.assertEqual((self.repo / "dirty-untracked.txt").read_text(), "must remain")
        self.assertIn("?? dirty-untracked.txt", git(self.repo, "status", "--short"))

    def test_tracked_and_untracked_dirty_shared_bytes_unchanged(self):
        (self.repo / "a.txt").write_text("local modification\n")
        before = git(self.repo, "status", "--porcelain=v1", "--untracked-files=all")
        self.call(lane="tracked_dirty")
        self.assertEqual((self.repo / "a.txt").read_text(), "local modification\n")
        self.assertEqual(git(self.repo, "status", "--porcelain=v1", "--untracked-files=all"), before)

    def test_stale_sha_fails_closed_before_checkout(self):
        with self.assertRaisesRegex(Blocked, "REMOTE_MAIN_SHA_MISMATCH"):
            self.call(sha="b" * 40)
        self.assertFalse((self.repo / ".git/kmj-fresh-main-lanes/ci_lane").exists())

    def test_existing_lane_not_reused_or_removed(self):
        self.call()
        target = self.repo / ".git/kmj-fresh-main-lanes/ci_lane"
        (target / "local-work.txt").write_text("preserve")
        with self.assertRaisesRegex(Blocked, "LANE_ALREADY_EXISTS"):
            self.call()
        self.assertEqual((target / "local-work.txt").read_text(), "preserve")

    def test_symlink_cache_rejected_without_follow(self):
        outside = self.temp / "outside"; outside.mkdir()
        cache = self.repo / ".git/kmj-fresh-main-lanes"
        cache.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(Blocked, "CACHE_DIRECTORY_UNSAFE"):
            self.call()
        self.assertEqual(list(outside.iterdir()), [])

    def test_loose_cache_mode_rejected(self):
        cache = self.repo / ".git/kmj-fresh-main-lanes"
        cache.mkdir(mode=0o777)
        cache.chmod(0o755)
        with self.assertRaisesRegex(Blocked, "CACHE_DIRECTORY_UNSAFE"):
            self.call()

    def test_bad_lane_id_rejected(self):
        for lane in ("../escape", "a/b", "a b", ".hidden", "", "a" * 49):
            with self.subTest(lane=lane), self.assertRaisesRegex(Blocked, "INVALID_ARGUMENT"):
                self.call(lane=lane)

    def test_noncanonical_origin_rejected_before_fetch(self):
        git(self.repo, "remote", "add", "origin", "git@github.com:kmjtechno/kmj-main-platform.git")
        with self.assertRaisesRegex(Blocked, "ORIGIN_NOT_CANONICAL_HTTPS"):
            self.call(fetch=True)
        self.assertEqual((self.repo / "dirty-untracked.txt").read_text(), "must remain")

    def test_root_denied_even_in_cached_mode(self):
        with patch("prepare_fresh_main_worktree_20261031.os.geteuid", return_value=0):
            with self.assertRaisesRegex(Blocked, "ROOT_NOT_ALLOWED"):
                prepare(self.repo, self.sha, "lane", fetch=False)

    def test_cli_failure_is_bounded_secret_free(self):
        with patch("prepare_fresh_main_worktree_20261031.os.geteuid", return_value=0):
            with contextlib.redirect_stdout(io.StringIO()) as stream:
                rc = main(["--repo", str(self.repo), "--expected-main-sha", self.sha, "--lane", "lane"])
        self.assertEqual(rc, 2)
        self.assertEqual(json.loads(stream.getvalue()), {
            "status": "BLOCKED", "reason": "ROOT_NOT_ALLOWED", "productionReleaseAttested": False})


if __name__ == "__main__":
    unittest.main()
