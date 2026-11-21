#!/usr/bin/env python3
"""Offline privacy and boundary tests for KMJ Postfix queue snapshot."""
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import unittest

SRC = pathlib.Path(__file__).with_name("kmj_postfix_queue_snapshot_20261121.py")
spec = importlib.util.spec_from_file_location("kmj_mail_queue", SRC)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NOW = 1800000000.0

def event(queue="deferred", hours=1, reasons=(), extra=None):
    d = {
        "queue_id": "ABCDEFabcdef",
        "sender": "customer-private@example.test",
        "queue_name": queue,
        "arrival_time": NOW - hours * 3600,
        "recipients": [
            {"address": "secret-customer@example.test", "delay_reason": r}
            for r in reasons
        ],
    }
    d.update(extra or {})
    return json.dumps(d) + "\n"

class QueueContract(unittest.TestCase):
    def snap(self, *lines):
        return module.snapshot(io.StringIO("".join(lines)), now=NOW)

    def test_empty_queue_is_drained_but_not_delivered(self):
        s = self.snap()
        self.assertEqual(s["queue_messages"], 0)
        self.assertTrue(s["queue_drained"])
        self.assertFalse(s["recipient_delivery_proven"])
        self.assertEqual(s["queue_mutation"], "NONE")

    def test_multiple_messages_and_recipients(self):
        s = self.snap(
            event(reasons=("525 5.7.1 unauthorized IP", "535 authentication failed")),
            event("active", 25, ("connect timed out",)),
        )
        self.assertEqual(s["queue_messages"], 2)
        self.assertEqual(s["queue_recipients"], 3)
        self.assertEqual(s["queue_states"], {"active": 1, "deferred": 1})
        self.assertEqual(
            s["last_recorded_delay_categories"],
            {"SMTP_525": 1, "SMTP_535": 1, "TIMEOUT": 1},
        )

    def test_lifetime_buckets_and_unknown_age(self):
        a = self.snap(
            event(hours=120), event(hours=119), event(hours=96),
            event(hours=24), event(hours=0),
            event(extra={"arrival_time": "garbled"}),
        )
        self.assertEqual(
            a["age_buckets"],
            {"AT_OR_OVER_120H": 1, "96_TO_UNDER_120H": 2,
             "24_TO_UNDER_96H": 1, "UNDER_24H": 1},
        )
        self.assertEqual(a["unknown_age_messages"], 1)
        self.assertEqual(a["oldest_message_hours"], 120.0)

    def test_future_timestamp_unknown_not_falsely_fresh(self):
        a = self.snap(event(extra={"arrival_time": NOW + 1000}))
        self.assertEqual(a["future_arrival_messages"], 1)
        self.assertEqual(a["unknown_age_messages"], 1)
        self.assertEqual(a["age_buckets"], {})

    def test_invalid_json_or_schema_fails_closed(self):
        for value in (
            "{bad-json}\n", "[]\n",
            event(extra={"recipients": "not-a-list"}),
            event(extra={"recipients": ["not-dict"]}),
        ):
            with self.subTest(value=value[:20]):
                with self.assertRaises(ValueError):
                    self.snap(value)

    def test_never_leaks_addresses_queue_ids_or_raw_errors(self):
        a = self.snap(event(reasons=(
            "525 5.7.1 alert for secret-customer@example.test queue ABCDEFabcdef",
        )))
        s = json.dumps(a)
        for phrase in (
            "secret-customer", "customer-private", "ABCDEFabcdef", "alert for",
        ):
            self.assertNotIn(phrase, s)

    def test_max_line_fails_closed(self):
        with self.assertRaises(ValueError):
            self.snap("x" * (module.MAX_LINE_BYTES + 1))

    def test_cli_zero_queue_valid_and_no_email_send(self):
        p = subprocess.run(
            [sys.executable, str(SRC)], input="", text=True, capture_output=True
        )
        self.assertEqual(p.returncode, 0)
        self.assertTrue(json.loads(p.stdout)["queue_drained"])
        script = SRC.read_text()
        for forbidden in (
            "subprocess.", "postsuper", "postqueue -f", "sendmail(",
            "smtplib", "requests.", "os.system",
        ):
            self.assertNotIn(forbidden, script)

if __name__ == "__main__":
    unittest.main()
