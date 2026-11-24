"""Fixture-only tests for the V3 local-only mode (--run-once-local).

Owner decision 2026-11-24: the Google VPS is not a dependency. The local-only
mode must (a) never contact Google/SFTP (no DNS lookup, no transfer, no host
key), (b) commit the vault cipher pair and then the daily snapshot in order,
(c) never claim a remote readback, and (d) report the failing phase and reason
instead of hiding it. No root, systemd, network or real backup data is used.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest import mock

SRC = Path(__file__).with_name("KMJ_OFFSITE_V3_DUAL_LOCAL_HEALTH_ONEPASS_20261117.py")
spec = importlib.util.spec_from_file_location("kmj_v3_health_onepass_local", SRC)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

SHA = "a" * 64


class FakeTx:
    def __init__(self, fail_pair=False, fail_daily=False):
        self.calls = []
        tx = self

        class Pair:
            def publish_after_verified_remote_readback(self, vault, path, stamp, sha, nbytes, expected_uid=0):
                tx.calls.append("pair")
                if fail_pair:
                    raise OSError("boom")
                return {"sidecar_pair_verified": True}

        class Daily:
            def publish_after_separately_verified_remote_readback(self, stage, daily, stamp, sha, expected_uid=0, allowed_uids=None):
                tx.calls.append("daily")
                if fail_daily:
                    raise OSError("EXDEV")
                return {"daily_snapshot_published": True, "platform_dump_sha256": "b" * 64}

        self.pair = Pair()
        self.daily = Daily()

    def _fresh_source_and_daily_preflight(self, vault, cipher, stage, daily, stamp, uid):
        self.calls.append("preflight")
        return Path("/x/fresh.age"), SHA, 10, "b" * 64

    # Any attempt to use the remote path must fail the test.
    def commit_after_same_invocation_v2_readback(self, **kw):
        raise AssertionError("remote commit must not be used in local-only mode")


def commit(tx, probe=lambda: "rel"):
    return h.commit_local_only(tx, probe=probe, expected_release="rel", vault="/v",
                               fresh_cipher="/c", stage_root="/s", daily_root="/d",
                               stamp="20261124T000000Z")


class LocalOnly(unittest.TestCase):
    def test_order_and_no_remote_claim(self):
        tx = FakeTx()
        r = commit(tx)
        self.assertEqual(tx.calls, ["preflight", "pair", "daily"])
        self.assertFalse(r["remote_sha_readback_same_invocation"])
        self.assertTrue(r["local_complete"])
        self.assertFalse(r["independent_remote_decrypt_restore_verified"])

    def test_pair_failure_reports_phase_and_reason(self):
        with self.assertRaises(h.LocalIncomplete) as c:
            commit(FakeTx(fail_pair=True))
        self.assertEqual(c.exception.phase, "LOCAL_NOT_COMMITTED")
        self.assertEqual(c.exception.reason, "OSError")

    def test_daily_failure_reports_phase(self):
        tx = FakeTx(fail_daily=True)
        with self.assertRaises(h.LocalIncomplete) as c:
            commit(tx)
        self.assertEqual(c.exception.phase, "CIPHER_PAIR_COMMITTED")
        self.assertEqual(str(c.exception), "INCOMPLETE_CIPHER_PAIR_COMMITTED")

    def test_release_change_blocks_before_any_write(self):
        tx = FakeTx()
        with self.assertRaises(h.Deny):
            commit(tx, probe=lambda: "other")
        self.assertEqual(tx.calls, [])

    def test_local_inspect_never_contacts_google(self):
        class T:
            VAULT = Path("/")
            def prop(self, *_a):
                raise AssertionError
            def dns_address(self):
                raise AssertionError("DNS must not be used")
            def pinned_conf(self):
                raise AssertionError("SFTP config must not be read")
            def host_key(self):
                raise AssertionError("host key must not be fetched")
        v3 = mock.Mock()
        v3.live_app.return_value = ("u", "rel", "app", "storage")
        v3.native_pg_restore_candidates.return_value = [(18, "pg")]
        v3.run.return_value = mock.Mock(returncode=0, stdout=b"pg_dump (PostgreSQL) 16.15\n")
        with mock.patch.object(h.os, "statvfs", return_value=mock.Mock(f_bavail=10**9, f_frsize=4096)):
            out = h.local_inspect(v3, T())
        self.assertEqual(out, ("u", "rel", "app", "storage"))
        v3.schedule_unit_preflight.assert_called_once()

    def test_receipt_gate_accepts_local_only_receipt(self):
        r = commit(FakeTx())
        self.assertTrue(h.receipt_verified(r, True))
        self.assertFalse(h.receipt_verified(r, False))  # no remote readback => not valid for Google mode

    def test_receipt_gate_google_mode_unchanged(self):
        google = {"remote_sha_readback_same_invocation": True, "local_cipher_sidecar_verified": True,
                  "local_daily_snapshot_verified": True, "local_complete": True}
        self.assertTrue(h.receipt_verified(google, False))
        self.assertFalse(h.receipt_verified(google, True))  # local-only must never accept a remote claim
        for k in ("local_cipher_sidecar_verified", "local_daily_snapshot_verified", "local_complete"):
            bad = dict(google, **{k: False})
            self.assertFalse(h.receipt_verified(bad, False), k)

    def test_new_mode_is_accepted_and_old_modes_kept(self):
        for mode in ("--run-once", "--run-once-local", "--preflight", "--audit-pins", "--selftest"):
            with mock.patch.object(h.sys, "argv", ["x", mode]), \
                 mock.patch.object(h, "selftest", return_value=0), \
                 mock.patch.object(h, "root_owner", side_effect=RuntimeError), \
                 mock.patch("builtins.print") as pr:
                rc = h.main()
            printed = " ".join(str(a) for c in pr.call_args_list for a in c.args)
            self.assertNotIn("BLOCKED_ARGS", printed, mode)
        with mock.patch.object(h.sys, "argv", ["x", "--bogus"]), mock.patch("builtins.print"):
            self.assertEqual(h.main(), 2)

    def test_blocker_includes_reason(self):
        err = h.LocalIncomplete("CIPHER_PAIR_COMMITTED", "OSError")
        with mock.patch.object(h.sys, "argv", ["x", "--run-once-local"]), \
             mock.patch.object(h, "root_owner"), \
             mock.patch.object(h, "run_once", side_effect=err), \
             mock.patch("builtins.print") as pr:
            self.assertEqual(h.main(), 3)
        printed = [c.args[0] for c in pr.call_args_list]
        self.assertIn("BLOCKER=INCOMPLETE_CIPHER_PAIR_COMMITTED_OSERROR", printed)


if __name__ == "__main__":
    unittest.main()
