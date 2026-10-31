#!/usr/bin/env python3
"""Offline adversarial tests; no VPS/root, secrets, SSH, DB or production writes."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "operations/audit-main-backup-upload-coverage-20261031.py"
spec = importlib.util.spec_from_file_location("upload_coverage", SCRIPT)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)
SHA = "dfa55d24b7cc5a0d1e0b0f28832d1f46acc9d031"
REL = "platform-574e443a2c75"


def add(tar, name, data=b"", kind=tarfile.REGTYPE):
    info = tarfile.TarInfo(name)
    info.type = kind
    info.size = len(data) if kind == tarfile.REGTYPE else 0
    tar.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)


class UploadCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.release = self.base / "release"
        app = self.release / "apps/platform"
        (app / "storage/app/public").mkdir(parents=True)
        (app / "public").mkdir()
        (app / "storage/app/public/example.txt").write_bytes(b"content")
        (app / "public/storage").symlink_to("../storage/app/public")
        self.bundle = self.base / "bundle.tar.gz"
        self.witness = self.base / "witness.json"
        self.make_bundle()

    def make_bundle(self, data=b"content", extra=None):
        inner = io.BytesIO()
        with tarfile.open(fileobj=inner, mode="w:gz") as t:
            add(t, "storage/app", kind=tarfile.DIRTYPE)
            add(t, "storage/app/public", kind=tarfile.DIRTYPE)
            add(t, "storage/app/public/example.txt", data)
            add(t, ".env", b"private")
            if extra:
                add(t, *extra)
        with tarfile.open(self.bundle, "w:gz") as t:
            for name, value in (
                ("database.dump", b"db"), ("storage.tar.gz", inner.getvalue()),
                ("metadata.txt", b"metadata"), ("SHA256SUMS", b"hashes")
            ):
                add(t, name, value)
        self.witness.write_text(json.dumps({
            "approvedSha": SHA, "currentRelease": REL,
            "backupSha256": hashlib.sha256(self.bundle.read_bytes()).hexdigest()
        }))

    def run_audit(self):
        return audit_module.audit(self.release, self.bundle, self.witness, SHA, REL)

    def test_matching_storage_app_is_advisory_only(self):
        result = self.run_audit()
        self.assertEqual(result["STORAGE_APP_CONTENT_PARITY"], "PASS")
        self.assertEqual(result["PUBLIC_STORAGE_LINK"], "EXPECTED")
        self.assertEqual(result["ARCHIVED_STORAGE_FILES"], "1")
        self.assertEqual(result["ALL_CUSTOMER_UPLOAD_LOCATIONS_VERIFIED"], "NO")

    def test_changed_live_upload_is_not_proven(self):
        (self.release / "apps/platform/storage/app/public/example.txt").write_bytes(b"changed")
        self.assertEqual(self.run_audit()["STORAGE_APP_CONTENT_PARITY"], "MISMATCH")

    def test_public_storage_outside_archive_is_flagged(self):
        link = self.release / "apps/platform/public/storage"
        link.unlink()
        link.symlink_to(self.base)
        self.assertEqual(self.run_audit()["PUBLIC_STORAGE_LINK"], "MISSING_OR_DIFFERENT")

    def test_alternate_upload_directory_requires_review(self):
        (self.release / "apps/platform/public/uploads").mkdir()
        self.assertEqual(self.run_audit()["ALTERNATE_PUBLIC_UPLOAD_DIRS"], "PRESENT_REVIEW")

    def test_symlink_inside_storage_fails_closed(self):
        (self.release / "apps/platform/storage/app/link").symlink_to(self.base)
        with self.assertRaises(audit_module.CoverageError):
            self.run_audit()

    def test_symlinked_storage_parent_cannot_redirect_root_scan(self):
        storage = self.release / "apps/platform/storage"
        outside = self.base / "outside-storage"
        storage.rename(outside)
        storage.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(audit_module.CoverageError):
            self.run_audit()

    def test_symlinked_public_target_cannot_claim_expected_link(self):
        target = self.release / "apps/platform/storage/app/public"
        outside = self.base / "outside-public"
        target.rename(outside)
        target.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(audit_module.CoverageError):
            self.run_audit()

    def test_traversal_in_archived_storage_fails_closed(self):
        self.make_bundle(extra=("../escape", b"x"))
        with self.assertRaises(audit_module.CoverageError):
            self.run_audit()

    def test_unreadable_subdirectory_cannot_be_silently_skipped(self):
        from unittest import mock
        def fail_walk(path, follow_symlinks=False, onerror=None):
            self.assertIsNotNone(onerror)
            onerror(PermissionError("private subdirectory"))
            yield from ()
        with mock.patch.object(audit_module.os, "fwalk", fail_walk):
            with self.assertRaises(audit_module.CoverageError):
                self.run_audit()

    def test_archive_digest_mismatch_fails_closed(self):
        self.witness.write_text(json.dumps({
            "approvedSha": SHA, "currentRelease": REL, "backupSha256": "0" * 64
        }))
        with self.assertRaises(audit_module.CoverageError):
            self.run_audit()


if __name__ == "__main__":
    unittest.main()
