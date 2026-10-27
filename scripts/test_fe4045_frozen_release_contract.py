"""Frozen fe4045 source QA: no moving-main dependency or production cutover."""
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/"scripts/operations"
PATHS={
    "stage":OPS/"stage-fe4045-frozen-qa-no-cutover-20261027.sh",
    "backup":OPS/"backup-fe4045-fixed-qa-20261027.sh",
    "seal":OPS/"seal-fe4045-fixed-qa-20261027.py",
    "rollback":OPS/"drill-fe4045-fixed-4mig-20261027.sh",
    "gateway":OPS/"audit-fe4045-fixed-gateway-20261027.py",
}
SHA="fe4045acd08d50a7438dbfc6fee0610b02e1df50"
def source(n):return PATHS[n].read_text(encoding="utf-8")
class FrozenRelease(unittest.TestCase):
 def test_syntax(self):
  for name,f in PATHS.items():
   with self.subTest(name=name):
    if f.suffix==".sh":subprocess.run(["bash","-n",str(f)],check=True,timeout=10)
    else:compile(f.read_text("utf-8"),str(f),"exec")
 def test_exact_sha_and_frozen_ref(self):
  for n in ("stage","backup","seal","rollback","gateway"):
   self.assertIn(SHA,source(n))
  stage=source("stage")
  for token in ("refs/heads/candidate/p0-fe4045-frozen-20261027",
                "SNAPSHOT_REF_DRIFT","SNAPSHOT_MOVED_DURING_BUILD",
                "KMJ_EXACT_FROZEN_SOURCE=PASS","KMJ_SNAPSHOT_NOT_PRODUCTION_APPROVAL=TRUE",
                "CANDIDATE_DIRTY","RUNTIME_ENV_REQUIRES_REVIEW",
                'git -C "$dest" checkout --detach -q FETCH_HEAD'):
   self.assertIn(token,stage)
  self.assertNotIn("refs/heads/main",stage)
 def test_backup_and_no_secret_offsite(self):
  for t in ("PRODUCTION_DATABASE_DUMP=PASS","LOCAL_DISPOSABLE_POSTGRES_RESTORE",
            "PRODUCTION_SWITCH NOT_ATTEMPTED"):
   self.assertIn(t,source("backup"))
  for t in ("ENV_EXCLUDED_FROM_OFFSITE_COPY=PASS","OFFSITE_TRANSFER=NOT_ATTEMPTED"):
   self.assertIn(t,source("seal"))
 def test_four_migrations_and_old_app(self):
  for token in ("ONLY_FOUR_EXPECTED_PENDING PASS",
                "2026_10_27_110000_add_content_to_products",
                "migrate:rollback --step=4 --force",
                "ISOLATED_FOUR_MIGRATIONS PASS",
                "ISOLATED_SCHEMA_ROLLBACK PASS","ISOLATED_FORWARD_REPLAY PASS",
                "OLD_RELEASE_EXPANDED_SCHEMA_BOOTSTRAP=PASS",
                "--auth-host=reject","listen_addresses=''",
                "PRODUCTION_ROLLBACK NOT_VERIFIED"):
   self.assertIn(token,source("rollback"))
  self.assertIn('DB_PASSWORD= \\\n    PGHOST=',source("rollback"))
 def test_cloud_safety_and_no_mutation(self):
  gen=(ROOT/"apps/platform/app/Services/ProductStudio/FreeCloudProductDraftGenerator.php").read_text()
  for token in ("PRICE_NOT_VERIFIED_ZERO", "RESPONSE_COST_NOT_VERIFIED_ZERO",
                "CLOUD_DRAFT_INCOMPLETE",
                "'allow_fallbacks' => false",
                "'max_price' => ['prompt' => 0, 'completion' => 0, 'request' => 0, 'image' => 0]",
                "'max_tokens' => 8000", "choices.0.finish_reason"):
   self.assertIn(token,gen)
  rate=(ROOT/"apps/platform/app/Services/ProductStudio/FreeCloudRateLimited.php").read_text()
  self.assertIn("FREE_CLOUD_RATE_LIMITED",rate)
  for n in PATHS:
   for bad in ("git reset --hard","ln -sfn","systemctl restart",
               "/etc/kmj-codebridge/main-platform-production-release.json",
               "rollbackVerified","backupVerified"):
    self.assertNotIn(bad,source(n))
if __name__=="__main__":unittest.main()
