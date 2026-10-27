"""Offline SHA-pinned Google recovery source contract; never touches live production."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parent
RESTORE=ROOT/"operations/verify-29a982-google-sftp-restore-20261027.sh"
VERIFY=ROOT/"operations/verify-29a982-backup-bundle-20261027.sh"

class GoogleRestoreContract(unittest.TestCase):
    def test_bash_parse(self):
        for path in (RESTORE,VERIFY):
            with self.subTest(path=path):
                subprocess.run(["bash","-n",str(path)],check=True,timeout=10)

    def test_exact_sha_and_strict_guard(self):
        s=RESTORE.read_text()
        for marker in (
            '[[ "$(id -u)" != 0 && "$(id -un)" == info ]]',
            '[[ "$(hostname -s)" == google-vps1 ]]',
            'KMJ_ACK_ISOLATED_RECOVERY',
            'expected_hash=973b593d7ea3f6f4d44ea7d832d76caf4cee0cd71817407a70f451c5071c4e3d',
            'offsite-29a98250b463.tar.gz.age',
            'google-vps-20261019.agekey',
            'SFTP_IMPORT_DIGEST',
            'SFTP_IMPORTED_ENCRYPTED_SHA256 PASS',
            'KMJ_P0_29A982_VERIFY_BACKUP_BUNDLE_20261027.sh',
            'RESTORE_CANDIDATE_SHA 29a98250b463998959fc52ac41b012aed1e76dba',
            'AGE_IDENTITY_OWNER',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker,s)
        self.assertNotIn('b1d672',s)

    def test_no_live_modification_and_disposable_database(self):
        s=RESTORE.read_text()
        for marker in ('--auth-host=reject',"listen_addresses=''","unix_socket_permissions=0700",
                        'pg_restore" --exit-on-error', 'POSTGRES_NETWORK_LISTENER DISABLED',
                        'GOOGLE_VPS_INDEPENDENT_RESTORE PASS', 'PRODUCTION_DATABASE_MODIFIED NO',
                        'SAFE_TO_ACTIVATE_PRODUCTION NOT_PROVEN',
                        'OFFSITE_REMOTE_ARCHIVE_RETENTION NOT_VERIFIED',
                        'RECOVERY_FREE_SPACE_12GIB'):
            with self.subTest(marker=marker):
                self.assertIn(marker,s)
        for bad in ('sudo ', 'systemctl restart', 'systemctl reload', 'ln -sfn',
                    'artisan migrate', '/home/kmjprod/current', 'git reset --hard',
                    'rm -rf /home'):
            with self.subTest(forbidden=bad):
                self.assertNotIn(bad,s)

    def test_bounded_backup_validator(self):
        s=VERIFY.read_text()
        for marker in ("BACKUP_AGE_IDENTITY", 'age -d', 'pg_restore',
                       "archive.getmembers()", "sha256sum", "BACKUP_ARCHIVE_INTEGRITY=PASS"):
            with self.subTest(marker=marker):
                self.assertIn(marker,s)

if __name__ == "__main__":
    unittest.main()
