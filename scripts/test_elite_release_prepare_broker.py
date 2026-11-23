#!/usr/bin/env python3
"""Offline tests for the release prepare broker (no network, no root, no helper execution)."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

HERE = Path(__file__).resolve().parent / "operations"
sys.path.insert(0, str(HERE))
import elite_release_prepare_broker as b  # noqa: E402

SHA = "a" * 40
NOW = 1_800_000_000
GREEN = {"total_count": 7, "check_runs": [{"status": "completed", "conclusion": "success"}] * 7}


def intent_body(**over):
    body = {"schema": b.INTENT_SCHEMA, "intent_id": str(uuid.uuid4()), "actor_user_id": 1,
            "action": b.INTENT_ACTION, "approved_sha": SHA, "created_at_unix": NOW,
            "expires_at_unix": NOW + 90, "owner_backup_rollback_attested": True,
            "migrate_after_activation_accepted": True}
    body.update(over)
    return body


def raw(body):
    return json.dumps(body).encode()


class Fake:
    """Deps double: records helper runs and lets each test choose live/main/check/helper behaviour."""
    def __init__(self, head=SHA, checks=GREEN, helper=b"HELPER", live="platform-" + "b" * 12, code=0, out=b.PREPARE_OK):
        self.head, self.payload, self.data, self.live_name = head, checks, helper, live
        self.code, self.out, self.runs = code, out, []

    def main_head(self):
        return self.head

    def checks(self, sha):
        return self.payload

    def helper(self, sha):
        return self.data

    def live(self):
        return self.live_name

    def run(self, data, args, timeout):
        self.runs.append((tuple(args), timeout))
        return self.code, self.out


class IntentTests(unittest.TestCase):
    def test_valid_intent_parses(self):
        self.assertEqual(b.parse_intent(raw(intent_body()), NOW)["approved_sha"], SHA)

    def test_rejects_bad_shapes(self):
        cases = [
            (intent_body(extra=1), "BLOCKED_INTENT_SCHEMA"),
            (intent_body(action="activate"), "BLOCKED_INTENT_ACTION"),
            (intent_body(schema="x"), "BLOCKED_INTENT_ACTION"),
            (intent_body(intent_id="not-a-uuid"), "BLOCKED_INTENT_ID"),
            (intent_body(actor_user_id=0), "BLOCKED_ACTOR_ID"),
            (intent_body(actor_user_id=True), "BLOCKED_ACTOR_ID"),
            (intent_body(approved_sha="A" * 40), "BLOCKED_RELEASE_IDENTITY"),
            (intent_body(approved_sha="a" * 39), "BLOCKED_RELEASE_IDENTITY"),
            (intent_body(expires_at_unix=NOW - 1), "BLOCKED_INTENT_EXPIRED_OR_FUTURE"),
            (intent_body(created_at_unix=NOW + 60, expires_at_unix=NOW + 100), "BLOCKED_INTENT_EXPIRED_OR_FUTURE"),
            (intent_body(expires_at_unix=NOW + 500), "BLOCKED_INTENT_EXPIRED_OR_FUTURE"),
            (intent_body(owner_backup_rollback_attested=False), "BLOCKED_OWNER_ATTESTATION_MISSING"),
            (intent_body(owner_backup_rollback_attested="yes"), "BLOCKED_OWNER_ATTESTATION_MISSING"),
            (intent_body(migrate_after_activation_accepted=False), "BLOCKED_MIGRATE_ACCEPTANCE_MISSING"),
        ]
        for body, code in cases:
            with self.assertRaises(ValueError, msg=code) as ctx:
                b.parse_intent(raw(body), NOW)
            self.assertEqual(str(ctx.exception), code)

    def test_duplicate_fields_and_non_json_are_refused(self):
        dup = b'{"schema":"a","schema":"b"}'
        with self.assertRaises(ValueError):
            b.parse_intent(dup, NOW)
        with self.assertRaises(ValueError):
            b.parse_intent(b"not json", NOW)
        with self.assertRaises(ValueError):
            b.parse_intent(b'{"actor_user_id": NaN}', NOW)

    def test_read_intent_enforces_file_identity(self):
        with tempfile.TemporaryDirectory() as d:
            ops = Path(d) / "ops"
            ops.mkdir(mode=0o750)
            path = ops / "release-prepare-request.json"
            path.write_bytes(raw(intent_body()))
            os.chmod(path, 0o640)
            uid = os.getuid()
            self.assertEqual(b.read_intent(path, uid, NOW)["approved_sha"], SHA)
            os.chmod(path, 0o666)
            with self.assertRaises(ValueError):
                b.read_intent(path, uid, NOW)
            os.chmod(path, 0o640)
            link = ops / "link.json"
            link.symlink_to(path)
            with self.assertRaises(OSError):
                b.read_intent(link, uid, NOW)
            with self.assertRaises(ValueError):
                b.read_intent(path, uid + 1, NOW)  # wrong owner


class CandidateTests(unittest.TestCase):
    def test_checks_must_all_be_completed_success_and_complete(self):
        self.assertTrue(b.checks_all_green(GREEN))
        bad = [
            {"total_count": 7, "check_runs": [{"status": "completed", "conclusion": "success"}] * 6},
            {"total_count": 3, "check_runs": [{"status": "completed", "conclusion": "success"}] * 3},
            {"total_count": 7, "check_runs": [{"status": "completed", "conclusion": "success"}] * 6
             + [{"status": "in_progress", "conclusion": None}]},
            {"total_count": 7, "check_runs": [{"status": "completed", "conclusion": "success"}] * 6
             + [{"status": "completed", "conclusion": "failure"}]},
            {"total_count": 7, "check_runs": [{"status": "completed", "conclusion": "success"}] * 6
             + [{"status": "completed", "conclusion": "skipped"}]},
            {"total_count": "7", "check_runs": []}, None, [], {"check_runs": "x"},
        ]
        for payload in bad:
            self.assertFalse(b.checks_all_green(payload), payload)

    def test_sha_must_be_the_current_main_head(self):
        b.verify_candidate(SHA, SHA, GREEN)
        with self.assertRaisesRegex(ValueError, "BLOCKED_SHA_NOT_MAIN_HEAD"):
            b.verify_candidate(SHA, "c" * 40, GREEN)
        with self.assertRaisesRegex(ValueError, "BLOCKED_SHA_NOT_MAIN_HEAD"):
            b.verify_candidate(SHA, "", GREEN)

    def test_helper_must_match_the_pinned_digest(self):
        self.assertFalse(b.helper_ok(b"anything else"))
        self.assertRegex(b.HELPER_SHA256, r"^[a-f0-9]{64}$")
        actual = (HERE / "owner-release-main-platform.sh").read_bytes()
        self.assertEqual(hashlib.sha256(actual).hexdigest(), b.HELPER_SHA256,
                         "the pinned helper hash must match the helper in this tree")
        self.assertTrue(b.helper_ok(actual))


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state"
        self.state.mkdir(mode=0o700)
        self.status = Path(self.tmp.name) / "status.json"
        self.uid = os.getuid()
        self.good = b"GOOD HELPER"

    def tearDown(self):
        self.tmp.cleanup()

    def deps(self, **kw):
        kw.setdefault("helper", self.good)
        return Fake(**kw)

    def run_prepare(self, fake, execute=True, **over):
        intent = b.parse_intent(raw(intent_body(**over)), NOW)
        old = b.HELPER_SHA256
        b.HELPER_SHA256 = hashlib.sha256(self.good).hexdigest()
        try:
            return b.prepare(intent, self.uid, NOW, fake, self.state, self.status, execute, self.uid)
        finally:
            b.HELPER_SHA256 = old

    def test_success_runs_only_prepare_only_and_records_pending_migration(self):
        fake = self.deps()
        self.assertEqual(self.run_prepare(fake), "PREPARED_AWAITING_ACTIVATION")
        self.assertEqual(fake.runs, [(("--prepare-only", SHA), b.PREPARE_TIMEOUT)])
        self.assertEqual(b.read_prepared(self.state), {"approved_sha": SHA, "prepared_at_unix": NOW,
                                                        "migrate_pending": True})
        self.assertEqual(json.loads(self.status.read_text())["state"], "prepared_awaiting_activation")

    def test_preflight_runs_nothing_and_claims_nothing(self):
        fake = self.deps()
        self.assertEqual(self.run_prepare(fake, execute=False), "PREPARE_PREFLIGHT_PASS")
        self.assertEqual(fake.runs, [])
        self.assertEqual(list(self.state.iterdir()), [])

    def test_blocks_before_running_anything(self):
        cases = [
            (self.deps(head="c" * 40), "BLOCKED_SHA_NOT_MAIN_HEAD"),
            (self.deps(checks={"total_count": 7, "check_runs": [{"status": "queued", "conclusion": None}] * 7}),
             "BLOCKED_EXACT_HEAD_CHECKS_NOT_GREEN"),
            (self.deps(helper=b"TAMPERED"), "BLOCKED_HELPER_HASH_MISMATCH"),
            (self.deps(live="platform-" + SHA[:12]), "BLOCKED_ALREADY_LIVE"),
        ]
        for fake, code in cases:
            with self.assertRaisesRegex(ValueError, code):
                self.run_prepare(fake)
            self.assertEqual(fake.runs, [], code)
            self.assertEqual(list(self.state.iterdir()), [], code)

    def test_same_intent_cannot_run_twice(self):
        fake = self.deps()
        intent = b.parse_intent(raw(intent_body()), NOW)
        b.claim_once(intent, NOW, self.state, self.uid)
        with self.assertRaisesRegex(ValueError, "BLOCKED_INTENT_ALREADY_CLAIMED"):
            b.claim_once(intent, NOW, self.state, self.uid)
        old = b.HELPER_SHA256
        b.HELPER_SHA256 = hashlib.sha256(self.good).hexdigest()
        try:
            with self.assertRaisesRegex(ValueError, "BLOCKED_INTENT_ALREADY_CLAIMED"):
                b.prepare(intent, self.uid, NOW, fake, self.state, self.status, True, self.uid)
        finally:
            b.HELPER_SHA256 = old
        self.assertEqual(fake.runs, [])

    def test_helper_failure_is_reported_and_leaves_no_pending_migration(self):
        for fake in (self.deps(code=3), self.deps(out="no marker"), self.deps(out=b.PREPARE_OK + " BLOCKED_X")):
            for f in self.state.iterdir():
                f.unlink()
            with self.assertRaisesRegex(ValueError, "BLOCKED_HELPER_FAILED"):
                self.run_prepare(fake)
            self.assertIsNone(b.read_prepared(self.state))
            self.assertEqual(json.loads(self.status.read_text())["state"], "prepare_failed")


class PostActivationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name)
        os.chmod(self.state, 0o700)
        self.status = self.state / "status.json"
        self.good = b"GOOD HELPER"
        self.uid = os.getuid()
        self.old = b.HELPER_SHA256
        b.HELPER_SHA256 = hashlib.sha256(self.good).hexdigest()

    def tearDown(self):
        b.HELPER_SHA256 = self.old
        self.tmp.cleanup()

    def go(self, fake, execute=True):
        return b.post_activation(self.uid, NOW, fake, self.state, self.status, execute)

    def test_nothing_due_without_a_prepared_candidate(self):
        self.assertEqual(self.go(Fake(helper=self.good)), "NO_POST_ACTIVATION_DUE")

    def test_waits_until_the_candidate_is_actually_live(self):
        b.write_prepared(SHA, NOW, self.state)
        fake = Fake(helper=self.good, live="platform-" + "b" * 12)
        self.assertEqual(self.go(fake), "CANDIDATE_NOT_LIVE_YET")
        self.assertEqual(fake.runs, [])

    def test_migrates_once_when_live_then_stops(self):
        b.write_prepared(SHA, NOW, self.state)
        fake = Fake(helper=self.good, live="platform-" + SHA[:12], out=b.MIGRATE_OK)
        self.assertEqual(self.go(fake), "POST_ACTIVATION_MIGRATE_DONE")
        self.assertEqual(fake.runs, [(("--post-activation", SHA), b.MIGRATE_TIMEOUT)])
        self.assertFalse(b.read_prepared(self.state)["migrate_pending"])
        self.assertEqual(self.go(fake), "NO_POST_ACTIVATION_DUE")
        self.assertEqual(len(fake.runs), 1)
        self.assertEqual(json.loads(self.status.read_text())["state"], "live_and_migrated")

    def test_failed_migrate_keeps_pending_and_reports(self):
        b.write_prepared(SHA, NOW, self.state)
        fake = Fake(helper=self.good, live="platform-" + SHA[:12], code=1, out="boom")
        with self.assertRaisesRegex(ValueError, "BLOCKED_MIGRATE_FAILED"):
            self.go(fake)
        self.assertTrue(b.read_prepared(self.state)["migrate_pending"])
        self.assertEqual(json.loads(self.status.read_text())["state"], "migrate_failed")

    def test_tampered_helper_never_runs_for_migrate(self):
        b.write_prepared(SHA, NOW, self.state)
        fake = Fake(helper=b"TAMPERED", live="platform-" + SHA[:12])
        with self.assertRaisesRegex(ValueError, "BLOCKED_HELPER_HASH_MISMATCH"):
            self.go(fake)
        self.assertEqual(fake.runs, [])

    def test_corrupt_prepared_state_is_ignored(self):
        (self.state / "prepared.json").write_text('{"approved_sha":"zz","prepared_at_unix":1,"migrate_pending":true}')
        self.assertEqual(self.go(Fake(helper=self.good)), "NO_POST_ACTIVATION_DUE")


class StaticBoundaryTests(unittest.TestCase):
    SRC = (HERE / "elite_release_prepare_broker.py").read_text(encoding="utf-8")
    UNIT = (HERE.parents[1] / "infra/server/systemd/kmj-elite-release-prepare-broker.service").read_text()
    TIMER = (HERE.parents[1] / "infra/server/systemd/kmj-elite-release-prepare-broker.timer").read_text()

    def test_no_shell_no_activation_no_eval(self):
        body = self.SRC.split('"""', 2)[2]
        for forbidden in ("shell=True", "os.system", "eval(", "exec(", "production_activate",
                          "systemctl", "approval.py", "--attest"):
            self.assertNotIn(forbidden, body)
        self.assertIn('"--prepare-only"', body)
        self.assertIn('"--post-activation"', body)
        self.assertEqual(body.count("subprocess.run("), 2)

    def test_helper_modes_are_fixed_literals_never_from_the_intent(self):
        self.assertIn('["--prepare-only", sha]', self.SRC)
        self.assertIn('["--post-activation", sha]', self.SRC)
        self.assertNotIn("intent[\"args\"]", self.SRC)

    def test_units_are_fixed_and_hardened(self):
        self.assertIn("ExecStart=/usr/bin/python3 -I -B /opt/kmj-main-platform-release-evidence/"
                      "elite_release_prepare_broker.py --execute", self.UNIT)
        self.assertIn("User=root", self.UNIT)
        self.assertIn("NoNewPrivileges=true", self.UNIT)
        self.assertIn("StateDirectoryMode=0700", self.UNIT)
        self.assertNotIn("[Install]", self.UNIT)
        self.assertIn("OnUnitInactiveSec=20s", self.TIMER)
        self.assertIn("Unit=kmj-elite-release-prepare-broker.service", self.TIMER)


if __name__ == "__main__":
    unittest.main()
