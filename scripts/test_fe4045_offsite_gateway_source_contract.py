"""Source-only contracts for fe4045 Google restore and secret-free gateway diagnosis."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/"scripts/operations"
FILES={
"upload":OPS/"upload-fe4045-google-age-sftp-20261027.sh",
"finalize":OPS/"finalize-fe4045-google-age-offsite-20261027.sh",
"restore":OPS/"restore-fe4045-google-independent-pg-20261027.sh",
"verify":OPS/"verify-fe4045-google-archive-20261027.sh",
"doctor":OPS/"audit-fe4045-codebridge-loopback-endpoints-20261027.py",
}
CIPHER="ea4fd973d4bdc678fae6df5368956be283f8bd335788d68d268dd448218d7d8f"
CANDIDATE="fe4045acd08d50a7438dbfc6fee0610b02e1df50"
def src(n):return FILES[n].read_text(encoding="utf-8")
class OffsiteAndGateway(unittest.TestCase):
 def test_syntax(self):
  for n,p in FILES.items():
   with self.subTest(n=n):
    if p.suffix==".sh":subprocess.run(["bash","-n",str(p)],check=True,timeout=10)
    else:compile(p.read_text(),str(p),"exec")
 def test_exact_ciphertext_and_remote_hash(self):
  for n in ("upload","finalize","restore"):
   self.assertIn(CIPHER,src(n))
   self.assertIn("offsite-fe4045acd08d",src(n))
   self.assertNotIn("3fb443d135f0",src(n))
  self.assertIn(CANDIDATE,src("restore"))
  for n in ("upload","finalize"):
   self.assertIn("246313",src(n))
   self.assertIn("incoming-"+CIPHER[:8],src(n))
 def test_strict_sftp_and_google_recovery(self):
  for v in ("StrictHostKeyChecking=yes","HostKeyAlgorithms=ssh-ed25519",
            "SSH_HOST_KEY_PIN PASS","SFTP_ENCRYPTED_UPLOAD PASS_PENDING_GOOGLE_SHA256",
            "SOURCE_HARDLINKED","ENCRYPTED_REMOTE_INCOMING_ALREADY_EXISTS"):
   self.assertIn(v,src("upload"))
  for v in ("FINAL_EXCLUSIVE_CREATE","GOOGLE_ENCRYPTED_ARCHIVE VERIFIED",
            "INCOMING_SHA256_OWNER_MODE_SIZE"):
   self.assertIn(v,src("finalize"))
  for v in ("GOOGLE_VPS_INDEPENDENT_RESTORE PASS",
            "KMJ_P0_FE4045_VERIFY_BACKUP_BUNDLE_20261027.sh",
            "POSTGRES_NETWORK_LISTENER DISABLED","RECOVERED_APP_SCHEMA PASS",
            "RECOVERED_STORAGE PASS","--auth-host=reject","listen_addresses=''",
            "SAFE_TO_ACTIVATE_PRODUCTION NOT_PROVEN"):
   self.assertIn(v,src("restore"))
  self.assertIn("sha256sum --check SHA256SUMS",src("verify"))
 def test_readonly_gateway_diagnosis(self):
  s=src("doctor")
  for v in ("CODEBRIDGE_AGENT_PUBLIC_URL","CODEBRIDGE_GATEWAY_URL",
            "kmj-codebridge-gateway-stage.service",
            "systemctl","is-active",'"ss","-H","-ltnp"',
            "APP_PORT_MATCHES_GATEWAY_PROCESS",
            "GATEWAY_DIAGNOSIS","ENV_VALUES_OR_SECRETS_OUTPUT",
            "SYSTEM_CHANGES","PRESENT_BUT_NOT_PINNED"):
   self.assertIn(v,s)
  for bad in ("subprocess.run([\"systemctl\",\"restart\"",
              "write_text(","write_bytes(","unlink(","rmtree(",
              "os.system(","print(upstream)","print(origin)"):
   self.assertNotIn(bad,s)
 def test_no_cutover(self):
  for n in FILES:
   for bad in ("ln -sfn","git reset --hard","artisan migrate",
               "/etc/kmj-codebridge/main-platform-production-release.json",
               "backupVerified","rollbackVerified"):
    self.assertNotIn(bad,src(n))
if __name__=="__main__":unittest.main()
