"""Synthetic, source-only exact babf906 SFTP Google offsite integrity gates."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATHS={
"upload":ROOT/"scripts/operations/upload-babf906-encrypted-backup-sftp-20261027.sh",
"finalize":ROOT/"scripts/operations/finalize-babf906-google-sftp-20261027.sh",
"restore":ROOT/"scripts/operations/restore-babf906-google-postgres-20261027.sh",
"verify":ROOT/"scripts/operations/verify-babf906-backup-bundle-20261027.sh",
}
sha="babf9060684d15b6188384386149466816140a98"
digest="77d5dbdc1211dcf1ea84c918236344accc56ca155f55cba3d348cd80cd55ff65"
class OffsiteContract(unittest.TestCase):
    def test_source_shell_parse(self):
        for label,path in PATHS.items():
            with self.subTest(label=label):
                subprocess.run(["bash","-n",str(path)],check=True,timeout=10)
    def test_candidate_hash_and_file_length(self):
        for label in ("upload","finalize","restore"):
            s=PATHS[label].read_text()
            self.assertIn(digest,s)
            self.assertIn("babf9060684d",s)
            self.assertNotIn("29a98250b463",s)
        for label in ("upload","finalize"):
            self.assertIn("249396",PATHS[label].read_text())
        self.assertIn(sha,PATHS["restore"].read_text())
    def test_pinned_ssh_and_no_automatic_cutover(self):
        s=PATHS["upload"].read_text()
        for v in ("StrictHostKeyChecking=yes","HostKeyAlgorithms=ssh-ed25519",
                  "IdentityAgent=none","SSH_HOST_KEY_PIN PASS",
                  "SFTP_ENCRYPTED_UPLOAD PASS_PENDING_GOOGLE_SHA256",
                  "PRODUCTION_ACTIVATION NOT_ATTEMPTED"):
            self.assertIn(v,s)
        for label,path in PATHS.items():
            with self.subTest(label=label):
                source=path.read_text()
                for forbidden in ("git reset --hard","ln -sfn","systemctl restart","artisan migrate",
                                  "sudo ","/etc/kmj-codebridge/main-platform-production-release.json"):
                    self.assertNotIn(forbidden,source)
    def test_rootless_google_validation_and_isolated_postgres(self):
        f=PATHS["finalize"].read_text()
        r=PATHS["restore"].read_text()
        for required in ("age-keygen -y","INCOMING_SHA256_OWNER_MODE_SIZE",
                         "FINAL_EXCLUSIVE_CREATE","GOOGLE_ENCRYPTED_ARCHIVE VERIFIED"):
            self.assertIn(required,f)
        for required in ('[[ "$(id -u)" != 0 && "$(id -un)" == info ]]',
                         '[[ "$(hostname -s)" == google-vps1 ]]',
                         "KMJ_ACK_ISOLATED_RECOVERY", "BACKUP_ARCHIVE_INTEGRITY PASS",
                         "GOOGLE_VPS_INDEPENDENT_RESTORE PASS",
                         "--auth-host=reject", "listen_addresses=''",
                         "POSTGRES_NETWORK_LISTENER DISABLED","PRODUCTION_DATABASE_MODIFIED NO",
                         "SAFE_TO_ACTIVATE_PRODUCTION NOT_PROVEN"):
            self.assertIn(required,r)
        self.assertIn("KMJ_P0_BABF906_VERIFY_BACKUP_BUNDLE_20261027.sh",r)
        self.assertIn("archive.getmembers()",PATHS["verify"].read_text())
if __name__=="__main__":
    unittest.main()
