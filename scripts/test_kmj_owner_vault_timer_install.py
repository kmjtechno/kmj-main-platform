"""Static contract tests for infra/server/KMJ_OWNER_VAULT_TIMER_INSTALL.sh (no root, no systemd)."""
from __future__ import annotations

import hashlib
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "infra/server/KMJ_OWNER_VAULT_TIMER_INSTALL.sh"
VAULT = ROOT / "scripts/kmj-owner-key-backup-vault.sh"


class OwnerVaultTimerInstallContract(unittest.TestCase):
    def setUp(self):
        self.text = INSTALL.read_text()

    def test_bash_syntax(self):
        subprocess.run(["bash", "-n", str(INSTALL)], check=True)

    def test_pinned_sha_matches_the_vault_script_in_this_commit(self):
        pinned = re.search(r"^SRC_SHA=([0-9a-f]{64})$", self.text, re.M).group(1)
        self.assertEqual(pinned, hashlib.sha256(VAULT.read_bytes()).hexdigest())

    def test_root_required_and_strict_mode(self):
        self.assertIn("set -Eeuo pipefail", self.text)
        self.assertIn('[[ "$(id -u)" == 0 ]] || die ROOT_REQUIRED', self.text)

    def test_service_is_hardened_and_scoped(self):
        for line in (
            "Type=oneshot", "NoNewPrivileges=yes", "PrivateTmp=yes", "ProtectSystem=strict",
            "ReadOnlyPaths=/var/backups/kmj-elite-daily /root/kmj-bootstrap",
            "ReadWritePaths=/var/backups/kmj-owner-vault",
        ):
            self.assertIn(line, self.text)

    def test_timer_is_persistent_and_hourly(self):
        self.assertIn("OnCalendar=hourly", self.text)
        self.assertIn("Persistent=true", self.text)

    def test_installer_never_deletes_backups_or_touches_v3(self):
        self.assertNotRegex(self.text, r"rm\s+-[a-zA-Z]*r")
        self.assertNotIn("kmj-elite-offsite-encrypted", self.text)
        self.assertNotIn("kmj-v3-dual-local-health", self.text)
        self.assertNotIn("offsite-age-recipients", self.text)

    def test_rolls_back_on_unit_verification_failure(self):
        self.assertIn("systemd-analyze verify", self.text)
        self.assertIn("rollback; die UNIT_VERIFY_FAILED", self.text)


if __name__ == "__main__":
    unittest.main()
