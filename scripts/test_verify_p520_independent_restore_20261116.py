"""Crypto-positive and adversarial 4C9 P520 offsite restore receipt tests."""
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path
import unittest

SRC = Path(__file__).with_name("verify-p520-independent-restore-20261116.py")
s = importlib.util.spec_from_file_location("p520_offsite", SRC)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
D = "a" * 64
S = "b" * 64
NOW = datetime(2026, 11, 16, 11, 0, tzinfo=timezone.utc)


def openssl(*args):
    subprocess.run(["openssl", *map(str, args)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class P520ReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        cls.priv, cls.pub = cls.dir / "private", cls.dir / "pub.pem"
        openssl("genpkey", "-algorithm", "ed25519", "-out", cls.priv)
        openssl("pkey", "-in", cls.priv, "-pubout", "-out", cls.pub)
        cls.public = cls.pub.read_bytes()
        cls.pubsha = hashlib.sha256(cls.public).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.receipt = {
            "schema": "kmj.independent-offsite.restore.v1",
            "receiver": "p520", "receiverHost": "DESKTOP-5FVJMET",
            "candidateSha": m.CANDIDATE, "expectedCurrentRelease": m.PREDECESSOR,
            "encryptedSha256": D, "sourceLocalSha256": S,
            "receivedCipherSha256": D, "receivedCipherBytes": 441334,
            "decryptVerified": True, "bundleManifestVerified": True,
            "isolatedPostgresRestoreVerified": True,
            "restoredStorageParityVerified": True,
            "networkIsolationVerified": True,
            "productionDatabaseUnchanged": True,
            "completedAtUtc": NOW.isoformat().replace("+00:00", "Z"),
        }

    def sign(self, raw):
        with tempfile.TemporaryDirectory() as d:
            f, sig = Path(d) / "payload", Path(d) / "signature"
            f.write_bytes(raw)
            openssl("pkeyutl", "-sign", "-rawin", "-inkey", self.priv,
                    "-in", f, "-out", sig)
            return sig.read_bytes()

    def check(self, receipt=None, raw=None, signature=None, public=None,
              pubsha=None, cipher=D, source=S, now=NOW):
        raw = raw or json.dumps(receipt or self.receipt, separators=(",", ":")).encode()
        signature = signature or self.sign(raw)
        return m.verify(raw, signature, public or self.public,
                        pubsha or self.pubsha, cipher, source, now)

    def test_signed_exact_receipt_passes_without_release_credit(self):
        x = self.check()
        self.assertEqual(x["receiptCrypto"], "PASS")
        self.assertEqual(x["productionApproval"], "NOT_GRANTED")
        self.assertEqual(x["googleVpsDependency"], "NONE_IN_VERIFIER")

    def test_modified_receipt_invalid_signature(self):
        raw = json.dumps(self.receipt, separators=(",", ":")).encode()
        sig = self.sign(raw)
        tampered = raw.replace(b"441334", b"441335")
        with self.assertRaisesRegex(m.Block, "ED25519_SIGNATURE_INVALID"):
            self.check(raw=tampered, signature=sig)

    def test_wrong_candidate_or_receiver_denied(self):
        for key, value in (("candidateSha", "0"*40), ("receiver", "google-vps"),
                           ("receiverHost", "fake"), ("encryptedSha256", S),
                           ("sourceLocalSha256", D), ("receivedCipherSha256", S),
                           ("expectedCurrentRelease", "platform-e5b43872bc03")):
            with self.subTest(key=key):
                r = dict(self.receipt)
                r[key] = value
                with self.assertRaises(m.Block):
                    self.check(receipt=r)

    def test_claimed_success_must_be_literal_boolean(self):
        for key in m.BOOLEANS:
            for value in (False, "true", 1, 0, None):
                with self.subTest(key=key,value=value):
                    r = dict(self.receipt)
                    r[key] = value
                    with self.assertRaisesRegex(m.Block, "RECOVERY_PROOF_FLAGS"):
                        self.check(receipt=r)

    def test_duplicate_key_and_extra_key_fail(self):
        raw = json.dumps(self.receipt).encode()
        raw = raw[:-1] + b',"receiver":"p520"}'
        with self.assertRaisesRegex(m.Block, "DUPLICATE_JSON_KEY"):
            self.check(raw=raw)
        r = dict(self.receipt)
        r["other"] = "anything"
        with self.assertRaisesRegex(m.Block, "RECEIPT_SCHEMA"):
            self.check(receipt=r)

    def test_stale_and_future_receipts_denied(self):
        with self.assertRaisesRegex(m.Block, "RECEIPT_STALE_OR_FUTURE"):
            self.check(now=NOW + timedelta(hours=49))
        with self.assertRaisesRegex(m.Block, "RECEIPT_STALE_OR_FUTURE"):
            self.check(now=NOW - timedelta(minutes=7))

    def test_untrusted_signer_or_pubkey_digest_denied(self):
        with self.assertRaisesRegex(m.Block, "UNTRUSTED_PUBLIC_KEY"):
            self.check(pubsha="0"*64)
        with self.assertRaisesRegex(m.Block, "UNPINNED_DIGEST_ARGUMENT"):
            self.check(source="NOT-A-SHA")

    def test_file_symlinks_hardlinks_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "payload"
            p.write_bytes(b"test")
            self.assertEqual(m.read_regular(p, 4096), b"test")
            sy = Path(d) / "symlink"
            sy.symlink_to(p)
            with self.assertRaises(OSError):
                m.read_regular(sy, 4096)
            hard = Path(d) / "hard"
            hard.hardlink_to(p)
            with self.assertRaisesRegex(m.Block, "UNTRUSTED_FILE"):
                m.read_regular(p, 4096)


if __name__ == "__main__":
    unittest.main()
