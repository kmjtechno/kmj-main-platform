#!/usr/bin/env python3
"""Source-only safety gates for three migrations against disposable PG."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/drill-codebridge-three-migrations-isolated-20261024.sh"
CODE = SCRIPT.read_text("utf-8")

class IsolatedThreeMigrations(unittest.TestCase):
    def test_bash_syntax(self):
        done = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_fixed_live_candidate_backup_and_lock(self):
        for value in ("b1d672bbc83a51ca3f8271435692825072444c8e",
                      "platform-8070dad72c55",
                      "pre-deploy-$SHORT.tar.gz", "pre-deploy-$SHORT.json",
                      "BACKUP_CHECKSUM_MISMATCH", "WITNESS_IDENTITY_MISMATCH",
                      "/run/lock/kmj-main-platform-production-release.lock",
                      "flock -n 9", "CANDIDATE_WRONG_SHA", "CANDIDATE_DIRTY"):
            self.assertIn(value, CODE, value)

    def test_disposable_no_network_postgres(self):
        for value in ("--auth-host=reject", "listen_addresses=''",
                      "unix_socket_permissions=0700", "-c port=$PORT",
                      "ISOLATED_POSTGRES_START_FAILED",
                      "PRIVATE_SOCKET_MISSING",
                      "DISPOSABLE_POSTGRES_RESTORE PASS"):
            self.assertIn(value, CODE, value)
        self.assertIn('$scratch/restore/pg-server.log', CODE)
        self.assertIn('tar -xOzf "$BACKUP" database.dump', CODE)
        self.assertNotIn('tar -xzf "$BACKUP"', CODE)

    def test_effective_connection_strict_before_writes(self):
        for value in ("ISOLATED_CONNECTION_INVALID",
                      "getenv('DB_HOST')", "getenv('DB_PORT')",
                      "getenv('DB_DATABASE')", "getenv('DB_USERNAME')",
                      "config('database.default')", "DB_URL=",
                      'DB_HOST="$SOCKET"', 'DB_PORT="$PORT"',
                      'DB_DATABASE="$DATABASE"', 'DB_USERNAME="$ROLE"',
                      "ONLY_THREE_EXPECTED_PENDING PASS"):
            self.assertIn(value, CODE, value)
        self.assertLess(CODE.index('"$scratch/verify.php" before'), CODE.index('artisan migrate --force'))

    def test_exact_three_expected_and_down_up(self):
        for name in (
            "2026_10_20_070000_create_customer_profiles_table",
            "2026_10_21_020500_create_omnidesk_activation_bindings",
            "2026_10_21_030000_add_current_nonce_to_omnidesk_activation_bindings",
        ):
            self.assertIn(name, CODE)
        for fragment in ("Schema::hasTable('customer_profiles')",
                         "Schema::hasTable('omnidesk_activation_bindings')",
                         "Schema::hasColumn('omnidesk_activation_bindings', 'current_nonce')",
                         "migrate:rollback --step=3 --force",
                         "ISOLATED_SCHEMA_ROLLBACK PASS",
                         "ISOLATED_FORWARD_REPLAY PASS"):
            self.assertIn(fragment, CODE)

    def test_production_never_changed_or_approved(self):
        for prohibited in (
            "systemctl restart", "systemctl reload", "systemctl start",
            "ALTER ROLE", "artisan migrate --database=production",
            "git reset --hard", "ln -s", "ln -sf", "os.replace(",
            "backupVerified", "rollbackVerified",
            "/etc/kmj-codebridge/main-platform-production-release.json",
            "curl | bash", "rsync ", "chown -R", "chmod 777"
        ):
            self.assertNotIn(prohibited, CODE, prohibited)
        for expected in ("PRODUCTION_DATABASE_WRITES NONE",
                         "PRODUCTION_MIGRATIONS NOT_ATTEMPTED",
                         "PRODUCTION_ACTIVATION NOT_ATTEMPTED",
                         "PRODUCTION_ROLLBACK NOT_VERIFIED"):
            self.assertIn(expected, CODE)

    def test_disposable_environment_only_with_strict_db_target(self):
        # Laravel's AppServiceProvider prohibits destructive commands in production;
        # rehearsal must select testing while retaining the production safeguard.
        for token in ("APP_ENV=testing", "APP_DEBUG=false", "MAIL_MAILER=log",
                      "QUEUE_CONNECTION=sync", "CACHE_STORE=array",
                      "SESSION_DRIVER=array", "APP_URL=http://localhost",
                      "$app->environment() !== 'testing'", "$app->isProduction()",
                      "ISOLATED_ENV_REQUIRED", "ISOLATED_CONNECTION_INVALID"):
            self.assertIn(token, CODE, token)
        self.assertNotIn("DB::prohibitDestructiveCommands(false)", CODE)
        self.assertNotIn('sed -i', CODE)
        self.assertLess(CODE.index('"$scratch/verify.php" before'), CODE.index("artisan migrate --force"))

    def test_rollback_failure_reports_no_raw_exception_or_sql_values(self):
        for token in (
            "ISOLATED_ROLLBACK_SQLSTATE=",
            "ISOLATED_ROLLBACK_CLASS=",
            "ROLLBACK_LOG_MENTIONS_",
            '("CUSTOMER_PROFILE", "2026_10_20_070000_create_customer_profiles_table")',
            '("OMNIDESK_BINDING", "2026_10_21_020500_create_omnidesk_activation_bindings")',
            '("OMNIDESK_NONCE", "2026_10_21_030000_add_current_nonce_to_omnidesk_activation_bindings")',
            "ISOLATED_MIGRATION_ROWS=",
            "ISOLATED_CUSTOMER_TABLE=",
            "ISOLATED_OMNIDESK_TABLE=",
            "log = Path(sys.argv[1]).read_text",
            "[-131072:]",
            "rollback_diagnostics",
        ):
            self.assertIn(token, CODE, token)
        self.assertNotIn('cat "$scratch/rollback.log"', CODE)
        self.assertNotIn('tail "$scratch/rollback.log"', CODE)
        self.assertNotIn('print(log)', CODE)
        self.assertNotIn('echo "$log"', CODE)

    def test_cleanup_no_archived_secret_print(self):
        for value in ("trap cleanup EXIT", "rm -rf -- \"$scratch\"",
                      "chmod 0600", "root:kmjprod", "OFFSITE_INDEPENDENT_RESTORE NOT_VERIFIED"):
            self.assertIn(value, CODE)
        self.assertNotIn('cat "$CANDIDATE/apps/platform/.env"', CODE)
        self.assertNotIn('tar -xOzf "$BACKUP" storage.tar.gz', CODE)

if __name__ == "__main__":
    unittest.main()
