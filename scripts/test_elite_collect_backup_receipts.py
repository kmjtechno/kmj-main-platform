import hashlib
import json
import os
import pathlib
import sys
import tempfile
import unittest

OPS = pathlib.Path(__file__).resolve().parent / "operations"
sys.path.insert(0, str(OPS))
import elite_collect_backup_receipts as col  # noqa: E402
import release_admission_receipts as ra  # noqa: E402

SHA = "a" * 40
EXP = "platform-" + "b" * 12
NOW = 1_800_000_000
UID = os.getuid()
BUNDLE = b"bundle-bytes"
DIGEST = hashlib.sha256(BUNDLE).hexdigest()


class BackupCollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        os.chmod(self.dir, 0o700)
        self.bundle = self.dir / ("pre-deploy-" + SHA[:12] + ".tar.gz")
        self.witness = self.dir / ("pre-deploy-" + SHA[:12] + ".json")
        self.put(self.bundle, BUNDLE)
        self.put(self.witness, json.dumps({"approvedSha": SHA, "currentRelease": EXP,
                                           "backupSha256": DIGEST}).encode())

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def put(path, data):
        if path.exists():
            path.unlink()
        path.write_bytes(data)
        os.chmod(path, 0o600)

    def run_collect(self, verify=lambda s, e: True):
        return col.collect(SHA, EXP, NOW, self.dir, UID, verify)

    def test_both_receipts_valid_when_everything_agrees(self):
        rs = self.run_collect()
        self.assertEqual([r["kind"] for r in rs], ["backup-witness", "disposable-restore"])
        for r in rs:
            self.assertIsNone(ra.receipt_problem(r, SHA, EXP, NOW))
            self.assertEqual(r["artifactSha256"], DIGEST)

    def test_tampered_bundle_refused(self):
        self.put(self.bundle, b"other-bytes")
        with self.assertRaises(ValueError):
            self.run_collect()

    def test_witness_bound_to_other_sha_or_predecessor_refused(self):
        for over in ({"approvedSha": "d" * 40}, {"currentRelease": "platform-" + "e" * 12},
                     {"backupSha256": "z" * 64}):
            rec = {"approvedSha": SHA, "currentRelease": EXP, "backupSha256": DIGEST}
            rec.update(over)
            self.put(self.witness, json.dumps(rec).encode())
            with self.assertRaises(Exception):
                self.run_collect()

    def test_loose_bundle_mode_and_open_dir_refused(self):
        os.chmod(self.bundle, 0o644)
        with self.assertRaises(ValueError):
            self.run_collect()
        os.chmod(self.bundle, 0o600)
        os.chmod(self.dir, 0o777)
        with self.assertRaises(ValueError):
            self.run_collect()

    def test_failed_uploads_verifier_yields_no_restore_receipt(self):
        with self.assertRaises(ValueError):
            self.run_collect(verify=lambda s, e: False)

    def test_cli_refuses_off_elite_and_bad_input(self):
        self.assertEqual(col.main(["x", "--check", "short", EXP]), 2)
        self.assertEqual(col.main(["x", "--nope", SHA, EXP]), 2)
        if os.geteuid() != 0:
            self.assertEqual(col.main(["x", "--write", SHA, EXP]), 2)

    def test_source_has_no_shell_or_backup_creation(self):
        src = (OPS / "elite_collect_backup_receipts.py").read_text()
        for bad in ("shell=True", "os.system", "pg_dump", "systemctl", "production-release.json"):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
