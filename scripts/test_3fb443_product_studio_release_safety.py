"""Static non-deploying safety contracts for the product studio exact-SHA release."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]/"scripts/operations"
FILES={
 "stage":ROOT/"stage-3fb443-current-main-no-activation-20261027.sh",
 "backup":ROOT/"prepare-3fb443-local-backup-restore-20261027.sh",
 "seal":ROOT/"seal-3fb443-sanitized-age-backup-20261027.py",
 "drill":ROOT/"drill-3fb443-four-migrations-rollback-20261027.sh",
 "gateway":ROOT/"audit-3fb443-private-codebridge-gateway-20261027.py",
}
SHA="3fb443d135f010a41f913b4e690289ab315769b8"
def read(n): return FILES[n].read_text("utf-8")
class CurrentProductStudioP0(unittest.TestCase):
 def test_parse(self):
  for label,f in FILES.items():
   with self.subTest(label=label):
    if f.suffix==".sh":subprocess.run(["bash","-n",str(f)],check=True,timeout=10)
    else:compile(f.read_text("utf-8"),str(f),"exec")
 def test_exact_sha_and_stager(self):
  for k in ("backup","seal","drill","gateway"):
   self.assertIn(SHA,read(k))
  self.assertIn("refs/heads/main",read("stage"))
  self.assertIn('[[ "$remote" == "$sha" ]]',read("stage"))
  self.assertIn("KMJ_PRODUCTION=UNCHANGED",read("stage"))
 def test_real_backup_only_disposable_db(self):
  for v in ("PRODUCTION_DATABASE_DUMP=PASS","LOCAL_DISPOSABLE_POSTGRES_RESTORE","OFFSITE_INDEPENDENT_RESTORE NOT_VERIFIED","PRODUCTION_SWITCH NOT_ATTEMPTED","CANDIDATE_ENV_PRESENT"):
   self.assertIn(v,read("backup"))
  for v in ("ENV_EXCLUDED_FROM_OFFSITE_COPY=PASS","OFFSITE_TRANSFER=NOT_ATTEMPTED","UNSAFE_STORAGE_ARCHIVE_MEMBER"):
   self.assertIn(v,read("seal"))
 def test_four_pending_migrations_and_reversibility(self):
  s=read("drill")
  for v in ("ONLY_FOUR_EXPECTED_PENDING PASS",
   "ISOLATED_FOUR_MIGRATIONS PASS",
   "2026_10_20_070000_create_customer_profiles_table",
   "2026_10_21_020500_create_omnidesk_activation_bindings",
   "2026_10_21_030000_add_current_nonce_to_omnidesk_activation_bindings",
   "2026_10_27_110000_add_content_to_products",
   "Schema::hasColumn('products', 'content')",
   "migrate:rollback --step=4 --force",
   "ISOLATED_SCHEMA_ROLLBACK PASS","ISOLATED_FORWARD_REPLAY PASS",
   "OLD_RELEASE_EXPANDED_SCHEMA_BOOTSTRAP=PASS",
   "PRODUCTION_ROLLBACK NOT_VERIFIED",
   "runuser -u kmjprod -- env -i",
   "--auth-host=reject","listen_addresses=''"):
   self.assertIn(v,s)
  self.assertNotIn("[REDACTED]",s)
  self.assertIn('DB_PASSWORD= \\\n    PGHOST=',s)
 def test_private_gateway_and_production_lock(self):
  for v in ("CODEBRIDGE_GATEWAY_URL","CODEBRIDGE_AGENT_PUBLIC_URL","is_loopback","PRIVATE_GATEWAY_SECRET_OUTPUT","PRODUCTION_CONFIGURATION_CHANGED"):
   self.assertIn(v,read("gateway"))
  for k in FILES:
   for bad in ("git reset --hard","ln -sfn","/etc/kmj-codebridge/main-platform-production-release.json","backupVerified","rollbackVerified"):
    self.assertNotIn(bad,read(k))
if __name__=="__main__":unittest.main()
