"""No network, no Postfix, no secrets, no production changes."""
import hashlib
import hmac
import io
import unittest
from unittest.mock import Mock
import kmj_postfix_inbound_pilot as pilot

KEY = bytes(range(32))
RAW = b"From: sender@example.invalid\r\nSubject: Pilot\r\n\r\nHello\r\n"
ARGS = ["sender=sender@example.invalid", "recipient=" + pilot.RECIPIENT]


class DirectPilotTest(unittest.TestCase):
    def deliver(self, status=201, receipt=b'{"state":"quarantined"}', args=None,
                raw=RAW, key=KEY):
        sender = Mock(return_value=(status, receipt))
        code = pilot.deliver(ARGS if args is None else args, io.BytesIO(raw),
                             lambda: key, sender)
        return code, sender

    def test_exact_hmac_and_raw(self):
        code, receiver = self.deliver()
        self.assertEqual(code, pilot.OK)
        raw, headers = receiver.call_args.args
        self.assertEqual(raw, RAW)
        values = ["kmj-inbound-v1", headers["X-KMJ-Mail-Event"],
                  headers["X-KMJ-Mail-Timestamp"], pilot.RECIPIENT,
                  "sender@example.invalid", hashlib.sha256(RAW).hexdigest()]
        self.assertEqual(headers["X-KMJ-Mail-Signature"],
                         hmac.new(KEY, "\n".join(values).encode(), hashlib.sha256).hexdigest())

    def test_duplicate_only_exact_status(self):
        self.assertEqual(self.deliver(200, b'{"state":"duplicate"}')[0], pilot.OK)
        for status, receipt in [(200, b'{"state":"quarantined"}'),
                                (201, b'{"state":"duplicate"}'),
                                (201, b'{}'), (201, b'null'), (201, b'broken'),
                                (302, b'{"state":"duplicate"}'),
                                (429, b'{}'), (503, b'{}'),
                                (201, b'x' * (pilot.MAX_RECEIPT + 1))]:
            with self.subTest(status=status, receipt=receipt[:20]):
                self.assertEqual(self.deliver(status, receipt)[0], pilot.TEMPFAIL)

    def test_recipient_fail_closed(self):
        for args in [[], ["sender=x@y", "recipient=info@kmjtechno.com"],
                     ARGS + ["recipient=other@example.invalid"]]:
            code, receiver = self.deliver(args=args)
            self.assertEqual(code, pilot.TEMPFAIL)
            receiver.assert_not_called()

    def test_bounded_input_and_key(self):
        for raw in [b"", b"x" * (pilot.MAX_BYTES + 1)]:
            code, receiver = self.deliver(raw=raw)
            self.assertEqual(code, pilot.DATAERR)
            receiver.assert_not_called()
        code, receiver = self.deliver(key=b"short")
        self.assertEqual(code, pilot.TEMPFAIL)
        receiver.assert_not_called()

    def test_null_sender_and_no_header_injection(self):
        code, receiver = self.deliver(args=["sender=", ARGS[1]])
        self.assertEqual(code, pilot.OK)
        self.assertEqual(receiver.call_args.args[1]["X-KMJ-Mail-Envelope-From"], "")
        code, receiver = self.deliver(args=["sender=a@b\r\nX-Evil: 1", ARGS[1]])
        self.assertEqual(code, pilot.DATAERR)
        receiver.assert_not_called()

    def test_connection_failure_defers(self):
        receiver = Mock(side_effect=TimeoutError("private test"))
        self.assertEqual(pilot.deliver(ARGS, io.BytesIO(RAW), lambda: KEY, receiver),
                         pilot.TEMPFAIL)


if __name__ == "__main__":
    unittest.main()
