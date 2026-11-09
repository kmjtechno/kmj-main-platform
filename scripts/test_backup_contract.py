from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / "scripts" / "backup_platform.sh"


def executable(path: Path, source: str) -> None:
    path.write_text(source, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class BackupContractTest(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.app = self.tmp / "platform"
        storage = self.app / "storage" / "app"
        storage.mkdir(parents=True)
        (storage / "proof.txt").write_text("backup-contract", encoding="utf-8")
        self.status_dir = self.tmp / "status"
        self.marker = self.tmp / "rclone.marker"

        executable(self.bin / "pg_dump", """#!/usr/bin/env python3
import pathlib, sys
for item in sys.argv[1:]:
    if item.startswith("--file="):
        pathlib.Path(item.split("=", 1)[1]).write_bytes(b"mock-db")
""")
        executable(self.bin / "age", """#!/usr/bin/env python3
import shutil, sys
args = sys.argv[1:]
out = args[args.index("-o") + 1]
shutil.copyfile(args[-1], out)
""")
        executable(self.bin / "rclone", """#!/usr/bin/env python3
import os, pathlib, shutil, sys
args = sys.argv[1:]
if len(args) < 3 or args[0] != "copyto":
    sys.exit(20)
src, dst = args[1:3]
download = src.startswith("mock:")
behavior = os.environ.get("FAKE_REMOTE_BEHAVIOR", "ok")
if (behavior == "upload_fail" and not download) or (behavior == "readback_fail" and download):
    sys.exit(21)
def remote_path(value):
    if value.startswith("mock:"):
        return pathlib.Path(os.environ["FAKE_REMOTE_ROOT"]) / value.removeprefix("mock:")
    return pathlib.Path(value)
destination = remote_path(dst)
destination.parent.mkdir(parents=True, exist_ok=True)
if not download:
    if "--immutable" not in args:
        sys.exit(22)
    if destination.exists():
        sys.exit(23)
shutil.copyfile(remote_path(src), destination)
if behavior == "corrupt_readback" and download:
    with destination.open("ab") as handle:
        handle.write(b"corrupt")
with open(os.environ["FAKE_REMOTE_MARKER"], "a", encoding="utf-8") as handle:
    handle.write(("get " if download else "put ") + str(src) + "\\n")
""")

        self.secret = "postgresql://user:super-secret@example.invalid/kmj"
        self.env = os.environ.copy()
        self.env.update({
            "PATH": f"{self.bin}:{self.env['PATH']}",
            "APP_ROOT": str(self.app),
            "BACKUP_DATABASE_URL": self.secret,
            "BACKUP_REMOTE": "mock:kmj-platform/staging",
            "BACKUP_AGE_RECIPIENT": "age1testrecipient",
            "BACKUP_TIER": "daily",
            "BACKUP_STATUS_DIR": str(self.status_dir),
            "FAKE_REMOTE_ROOT": str(self.tmp / "remote"),
            "FAKE_REMOTE_MARKER": str(self.marker),
        })

    def run_backup(self, behavior: str = "ok", **overrides: str) -> subprocess.CompletedProcess:
        env = {**self.env, "FAKE_REMOTE_BEHAVIOR": behavior, **overrides}
        run = subprocess.run(["bash", str(BACKUP)], env=env, text=True,
                             capture_output=True, check=False)
        output = run.stdout + run.stderr
        self.assertNotIn(self.secret, output)
        self.assertNotIn("super-secret", output)
        return run

    def test_success_requires_an_upload_and_matching_remote_readback(self) -> None:
        run = self.run_backup()
        output = run.stdout + run.stderr
        self.assertEqual(run.returncode, 0, output)
        transfer = self.marker.read_text(encoding="utf-8")
        self.assertIn("put ", transfer)
        self.assertIn("get mock:kmj-platform/staging/daily/", transfer)
        status_file = self.status_dir / "backup-status-daily.status"
        self.assertTrue(status_file.exists(), output)
        self.assertEqual(stat.S_IMODE(status_file.stat().st_mode), 0o600)
        status = status_file.read_text(encoding="utf-8")
        self.assertIn("status=success", status)
        self.assertIn("completed_at_utc=", status)
        self.assertNotIn(self.secret, status)
        self.assertNotIn("BACKUP_REMOTE", status)
        self.assertIn("SHA-256 readback verified", output)

    def test_two_backups_in_one_second_cannot_overwrite_remote_object(self) -> None:
        first = self.run_backup()
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_backup()
        self.assertEqual(second.returncode, 0, second.stderr)
        remote_dir = self.tmp / "remote" / "kmj-platform" / "staging" / "daily"
        objects = list(remote_dir.glob("*.tar.gz.age"))
        self.assertEqual(len(objects), 2)
        self.assertNotEqual(objects[0].name, objects[1].name)
        for path in objects:
            self.assertRegex(path.name, r"-[0-9a-f]{24}\.tar\.gz\.age$")

    def test_upload_failure_never_publishes_success(self) -> None:
        run = self.run_backup("upload_fail")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("upload failed", run.stderr)
        self.assertFalse((self.status_dir / "backup-status-daily.status").exists())

    def test_readback_failure_never_publishes_success(self) -> None:
        run = self.run_backup("readback_fail")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("readback failed", run.stderr)
        self.assertFalse((self.status_dir / "backup-status-daily.status").exists())

    def test_corrupt_remote_ciphertext_never_publishes_success(self) -> None:
        run = self.run_backup("corrupt_readback")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("checksum mismatch", run.stderr)
        self.assertFalse((self.status_dir / "backup-status-daily.status").exists())

    def test_invalid_backup_tier_is_rejected_before_upload(self) -> None:
        run = self.run_backup(BACKUP_TIER="../other")
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse(self.marker.exists())
        self.assertFalse(self.status_dir.exists())

    def test_status_directory_symlink_is_rejected(self) -> None:
        redirect = self.tmp / "redirect"
        redirect.mkdir()
        self.status_dir.symlink_to(redirect, target_is_directory=True)
        run = self.run_backup()
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("unsafe backup status directory", run.stderr)
        self.assertFalse((redirect / "backup-status-daily.status").exists())


if __name__ == "__main__":
    unittest.main()
