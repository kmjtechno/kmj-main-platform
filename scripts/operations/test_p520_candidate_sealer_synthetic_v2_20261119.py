"""Synthetic only: exercise sanitized CE6->Licensing Hub AGE payload preparation.

No AGE private keys, no customer data, no production paths or host operations.
CI patches only the precondition that requires real root-owned filesystem
ownership; production function is unchanged and keeps its root-only guard.
"""
from __future__ import annotations
import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("seal-main-platform-p520-candidate-v2-20261119.py")
spec = importlib.util.spec_from_file_location("kmj_synthetic_p520_sealer", SOURCE)
assert spec is not None and spec.loader is not None
sealer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sealer)

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def archive_bytes(members: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as out:
        for name, payload in members.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(payload)
            entry.mode = 0o600
            out.addfile(entry, BytesIO(payload))
    return output.getvalue()

def members(archive: bytes) -> dict[str, bytes]:
    values = {}
    with tarfile.open(fileobj=BytesIO(archive), mode="r:gz") as opened:
        for entry in opened:
            data = opened.extractfile(entry)
            if not entry.isfile() or data is None:
                raise AssertionError("UNEXPECTED_MEMBER")
            values[entry.name] = data.read()
    return values

class SyntheticCandidateSealerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="kmj-p520-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.original_root = sealer.ROOT
        sealer.ROOT = Path(self.temp.name)
        self.addCleanup(setattr, sealer, "ROOT", self.original_root)
        self.target = sealer.Target(sealer.EXACT_CANDIDATE, sealer.EXACT_LIVE)
        self.secret = b"CI_SYNTHETIC_ENV_ONLY=never_transmit"
        self.storage = archive_bytes({
            ".env": self.secret,
            "storage/app/readme.txt": b"CI_SYNTHETIC_UPLOAD\n",
        })
        self.db = b"PGDMP" + b"CI_SYNTHETIC_DATABASE_DUMP"
        self.metadata = (
            "approved_sha=" + sealer.EXACT_CANDIDATE + "\n"
            "current_release=" + sealer.EXACT_LIVE + "\n"
            "synthetic_data_only=YES\n"
        ).encode("ascii")
        self._write_bundle(self.storage)

    def _write_bundle(self, storage: bytes) -> None:
        files = {
            "database.dump": self.db,
            "storage.tar.gz": storage,
            "metadata.txt": self.metadata,
        }
        manifest = "".join(digest(value) + "  " + name + "\n"
                           for name, value in files.items()).encode("ascii")
        files["SHA256SUMS"] = manifest
        self.target.original.write_bytes(archive_bytes(files))
        self.target.original.chmod(0o600)
        witness = {
            "approvedSha": self.target.sha,
            "currentRelease": self.target.release,
            "backupSha256": digest(self.target.original.read_bytes()),
        }
        self.target.witness.write_text(json.dumps(witness), encoding="utf-8")
        self.target.witness.chmod(0o600)

    def _repack(self):
        scratch = Path(self.temp.name) / "scratch"
        scratch.mkdir()
        # In CI no root ownership: isolate the uid requirement from archive logic.
        with patch.object(sealer, "verify_root_only", lambda _: None):
            return sealer.repack_verified_local(
                self.target, self.target.original, self.target.witness, scratch
            )

    def test_valid_synthetic_bundle_strips_env_and_binds_exact_candidate(self):
        packaged, original_sha = self._repack()
        self.assertEqual(original_sha, digest(self.target.original.read_bytes()))
        data = members(packaged.read_bytes())
        self.assertEqual(set(data), {
            "database.dump", "storage.tar.gz", "metadata.txt", "SHA256SUMS"
        })
        self.assertEqual(data["database.dump"], self.db)
        self.assertNotIn(self.secret, packaged.read_bytes())
        restored_storage = members(data["storage.tar.gz"])
        self.assertEqual(restored_storage, {
            "storage/app/readme.txt": b"CI_SYNTHETIC_UPLOAD\n"
        })
        self.assertIn(b"target_sha=" + sealer.EXACT_CANDIDATE.encode(), data["metadata.txt"])
        self.assertIn(b"current_release=" + sealer.EXACT_LIVE.encode(), data["metadata.txt"])
        self.assertIn(b"production_env_excluded=YES", data["metadata.txt"])
        for name in ("database.dump", "storage.tar.gz", "metadata.txt"):
            self.assertIn((digest(data[name]) + "  " + name).encode(), data["SHA256SUMS"])

    def test_tampered_source_archive_hash_is_rejected(self):
        witness = json.loads(self.target.witness.read_text())
        witness["backupSha256"] = "0" * 64
        self.target.witness.write_text(json.dumps(witness))
        with self.assertRaisesRegex(RuntimeError, "WITNESS_DIGEST_MISMATCH"):
            self._repack()

    def test_stale_4c9_witness_identity_is_rejected(self):
        witness = json.loads(self.target.witness.read_text())
        witness["approvedSha"] = "4c9d59103b99a6cfe675bb7b8961fc956eb294f0"
        self.target.witness.write_text(json.dumps(witness))
        with self.assertRaisesRegex(RuntimeError, "WITNESS_RELEASE_MISMATCH"):
            self._repack()

    def test_nested_path_traversal_is_rejected(self):
        malicious_storage = archive_bytes({
            "storage/app/readme.txt": b"SAFE",
            "../storage/app/escape.txt": b"NOT_ALLOWED",
        })
        self._write_bundle(malicious_storage)
        with self.assertRaisesRegex(RuntimeError, "UNSAFE_STORAGE_ARCHIVE_MEMBER"):
            self._repack()

if __name__ == "__main__":
    unittest.main()
