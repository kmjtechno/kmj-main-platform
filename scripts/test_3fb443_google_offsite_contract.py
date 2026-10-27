"""3fb443 source-only offsite SFTP/Google independent recovery contracts."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]/"scripts/operations"
F={
    "upload":ROOT/"upload-3fb443-sftp-encrypted-bundle-20261027.sh",
    "finalize":ROOT/"finalize-3fb443-google-offsite-20261027.sh",
    "restore":ROOT/"restore-3fb443-google-postgres-20261027.sh",
    "verify":ROOT/"verify-3fb443-google-age-bundle-20261027.sh",
}
TARGET="3fb443d135f010a41f913b4e690289ab315769b8"
ENCRYPTED="8ec0fc1ef637a683dc7fe0493394c3c6d1613c8e233a36964fa7ab1dc33c6124"
def source(key):return F[key].read_text(encoding="utf-8")
class RecoveryContracts(unittest.TestCase):
    def test_shell_parse(self):
        for name,path in F.items():
            with self.subTest(name=name):
                subprocess.run(["bash","-n",str(path)],check=True,timeout=10)
    def test_exact_ciphertext_identity_and_size(self):
        for name in ("upload","finalize","restore"):
            s=source(name)
            self.assertIn(ENCRYPTED,s)
            self.assertIn("3fb443d135f0",s)
            self.assertNotIn("babf9060684d",s)
        self.assertIn(TARGET,source("restore"))
        for name in ("upload","finalize"):
            s=source(name)
            self.assertIn("239040",s)
            self.assertIn("incoming-"+ENCRYPTED[:8],s)
        self.assertNotIn("973b593d",source("upload"))
    def test_strict_pinned_ssh(self):
        s=source("upload")
        for marker in ("StrictHostKeyChecking=yes","HostKeyAlgorithms=ssh-ed25519",
                       "IdentityAgent=none","SSH_HOST_KEY_PIN PASS","SSH_AUTH PASS",
                       "SFTP_ENCRYPTED_UPLOAD PASS_PENDING_GOOGLE_SHA256",
                       "ENCRYPTED_DIGEST_MISMATCH",
                       "ENCRYPTED_REMOTE_INCOMING_ALREADY_EXISTS",
                       "PRODUCTION_ACTIVATION NOT_ATTEMPTED"):
            self.assertIn(marker,s)
    def test_google_finalizer_and_disposable_restore(self):
        f,r=source("finalize"),source("restore")
        for token in ("age-keygen -y","FINAL_EXCLUSIVE_CREATE","FINAL_READBACK",
                      "INCOMING_SHA256_OWNER_MODE_SIZE"):
            self.assertIn(token,f)
        for token in ("GOOGLE_VPS_INDEPENDENT_RESTORE PASS",
                      "KMJ_P0_3FB443_VERIFY_BACKUP_BUNDLE_20261027.sh",
                      "RECOVERED_APP_SCHEMA PASS","RECOVERED_STORAGE PASS",
                      "--auth-host=reject","listen_addresses=''","unix_socket_permissions=0700",
                      "PRODUCTION_DATABASE_MODIFIED NO","SAFE_TO_ACTIVATE_PRODUCTION NOT_PROVEN",
                      "OFFSITE_REMOTE_ARCHIVE_RETENTION NOT_VERIFIED"):
            self.assertIn(token,r)
        self.assertIn("archive.getmembers()",source("verify"))
        self.assertIn("sha256sum --check SHA256SUMS",source("verify"))
    def test_no_release_approval_or_prod_mutation(self):
        for key in F:
            text=source(key)
            for forbidden in ("git reset --hard","ln -sfn","systemctl restart",
                              "systemctl reload","artisan migrate",
                              "/etc/kmj-codebridge/main-platform-production-release.json",
                              "rollbackVerified","backupVerified"):
                self.assertNotIn(forbidden,text)
if __name__=="__main__":unittest.main()
