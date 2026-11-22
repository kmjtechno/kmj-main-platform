import json
import os
import pathlib
import sys
import tempfile
import unittest

OPS = pathlib.Path(__file__).resolve().parent / "operations"
sys.path.insert(0, str(OPS))
import release_admission_receipts as ra  # noqa: E402
import release_receipt_store as store  # noqa: E402

SHA = "a" * 40
EXP = "platform-" + "b" * 12
NOW = 1_800_000_000
UID = os.getuid()


def receipt(kind):
    return {"schema": ra.RECEIPT_SCHEMA, "kind": kind, "host": "kmj-elite",
            "approvedSha": SHA, "expectedCurrentRelease": EXP,
            "capturedAt": NOW - 60, "result": "pass", "artifactSha256": "c" * 64}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        os.chmod(self.dir, 0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, kind, mode=0o600, text=None):
        p = self.dir / "{}-{}.json".format(kind, SHA[:12])
        p.write_text(text if text is not None else json.dumps(receipt(kind)))
        os.chmod(p, mode)
        return p

    def fill(self):
        for k in ra.KIND_TO_FLAG:
            self.put(k)

    def test_full_protected_set_yields_admission(self):
        self.fill()
        adm, b = store.evaluate(self.dir, SHA, EXP, True, NOW, UID)
        self.assertEqual(b, [])
        self.assertTrue(adm["standingOwnerAuthorization"])

    def test_untrusted_owner_is_refused(self):
        self.fill()
        adm, b = store.evaluate(self.dir, SHA, EXP, True, NOW, UID + 1)
        self.assertIsNone(adm)
        self.assertTrue(all(x.startswith("RECEIPT_MISSING") for x in b if x != "OWNER_AUTHORIZATION_MISSING"))

    def test_loose_mode_symlink_hardlink_and_size_refused(self):
        self.fill()
        self.put("public-qa", mode=0o644)
        adm, b = store.evaluate(self.dir, SHA, EXP, True, NOW, UID)
        self.assertIsNone(adm)
        self.assertIn("RECEIPT_MISSING:public-qa", b)
        self.fill()
        p = self.dir / "public-qa-{}.json".format(SHA[:12])
        target = self.dir / "real.json"
        p.rename(target)
        os.symlink(target, p)
        self.assertIn("RECEIPT_MISSING:public-qa", store.evaluate(self.dir, SHA, EXP, True, NOW, UID)[1])
        p.unlink()
        target.rename(p)
        os.link(p, self.dir / "alias.json")
        self.assertIn("RECEIPT_MISSING:public-qa", store.evaluate(self.dir, SHA, EXP, True, NOW, UID)[1])
        (self.dir / "alias.json").unlink()
        self.put("public-qa", text=" " * 5000)
        self.assertIn("RECEIPT_MISSING:public-qa", store.evaluate(self.dir, SHA, EXP, True, NOW, UID)[1])

    def test_duplicate_keys_and_bad_json_refused(self):
        self.fill()
        self.put("backup-witness", text='{"kind":"a","kind":"b"}')
        self.assertIn("RECEIPT_MISSING:backup-witness", store.evaluate(self.dir, SHA, EXP, True, NOW, UID)[1])
        self.put("backup-witness", text="NaN")
        self.assertIn("RECEIPT_MISSING:backup-witness", store.evaluate(self.dir, SHA, EXP, True, NOW, UID)[1])

    def test_group_writable_directory_refused(self):
        self.fill()
        os.chmod(self.dir, 0o770)
        adm, _ = store.evaluate(self.dir, SHA, EXP, True, NOW, UID)
        self.assertIsNone(adm)

    def test_receipt_for_other_sha_not_used(self):
        self.fill()
        other = "d" * 40
        adm, b = store.evaluate(self.dir, other, EXP, True, NOW, UID)
        self.assertIsNone(adm)

    def test_reader_writes_nothing(self):
        self.fill()
        before = sorted(os.listdir(self.dir))
        store.evaluate(self.dir, SHA, EXP, True, NOW, UID)
        self.assertEqual(before, sorted(os.listdir(self.dir)))


if __name__ == "__main__":
    unittest.main()
