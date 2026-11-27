"""Source-only locked SHA 52f4 Main Platform production release invariants."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/"scripts/operations"
FILES={
"stage":OPS/"stage-52f4-cloud-quota-ops-only-20261027.sh",
"backup":OPS/"backup-52f4-cloud-quota-local-restore-20261027.sh",
"seal":OPS/"seal-52f4-cloud-quota-age-offsite-20261027.py",
"drill":OPS/"drill-52f4-cloud-quota-four-migrations-20261027.sh",
"gateway":OPS/"audit-52f4-cloud-quota-private-gateway-20261027.py",
}
SHA="52f4b27c4dc58f7b3f30467b7a221aa4b1b8ba04"

def src(n): return FILES[n].read_text(encoding="utf-8")

class ExactP0(unittest.TestCase):
    def test_syntax(self):
        for name,path in FILES.items():
            with self.subTest(name=name):
                if path.suffix==".sh":
                    subprocess.run(["bash","-n",str(path)],check=True,timeout=10)
                else:
                    compile(path.read_text("utf-8"),str(path),"exec")

    def test_exact_sha_immutable_ops_only_advance(self):
        for name in ("backup","seal","drill","gateway"):
            self.assertIn(SHA,src(name))
            self.assertNotIn("29c2e1421aa3",src(name))
        for gate in ("merge-base --is-ancestor",
                     "BLOCKED_APPLICATION_SOURCE_ADVANCED",
                     "BLOCKED_MAIN_TOO_FAR_AHEAD",
                     "MAIN_MOVED_DURING_BUILD",
                     'git -C "$dest" checkout --detach -q "$exact"',
                     "refs/heads/main","CANDIDATE_DIRTY",
                     "KMJ_PRODUCTION=UNCHANGED"):
            self.assertIn(gate,src("stage"))

    def test_four_migration_disposable_drill(self):
        s=src("drill")
        for gate in ("ONLY_FOUR_EXPECTED_PENDING PASS",
                     "ISOLATED_FOUR_MIGRATIONS PASS",
                     "2026_10_27_110000_add_content_to_products",
                     "migrate:rollback --step=4 --force",
                     "ISOLATED_SCHEMA_ROLLBACK PASS",
                     "ISOLATED_FORWARD_REPLAY PASS",
                     "OLD_RELEASE_EXPANDED_SCHEMA_BOOTSTRAP=PASS",
                     "runuser -u kmjprod -- env -i",
                     "--auth-host=reject","listen_addresses=''"):
            self.assertIn(gate,s)
        self.assertIn('DB_PASSWORD= \\\n    PGHOST=',s)
        self.assertNotIn("[REDACTED]",s)

    def test_private_backup_and_gateway(self):
        for gate in ("PRODUCTION_DATABASE_DUMP=PASS",
                     "LOCAL_DISPOSABLE_POSTGRES_RESTORE",
                     "PRODUCTION_SWITCH NOT_ATTEMPTED"):
            self.assertIn(gate,src("backup"))
        for gate in ("ENV_EXCLUDED_FROM_OFFSITE_COPY=PASS",
                     "OFFSITE_TRANSFER=NOT_ATTEMPTED"):
            self.assertIn(gate,src("seal"))
        for gate in ("CODEBRIDGE_GATEWAY_URL",
                     "PRIVATE_GATEWAY_ENV",
                     "PRIVATE_GATEWAY_TCP",
                     "PRODUCTION_CONFIGURATION_CHANGED"):
            self.assertIn(gate,src("gateway"))

    def test_cloud_zero_price_and_429_cooldown(self):
        model=(ROOT/"apps/platform/app/Services/ProductStudio/FreeCloudProductDraftGenerator.php").read_text()
        exception=(ROOT/"apps/platform/app/Services/ProductStudio/FreeCloudRateLimited.php").read_text()
        for gate in ("PRICE_NOT_VERIFIED_ZERO","RESPONSE_COST_NOT_VERIFIED_ZERO",
                     "'allow_fallbacks' => false", "'data_collection' => 'deny'",
                     "'max_price' => ['prompt' => 0, 'completion' => 0, 'request' => 0, 'image' => 0]",
                     "NO_VERIFIED_FREE_CLOUD_IMAGE_ROUTE",
                     "Cache::put('product-studio-cloud-cooldown'",
                     "new FreeCloudRateLimited($retryAfter)",
                     "min(86400, max(1, (int) $header))"):
            self.assertIn(gate,model)
        self.assertIn("FREE_CLOUD_RATE_LIMITED",exception)
        config=(ROOT/"apps/platform/config/product_studio.php").read_text()
        self.assertIn("OPENROUTER_API_KEY",config)
        self.assertIn("'enabled' => (bool) env('KMJ_PRODUCT_TEXT_ENABLED', false)",config)

    def test_never_cut_over(self):
        for name in FILES:
            s=src(name)
            for bad in ("git reset --hard","ln -sfn",
                        "systemctl restart",
                        "/etc/kmj-codebridge/main-platform-production-release.json",
                        "rollbackVerified","backupVerified"):
                self.assertNotIn(bad,s)

if __name__=="__main__":
    unittest.main()
