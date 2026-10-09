"""Offline regressions for read-only staging DNS/TLS isolation preflight."""
import importlib.util
import pathlib
import ssl
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / "ops/staging/preflight_origin.py"
spec = importlib.util.spec_from_file_location("staging_origin_preflight", PATH)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class StageOriginPreflightTests(unittest.TestCase):
    def test_fails_closed_when_staging_points_to_production(self):
        hosts = {preflight.STAGING: {"151.243.146.95"}, preflight.PRODUCTION: {"151.243.146.95"}}
        report = preflight.inspect(resolver=hosts.__getitem__, probe=lambda _: None)
        self.assertEqual(report["result"], "FAIL")
        self.assertIn("STAGING_SHARES_PRODUCTION_IP", report["issues"])

    def test_fails_closed_on_invalid_certificate(self):
        hosts = {preflight.STAGING: {"203.0.113.10"}, preflight.PRODUCTION: {"151.243.146.95"}}
        def fail_certificate(_):
            raise ssl.SSLCertVerificationError("hostname mismatch")
        report = preflight.inspect(resolver=hosts.__getitem__, probe=fail_certificate)
        self.assertEqual(report["issues"], ["STAGING_TLS_NOT_VERIFIED"])

    def test_fails_closed_when_dns_unavailable(self):
        def fail_dns(_):
            raise socket_error()
        report = preflight.inspect(resolver=fail_dns, probe=lambda _: None)
        self.assertIn("DNS_LOOKUP_FAILED", report["issues"])

    def test_success_requires_distinct_dns_and_trusted_tls(self):
        hosts = {preflight.STAGING: {"203.0.113.10"}, preflight.PRODUCTION: {"151.243.146.95"}}
        visited = []
        report = preflight.inspect(resolver=hosts.__getitem__, probe=visited.append)
        self.assertEqual(report["result"], "PASS")
        self.assertEqual(report["issues"], [])
        self.assertEqual(visited, [preflight.STAGING])
        self.assertIn("not_application_or_database_isolation", report["scope"])


def socket_error():
    return OSError("resolver failed")


if __name__ == "__main__":
    unittest.main()
