#!/usr/bin/env python3
"""No-host-mutation regression suite for the owner release activation broker."""
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
import uuid
from unittest.mock import patch

SOURCE = Path(__file__).parent / "operations" / "elite_owner_activation_broker.py"
spec = importlib.util.spec_from_file_location("elite_owner_activation_broker", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SHA = "a" * 40
PREDECESSOR = "platform-" + "b" * 12
NOW = 1771000100


def intent(**overrides):
    d = {
        "schema": "kmj.elite.production-activation-intent.v1",
        "intent_id": str(uuid.UUID("12345678-1234-4234-9234-123456789abc")),
        "actor_user_id": 7,
        "action": "activate_existing_approved_release",
        "approved_sha": SHA,
        "expected_current_release": PREDECESSOR,
        "created_at_unix": NOW - 20,
        "expires_at_unix": NOW + 50,
    }
    d.update(overrides)
    return d


class FakeGate:
    APPROVAL = Path("/etc/fixed/approval")
    ADMISSION_DIR = Path("/etc/fixed")
    source_decision = "READY_APPROVED_RELEASE"
    source_current = PREDECESSOR
    source_remote = SHA
    source_candidate = SHA
    source_approval = {"approvedSha": SHA, "expectedCurrentRelease": PREDECESSOR}
    source_admission = {"standingOwnerAuthorization": True}

    def protected_json(self, path):
        return self.source_approval if path == self.APPROVAL else self.source_admission

    def live_release(self):
        return self.source_current

    def remote_sha(self):
        return self.source_remote

    def candidate_sha(self, sha):
        return self.source_candidate

    def decision(self, approval, admission, current, remote, candidate):
        return self.source_decision


class ActivationBrokerTests(unittest.TestCase):
    def test_valid_short_lived_exact_intent(self):
        self.assertEqual(mod.validate_intent(intent(), NOW)["approved_sha"], SHA)
        self.assertEqual(mod.strict_json(json.dumps(intent()).encode())["actor_user_id"], 7)

    def test_duplicate_fields_and_extra_fields_rejected(self):
        raw = json.dumps(intent())
        raw = raw.replace('"actor_user_id": 7', '"actor_user_id": 7, "actor_user_id": 8')
        with self.assertRaisesRegex(ValueError, "DUPLICATE_INTENT"):
            mod.strict_json(raw.encode())
        with self.assertRaisesRegex(ValueError, "INTENT_SCHEMA"):
            mod.strict_json(json.dumps(intent(shell="/bin/sh")).encode())

    def test_no_arbitrary_actions_or_wrong_schema(self):
        for bad in (
            {"action": "shell"},
            {"action": "change_dns"},
            {"action": "stage_and_activate"},
            {"schema": "kmj.elite.production-activation-intent.v2"},
        ):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "INTENT_ACTION"):
                    mod.validate_intent(intent(**bad), NOW)

    def test_exact_sha_and_live_predecessor_required(self):
        for bad in (
            {"approved_sha": "a" * 39},
            {"approved_sha": "A" * 40},
            {"approved_sha": SHA + "; rm -rf /"},
            {"expected_current_release": "platform-" + "a" * 12},
            {"expected_current_release": "platform-" + "b" * 11},
            {"expected_current_release": "platform-" + "B" * 12},
        ):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "RELEASE_IDENTITY"):
                    mod.validate_intent(intent(**bad), NOW)

    def test_boolean_zero_or_huge_actor_id_rejected(self):
        for value in (False, True, 0, -4, "7", 1.1, 999999999999999999):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "ACTOR_ID"):
                    mod.validate_intent(intent(actor_user_id=value), NOW)

    def test_only_canonical_v4_request_identity(self):
        for val in ("not-uuid", str(uuid.uuid1()), str(uuid.uuid4()).upper(), "", 9):
            with self.subTest(val=val):
                with self.assertRaisesRegex(ValueError, "INTENT_ID"):
                    mod.validate_intent(intent(intent_id=val), NOW)

    def test_missing_clock_or_expired_or_unbounded_intent_rejected(self):
        for bad in (
            {"created_at_unix": NOW - 121},
            {"created_at_unix": NOW + 6},
            {"expires_at_unix": NOW},
            {"expires_at_unix": NOW + 200},
            {"created_at_unix": "123"},
            {"created_at_unix": True},
            {"expires_at_unix": True},
        ):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "EXPIRED_OR_FUTURE"):
                    mod.validate_intent(intent(**bad), NOW)

    def test_missing_changed_root_approval_or_gate_cannot_start(self):
        for attr, bad in (
            ("source_decision", "BLOCKED_CANDIDATE_IDENTITY"),
            ("source_current", "platform-" + "c" * 12),
            ("source_remote", "c" * 40),
            ("source_candidate", "c" * 40),
            ("source_approval", {"approvedSha": "c" * 40,
                                 "expectedCurrentRelease": PREDECESSOR}),
        ):
            with self.subTest(attr=attr):
                gate = FakeGate()
                setattr(gate, attr, bad)
                with self.assertRaisesRegex(ValueError, "PROTECTED_GATE"):
                    mod.protected_activation_match(intent(), gate)

    def test_exact_protected_gate_is_required_not_merely_browser_request(self):
        self.assertEqual(
            mod.protected_activation_match(intent(), FakeGate()),
            "READY_APPROVED_RELEASE",
        )

    def test_read_untrusted_symlink_and_writable_file_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "intent.json"
            p.write_text(json.dumps(intent()))
            p.chmod(0o640)
            p.parent.chmod(0o777)
            with patch.object(mod, "INTENT", p):
                # A tmp directory is not the owner-controlled fixed inbox.
                with self.assertRaisesRegex(ValueError, "INTENT_PARENT"):
                    mod.read_owner_intent(p, p.stat().st_uid, NOW)
            p.chmod(0o666)
            with self.assertRaisesRegex(ValueError, "INTENT_PARENT"):
                mod.read_owner_intent(p, p.stat().st_uid + 1, NOW)

    def test_root_state_directory_cannot_be_world_writable(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            p.chmod(0o777)
            with patch.object(mod, "STATE_DIR", p):
                with self.assertRaisesRegex(ValueError, "ROOT_STATE_DIR"):
                    mod.check_root_state_dir()

    def test_request_without_root_or_wrong_host_never_triggers(self):
        with patch.object(mod.os, "geteuid", return_value=1000), patch.object(
            mod, "trigger_fixed_unit", side_effect=AssertionError("MUTATION")
        ):
            self.assertEqual(mod.run(execute=True, now=NOW), 2)
        with patch.object(mod.os, "geteuid", return_value=0), patch.object(
            mod.socket, "gethostname", return_value="google-vps1"
        ), patch.object(mod, "trigger_fixed_unit", side_effect=AssertionError("MUTATION")):
            self.assertEqual(mod.run(execute=True, now=NOW), 2)

    def test_inspect_does_not_claim_or_start_and_execute_claims_before_trigger(self):
        events = []
        with patch.object(mod.os, "geteuid", return_value=0), patch.object(
            mod.socket, "gethostname", return_value="KMJ-elite"
        ), patch.object(mod.pwd, "getpwnam") as person, patch.object(
            mod, "read_owner_intent", return_value=intent()
        ), patch.object(mod, "check_root_state_dir"), patch.object(
            mod.Path, "exists", return_value=False
        ), patch.object(mod.Path, "is_symlink", return_value=False), patch.object(
            mod, "trusted_gate", return_value=FakeGate()
        ), patch.object(mod, "fixed_unit_status", return_value=True), patch.object(
            mod, "claim_once", side_effect=lambda *_: events.append("CLAIM")
        ), patch.object(
            mod, "trigger_fixed_unit", side_effect=lambda: events.append("START") or True
        ):
            person.return_value.pw_uid = 1001
            self.assertEqual(mod.run(execute=False, now=NOW), 0)
            self.assertEqual(events, [])
            self.assertEqual(mod.run(execute=True, now=NOW), 0)
            self.assertEqual(events, ["CLAIM", "START"])

    def test_expired_intent_is_retired_only_on_execute_without_deploy(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "intent.json"
            p.write_text(json.dumps(intent(created_at_unix=NOW - 110, expires_at_unix=NOW)))
            p.chmod(0o640)
            uid = p.stat().st_uid
            with patch.object(mod, "INTENT", p), patch.object(mod.os, "geteuid", return_value=0), \
                    patch.object(mod.socket, "gethostname", return_value="KMJ-elite"), \
                    patch.object(mod.pwd, "getpwnam") as person, \
                    patch.object(mod, "trigger_fixed_unit") as trigger, \
                    patch.object(mod, "claim_once") as claim:
                person.return_value.pw_uid = uid
                self.assertEqual(mod.run(execute=False, now=NOW), 2)
                self.assertTrue(p.exists())
                self.assertEqual(mod.run(execute=True, now=NOW), 0)
                self.assertFalse(p.exists())
                trigger.assert_not_called()
                claim.assert_not_called()

    def test_cleanup_does_not_remove_fresh_future_malformed_or_linked_intents(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "intent.json"
            for obj in (intent(), intent(created_at_unix=NOW + 50, expires_at_unix=NOW + 100)):
                p.write_text(json.dumps(obj))
                p.chmod(0o640)
                self.assertFalse(mod.retire_expired_intent(p, p.stat().st_uid, NOW))
                self.assertTrue(p.exists())
            p.write_text(json.dumps(intent(created_at_unix=NOW - 200, expires_at_unix=NOW - 1)))
            with self.assertRaisesRegex(ValueError, "EXPIRED_OR_FUTURE"):
                mod.retire_expired_intent(p, p.stat().st_uid, NOW)
            self.assertTrue(p.exists())
            p.write_text(json.dumps(intent(created_at_unix=NOW - 110, expires_at_unix=NOW)))
            other = Path(temp) / "other.json"
            other.hardlink_to(p)
            with self.assertRaisesRegex(ValueError, "INTENT_IDENTITY"):
                mod.retire_expired_intent(p, p.stat().st_uid, NOW)
            p.unlink()
            p.symlink_to(other)
            with self.assertRaises(OSError):
                mod.retire_expired_intent(p, other.stat().st_uid, NOW)
            self.assertTrue(p.is_symlink())
            self.assertTrue(other.exists())

    def test_intent_expiring_during_preflight_cannot_be_claimed_or_started(self):
        with patch.object(mod.os, "geteuid", return_value=0), \
                patch.object(mod.socket, "gethostname", return_value="KMJ-elite"), \
                patch.object(mod.pwd, "getpwnam"), \
                patch.object(mod, "read_owner_intent", side_effect=[
                    intent(), ValueError("BLOCKED_INTENT_EXPIRED_OR_FUTURE")]), \
                patch.object(mod, "previously_claimed", return_value=False), \
                patch.object(mod, "trusted_gate", return_value=FakeGate()), \
                patch.object(mod, "fixed_unit_status", return_value=True), \
                patch.object(mod, "claim_once") as claim, \
                patch.object(mod, "trigger_fixed_unit") as trigger:
            self.assertEqual(mod.run(execute=True, now=NOW), 2)
            claim.assert_not_called()
            trigger.assert_not_called()

    def test_immutable_fixed_unit_and_no_bypass_paths(self):
        text = SOURCE.read_text()
        self.assertEqual(mod.UNIT, "kmj-main-platform-production-release.service")
        self.assertNotIn("shell=True", text)
        self.assertNotIn("StrictHostKeyChecking=no", text)
        self.assertNotIn("subprocess.Popen", text)
        self.assertNotIn("systemctl enable", text)
        self.assertNotIn("git reset", text)
        self.assertNotIn("os.unlink(INTENT)", text)
        self.assertIn("O_NOFOLLOW", text)
        self.assertIn("O_EXCL", text)
        self.assertIn("BLOCKED_PROTECTED_GATE_", text)


if __name__ == "__main__":
    unittest.main()
