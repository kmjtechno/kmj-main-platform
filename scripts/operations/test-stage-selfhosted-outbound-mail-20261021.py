#!/usr/bin/env python3
"""Static-only assertions: never execute installer or connect to any mail server."""
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().with_name("stage-selfhosted-outbound-mail-20261021.sh")

class StageControls(unittest.TestCase):
    def test_actual_argument_guard_without_running_installer(self):
        source = SCRIPT.read_text()
        start = source.index('if [[ "${1:-}" != --stage ]]')
        end = source.index("\nfi", start) + len("\nfi")
        isolated_guard = "set -eu\n" + source[start:end]
        def check(*args):
            return subprocess.run(
                ["bash", "-c", isolated_guard, "stage-guard", *args],
                capture_output=True, text=True, timeout=5, check=False,
            )
        valid = check("--stage")
        self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
        for invalid in ((), ("stage",), ("--stage", "unexpected")):
            failed = check(*invalid)
            self.assertEqual(failed.returncode, 2, failed.stderr)
            self.assertIn("USAGE=bash script.sh --stage", failed.stdout)

    def test_bash_variables_expand_instead_of_literal_backslashes(self):
        source = SCRIPT.read_text()
        self.assertNotIn("\\${", source)
        self.assertIn('"${1:-}" != --stage', source)
        self.assertIn('"${ID:-}" == ubuntu', source)
        self.assertIn('"${VERSION_ID:-}" ==', source)

    def test_existing_directory_safety_without_running_installer(self):
        # Extract only the read-only filesystem guard, never execute apt or services.
        source = SCRIPT.read_text()
        start = source.index("check_preexisting_dkim_tree() {")
        end = source.index("\n}\ncheck_preexisting_dkim_tree /etc/opendkim", start) + 2
        guard = source[start:end]
        shell = 'set -euo pipefail\nfail() { echo "BLOCKED:$1"; exit 2; }\n' + guard + '\ncheck_preexisting_dkim_tree "$1"'

        def check(root):
            return subprocess.run(
                ["bash", "-c", shell, "guard", str(root)],
                capture_output=True, text=True, timeout=5, check=False,
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "opendkim"
            self.assertEqual(check(root).returncode, 0)  # entirely absent
            keydir = root / "keys" / "kmjtechno.com"
            keydir.mkdir(parents=True)
            self.assertEqual(check(root).returncode, 0)  # empty scaffolding allowed
            private = keydir / "kmjmail2026.private"
            private.write_text("private-material-placeholder")
            blocked = check(root)
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("EXISTING_DKIM_KEY_MATERIAL_DO_NOT_OVERWRITE", blocked.stdout)
            self.assertEqual(private.read_text(), "private-material-placeholder")
            private.unlink()

            unrelated = root / "TrustedHosts"
            unrelated.write_text("existing-config")
            self.assertEqual(check(root).returncode, 2)
            self.assertEqual(unrelated.read_text(), "existing-config")
            unrelated.unlink()

            other_keydir = root / "keys" / "another-domain"
            other_keydir.mkdir()
            self.assertEqual(check(root).returncode, 2)
            other_keydir.rmdir()

            keydir.rmdir()
            (root / "keys").rmdir()
            root.rmdir()
            root.symlink_to(Path(tmp), target_is_directory=True)
            self.assertIn("EXISTING_DKIM_SYMLINK", check(root).stdout)

    def test_directory_check_is_repeated_after_install(self):
        source = SCRIPT.read_text()
        self.assertEqual(source.count("check_preexisting_dkim_tree /etc/opendkim"), 2)
        self.assertLess(source.index("check_preexisting_dkim_tree /etc/opendkim"),
                        source.index("apt-get update -qq"))
        self.assertGreater(source.rindex("check_preexisting_dkim_tree /etc/opendkim"),
                           source.index("apt-get install -y -qq"))

    def test_abort_disables_services_and_success_checks_reboot_safety(self):
        source = SCRIPT.read_text()
        cleanup_start = source.index("cleanup() {")
        cleanup_end = source.index("\n}\ntrap cleanup EXIT", cleanup_start)
        cleanup = source[cleanup_start:cleanup_end]
        self.assertIn("systemctl stop postfix opendkim", cleanup)
        self.assertIn("systemctl disable postfix opendkim", cleanup)
        self.assertIn("MAIL_STAGE=INCOMPLETE_EXIT_", cleanup)
        self.assertIn('active=$(systemctl is-active "$service"', source)
        self.assertIn('enabled=$(systemctl is-enabled "$service"', source)
        self.assertIn("MAIL_SERVICE_STILL_ACTIVE", source)
        self.assertIn("MAIL_SERVICE_AUTOSTART_NOT_DISABLED", source)
        self.assertLess(source.index("MAIL_SERVICE_AUTOSTART_NOT_DISABLED"),
                        source.index("MAIL_STAGE=PASS"))

    def test_fail_closed_host_and_operator(self):
        s = SCRIPT.read_text()
        for required in [
            "hostname -s", "ROOT_REQUIRED", "OWNER_TTY_REQUIRED",
            "STAGE LOCAL MAIL", "EXISTING_MAIL_CONFIG_DO_NOT_OVERWRITE",
            "EXISTING_OPENDKIM_CONFIG_DO_NOT_OVERWRITE", "MAIL_A_RECORD_MISMATCH",
            "INSUFFICIENT_DISK", "NO_TEST_EMAIL_WILL_BE_SENT",
        ]:
            self.assertIn(required, s)

    def test_only_local_send_submission(self):
        s = SCRIPT.read_text()
        for required in [
            "inet_interfaces = loopback-only", "mydestination = localhost",
            "mynetworks = 127.0.0.0/8", "relayhost =",
            "milter_default_action = tempfail",
            "non_smtpd_milters = inet:127.0.0.1:8891",
            "SERVICES=STOPPED_DISABLED", "DKIM_PUBLIC_TXT_BEGIN",
        ]:
            self.assertIn(required, s)

    def test_bootstrap_does_not_require_uninstalled_postconf(self):
        s = SCRIPT.read_text()
        preinstall = s.split("apt-get install -y -qq", 1)[0]
        self.assertNotIn("for cmd in apt-get dpkg-query debconf-set-selections postconf", preinstall)
        self.assertIn("POSTCONF_NOT_INSTALLED", s)

    def test_preserves_production(self):
        s = SCRIPT.read_text()
        for prohibited in [
            "artisan migrate", "systemctl restart nginx",
            "/home/kmjprod/current", "cloudflare.request",
            "MAIL_MAILER=smtp", "/etc/nginx", "ufw allow",
            "chmod 777", "opendkim-genkey -b 1024",
        ]:
            self.assertNotIn(prohibited, s)

if __name__ == "__main__":
    unittest.main()
