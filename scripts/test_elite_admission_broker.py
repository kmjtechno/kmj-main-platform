import json
import os
import pathlib
import stat
import sys
import tempfile
import unittest
import uuid

OPS = pathlib.Path(__file__).resolve().parent / "operations"
sys.path.insert(0, str(OPS))
import elite_admission_broker as br  # noqa: E402
import main_platform_autopublish_gate as gate  # noqa: E402
import release_admission_receipts as ra  # noqa: E402

SHA = "a" * 40
PREV = "platform-" + "b" * 12
NOW = 1_800_000_000
UID = os.getuid()
APPROVAL = {"approvedSha": SHA, "expectedCurrentRelease": PREV,
            "backupVerified": True, "rollbackVerified": True}


def intent(**over):
    obj = {"schema": br.INTENT_SCHEMA, "intent_id": str(uuid.uuid4()), "actor_user_id": 7,
           "action": br.INTENT_ACTION, "approved_sha": SHA, "expected_current_release": PREV,
           "created_at_unix": NOW - 5, "expires_at_unix": NOW + 60,
           "owner_authenticated_qa_attested": True}
    obj.update(over)
    return obj


def raw(obj):
    return json.dumps(obj).encode()


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.rec = self.root / "receipts"
        self.rec.mkdir(mode=0o700)
        for kind in ra.KIND_TO_FLAG:
            if kind == "authenticated-qa":
                continue
            p = self.rec / "{}-{}.json".format(kind, SHA[:12])
            p.write_text(json.dumps({
                "schema": ra.RECEIPT_SCHEMA, "kind": kind, "host": "kmj-elite",
                "approvedSha": SHA, "expectedCurrentRelease": PREV, "capturedAt": NOW - 30,
                "result": "pass", "artifactSha256": "c" * 64}))
            os.chmod(p, 0o600)

    def tearDown(self):
        self.tmp.cleanup()

    def decide(self, it=None, approval=APPROVAL, live=PREV):
        it = it or intent()
        return br.decide(it, raw(it), approval, live, self.rec, NOW, UID)

    def test_full_evidence_yields_admission_the_real_gate_accepts(self):
        adm, b = self.decide()
        self.assertEqual(b, [])
        self.assertEqual(gate.decision(APPROVAL, adm, PREV, SHA, SHA), "READY_APPROVED_RELEASE")

    def test_missing_receipt_blocks(self):
        (self.rec / "public-qa-{}.json".format(SHA[:12])).unlink()
        adm, b = self.decide()
        self.assertIsNone(adm)
        self.assertIn("RECEIPT_MISSING:public-qa", b)

    def test_approval_and_live_mismatch_block(self):
        for approval, live in ((dict(APPROVAL, approvedSha="d" * 40), PREV),
                               (dict(APPROVAL, backupVerified=False), PREV),
                               ({"x": 1}, PREV), (APPROVAL, "platform-" + "e" * 12)):
            self.assertIsNone(self.decide(approval=approval, live=live)[0])

    def test_planted_authenticated_qa_receipt_is_ignored(self):
        p = self.rec / "authenticated-qa-{}.json".format(SHA[:12])
        p.write_text("{}")
        os.chmod(p, 0o600)
        self.assertEqual(self.decide()[1], [])

    def test_intent_defects_refused(self):
        defects = [
            {"owner_authenticated_qa_attested": False}, {"owner_authenticated_qa_attested": 1},
            {"schema": "x"}, {"action": "activate_existing_approved_release"},
            {"intent_id": "not-a-uuid"}, {"actor_user_id": True}, {"actor_user_id": 0},
            {"approved_sha": "z" * 40}, {"expected_current_release": "platform-" + SHA[:12]},
            {"created_at_unix": NOW - 500}, {"expires_at_unix": NOW - 1},
            {"expires_at_unix": NOW + 500},
        ]
        for over in defects:
            with self.assertRaises(ValueError, msg=str(over)):
                br.parse_intent(raw(intent(**over)), NOW)
        extra = intent()
        extra["extra"] = 1
        with self.assertRaises(ValueError):
            br.parse_intent(raw(extra), NOW)
        with self.assertRaises(ValueError):
            br.parse_intent(b'{"schema":"a","schema":"b"}', NOW)

    def test_write_admission_private_and_no_clobber(self):
        adm, _ = self.decide()
        d = self.root / "etc"
        d.mkdir(mode=0o755)
        p = br.write_admission(adm, d, UID)
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
        self.assertEqual(sorted(x.name for x in d.iterdir()), [p.name])
        with self.assertRaises(ValueError):
            br.write_admission(adm, d, UID)
        d.chmod(0o777)
        with self.assertRaises(ValueError):
            br.write_admission(adm, d, UID)

    def test_claim_once_blocks_replay(self):
        st = self.root / "state"
        st.mkdir(mode=0o700)
        it = intent()
        br.claim_once(it, NOW, st, UID)
        with self.assertRaises(ValueError):
            br.claim_once(it, NOW, st, UID)

    def test_run_refuses_off_elite_and_source_is_safe(self):
        if os.geteuid() != 0:
            self.assertEqual(br.run(True, NOW), 2)
        src = (OPS / "elite_admission_broker.py").read_text()
        for bad in ("shell=True", "os.system", "systemctl", "subprocess", "production-release.json\"", "rollbackVerified\": True"):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
