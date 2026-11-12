"""Zero-network negative/functional tests for KMJ exact-scope IP autopilot.

Never uses real Cloudflare credentials, DNS, root privileges, service control,
SMTP or production directories.
"""
import importlib.util
import ipaddress
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("kmj-origin-ip-autopilot-20261112.py")
SPEC = importlib.util.spec_from_file_location("kmj_origin_ip_autopilot", SOURCE)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
OLD = "150.242.200.81"
NEW = "150.242.200.82"


class ReconcilerTests(unittest.TestCase):
    def test_public_ipv4_rejects_private_reserved_and_noncanonical(self):
        for value in ("127.0.0.1", "10.0.0.1", "192.168.1.2",
                      "169.254.1.2", "2001:db8::1", "example.org",
                      "150.242.200.82\n", "0.0.0.0", "255.255.255.255"):
            with self.subTest(value=value), self.assertRaises(m.Block):
                m.public_ipv4(value)
        self.assertEqual(m.public_ipv4(NEW), NEW)

    def test_cloudflare_token_not_in_any_report(self):
        for value in ("A token with spaces", "A/B", "x" * 200):
            with self.subTest(value=value), self.assertRaises(m.Block):
                m.emit("X", value)

    def test_independent_egress_agreement_required(self):
        with patch.object(m, "url_text", side_effect=[NEW.encode(), (NEW + "\n").encode()]):
            self.assertEqual(m.detected_egress(), NEW)
        with patch.object(m, "url_text", side_effect=[OLD.encode(), NEW.encode()]):
            with self.assertRaisesRegex(m.Block, "EGRESS_IP_CONSENSUS_FAILED"):
                m.detected_egress()

    def test_exact_record_names_rejected_outside_allowlist(self):
        for name, typ in [("host.kmjtechno.com", "A"),
                          ("authsp.kmjtechno.com", "A"),
                          ("kmjtechno.com", "AAAA"),
                          ("mail.kmjtechno.com", "TXT")]:
            with self.subTest(name=name, typ=typ), self.assertRaises(m.Block):
                m.records("a"*32, "faketoken", name=name, record_type=typ)

    def test_spf_must_preserve_existing_reviewed_policy(self):
        good = f"v=spf1 ip4:{OLD} include:_spf.mx.cloudflare.net ~all"
        self.assertEqual(m.spf_ipv4(good), OLD)
        for raw in ("v=spf1 -all", "v=spf1 include:unknown ~all",
                    good + " ip4:1.2.3.4", good.replace("~all", "+all"),
                    good.replace(OLD, "127.0.0.1")):
            with self.assertRaises(m.Block):
                m.spf_ipv4(raw)

    def scenario(self, mode="ddns", olds=None, spf_ip=OLD):
        a = {name: {"id": f"{i+1:032x}", "name": name, "type": "A",
                    "content": (olds or {}).get(name, OLD), "proxied": False}
             for i, name in enumerate(m.EXPECTED_HOSTS)}
        spf = {"id": "f"*32, "name": m.ZONE_HOST, "type": "TXT",
               "content": f"v=spf1 ip4:{spf_ip} include:_spf.mx.cloudflare.net ~all"}
        edits = []
        def exact_a(zone, token, name):
            return a[name]
        def exact_spf(zone, token):
            return spf
        def patch_rec(zone, token, record, value):
            edits.append((record["name"], value))
            record["content"] = value
        return a, spf, edits, exact_a, exact_spf, patch_rec

    def test_exact_five_a_plus_spf_only_updated(self):
        a, spf, edits, exact_a, exact_spf, update = self.scenario()
        with patch.object(m, "exact_a", side_effect=exact_a), \
             patch.object(m, "exact_spf", side_effect=exact_spf), \
             patch.object(m, "patch_record", side_effect=update), \
             patch.object(m, "origin_https") as health:
            res = m.reconcile("a"*32, "ddns", "fake", NEW, apply=True)
        self.assertEqual([r[0] for r in edits], [*m.EXPECTED_HOSTS, m.ZONE_HOST])
        self.assertEqual(len(edits), 6)
        self.assertTrue(res["fully_converged"])
        health.assert_called_once_with(NEW, mode="ddns")
        self.assertEqual(spf["content"], f"v=spf1 ip4:{NEW} include:_spf.mx.cloudflare.net ~all")

    def test_inspect_never_mutates(self):
        _, _, edits, exact_a, exact_spf, update = self.scenario()
        with patch.object(m, "exact_a", side_effect=exact_a), \
             patch.object(m, "exact_spf", side_effect=exact_spf), \
             patch.object(m, "patch_record", side_effect=update), \
             patch.object(m, "origin_https") as health:
            res = m.reconcile("a"*32, "ddns", "fake", NEW, apply=False)
        self.assertEqual(res["a_records_to_change"], 5)
        self.assertEqual(edits, [])
        health.assert_not_called()

    def test_partial_prior_attempt_converges(self):
        _, _, edits, exact_a, exact_spf, update = self.scenario(
            olds={"kmjtechno.com": NEW, "www.kmjtechno.com": NEW})
        with patch.object(m, "exact_a", side_effect=exact_a), \
             patch.object(m, "exact_spf", side_effect=exact_spf), \
             patch.object(m, "patch_record", side_effect=update), \
             patch.object(m, "origin_https"):
            m.reconcile("a"*32, "ddns", "fake", NEW, apply=True)
        self.assertEqual(len(edits), 4)

    def test_multiple_unreviewed_origins_fail_without_mutation(self):
        a, spf, edits, exact_a, exact_spf, update = self.scenario(
            olds={"kmjtechno.com": "150.242.200.83",
                  "staging.kmjtechno.com": "150.242.200.84"})
        with patch.object(m, "exact_a", side_effect=exact_a), \
             patch.object(m, "exact_spf", side_effect=exact_spf), \
             patch.object(m, "patch_record", side_effect=update):
            with self.assertRaisesRegex(m.Block, "MIXED_OLD_A_RECORDS"):
                m.reconcile("a"*32, "ddns", "fake", NEW, apply=True)
        self.assertEqual(edits, [])

    def test_spf_mismatch_blocks_all_updates(self):
        _, _, edits, exact_a, _, update = self.scenario()
        with patch.object(m, "exact_a", side_effect=exact_a), \
             patch.object(m, "exact_spf", return_value={"content":
                 "v=spf1 ip4:150.242.200.93 include:_spf.mx.cloudflare.net ~all"}), \
             patch.object(m, "patch_record", side_effect=update):
            with self.assertRaisesRegex(m.Block, "SPF_IP_NOT_CONSISTENT_WITH_A"):
                m.reconcile("a"*32, "ddns", "fake", NEW, apply=True)
        self.assertEqual(edits, [])

    def test_mail_only_mode_never_changes_web_and_skips_web_probe(self):
        _, _, edits, exact_a, exact_spf, update = self.scenario()
        with patch.object(m, "exact_a", side_effect=exact_a), \
             patch.object(m, "exact_spf", side_effect=exact_spf), \
             patch.object(m, "patch_record", side_effect=update), \
             patch.object(m, "origin_https") as health:
            m.reconcile("a"*32, "mail_only", "fake", NEW, apply=True)
        self.assertEqual([x[0] for x in edits], [m.MAIL_HOST, m.ZONE_HOST])
        health.assert_called_once_with(NEW, mode="mail_only")

    def test_origin_health_failure_halts_updates(self):
        _, _, edits, exact_a, exact_spf, update = self.scenario()
        with patch.object(m, "exact_a", side_effect=exact_a), \
             patch.object(m, "exact_spf", side_effect=exact_spf), \
             patch.object(m, "patch_record", side_effect=update), \
             patch.object(m, "origin_https", side_effect=m.Block("ORIGIN_HTTPS_PREFLIGHT_FAILED")):
            with self.assertRaises(m.Block):
                m.reconcile("a"*32, "ddns", "fake", NEW, apply=True)
        self.assertEqual(edits, [])

    def test_idempotent_current_ip_no_record_writes(self):
        _, _, edits, exact_a, exact_spf, update = self.scenario(
            olds={name: NEW for name in m.EXPECTED_HOSTS}, spf_ip=NEW)
        with patch.object(m, "exact_a", side_effect=exact_a), \
             patch.object(m, "exact_spf", side_effect=exact_spf), \
             patch.object(m, "patch_record", side_effect=update):
            res = m.reconcile("a"*32, "ddns", "fake", NEW, apply=True)
        self.assertTrue(res["fully_converged"])
        self.assertEqual(edits, [])

    def test_https_sni_probe_never_executes_shell(self):
        with patch.object(m.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"200", b"")) as runner:
            m.origin_https(NEW, mode="ddns")
        self.assertEqual(runner.call_count, 3)
        for call in runner.call_args_list:
            self.assertEqual(call.args[0][0], "/usr/bin/curl")
            self.assertEqual(call.kwargs["stderr"], subprocess.DEVNULL)
            self.assertEqual(call.kwargs["stdin"], subprocess.DEVNULL)
            self.assertIn("--resolve", call.args[0])
            self.assertFalse(call.kwargs.get("shell", False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
