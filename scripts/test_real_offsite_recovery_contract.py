from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRILL = ROOT / "scripts" / "operations" / "verify-real-offsite-recovery.sh"


class RealOffsiteRestoreDrillContract(unittest.TestCase):
    def test_shell_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(DRILL)], check=True)

    def test_missing_operator_ack_fails_closed_without_network(self) -> None:
        env = os.environ.copy()
        for key in ("KMJ_ACK_ISOLATED_RECOVERY", "BACKUP_REMOTE_OBJECT", "BACKUP_AGE_IDENTITY"):
            env.pop(key, None)
        result = subprocess.run(
            ["bash", str(DRILL)], env=env, text=True,
            capture_output=True, check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("BLOCKED", result.stdout)
        self.assertNotIn("OFFSITE_RETRIEVAL=PASS", result.stdout)

    def test_disposable_restore_and_release_evidence_boundaries(self) -> None:
        source = DRILL.read_text(encoding="utf-8")
        for required in (
            "UNPRIVILEGED_OPERATOR",
            "INDEPENDENT_HOST_REQUIRED",
            "KMJ_ACK_ISOLATED_RECOVERY",
            "rclone copyto",
            "verify_backup_bundle.sh",
            "--auth-host=reject",
            "listen_addresses=''",
            "unix_socket_permissions=0700",
            "pg_restore",
            "to_regclass('public.users')",
            "RECOVERED_APP_FUNCTIONAL_QA NOT_VERIFIED",
            "MATCHING_PRODUCTION_APPROVAL NOT_VERIFIED",
            "SAFE_TO_ACTIVATE_PRODUCTION NOT_PROVEN",
        ):
            self.assertIn(required, source)
        for prohibited in ("systemctl restart", "DROP DATABASE", "PRODUCTION_DATABASE_MODIFIED YES"):
            self.assertNotIn(prohibited, source)


if __name__ == "__main__":
    unittest.main()
