"""Non-deploying source guard for exact 29c2 verified-zero cloud Product Studio release."""
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/"scripts/operations"
FILES={
"stage":OPS/"stage-29c2-cloud-only-ops-advance-20261027.sh",
"backup":OPS/"backup-29c2-cloud-local-disposable-restore-20261027.sh",
"seal":OPS/"seal-29c2-cloud-age-offsite-20261027.py",
"rollback":OPS/"drill-29c2-cloud-four-migrations-20261027.sh",
"gateway":OPS/"audit-29c2-cloud-private-gateway-20261027.py",
}
SHA="29c2e1421aa3fdd6f4ed32d0edff766469cf9a98"
def code(k):return FILES[k].read_text(encoding="utf-8")
class ReleaseSourceSafety(unittest.TestCase):
 def test_syntax(self):
  for k,path in FILES.items():
   with self.subTest(k=k):
    if path.suffix==".sh": subprocess.run(["bash","-n",str(path)],check=True,timeout=10)
    else: compile(path.read_text(encoding="utf-8"),str(path),"exec")
 def test_pinned_release_source_only(self):
  for k in ("backup","seal","rollback","gateway"):
   self.assertIn(SHA,code(k))
   self.assertNotIn("3fb443d135f010",code(k))
  for marker in ("merge-base --is-ancestor", "BLOCKED_APPLICATION_SOURCE_ADVANCED",
                 "MAIN_MOVED_DURING_BUILD", "refs/heads/main",
                 "git -C \"$dest\" checkout --detach -q \"$exact\""):
   self.assertIn(marker,code("stage"))
 def test_four_migration_recovery_and_old_read(self):
  for marker in ("2026_10_27_110000_add_content_to_products",
                 "ONLY_FOUR_EXPECTED_PENDING PASS","ISOLATED_FOUR_MIGRATIONS PASS",
                 "migrate:rollback --step=4 --force",
                 "OLD_RELEASE_EXPANDED_SCHEMA_BOOTSTRAP=PASS",
                 "ISOLATED_SCHEMA_ROLLBACK PASS", "ISOLATED_FORWARD_REPLAY PASS",
                 "--auth-host=reject","listen_addresses=''",
                 "runuser -u kmjprod -- env -i"):
   self.assertIn(marker,code("rollback"))
  self.assertIn('DB_PASSWORD= \\\n    PGHOST=',code("rollback"))
 def test_local_backup_and_gateway(self):
  for marker in ("PRODUCTION_DATABASE_DUMP=PASS","LOCAL_DISPOSABLE_POSTGRES_RESTORE",
                 "OFFSITE_INDEPENDENT_RESTORE NOT_VERIFIED",
                 "PRODUCTION_SWITCH NOT_ATTEMPTED"):
   self.assertIn(marker,code("backup"))
  for marker in ("ENV_EXCLUDED_FROM_OFFSITE_COPY=PASS",
                 "OFFSITE_TRANSFER=NOT_ATTEMPTED"):
   self.assertIn(marker,code("seal"))
  for marker in ("CODEBRIDGE_GATEWAY_URL","PRIVATE_GATEWAY_ENV",
                 "PRIVATE_GATEWAY_TCP","PRODUCTION_CONFIGURATION_CHANGED"):
   self.assertIn(marker,code("gateway"))
 def test_cloud_zero_cost_and_explicit_unavailable_image(self):
  content=(ROOT/"apps/platform/app/Services/ProductStudio/FreeCloudProductDraftGenerator.php").read_text()
  for marker in ("PRICE_NOT_VERIFIED_ZERO", "RESPONSE_COST_NOT_VERIFIED_ZERO",
                 "'max_price' => ['prompt' => 0, 'completion' => 0, 'request' => 0, 'image' => 0]",
                 "'allow_fallbacks' => false", "'data_collection' => 'deny'",
                 "NO_VERIFIED_FREE_CLOUD_IMAGE_ROUTE"):
   self.assertIn(marker,content)
  conf=(ROOT/"apps/platform/config/product_studio.php").read_text()
  self.assertIn("'enabled' => (bool) env('KMJ_PRODUCT_TEXT_ENABLED', false)",conf)
  self.assertIn("OPENROUTER_API_KEY",conf)
 def test_no_live_changes(self):
  for k in FILES:
   for bad in ("git reset --hard","ln -sfn","systemctl restart",
               "/etc/kmj-codebridge/main-platform-production-release.json",
               "rollbackVerified","backupVerified"):
    self.assertNotIn(bad,code(k))
if __name__=="__main__":unittest.main()
