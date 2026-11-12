"""b7b391 immutable production source contracts; no live network or DB."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/"scripts/operations"
SHA="b7b39174f5fdf47dd25890ece85c54eef29b4a96"
FILES={
"stage":OPS/"stage-b7b391-current-main-no-activation-20261027.sh",
"backup":OPS/"prepare-b7b391-protected-backup-restore-20261027.sh",
"seal":OPS/"seal-b7b391-age-offsite-20261027.py",
"rollback":OPS/"drill-b7b391-isolated-migrations-rollback-20261027.sh",
"gateway":OPS/"audit-b7b391-private-codebridge-gateway-20261027.py",
}
def code(name):return FILES[name].read_text("utf-8")
class Contract(unittest.TestCase):
    def test_syntax(self):
        for name,path in FILES.items():
            with self.subTest(name=name):
                if path.suffix==".sh":
                    subprocess.run(["bash","-n",str(path)],check=True,timeout=10)
                else:
                    compile(path.read_text("utf-8"),str(path),"exec")
    def test_correct_release_source(self):
        for name in ("backup","seal","rollback","gateway"):
            with self.subTest(name=name):
                self.assertIn(SHA,code(name))
                self.assertNotIn("babf9060684d",code(name))
        self.assertIn("refs/heads/main",code("stage"))
        self.assertIn('[[ "$remote" == "$sha" ]]',code("stage"))
        self.assertIn("KMJ_PRODUCTION=UNCHANGED",code("stage"))
    def test_backup_and_secret_stripping(self):
        for v in ("CANDIDATE_ENV_PRESENT","PRODUCTION_DATABASE_DUMP=PASS",
                  "LOCAL_DISPOSABLE_POSTGRES_RESTORE","OFFSITE_INDEPENDENT_RESTORE NOT_VERIFIED",
                  "PRODUCTION_SWITCH NOT_ATTEMPTED"):
            self.assertIn(v,code("backup"))
        for v in ("ENV_EXCLUDED_FROM_OFFSITE_COPY=PASS",
                  "OFFSITE_TRANSFER=NOT_ATTEMPTED",
                  "WITNESS_DIGEST_MISMATCH","UNSAFE_STORAGE_ARCHIVE_MEMBER"):
            self.assertIn(v,code("seal"))
    def test_disposable_migration_rollback(self):
        for v in ("ISOLATED_CONNECTION_INVALID","--auth-host=reject",
                  "listen_addresses=''","runuser -u kmjprod -- env -i",
                  "ISOLATED_SCHEMA_ROLLBACK PASS",
                  "ISOLATED_FORWARD_REPLAY PASS","PRODUCTION_ROLLBACK NOT_VERIFIED",
                  "ISOLATED_PG_CLEANUP=BLOCKED_PROCESS_STILL_PRESENT"):
            self.assertIn(v,code("rollback"))
        self.assertIn('DB_PASSWORD= \\\n    PGHOST=',code("rollback"))
        self.assertNotIn("[REDACTED]",code("rollback"))
    def test_gateway_is_readonly_and_local(self):
        for v in ("CODEBRIDGE_GATEWAY_URL","CODEBRIDGE_AGENT_PUBLIC_URL",
                  "is_loopback","PRIVATE_GATEWAY_ENV","PRIVATE_GATEWAY_TCP",
                  "PRIVATE_GATEWAY_SECRET_OUTPUT","PRODUCTION_CONFIGURATION_CHANGED"):
            self.assertIn(v,code("gateway"))
        for forbidden in ("shutil.rmtree","subprocess.run(","os.system(","unlink(","write_text(","write_bytes("):
            self.assertNotIn(forbidden,code("gateway"))
    def test_no_unsafe_prod_mutation(self):
        for name in ("stage","backup","seal","rollback","gateway"):
            for fragment in ("/etc/kmj-codebridge/main-platform-production-release.json",
                             "git reset --hard","ln -sfn","rollbackVerified","backupVerified"):
                with self.subTest(name=name,fragment=fragment):
                    self.assertNotIn(fragment,code(name))
if __name__=="__main__":unittest.main()
