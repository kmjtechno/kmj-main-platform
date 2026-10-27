"""Source-only checks for exact babf906 isolated three-migration reversal and old-code compatibility."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/"scripts/operations/drill-babf906-isolated-migrations-rollback-20261027.sh"
S=FILE.read_text()
class MigrationRollbackSourceSafety(unittest.TestCase):
    def test_bash_syntax(self):
        subprocess.run(["bash","-n",str(FILE)],check=True,timeout=10)
    def test_exact_candidate_and_local_witness(self):
        for token in ("babf9060684d15b6188384386149466816140a98",
                      "pre-deploy-$SHORT.tar.gz","pre-deploy-$SHORT.json",
                      "platform-8070dad72c55","BACKUP_CHECKSUM_MISMATCH",
                      "WITNESS_IDENTITY_MISMATCH","CANDIDATE_WRONG_SHA",
                      "CANDIDATE_ENV_PRESENT","CANDIDATE_CONFIG_CACHED"):
            self.assertIn(token,S)
        self.assertNotIn("b1d672bbc83a",S)
    def test_never_targets_prod_database(self):
        for token in ("--auth-host=reject","listen_addresses=''","unix_socket_permissions=0700",
                      "kmj-schema-drill.","APP_ENV=testing","APP_CONFIG_CACHE=",
                      "runuser -u kmjprod -- env -i",
                      "ISOLATED_CONNECTION_INVALID",
                      "ONLY_THREE_EXPECTED_PENDING PASS"):
            self.assertIn(token,S)
        self.assertLess(S.index('"$scratch/verify.php" before'),
                        S.index("artisan migrate --force"))
        for token in ("systemctl restart","systemctl reload","ln -sfn",
                      "git reset --hard","backupVerified","rollbackVerified",
                      "/etc/kmj-codebridge/main-platform-production-release.json"):
            self.assertNotIn(token,S)
    def test_ephemeral_credentials_and_cleanup(self):
        for token in ("DISPOSABLE_APP_KEY","APP_KEY=\"$DISPOSABLE_APP_KEY\"",
                      "ISOLATED_PG_CLEANUP=BLOCKED_PROCESS_STILL_PRESENT",
                      "PRODUCTION_DATABASE_WRITES NONE",
                      "PRODUCTION_ACTIVATION NOT_ATTEMPTED",
                      "PRODUCTION_ROLLBACK NOT_VERIFIED"):
            self.assertIn(token,S)
        self.assertNotIn("CANDIDATE_ENV_MISSING",S)
    def test_migration_and_compatibility_contract(self):
        for token in ("2026_10_20_070000_create_customer_profiles_table",
                      "2026_10_21_020500_create_omnidesk_activation_bindings",
                      "2026_10_21_030000_add_current_nonce_to_omnidesk_activation_bindings",
                      "migrate:rollback --step=3 --force",
                      "ISOLATED_SCHEMA_ROLLBACK PASS",
                      "ISOLATED_FORWARD_REPLAY PASS",
                      "OLD_RELEASE_EXPANDED_SCHEMA_BOOTSTRAP=PASS",
                      "OLD_RELEASE_DISPOSABLE_DB_READ=PASS",
                      "ISOLATED_MIGRATION_DRILL PASS"):
            self.assertIn(token,S)
if __name__=="__main__": unittest.main()
