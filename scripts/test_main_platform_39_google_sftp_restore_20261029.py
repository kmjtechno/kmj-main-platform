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
META = re.search(r"python3 - \"\$tmp/extracted/metadata.txt\" \"\$expected_source_sha\" <<'PY'\n(.*?)\nPY\n", SOURCE, re.S).group(1)
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
                       "listen_addresses=''", "STORAGE_EXTRACTION_PARITY_CONTENT_SHA256 PASS",
                       "PRODUCTION_DATABASE_MODIFIED NO", "GOOGLE_VPS_INDEPENDENT_RESTORE PASS"):
            self.assertIn(marker, SOURCE)
        for stale in ("b1d672", "867311da52431737", "8070dad72c55"):
            self.assertNotIn(stale, SOURCE)

    def test_database_phase_runs_in_a_real_os_sandbox(self):
        for flag in ("bwrap", "--unshare-all", "--die-with-parent", "--cap-drop ALL", "--ro-bind / /",
                     '--tmpfs "$HOME"', '--bind "$tmp" "$tmp"', "DATABASE_PHASE_OS_SANDBOX PASS"):
            self.assertIn(flag, SOURCE)
        self.assertNotIn("--share-net", SOURCE)
        # No postgres client/server binary is invoked outside the sandboxed phase script.
        outer = SOURCE.split("cat >\"$tmp/db-phase.sh\"")[0] + SOURCE.split("INNER\nchmod")[1]
        for tool in ("initdb\" ", "pg_ctl\" ", "pg_restore\" ", "createdb\" ", "psql\" "):
            self.assertNotIn("$pgbin/" + tool, outer)

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

    def run_meta(self, content: str, source: str = "bbf95ca55df0b031f8e875540a476973c5a58bad1ec89fea8e9e2a5a7cc45cdd"):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "metadata.txt"
            path.write_text(content)
            return subprocess.run(["python3", "-c", META, str(path), source], capture_output=True)

    GOOD_META = ("backup_kind=offsite_sanitized_local_witness\n"
                 "source_local_sha256=bbf95ca55df0b031f8e875540a476973c5a58bad1ec89fea8e9e2a5a7cc45cdd\n"
                 "target_sha=39b88b36d071d3f78f2392d609d3febc2c530165\n"
                 "current_release=platform-574e443a2c75\nproduction_env_excluded=YES\n")

    def test_metadata_binding_accepts_exact_and_rejects_every_deviation(self):
        self.assertEqual(self.run_meta(self.GOOD_META).returncode, 0)
        for bad in (self.GOOD_META.replace("39b88b36d071d3f78f", "b1d672bbc83a51ca3f"),
                    self.GOOD_META.replace("platform-574e443a2c75", "platform-8070dad72c55"),
                    self.GOOD_META.replace("YES", "NO"),
                    self.GOOD_META + "extra=1\n",
                    self.GOOD_META + "target_sha=39b88b36d071d3f78f2392d609d3febc2c530165\n",
                    self.GOOD_META.replace("bbf95ca5", "00000000")):
            self.assertNotEqual(self.run_meta(bad).returncode, 0, bad)
        self.assertNotEqual(self.run_meta(self.GOOD_META, "0" * 64).returncode, 0)

    def test_parity_rejects_same_length_corruption(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            make_tar(t / "s.tgz", [("storage/app", None), ("storage/app/a.txt", b"YES")])
            base = t / "root"
            (base / "storage/app").mkdir(parents=True)
            (base / "storage/app/a.txt").write_bytes(b"BAD")  # same size, different bytes
            self.assertNotEqual(parity(t / "s.tgz", base).returncode, 0)
            (base / "storage/app/a.txt").write_bytes(b"YES")
            self.assertEqual(parity(t / "s.tgz", base).returncode, 0)

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
