#!/usr/bin/env python3
"""Contract + parity-logic tests for the 39b88b36d071 Google SFTP restore drill."""
from __future__ import annotations

import io
import os
import re
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "operations/verify-main-platform-39b88b36d071-google-sftp-restore-20261029.sh"
SOURCE = SCRIPT.read_text(encoding="utf-8")
PARITY = re.search(r"python3 - \"\$tmp/extracted/storage.tar.gz\" \"\$tmp/restored-storage\" <<'PY'\n(.*?)\nPY\n", SOURCE, re.S).group(1)


def parity(archive: Path, root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["python3", "-c", PARITY, str(archive), str(root)], capture_output=True, text=True)


def make_tar(path: Path, entries):
    with tarfile.open(path, "w:gz") as tar:
        for name, body in entries:
            info = tarfile.TarInfo(name)
            if body is None:
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            else:
                info.size = len(body)
                tar.addfile(info, io.BytesIO(body))


class Google39RestoreContract(unittest.TestCase):
    def test_syntax_and_pins(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
        for marker in ("NONROOT_INFO_REQUIRED", "GOOGLE_RECOVERY_HOST_REQUIRED", "OPERATOR_CONSENT",
                       "KMJ_EXPECTED_ENCRYPTED_SHA256", "EXPECTED_ENCRYPTED_SHA256",
                       "offsite-39b88b36d071.tar.gz.age", "39b88b36d071d3f78f2392d609d3febc2c530165",
                       "SFTP_IMPORT_DIGEST", "BACKUP_ARCHIVE_INTEGRITY PASS", "--auth-host=reject",
                       "listen_addresses=''", "STORAGE_EXTRACTION_PARITY PASS",
                       "PRODUCTION_DATABASE_MODIFIED NO", "GOOGLE_VPS_INDEPENDENT_RESTORE PASS"):
            self.assertIn(marker, SOURCE)
        for stale in ("b1d672", "867311da52431737", "8070dad72c55"):
            self.assertNotIn(stale, SOURCE)

    def test_never_claims_production_readiness(self):
        for claim in ("SAFE_TO_ACTIVATE_PRODUCTION NOT_PROVEN", "MATCHING_PRODUCTION_APPROVAL NOT_VERIFIED",
                      "OFFSITE_REMOTE_ARCHIVE_RETENTION NOT_VERIFIED"):
            self.assertIn(claim, SOURCE)

    def test_expected_hash_must_be_64_hex_before_any_work(self):
        # Blocks on missing/invalid hash regardless of host checks ordering.
        env = {k: v for k, v in os.environ.items() if not k.startswith("KMJ_")}
        r = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2)
        self.assertRegex(r.stdout, r"BLOCKED")

    def test_parity_accepts_exact_extraction(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            make_tar(t / "s.tgz", [("storage/app", None), ("storage/app/a.txt", b"abc")])
            (t / "root/storage/app").mkdir(parents=True)
            (t / "root/storage/app/a.txt").write_bytes(b"abc")
            r = parity(t / "s.tgz", t / "root")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.split(), ["1", "3"])

    def test_parity_rejects_missing_extra_resized_and_symlink(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            make_tar(t / "s.tgz", [("storage/app", None), ("storage/app/a.txt", b"abc")])
            base = t / "root"
            (base / "storage/app").mkdir(parents=True)
            self.assertNotEqual(parity(t / "s.tgz", base).returncode, 0)  # missing file
            (base / "storage/app/a.txt").write_bytes(b"abcd")
            self.assertNotEqual(parity(t / "s.tgz", base).returncode, 0)  # wrong size
            (base / "storage/app/a.txt").write_bytes(b"abc")
            self.assertEqual(parity(t / "s.tgz", base).returncode, 0)
            (base / "storage/app/extra").write_bytes(b"x")
            self.assertNotEqual(parity(t / "s.tgz", base).returncode, 0)  # extra
            (base / "storage/app/extra").unlink()
            (base / "storage/app/link").symlink_to("/etc/passwd")
            self.assertNotEqual(parity(t / "s.tgz", base).returncode, 0)  # symlink


if __name__ == "__main__":
    unittest.main()
