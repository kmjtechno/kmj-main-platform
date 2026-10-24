#!/usr/bin/env python3
"""Contract verification for the exact-SHA Google VPS SFTP-import restore drill."""
from __future__ import annotations
import os
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "operations/verify-codebridge-b1d672-google-sftp-restore-20261024.sh"
SOURCE = SCRIPT.read_text(encoding="utf-8")
SHA = "867311da52431737b24f9ba5f0a8ed7ff34136e86e08bda6c0c4be7ce9e43004"

class CodeBridgeGoogleSftpImportContract(unittest.TestCase):
    def test_bash_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_exact_import_and_private_identity(self):
        for marker in (
            "NONROOT_INFO_REQUIRED", "GOOGLE_RECOVERY_HOST_REQUIRED",
            "OPERATOR_CONSENT", "SFTP_IMPORT_MISSING", "SFTP_IMPORT_OWNER",
            "SFTP_IMPORT_MODE", "SFTP_IMPORT_DIGEST", "SFTP_IMPORT_COPY_DIGEST",
            SHA, "offsite-b1d672bbc83a.tar.gz.age",
            "google-vps-20261019.agekey",
            "AGE_IDENTITY_MODE", "SFTP_IMPORTED_ENCRYPTED_SHA256 PASS",
            "GOOGLE_VPS_INDEPENDENT_RESTORE PASS",
        ):
            self.assertIn(marker, SOURCE)

    def test_verified_archive_full_restore_with_no_network_listener(self):
        for marker in (
            "verify_backup_bundle.sh", "BACKUP_ARCHIVE_INTEGRITY PASS",
            "--auth-host=reject", "listen_addresses=''",
            "unix_socket_permissions=0700", "DISPOSABLE_POSTGRES_RESTORE PASS",
            "RECOVERED_APP_SCHEMA PASS", "RECOVERED_STORAGE PASS",
            "POSTGRES_NETWORK_LISTENER DISABLED",
            "PRODUCTION_DATABASE_MODIFIED NO",
        ):
            self.assertIn(marker, SOURCE)

    def test_exact_current_candidate_is_pinned(self):
        self.assertIn("RESTORE_CANDIDATE_SHA b1d672bbc83a51ca3f8271435692825072444c8e", SOURCE)
        self.assertNotIn("offsite-f4b6d3ff96b0.tar.gz.age", SOURCE)
        self.assertNotIn("b1e2cf4b417dc9337542e0bffd7273e70e04a9391a181bd084e8f27a76b24e34", SOURCE)

    def test_no_false_remote_claim_or_live_mutation(self):
        self.assertIn("OFFSITE_RCLONE_RETRIEVAL NOT_ATTEMPTED", SOURCE)
        self.assertIn("SAFE_TO_ACTIVATE_PRODUCTION NOT_PROVEN", SOURCE)
        self.assertIn("OFFSITE_REMOTE_ARCHIVE_RETENTION NOT_VERIFIED", SOURCE)
        for forbidden in (
            "rclone copy", "scp ", "ssh ", "PGPASSWORD=", "artisan migrate",
            "systemctl restart", "systemctl reload", "ALTER ROLE",
            "ln -sfn", "git reset", "/etc/kmj-codebridge/main-platform-production-release.json",
            "BACKUP_REMOTE_OBJECT", "/tmp/kmj-real-offsite",
        ):
            self.assertNotIn(forbidden, SOURCE)

    def test_fail_closed_before_any_data_access_when_wrong_host(self):
        # Runs in CI (not google-vps1), or if the operator confirms wrong host
        # then the script must fail before trying to read/transfer the snapshot.
        env = {**os.environ, "KMJ_ACK_ISOLATED_RECOVERY": "YES"}
        result = subprocess.run(["bash", str(SCRIPT)], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("BLOCKED", result.stdout)
        self.assertNotIn("DISPOSABLE_POSTGRES_RESTORE=PASS", result.stdout)

if __name__ == "__main__":
    unittest.main()
