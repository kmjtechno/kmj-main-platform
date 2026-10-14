#!/usr/bin/env python3
"""Offline tests; zero Cloudflare network calls and no real secrets."""
import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path
from unittest import TestCase, main, mock

PATH = Path(__file__).with_name("kmj-mail-cloudflare-dkim.py")
spec = importlib.util.spec_from_file_location("kmj_mail_cf", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
VALUE = "v=DKIM1; k=rsa; p=TEST_PUBLIC_ONLY"
RECORD = "kmj2026._domainkey.kmjtechno.com"


class CloudflareDkimTests(TestCase):
    def execute(self, existing, new_result=None):
        responses = [[{"id": "zone123", "name": "kmjtechno.com"}], existing]
        if new_result is not None:
            responses.append(new_result)
        with mock.patch.object(module.os, "geteuid", return_value=0), \
            mock.patch.object(module, "public_record", return_value=VALUE), \
            mock.patch.object(module, "require_private_file"), \
            mock.patch.object(module.TOKENFILE.__class__, "read_text", return_value="private-test-token-not-real-123456"), \
            mock.patch.object(module, "request", side_effect=responses) as call, \
            mock.patch("sys.argv", ["publisher", "--apply"]), \
            redirect_stdout(io.StringIO()) as output:
            module.main()
            return output.getvalue(), call.call_args_list

    def test_already_published_is_idempotent(self):
        output, calls = self.execute([{"type": "TXT", "name": RECORD, "content": VALUE}])
        self.assertIn("PASS_ALREADY_PUBLISHED", output)
        self.assertEqual([c.args[0] for c in calls], ["GET", "GET"])

    def test_never_overwrites_conflicting_selector(self):
        with self.assertRaises(SystemExit):
            self.execute([{"type": "TXT", "name": RECORD, "content": "v=DKIM1; p=DIFFERENT"}])

    def test_new_record_creates_only_dkim_txt(self):
        output, calls = self.execute([], {"name": RECORD, "type": "TXT"})
        self.assertIn("PASS_PUBLISHED_PUBLIC_KEY", output)
        self.assertEqual([c.args[0] for c in calls], ["GET", "GET", "POST"])
        self.assertEqual(calls[2].args[3], {"type": "TXT", "name": RECORD, "content": VALUE, "ttl": 1})

    def test_no_apply_makes_no_api_calls(self):
        with mock.patch.object(module.os, "geteuid", return_value=0), \
            mock.patch.object(module, "public_record", return_value=VALUE), \
            mock.patch.object(module, "request") as called, \
            mock.patch("sys.argv", ["publisher"]), redirect_stdout(io.StringIO()) as output:
            module.main()
            called.assert_not_called()
            self.assertIn("CLOUDFLARE_WRITE=NOT_REQUESTED", output.getvalue())


if __name__ == "__main__":
    main()
