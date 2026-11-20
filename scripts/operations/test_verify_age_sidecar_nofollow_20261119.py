#!/usr/bin/env python3
"""Hermetic fixtures: no production files, keys, or services."""
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("verify-age-sidecar-nofollow-20261119.py")
spec = importlib.util.spec_from_file_location("age_verifier", SCRIPT)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

class SidecarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.c = self.root / "20261118T074553Z.tar.age"
        self.s = self.root / "20261118T074553Z.tar.age.sha256"
        self.c.write_bytes(b"synthetic encrypted bytes only")
        self.good = hashlib.sha256(self.c.read_bytes()).hexdigest() + "  " + self.c.name + "\n"
        self.s.write_text(self.good, encoding="ascii")

    def test_relative_cipher_rejected(self):
        with self.assertRaises(v.Rejected):
            v.verify(self.c.name, str(self.s))

    def test_relative_sidecar_rejected(self):
        with self.assertRaises(v.Rejected):
            v.verify(str(self.c), self.s.name)

    def test_cipher_dot_segment_rejected(self):
        path = str(self.root) + "/./" + self.c.name
        with self.assertRaises(v.Rejected):
            v.verify(path, str(self.s))

    def test_sidecar_parent_segment_rejected(self):
        path = str(self.root) + "/../" + self.root.name + "/" + self.s.name
        with self.assertRaises(v.Rejected):
            v.verify(str(self.c), path)

    def test_double_slash_parent_rejected(self):
        path = str(self.root) + "//" + self.c.name
        with self.assertRaises(v.Rejected):
            v.verify(path, str(self.s))

    def test_valid(self):
        v.verify(str(self.c), str(self.s))

    def test_sidecar_wrong_filename_rejected(self):
        alias = self.root / "unrelated.sha256"
        alias.write_text(self.good, encoding="ascii")
        with self.assertRaises(v.Rejected):
            v.verify(str(self.c), str(alias))

    def test_sidecar_wrong_ciphertext_suffix_rejected(self):
        alias = self.root / (self.c.name + ".sha256.backup")
        alias.write_text(self.good, encoding="ascii")
        with self.assertRaises(v.Rejected):
            v.verify(str(self.c), str(alias))

    def test_matching_sidecar_in_different_directory_rejected(self):
        other = self.root / "untrusted"
        other.mkdir()
        remote_sidecar = other / self.s.name
        remote_sidecar.write_text(self.good, encoding="ascii")
        with self.assertRaises(v.Rejected):
            v.verify(str(self.c), str(remote_sidecar))

    def test_zero_byte_cipher_rejected_even_with_matching_digest(self):
        self.c.write_bytes(b"")
        self.s.write_text(hashlib.sha256(b"").hexdigest() + "  " + self.c.name + "\n", encoding="ascii")
        with self.assertRaises(v.Rejected):
            v.verify(str(self.c), str(self.s))

    def test_zero_byte_sidecar_rejected(self):
        self.s.write_bytes(b"")
        with self.assertRaises(v.Rejected):
            v.verify(str(self.c), str(self.s))

    def test_digest_mismatch(self):
        self.c.write_bytes(b"modified")
        with self.assertRaises(v.Rejected):
            v.verify(str(self.c), str(self.s))

    def test_duplicate_line(self):
        self.s.write_text(self.good * 2)
        with self.assertRaises(v.Rejected):
            v.verify(str(self.c), str(self.s))

    def test_trailing_data(self):
        self.s.write_text(self.good + "\n")
        with self.assertRaises(v.Rejected):
            v.verify(str(self.c), str(self.s))

    def test_wrong_basename(self):
        self.s.write_text(self.good.replace(self.c.name, "other.tar.age"))
        with self.assertRaises(v.Rejected):
            v.verify(str(self.c), str(self.s))

    def test_uppercase_digest(self):
        self.s.write_text(self.good[:64].upper() + self.good[64:])
        with self.assertRaises(v.Rejected):
            v.verify(str(self.c), str(self.s))

    def test_cipher_symlink(self):
        link = self.root / "alias.tar.age"
        link.symlink_to(self.c)
        matching_sidecar = self.root / "alias.tar.age.sha256"
        matching_sidecar.write_text(self.good.replace(self.c.name, link.name), encoding="ascii")
        with self.assertRaises(OSError):
            v.verify(str(link), str(matching_sidecar))

    def test_sidecar_symlink(self):
        link = self.root / (self.c.name + ".sha256")
        self.s.unlink()
        link.symlink_to(self.root / "real.sha256")
        (self.root / "real.sha256").write_text(self.good, encoding="ascii")
        with self.assertRaises(OSError):
            v.verify(str(self.c), str(link))

    def test_parent_symlink(self):
        link = self.root / "linked"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            v.verify(str(link / self.c.name), str(self.s))

    def test_hardlink(self):
        link = self.root / "copy.tar.age"
        os.link(self.c, link)
        with self.assertRaises(v.Rejected):
            v.verify(str(self.c), str(self.s))

    def test_fifo(self):
        fifo = self.root / "pipe.tar.age"
        os.mkfifo(fifo)
        with self.assertRaises(v.Rejected):
            v.verify(str(fifo), str(self.s))

    def test_missing_sidecar(self):
        self.s.unlink()
        with self.assertRaises(OSError):
            v.verify(str(self.c), str(self.s))

    def test_cipher_swap_during_hash(self):
        original = v.os.read
        swapped = False
        def swap(fd, size):
            nonlocal swapped
            data = original(fd, size)
            if size == 1024 * 1024 and not swapped:
                swapped = True
                self.c.rename(self.root / "old.tar.age")
                self.c.write_bytes(b"replacement")
            return data
        v.os.read = swap
        try:
            with self.assertRaises(v.Rejected):
                v.verify(str(self.c), str(self.s))
        finally:
            v.os.read = original

    def test_cipher_entry_swap_at_final_rewalk(self):
        original = v.open_parent
        calls = 0
        def rewalk(path):
            nonlocal calls
            calls += 1
            if calls == 3:
                self.c.rename(self.root / "cipher-original.tar.age")
                self.c.write_bytes(b"replacement")
            return original(path)
        v.open_parent = rewalk
        try:
            with self.assertRaises(v.Rejected):
                v.verify(str(self.c), str(self.s))
        finally:
            v.open_parent = original

    def test_sidecar_entry_swap_at_final_rewalk(self):
        original = v.open_parent
        calls = 0
        def rewalk(path):
            nonlocal calls
            calls += 1
            if calls == 4:
                self.s.rename(self.root / "sidecar-original.sha256")
                self.s.write_text(self.good, encoding="ascii")
            return original(path)
        v.open_parent = rewalk
        try:
            with self.assertRaises(v.Rejected):
                v.verify(str(self.c), str(self.s))
        finally:
            v.open_parent = original

    def test_parent_directory_swap_during_hash(self):
        original = v.os.read
        archive_dir = self.root / "archive"
        archive_dir.mkdir()
        moved_cipher = archive_dir / self.c.name
        moved_sidecar = archive_dir / self.s.name
        self.c.rename(moved_cipher)
        self.s.rename(moved_sidecar)
        swapped = False
        def swap(fd, size):
            nonlocal swapped
            data = original(fd, size)
            if size == 1024 * 1024 and not swapped:
                swapped = True
                archive_dir.rename(self.root / "renamed")
                archive_dir.mkdir()
            return data
        v.os.read = swap
        try:
            with self.assertRaises(v.Rejected):
                v.verify(str(moved_cipher), str(moved_sidecar))
        finally:
            v.os.read = original

if __name__ == "__main__":
    unittest.main()
