"""Synthetic-only restore byte-parity tests. No remote, production DB or root."""
from __future__ import annotations
import importlib.util
import io
import os
import subprocess
from pathlib import Path
import tarfile
import tempfile
import unittest

SOURCE = Path(__file__).parent / "operations/verify-restored-storage-parity.py"
spec = importlib.util.spec_from_file_location("restored_storage_parity", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RestoredStorageParityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.output = self.base / "restored"
        self.output.mkdir()
        self.tar = self.base / "storage.tar.gz"
        self.make_tar()
        (self.output / "storage/app/public").mkdir(parents=True)
        (self.output / "storage/app/public/picture.png").write_bytes(b"original upload")

    def make_tar(self, extra=None):
        with tarfile.open(self.tar, "w:gz") as archive:
            for path in ("storage/app", "storage/app/public"):
                info = tarfile.TarInfo(path)
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            info = tarfile.TarInfo("storage/app/public/picture.png")
            data = b"original upload"
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
            if extra:
                name, data, kind = extra
                info = tarfile.TarInfo(name)
                info.type = kind
                info.size = len(data) if kind == tarfile.REGTYPE else 0
                archive.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)

    def assert_rejected(self):
        with self.assertRaises(module.StorageParityError):
            module.verify(self.tar, self.output)

    def test_exact_bytes_pass(self):
        self.assertEqual(module.verify(self.tar, self.output), 1)

    def test_changed_upload_rejected(self):
        (self.output / "storage/app/public/picture.png").write_bytes(b"tampered upload")
        self.assert_rejected()

    def test_missing_upload_rejected(self):
        (self.output / "storage/app/public/picture.png").unlink()
        self.assert_rejected()

    def test_extra_upload_rejected(self):
        (self.output / "storage/app/public/extra.png").write_bytes(b"extra")
        self.assert_rejected()

    def test_symlink_rejected(self):
        p = self.output / "storage/app/public/picture.png"
        p.unlink()
        p.symlink_to(self.tar)
        self.assert_rejected()

    def test_symlinked_directory_rejected(self):
        path = self.output / "storage/app/public"
        path.rename(self.output / "other")
        path.symlink_to(self.output / "other", target_is_directory=True)
        self.assert_rejected()

    def test_extra_directory_rejected(self):
        (self.output / "storage/app/extra").mkdir()
        self.assert_rejected()

    def test_duplicate_archive_entry_rejected(self):
        self.make_tar(extra=("storage/app/public/picture.png", b"x", tarfile.REGTYPE))
        self.assert_rejected()

    def test_archived_symlink_rejected(self):
        self.make_tar(extra=("storage/app/danger", b"", tarfile.SYMTYPE))
        self.assert_rejected()

    def test_archive_traversal_rejected(self):
        self.make_tar(extra=("storage/app/../outside", b"x", tarfile.REGTYPE))
        self.assert_rejected()

    def test_symlinked_restored_root_ancestor_rejected(self):
        alias = self.base / "restored-alias"
        alias.symlink_to(self.output, target_is_directory=True)
        with self.assertRaises(module.StorageParityError):
            module.verify(self.tar, alias)

    def test_restored_root_replaced_during_walk_is_rejected(self):
        # Even if open descriptors still refer to the original scratch tree,
        # the pathname must not silently point to a different directory.
        from unittest import mock
        original_walk = module.os.fwalk
        swapped = False

        def swapped_walk(*args, **kwargs):
            nonlocal swapped
            if swapped:
                yield from original_walk(*args, **kwargs)
                return
            swapped = True
            walk = original_walk(*args, **kwargs)
            first = next(walk)
            self.output.rename(self.base / "original-restored")
            self.output.mkdir()
            yield first
            yield from walk

        with mock.patch.object(module.os, "fwalk", side_effect=swapped_walk):
            self.assert_rejected()

    def test_nested_restored_directory_swapped_after_hashing_is_rejected(self):
        # A root-only inode recheck misses a replacement below storage/app.
        # Simulate a swap after the first descriptor-anchored walk completes.
        from unittest import mock
        original_walk = module.os.fwalk
        walks = 0

        def swapped_walk(*args, **kwargs):
            nonlocal walks
            walks += 1
            yield from original_walk(*args, **kwargs)
            if walks == 1:
                original = self.output / "storage/app/public"
                original.rename(self.base / "original-public")
                original.mkdir()
                (original / "picture.png").write_bytes(b"replacement bytes")

        with mock.patch.object(module.os, "fwalk", side_effect=swapped_walk):
            self.assert_rejected()

    def test_byte_identical_file_replaced_after_hashing_is_rejected(self):
        # A second directory-only inode walk misses a file swapped after
        # its bytes were hashed. The new file has identical content.
        from unittest import mock
        original_walk = module.os.fwalk
        walks = 0

        def swapped_walk(*args, **kwargs):
            nonlocal walks
            walks += 1
            yield from original_walk(*args, **kwargs)
            if walks == 1:
                target = self.output / "storage/app/public/picture.png"
                target.rename(self.base / "original-picture.png")
                target.write_bytes(b"original upload")

        with mock.patch.object(module.os, "fwalk", side_effect=swapped_walk):
            self.assert_rejected()

    def test_hardlink_to_external_file_is_not_an_independent_restore(self):
        # A byte-for-byte match must still fail if the supposed scratch
        # restore is actually another link to a file outside the restore.
        original = self.base / "live-picture.png"
        original.write_bytes(b"original upload")
        target = self.output / "storage/app/public/picture.png"
        target.unlink()
        os.link(original, target)
        self.assert_rejected()

    def test_file_reads_are_descriptor_anchored(self):
        from unittest import mock
        original_open = module.os.open
        observed = []

        def checked_open(path, flags, *args, **kwargs):
            if path == "picture.png":
                observed.append(kwargs.get("dir_fd"))
                self.assertIsNotNone(kwargs.get("dir_fd"))
                self.assertTrue(flags & module.os.O_NOFOLLOW)
            return original_open(path, flags, *args, **kwargs)

        with mock.patch.object(module.os, "open", side_effect=checked_open):
            self.assertEqual(module.verify(self.tar, self.output), 1)
        self.assertTrue(observed)

    def test_unreadable_nested_directory_is_not_silently_skipped(self):
        from unittest import mock

        def broken_walk(*args, **kwargs):
            self.assertIsNotNone(kwargs.get("dir_fd"))
            self.assertIsNotNone(kwargs.get("onerror"))
            kwargs["onerror"](PermissionError("blocked"))
            yield from ()

        with mock.patch.object(module.os, "fwalk", side_effect=broken_walk):
            self.assert_rejected()

    def test_cli_reports_exact_verified_counts(self):
        from unittest import mock
        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(module.main([str(self.tar), str(self.output)]), 0)
        self.assertEqual(output.getvalue().splitlines(), [
            "RECOVERED_STORAGE_CONTENT_PARITY=PASS",
            "RECOVERED_STORAGE_FILES_VERIFIED=1",
            f"RECOVERED_STORAGE_BYTES_VERIFIED={len(b'original upload')}",
        ])

    def test_google_sftp_restore_calls_hardened_parity_verifier(self):
        script = Path(__file__).parent / "operations/verify-main-platform-google-sftp-restore-20261030.sh"
        content = script.read_text()
        self.assertIn('python3 "$repo/scripts/operations/verify-restored-storage-parity.py"', content)
        self.assertNotIn("os.walk(root", content)
        self.assertIn("STORAGE_EXTRACTION_PARITY_CONTENT_SHA256", content)
        subprocess.run(["bash", "-n", str(script)], check=True)
        for key, value in (("RECOVERED_STORAGE_FILES_VERIFIED", "17"),
                           ("RECOVERED_STORAGE_BYTES_VERIFIED", "61")):
            line = next(line for line in content.splitlines()
                        if "sed -n '" in line and f"^{key}=" in line)
            expression = line.split("sed -n '", 1)[1].split("'", 1)[0]
            result = subprocess.run(
                ["sed", "-n", expression], input=f"{key}={value}\\n",
                text=True, capture_output=True, check=True,
            )
            self.assertEqual(result.stdout, value + "\\n")

    def test_bad_argument_count_rejected(self):
        self.assertEqual(module.main([]), 2)


if __name__ == "__main__":
    unittest.main()
