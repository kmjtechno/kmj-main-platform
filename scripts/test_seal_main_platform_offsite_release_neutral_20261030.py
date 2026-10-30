#!/usr/bin/env python3
"""Synthetic, no-live tests of the RELEASE-NEUTRAL local-to-offsite sealing script (two validated ids only)."""
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

FILE = Path(__file__).resolve().parents[1] / "scripts/operations/seal-main-platform-offsite-20261030.py"
SPEC = importlib.util.spec_from_file_location("neutral_seal", FILE)
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


def make_snapshot(root: Path, target, *, include_env=True, with_link=False) -> tuple[Path, Path]:
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
            f"current_release={target.release}\n"
            f"approved_sha={target.sha}\n"
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
        "approvedSha": target.sha,
        "currentRelease": target.release,
    }))
    return original, witness


SHA_A = "a" * 12 + "1" * 28
REL_A = "platform-" + "b" * 12
SHA_OLD = "39b88b36d071d3f78f2392d609d3febc2c530165"


def tgt(sha=SHA_A, rel=REL_A):
    return mod.Target(sha, rel)


class ReleaseNeutralSealTest(unittest.TestCase):
    def test_arguments_are_exactly_two_validated_ids(self):
        t = mod.parse_args(["--candidate-sha", SHA_A, "--expected-release", REL_A])
        self.assertEqual((t.sha, t.release), (SHA_A, REL_A))
        self.assertEqual(t.original.name, f"pre-deploy-{SHA_A[:12]}.tar.gz")
        self.assertEqual(t.witness.name, f"pre-deploy-{SHA_A[:12]}.json")
        self.assertEqual(t.output.name, f"offsite-{SHA_A[:12]}.tar.gz.age")
        self.assertEqual(str(t.expected_release), f"/home/kmjprod/releases/{REL_A}")
        for bad in (
            [], ["--candidate-sha", SHA_A], ["--expected-release", REL_A, "--candidate-sha", SHA_A],
            ["--candidate-sha", SHA_A, "--expected-release", REL_A, "--output", "/tmp/x"],
            ["--candidate-sha", SHA_A, "--expected-release", REL_A, "extra"],
            ["--candidate-sha=" + SHA_A, "--expected-release=" + REL_A],
        ):
            with self.assertRaisesRegex(RuntimeError, "USAGE_CANDIDATE_SHA_AND_EXPECTED_RELEASE_ONLY"):
                mod.parse_args(bad)

    def test_malicious_or_malformed_identifiers_are_refused(self):
        for sha in ("", "abc", SHA_A.upper(), SHA_A[:-1], SHA_A + "0", "../" + SHA_A[:37], SHA_A[:39] + "/", SHA_A[:39] + "\n", SHA_A[:39] + "g", None):
            with self.assertRaisesRegex(RuntimeError, "CANDIDATE_SHA_INVALID"):
                mod.Target(sha, REL_A)
        for rel in ("", "platform-", "platform-" + "b" * 11, "platform-" + "b" * 13, "platform-" + "B" * 12,
                    "../platform-" + "b" * 12, "platform-" + "b" * 12 + "/../x", "platform-" + "b" * 12 + "\n", "release-" + "b" * 12, None):
            with self.assertRaisesRegex(RuntimeError, "EXPECTED_RELEASE_INVALID"):
                mod.Target(SHA_A, rel)

    def test_paths_cannot_escape_the_fixed_backup_directory(self):
        t = tgt()
        for path in (t.original, t.witness, t.output):
            self.assertEqual(path.parent, mod.ROOT)
            self.assertNotIn("..", path.parts)

    def test_valid_snapshot_removes_env_and_preserves_customer_storage(self):
        t = tgt()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original, witness = make_snapshot(root, t)
            original_hash = mod.digest(original)
            with patch.object(mod, "verify_root_only"):
                outer, verified = mod.repack_verified_local(t, original, witness, root / "source-repack")
            self.assertEqual(original_hash, verified)
            self.assertEqual(original_hash, mod.digest(original))
            with tarfile.open(outer, "r:gz") as archive:
                self.assertEqual(set(archive.getnames()), mod.MEMBERS)
                content = {n: archive.extractfile(n).read() for n in mod.MEMBERS}
            self.assertIn(b"production_env_excluded=YES", content["metadata.txt"])
            self.assertIn(f"target_sha={t.sha}".encode(), content["metadata.txt"])
            self.assertIn(f"current_release={t.release}".encode(), content["metadata.txt"])
            self.assertNotIn(b"PRODUCTION_SECRET=DO_NOT_EXPORT", outer.read_bytes())

    def test_witness_for_an_old_candidate_is_rejected(self):
        t = tgt()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original, witness = make_snapshot(root, t)
            data = json.loads(witness.read_text())
            data["approvedSha"] = SHA_OLD
            witness.write_text(json.dumps(data))
            with patch.object(mod, "verify_root_only"), self.assertRaisesRegex(RuntimeError, "WITNESS_RELEASE_MISMATCH"):
                mod.repack_verified_local(t, original, witness, root / "source-repack")

    def test_witness_for_a_different_active_release_is_rejected(self):
        t = tgt()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original, witness = make_snapshot(root, t)
            data = json.loads(witness.read_text())
            data["currentRelease"] = "platform-574e443a2c75"
            witness.write_text(json.dumps(data))
            with patch.object(mod, "verify_root_only"), self.assertRaisesRegex(RuntimeError, "WITNESS_RELEASE_MISMATCH"):
                mod.repack_verified_local(t, original, witness, root / "source-repack")

    def test_witness_digest_must_match_archive_bytes(self):
        t = tgt()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original, witness = make_snapshot(root, t)
            data = json.loads(witness.read_text())
            data["backupSha256"] = "0" * 64
            witness.write_text(json.dumps(data))
            with patch.object(mod, "verify_root_only"), self.assertRaisesRegex(RuntimeError, "WITNESS_DIGEST_MISMATCH"):
                mod.repack_verified_local(t, original, witness, root / "source-repack")

    def test_archive_metadata_for_another_candidate_is_rejected(self):
        t = tgt()
        other = tgt(sha="c" * 40)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original, witness = make_snapshot(root, other)  # archive says "other"
            data = json.loads(witness.read_text())
            data["approvedSha"], data["currentRelease"] = t.sha, t.release  # witness lies
            witness.write_text(json.dumps(data))
            with patch.object(mod, "verify_root_only"), self.assertRaisesRegex(RuntimeError, "SOURCE_METADATA_MISMATCH"):
                mod.repack_verified_local(t, original, witness, root / "source-repack")

    def test_unsafe_inner_symlink_rejected(self):
        t = tgt()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original, witness = make_snapshot(root, t, with_link=True)
            with patch.object(mod, "verify_root_only"), self.assertRaisesRegex(RuntimeError, "UNSAFE_STORAGE_ARCHIVE_MEMBER"):
                mod.repack_verified_local(t, original, witness, root / "source-repack")

    def test_source_has_no_pinned_release_and_no_side_effects(self):
        source = FILE.read_text()
        for pinned in ("39b88b36d071", "574e443a2c75", "f4b6d3ff96b0"):
            self.assertNotIn(pinned, source)
        for prohibited in ("systemctl restart", "systemctl reload", "artisan migrate", "ALTER ROLE", "ln -sfn",
                           "git reset --hard", "rclone copy", "scp ", "ssh ", "chown -R", "shell=True", "os.environ"):
            self.assertNotIn(prohibited, source)
        self.assertIn("os.link(sealed, OUTPUT)", source)
        self.assertIn("CURRENT.resolve(strict=True) != EXPECTED_RELEASE", source)
        self.assertIn("OFFSITE_TRANSFER=NOT_ATTEMPTED", source)

    def test_main_refuses_without_root_before_any_filesystem_access(self):
        with patch.object(mod.os, "geteuid", return_value=1000), self.assertRaisesRegex(RuntimeError, "WRONG_OPERATOR_OR_HOST"):
            mod.main(["--candidate-sha", SHA_A, "--expected-release", REL_A])


if __name__ == "__main__":
    unittest.main()
