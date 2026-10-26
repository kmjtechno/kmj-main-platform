"""Negative controls for the Secure AI Coding release gate."""
import unittest

from scripts.security_release_gate import (
    is_private_path,
    scan_source_text,
    validate_production_env,
)


class SecurityReleaseGateTest(unittest.TestCase):
    def test_private_configs_blocked_but_public_examples_allowed(self):
        for item in [".env", "apps/platform/.env.production", "secrets/id_rsa",
                     "etc/cert.p12", "dev/agent.json"]:
            with self.subTest(item=item):
                self.assertTrue(is_private_path(item))
        self.assertFalse(is_private_path("apps/platform/.env.example"))
        self.assertFalse(is_private_path("apps/platform/.env.production.example"))

    def test_secret_detection_does_not_print_the_secret(self):
        token = "ghp_" + "A" * 40
        matches = scan_source_text("TOKEN=" + token, "sample.py")
        self.assertEqual(len(matches), 1)
        self.assertIn("GitHub token", matches[0])
        self.assertNotIn(token, matches[0])

    def test_safe_source_is_accepted(self):
        self.assertEqual([], scan_source_text(
            "const header = \"Bearer \" + token;\nAPP_DEBUG=false",
            "safe.js",
        ))

    def test_production_values_fail_closed_without_leaking(self):
        good = ("APP_ENV=production\nAPP_DEBUG=false\n"
                "APP_URL=https://kmjtechno.com\nSESSION_SECURE_COOKIE=true\n")
        self.assertEqual([], validate_production_env(good))
        findings = validate_production_env(
            "APP_ENV=local\nAPP_DEBUG=true\nAPP_URL=http://localhost\n"
        )
        self.assertEqual(len(findings), 4)
        self.assertTrue(all("missing or insecure" in item for item in findings))


if __name__ == "__main__":
    unittest.main()
