import copy
import pathlib
import sys
import unittest

OPS = pathlib.Path(__file__).resolve().parent / "operations"
sys.path.insert(0, str(OPS))
import release_admission_receipts as ra  # noqa: E402
import main_platform_autopublish_gate as gate  # noqa: E402

SHA = "a" * 40
EXP = "platform-" + "b" * 12
NOW = 1_800_000_000


def receipt(kind, **over):
    r = {"schema": ra.RECEIPT_SCHEMA, "kind": kind, "host": "kmj-elite",
         "approvedSha": SHA, "expectedCurrentRelease": EXP,
         "capturedAt": NOW - 60, "result": "pass", "artifactSha256": "c" * 64}
    r.update(over)
    return r


def all_receipts():
    return [receipt(k) for k in ra.KIND_TO_FLAG]


class AdmissionReceiptTests(unittest.TestCase):
    def test_full_set_builds_admission_the_real_gate_accepts(self):
        adm, blockers = ra.build_admission(all_receipts(), SHA, EXP, True, NOW)
        self.assertEqual(blockers, [])
        approval = {"approvedSha": SHA, "expectedCurrentRelease": EXP,
                    "backupVerified": True, "rollbackVerified": True}
        self.assertEqual(gate.decision(approval, adm, EXP, SHA, SHA),
                         "READY_APPROVED_RELEASE")

    def test_flags_cover_exactly_the_gate_keys(self):
        self.assertEqual(set(ra.KIND_TO_FLAG.values()),
                         set(gate.ELITE_LOCAL_ACCEPTANCE_KEYS))

    def test_missing_receipt_blocks(self):
        rs = [r for r in all_receipts() if r["kind"] != "public-qa"]
        adm, b = ra.build_admission(rs, SHA, EXP, True, NOW)
        self.assertIsNone(adm)
        self.assertIn("RECEIPT_MISSING:public-qa", b)

    def test_owner_authorization_must_be_literal_true(self):
        for v in (False, None, 1, "true"):
            adm, b = ra.build_admission(all_receipts(), SHA, EXP, v, NOW)
            self.assertIsNone(adm)
            self.assertIn("OWNER_AUTHORIZATION_MISSING", b)

    def test_bad_receipts_block(self):
        cases = {
            "RECEIPT_IDENTITY": {"approvedSha": "d" * 40},
            "RECEIPT_IDENTITY ": {"expectedCurrentRelease": "platform-" + "e" * 12},
            "RECEIPT_STALE": {"capturedAt": NOW - ra.MAX_AGE_SECONDS - 1},
            "RECEIPT_STALE ": {"capturedAt": NOW + 3600},
            "RECEIPT_NOT_PASS": {"result": "fail"},
            "RECEIPT_HOST": {"host": "other"},
            "RECEIPT_ARTIFACT": {"artifactSha256": "xyz"},
            "RECEIPT_TIME": {"capturedAt": True},
            "RECEIPT_SCHEMA": {"schema": "v0"},
        }
        for code, over in cases.items():
            rs = all_receipts()
            rs[0] = receipt(rs[0]["kind"], **over)
            adm, b = ra.build_admission(rs, SHA, EXP, True, NOW)
            self.assertIsNone(adm, code)
            self.assertTrue(any(x.startswith(code.strip()) for x in b), (code, b))

    def test_extra_key_and_duplicate_kind_block(self):
        rs = all_receipts()
        rs[0] = dict(rs[0], extra=1)
        self.assertIsNone(ra.build_admission(rs, SHA, EXP, True, NOW)[0])
        rs = all_receipts() + [copy.deepcopy(all_receipts()[0])]
        adm, b = ra.build_admission(rs, SHA, EXP, True, NOW)
        self.assertIsNone(adm)
        self.assertTrue(any(x.startswith("RECEIPT_DUPLICATE") for x in b))

    def test_bad_inputs_block(self):
        for args in (("x", EXP, True, NOW), (SHA, "x", True, NOW), (SHA, EXP, True, True)):
            self.assertEqual(ra.build_admission(all_receipts(), *args)[1], ["INPUT_IDENTITY"])
        self.assertIsNone(ra.build_admission("nope", SHA, EXP, True, NOW)[0])


if __name__ == "__main__":
    unittest.main()
