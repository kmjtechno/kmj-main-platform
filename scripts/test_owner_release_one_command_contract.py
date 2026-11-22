"""Hardware-free contract for the one-command owner release helper."""
from pathlib import Path
import re
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parent / "operations" / "owner-release-main-platform.sh"
SOURCE = SCRIPT.read_text(encoding="utf-8")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


class OwnerReleaseOneCommandContract(unittest.TestCase):
    def call(self, *args: str):
        return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, timeout=8)

    def test_requires_exact_sha_before_any_filesystem_or_network_action(self):
        for arguments in [(), ("a" * 39,), ("not-a-sha",), ("a" * 41,), ("a" * 40, "extra")]:
            result = self.call(*arguments)
            self.assertEqual(result.returncode, 2)
            self.assertIn("KMJ_OWNER_RELEASE=BLOCKED_EXACT_SHA_REQUIRED", result.stdout)

    def test_wrong_host_refuses_with_a_valid_sha(self):
        result = self.call("a" * 40)
        self.assertEqual(result.returncode, 2)
        self.assertIn("KMJ_OWNER_RELEASE=BLOCKED_WRONG_HOST", result.stdout)

    def test_every_downloaded_helper_is_hash_pinned_and_checked_before_use(self):
        pins = re.findall(r"^(?:PIN_[A-Z]+|APPROVAL_SHA256)=([a-f0-9]+)$", SOURCE, re.M)
        self.assertEqual(len(pins), 5)
        for pin in pins:
            self.assertRegex(pin, SHA256)
        self.assertEqual(SOURCE.count('get "'), 5)
        self.assertIn("sha256sum -c -", SOURCE)
        self.assertLess(SOURCE.index('get "$APPROVAL_URL"'), SOURCE.index('bash stage.sh "$SHA"'))

    def test_it_never_activates_production_or_pipes_the_network_into_a_shell(self):
        self.assertNotRegex(SOURCE, r"curl[^\n]*\|\s*(ba)?sh")
        self.assertNotIn("production_activate", SOURCE)
        self.assertNotIn("systemctl start", SOURCE)
        self.assertNotIn("rm -rf /", SOURCE)
        self.assertIn("set -Eeuo pipefail", SOURCE)
        self.assertIn("ALREADY_LIVE", SOURCE)

    def test_live_release_is_derived_and_validated_not_typed(self):
        self.assertIn('readlink -f "$ROOT/current"', SOURCE)
        self.assertIn("^platform-[a-f0-9]{12}$", SOURCE)


if __name__ == "__main__":
    unittest.main()
