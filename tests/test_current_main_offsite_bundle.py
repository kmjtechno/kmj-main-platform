"""Synthetic exact-SHA offsite sealing tests; no production data used."""
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

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/operations/seal-current-main-production-backup-for-offsite-20261027.py"
SPEC = importlib.util.spec_from_file_location("stage_production_offsite", FILE)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
SHA = "a" * 40
OLD = "platform-8070dad72c55"


def pack(path, members):
    with tarfile.open(path, "w:gz") as archive:
        for name, data, kind in members:
            info = tarfile.TarInfo(name)
            if kind == "link":
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/shadow"
                archive.addfile(info)
            elif kind == "dir":
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            else:
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))


def fixture(root, *, evil=False):
    mod.TARGET_SHA = SHA
    mod.EXPECTED_RELEASE = Path("/home/kmjprod/releases") / OLD
    inner = root / "private-storage.tar.gz"
    entries = [
        ("storage/app", b"", "dir"),
        ("storage/app/public", b"", "dir"),
        ("storage/app/private", b"", "dir"),
        ("storage/app/private/user-file", b"SENSITIVE_SAMPLE_NOT_PRODUCTION", "file"),
        (".env", b"APP_KEY=SENSITIVE_KEY_DO_NOT_EXPORT", "file"),
    ]
    if evil:
        entries.append(("storage/app/private/escape", b"", "link"))
    pack(inner, entries)
    values = {
        "database.dump": b"PGDMP-SYNTHETIC-ONLY",
        "storage.tar.gz": inner.read_bytes(),
        "metadata.txt": (
            f"current_release={OLD}\napproved_sha={SHA}\n"
            "backup_kind=local_unencrypted_root_only\n"
        ).encode(),
    }
    values["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(values[n]).hexdigest()}  {n}\n"
        for n in ("database.dump", "storage.tar.gz", "metadata.txt")
    ).encode()
    outer = root / "local.tar.gz"
    pack(outer, [(n, b, "file") for n, b in values.items()])
    witness = root / "local.json"
    witness.write_text(json.dumps({
        "approvedSha": SHA,
        "currentRelease": OLD,
        "backupSha256": hashlib.sha256(outer.read_bytes()).hexdigest(),
    }))
    (root / "scratch").mkdir()
    return outer, witness


class ExactMainSealerTests(unittest.TestCase):
    def test_invalid_cli_refused_before_host_or_data(self):
        for args in ([], ["main"], [SHA], [SHA, "wrong"]):
            with self.subTest(args=args):
                p = subprocess.run([sys.executable, "-B", str(FILE), *args],
                                   capture_output=True, text=True, timeout=8)
                self.assertEqual(p.returncode, 2)
                self.assertIn("EXACT_SHA_AND_CURRENT_RELEASE_REQUIRED", p.stderr)

    def test_wrong_host_refused(self):
        p = subprocess.run([sys.executable, "-B", str(FILE), SHA, OLD],
                           capture_output=True, text=True, timeout=8)
        self.assertEqual(p.returncode, 2)
        self.assertIn("WRONG_OPERATOR_OR_HOST", p.stderr)

    def test_real_source_bundle_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outer, witness = fixture(root)
            with patch.object(mod, "verify_root_only"):
                result, digest = mod.repack_verified_local(
                    outer, witness, root / "scratch")
            self.assertEqual(digest, mod.digest(outer))
            with tarfile.open(result, "r:gz") as archive:
                parts = {name: archive.extractfile(name).read()
                         for name in mod.MEMBERS}
            self.assertIn(b"production_env_excluded=YES", parts["metadata.txt"])
            sanitized = root / "redacted-storage.tar.gz"
            sanitized.write_bytes(parts["storage.tar.gz"])
            with tarfile.open(sanitized, "r:gz") as tf:
                self.assertNotIn(".env", tf.getnames())
                self.assertIn("storage/app/private/user-file", tf.getnames())
            self.assertNotIn(b"SENSITIVE_KEY_DO_NOT_EXPORT", result.read_bytes())

    def test_untrusted_storage_link_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outer, witness = fixture(root, evil=True)
            with patch.object(mod, "verify_root_only"):
                with self.assertRaisesRegex(RuntimeError, "UNSAFE_STORAGE_ARCHIVE_MEMBER"):
                    mod.repack_verified_local(outer, witness, root / "scratch")

    def test_no_live_or_remote_mutations(self):
        s = FILE.read_text()
        for forbidden in ("rclone copy", "scp ", "ssh ", "systemctl",
                          "artisan migrate", "git reset", "git clean",
                          "/etc/kmj-codebridge/main-platform-production-release.json"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, s)
        for required in ("OFFSITE_TRANSFER=NOT_ATTEMPTED",
                         "TARGET_MAIN_MOVED", "TARGET_NOT_CURRENT_MAIN",
                         "ENV_EXCLUDED_FROM_OFFSITE_COPY=PASS",
                         "PRODUCTION_RELEASE_CHANGED", "os.link(sealed, OUTPUT)"):
            with self.subTest(required=required):
                self.assertIn(required, s)


if __name__ == "__main__":
    unittest.main()
