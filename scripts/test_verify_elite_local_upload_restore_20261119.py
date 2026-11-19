"""Offline safety regression for Elite-only disposable upload restore proof.

Mocks no root permissions, does not read live DB, upload data or credentials.
"""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest

SCRIPT = (Path(__file__).resolve().parent /
          "operations/verify-elite-local-upload-restore-20261119.py")
spec = importlib.util.spec_from_file_location("kmj_elite_upload_restore", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
SHA = "681d75531cd5fa91e47de2b4b639129ca53bcee2"
PREV = "platform-ce6ad7dc9d89"


def archive_bytes(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as arc:
        for name, kind, body in entries:
            item = tarfile.TarInfo(name)
            item.mode = 0o600
            if kind == "dir":
                item.type = tarfile.DIRTYPE
            elif kind == "symlink":
                item.type = tarfile.SYMTYPE
                item.linkname = "../../outside"
            else:
                item.type = tarfile.REGTYPE
                item.size = len(body)
            arc.addfile(item, io.BytesIO(body) if kind == "file" else None)
    return output.getvalue()


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / "pre-deploy-681d75531cd5.tar.gz"
        self.witness = self.root / "pre-deploy-681d75531cd5.json"
        self.scratch = self.root / "scratch"
        self.scratch.mkdir(mode=0o700)

    def fixture(self, *, inner_entries=None, outer_extra=None,
                meta=None, bad_sums=False, witness_sha=None):
        inner_entries = inner_entries if inner_entries is not None else [
            ("storage/app", "dir", b""),
            ("storage/app/public", "dir", b""),
            ("storage/app/public/picture.png", "file", b"test upload bytes"),
            (".env", "file", b"APP_KEY=test-fixture-only\n"),
        ]
        inner = archive_bytes(inner_entries)
        metadata = meta if meta is not None else (
            f"current_release={PREV}\napproved_sha={SHA}\n"
            "backup_kind=local_unencrypted_root_only\n").encode()
        base = [
            ("database.dump", b"PGDMP synthetic test only"),
            ("storage.tar.gz", inner),
            ("metadata.txt", metadata),
        ]
        sums = "".join(
            f"{hashlib.sha256(body).hexdigest()}  {name}\n"
            for name, body in base
        ).encode()
        if bad_sums:
            sums = sums.replace(sums[:1], b"0" if sums[:1] != b"0" else b"1", 1)
        outer = archive_bytes(
            [(name, "file", body) for name, body in
             base + [("SHA256SUMS", sums)]] + (outer_extra or []))
        self.archive.write_bytes(outer)
        self.archive.chmod(0o600)
        self.witness.write_text(json.dumps({
            "approvedSha": SHA, "currentRelease": PREV,
            "backupSha256": witness_sha or hashlib.sha256(outer).hexdigest(),
        }))
        self.witness.chmod(0o600)

    def check(self):
        return mod.verify_archive(self.archive, self.witness, SHA, PREV,
                                  self.scratch, uid=os.geteuid())

    def test_restores_actual_upload_and_env_bytes_with_sha_readback(self):
        self.fixture()
        self.assertEqual(self.check(), (1, len(b"test upload bytes")))
        root = self.scratch / "restored"
        self.assertEqual((root / "storage/app/public/picture.png").read_bytes(),
                         b"test upload bytes")
        self.assertEqual((root / ".env").read_bytes(),
                         b"APP_KEY=test-fixture-only\n")
        self.assertEqual(
            stat.S_IMODE((root / ".env").stat().st_mode), 0o600)

    def test_rejects_wrong_witness_sha_or_release(self):
        self.fixture(witness_sha="a" * 64)
        with self.assertRaisesRegex(mod.Blocked, "BUNDLE_WITNESS_SHA_MISMATCH"):
            self.check()
        self.fixture()
        with self.assertRaisesRegex(mod.Blocked, "WITNESS_CANDIDATE_MISMATCH"):
            mod.verify_archive(self.archive, self.witness, SHA,
                               "platform-" + "b" * 12,
                               self.scratch, uid=os.geteuid())

    def test_rejects_root_archive_symlink_or_hardlink(self):
        self.fixture()
        link = self.root / "alias.tar.gz"
        link.symlink_to(self.archive)
        with self.assertRaises(mod.Blocked):
            mod.verify_archive(link, self.witness, SHA, PREV,
                               self.scratch, uid=os.geteuid())
        other = self.root / "other.tar.gz"
        os.link(self.archive, other)
        with self.assertRaises(mod.Blocked):
            self.check()

    def test_rejects_inner_traversal_symlink_or_duplicate(self):
        for bad in [
            [("storage/app", "dir", b""), ("storage/app/../escape", "file", b"x"),
             (".env", "file", b"fake")],
            [("storage/app", "dir", b""), ("storage/app/link", "symlink", b""),
             (".env", "file", b"fake")],
            [("storage/app", "dir", b""), ("storage/app/p", "file", b"x"),
             ("storage/app/p", "file", b"y"), (".env", "file", b"fake")],
        ]:
            with self.subTest(bad=bad[1][0]):
                self.fixture(inner_entries=bad)
                with self.assertRaises(mod.Blocked):
                    self.check()

    def test_rejects_missing_env_storage_and_outer_extra(self):
        for inner in [
            [("storage/app", "dir", b""), ("storage/app/f", "file", b"x")],
            [(".env", "file", b"KEY=a"), ("storage/app/f", "file", b"x")],
        ]:
            with self.subTest(inner=inner):
                self.fixture(inner_entries=inner)
                with self.assertRaises(mod.Blocked):
                    self.check()
        self.fixture(outer_extra=[("../outside", "file", b"x")])
        with self.assertRaisesRegex(mod.Blocked, "BUNDLE_LAYOUT_INVALID"):
            self.check()

    def test_rejects_modified_checksum_or_metadata(self):
        self.fixture(bad_sums=True)
        with self.assertRaisesRegex(mod.Blocked, "BUNDLE_CONTENT_SHA_MISMATCH"):
            self.check()
        self.fixture(meta=b"approved_sha=fake\n")
        with self.assertRaisesRegex(mod.Blocked, "BUNDLE_METADATA_MISMATCH"):
            self.check()

    def test_rejects_owner_or_perms_unsafe(self):
        self.fixture()
        self.archive.chmod(0o644)
        with self.assertRaises(mod.Blocked):
            self.check()

    def test_member_name_rejects_unsafe_components(self):
        for bad in ("/absolute", "storage/app/../other",
                    "storage/app//other", "storage/app\\other",
                    "storage/app/file\nbad", "storage/app/C:evil"):
            with self.subTest(bad=bad):
                with self.assertRaises(mod.Blocked):
                    mod.safe_member_name(bad)


if __name__ == "__main__":
    unittest.main()
