#!/usr/bin/env python3
"""Synthetic, no-live, fixture-based testing of P0 local-to-offsite sealing."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[1] / "scripts/operations/seal-29a982-offsite-backup-20261027.py"
SPEC = importlib.util.spec_from_file_location("p0_seal", FILE)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def archive_file(path: Path, entries: list[tuple[str, bytes, str]]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name, body, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == "link":
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/shadow"
                info.size = 0
                archive.addfile(info)
            elif kind == "dir":
                info.type = tarfile.DIRTYPE
                info.size = 0
                archive.addfile(info)
            else:
                info.size = len(body)
                archive.addfile(info, io.BytesIO(body))


def make_snapshot(root: Path, *, include_env=True, with_link=False) -> tuple[Path, Path]:
    storage = root / "prepared-storage.tar.gz"
    parts: list[tuple[str, bytes, str]] = [
        ("storage/app", b"", "dir"),
        ("storage/app/durable.txt", b"TEST_CUSTOMER_DATA", "file"),
    ]
    if include_env:
        parts.append((".env", b"PRODUCTION_SECRET=DO_NOT_EXPORT", "file"))
    if with_link:
        parts.append(("storage/app/hazard", b"", "link"))
    archive_file(storage, parts)
    files = {
        "database.dump": b"PGDMP-TEST-ONLY",
        "storage.tar.gz": storage.read_bytes(),
        "metadata.txt": (
            f"current_release={mod.EXPECTED_RELEASE.name}\n"
            f"approved_sha={mod.TARGET_SHA}\n"
            "backup_kind=local_unencrypted_root_only\n"
        ).encode(),
    }
    files["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(files[name]).hexdigest()}  {name}\n"
        for name in ("database.dump", "storage.tar.gz", "metadata.txt")
    ).encode()
    original = root / "original.tar.gz"
    archive_file(original, [(k,v,"file") for k,v in files.items()])
    (root / "source-repack").mkdir(mode=0o700)
    witness = root / "witness.json"
    witness.write_text(json.dumps({
        "backupSha256": hashlib.sha256(original.read_bytes()).hexdigest(),
        "approvedSha": mod.TARGET_SHA,
        "currentRelease": mod.EXPECTED_RELEASE.name,
    }))
    return original, witness


class SealCodeBridgeCandidateBackupTest(unittest.TestCase):
    def test_valid_snapshot_removes_env_and_preserves_customer_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original, witness = make_snapshot(root)
            original_hash = mod.digest(original)
            with patch.object(mod, "verify_root_only"):
                outer, verified_sha = mod.repack_verified_local(original, witness, root / "source-repack")
            self.assertEqual(original_hash, verified_sha)
            self.assertEqual(original_hash, mod.digest(original))
            with tarfile.open(outer, "r:gz") as archive:
                self.assertEqual(set(archive.getnames()), mod.MEMBERS)
                content = {name: archive.extractfile(name).read() for name in mod.MEMBERS}
            self.assertIn(b"production_env_excluded=YES", content["metadata.txt"])
            storage = root / "final-storage.tar.gz"
            storage.write_bytes(content["storage.tar.gz"])
            with tarfile.open(storage, "r:gz") as tf:
                names = tf.getnames()
                self.assertNotIn(".env", names)
                self.assertIn("storage/app/durable.txt", names)
                self.assertEqual(tf.extractfile("storage/app/durable.txt").read(), b"TEST_CUSTOMER_DATA")
            self.assertNotIn(b"PRODUCTION_SECRET=DO_NOT_EXPORT", outer.read_bytes())

    def test_witness_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original, witness=make_snapshot(root)
            data=json.loads(witness.read_text())
            data["backupSha256"]="0"*64
            witness.write_text(json.dumps(data))
            with patch.object(mod,"verify_root_only"),self.assertRaisesRegex(RuntimeError,"WITNESS_DIGEST_MISMATCH"):
                mod.repack_verified_local(original,witness,root/"source-repack")

    def test_unsafe_inner_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original,witness=make_snapshot(root,with_link=True)
            with patch.object(mod,"verify_root_only"),self.assertRaisesRegex(RuntimeError,"UNSAFE_STORAGE_ARCHIVE_MEMBER"):
                mod.repack_verified_local(original,witness,root/"source-repack")

    def test_missing_env_fails_source_specific_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original,witness=make_snapshot(root,include_env=False)
            with patch.object(mod,"verify_root_only"),self.assertRaisesRegex(RuntimeError,"SOURCE_STORAGE_CONTRACT_MISMATCH"):
                mod.repack_verified_local(original,witness,root/"source-repack")


    def test_current_candidate_identity_and_encrypted_output_are_pinned(self):
        self.assertEqual(mod.TARGET_SHA, "29a98250b463998959fc52ac41b012aed1e76dba")
        self.assertEqual(mod.EXPECTED_RELEASE.name, "platform-8070dad72c55")
        self.assertEqual(mod.ORIGINAL.name, "pre-deploy-29a98250b463.tar.gz")
        self.assertEqual(mod.WITNESS.name, "pre-deploy-29a98250b463.json")
        self.assertEqual(mod.OUTPUT.name, "offsite-29a98250b463.tar.gz.age")
        self.assertTrue(mod.RECIPIENT.startswith("age1"))
        self.assertNotIn("f4b6d3ff96b0", FILE.read_text())

    def test_does_not_execute_production_side_effects(self):
        source=FILE.read_text()
        for prohibited in (
            "systemctl restart","systemctl reload","artisan migrate",
            "ALTER ROLE","ln -sfn","git reset --hard","rclone copy",
            "scp ","ssh ","/etc/kmj-codebridge/main-platform-production-release.json",
            "chown -R",
        ):
            self.assertNotIn(prohibited,source)
        self.assertIn("os.link(sealed, OUTPUT)",source)
        self.assertIn('if CURRENT.resolve(strict=True) != EXPECTED_RELEASE',source)
        self.assertIn("ENV_EXCLUDED_FROM_OFFSITE_COPY=PASS",source)
        self.assertIn("OFFSITE_TRANSFER=NOT_ATTEMPTED",source)

if __name__ == "__main__":
    unittest.main()
